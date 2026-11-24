"""The no-model baseline: do exactly what the ticket form says, the way a rushed queue often does.

It pastes the supplied copy into the part of the page the requester picked, calls every edit low risk, and
never sends anything to compliance. The eval must block it.
"""

from __future__ import annotations

FORM_PARTS = {
    "headline": "headline",
    "body": "body",
    "button label": "cta_label",
    "button link": "cta_url",
    "meta description": "meta_description",
    "image alt text": "hero_alt",
    "last-updated date": "updated_on",
    "rate example": "rate_note",
    "title": "title",
}


def literal_editor(ticket: dict, page: dict | None) -> dict:
    field = FORM_PARTS.get(ticket.get("part", ""))
    changes = [{"field": field, "new_value": ticket["new_copy"]}] if field and ticket.get("new_copy") else []
    return {"decision": "edit", "risk": "low", "changes": changes, "reason": "Applied the requested copy."}
