"""The Claude step: read one change request and the page as it stands, and propose the edit (or send it on).

Structured output fixes the shape of the reply; the compliance checks and a separate judge grade the
content. Reads the key from ANTHROPIC_API_KEY.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from . import site

HERE = Path(__file__).parent
MODEL = "claude-opus-5-5"
EFFORT = "low"
# USD per million tokens (input, output), first-party list prices.
PRICES = {"claude-opus-5-5": (4.00, 20.00), "claude-sonnet-5-5": (2.00, 10.00), "claude-haiku-5-5": (0.10, 0.50)}

PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "risk", "changes", "reason"],
    "properties": {
        "decision": {"type": "string", "enum": ["edit", "send_to_review"]},
        "risk": {"type": "string", "enum": ["low", "standard", "high"]},
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["field", "new_value"],
                "properties": {
                    "field": {"type": "string", "enum": list(site.EDITABLE)},
                    "new_value": {"type": "string"},
                },
            },
        },
        "reason": {"type": "string"},
    },
}

SYSTEM = (
    "Follow the guide exactly. Reply with one record for the change request.\n\n"
    f"<guide>\n{(HERE / 'editor_guide.md').read_text()}</guide>\n\n"
    f"<site_pages>\n{chr(10).join(site.SLUGS)}\n</site_pages>"
)


def render(ticket: dict, page: dict | None) -> str:
    shown = "(no page with that id exists)" if page is None else json.dumps(page, indent=2)
    if page is not None:
        fine_print = "\n".join(f"{d}: {site.DISCLOSURES[d]}" for d in page["disclosure_ids"]) or "(none)"
        shown += f"\n\nFine print on this page:\n{fine_print}"
    parts = [f"Page id: {ticket['page_id']}", f"Request: {ticket['request']}"]
    if ticket.get("new_copy"):
        parts.append(f"New copy supplied by the requester: {ticket['new_copy']}")
    return "\n".join(parts) + f"\n\n<page>\n{shown}\n</page>"


class ClaudeEditor:
    def __init__(self, model: str = MODEL, effort: str = EFFORT, client: Any = None) -> None:
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        self.client, self.model, self.effort = client, model, effort

    def __call__(self, ticket: dict, page: dict | None) -> dict:
        start = time.perf_counter()
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=8000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": PROPOSAL_SCHEMA}},
            system=SYSTEM,
            messages=[{"role": "user", "content": render(ticket, page)}],
        )
        latency = time.perf_counter() - start
        if response.stop_reason == "refusal":
            raise RuntimeError("the model declined this request")
        if response.stop_reason == "max_tokens":
            raise RuntimeError("the reply was cut off at max_tokens")
        record = json.loads(next(b.text for b in response.content if b.type == "text"))
        record["_meta"] = {
            "model": getattr(response, "model", self.model),
            "cost_usd": self.cost(response),
            "latency_s": round(latency, 3),
        }
        return record

    def cost(self, response: Any) -> float:
        price = PRICES.get(getattr(response, "model", self.model)) or PRICES.get(self.model)
        if not price:
            return 0.0
        u = response.usage
        return round((u.input_tokens * price[0] + u.output_tokens * price[1]) / 1_000_000, 6)
