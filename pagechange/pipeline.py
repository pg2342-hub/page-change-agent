"""One change request, end to end: read the page, ask the editor, check the draft, save it, read it back.

The editor is Claude in live runs (pagechange.claude) or the literal baseline (pagechange.baseline). The
same compliance checks guard both: a draft that fails a blocking check is never written, and the ticket goes
to compliance instead. Nothing is ever published.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from . import compliance, site
from .cms import CMSError

READY = "ready-for-approval"
COMPLIANCE = "needs-compliance"


def handle(ticket: dict, editor: Callable[[dict, dict | None], dict], cms: Any) -> dict[str, Any]:
    start = time.perf_counter()
    page_id = ticket["page_id"]
    try:
        current = cms.get(page_id)
    except CMSError:
        current = None
    before = current["fields"] if current else None

    proposal = editor(ticket, before)
    meta = proposal.pop("_meta", {})
    result: dict[str, Any] = {
        "ticket": ticket,
        "proposal": proposal,
        "before": before,
        "after": before,
        "changed": [],
        "findings": [],
        "label": COMPLIANCE,
        "risk": proposal.get("risk", "high"),
        "stopped_by": None,
        "reason": proposal.get("reason", ""),
        "cms": {"system": cms.name, "written": False, "published": False},
        "cost_usd": meta.get("cost_usd", 0.0),
        "model": meta.get("model", ""),
        "agent_latency_s": meta.get("latency_s"),
    }

    if before is None:
        result.update(
            stopped_by="missing page", risk="high", reason=f"No page {page_id!r} on the site. " + result["reason"]
        )
        return _done(result, start)
    if proposal["decision"] == "send_to_review" or proposal.get("risk") == "high":
        # An edit the agent itself calls high risk is not drafted: high risk always means compliance.
        result.update(stopped_by="agent", risk="high")
        return _done(result, start)

    after = dict(before)
    unknown = [c["field"] for c in proposal["changes"] if c["field"] not in site.EDITABLE]
    for c in proposal["changes"]:
        if c["field"] in site.EDITABLE:
            after[c["field"]] = c["new_value"]
    findings = compliance.check(page_id, before, after)
    blocking = compliance.blocking_failures(findings)
    result.update(
        after=after, changed=compliance.changed_fields(before, after), findings=[f.as_dict() for f in findings]
    )

    if unknown or blocking:
        why = [f"{f.label.lower()}: {f.detail}" for f in blocking] + [f"cannot edit {u}" for u in unknown]
        result.update(stopped_by="guardrail", risk="high", reason="Guardrail stopped the draft: " + "; ".join(why))
        return _done(result, start)
    if not result["changed"]:
        result.update(stopped_by="no change", risk="high", reason="The draft changes nothing. " + result["reason"])
        return _done(result, start)

    version = current["version"]
    try:
        new_version = cms.save_draft(page_id, after, version)
        back = cms.get(page_id)
    except CMSError as err:
        result.update(stopped_by="cms error", risk="high", reason=f"The CMS refused the draft: {err}")
        return _done(result, start)
    match = all(back["fields"].get(k) == after.get(k) for k in result["changed"])
    result["label"] = READY if match else COMPLIANCE
    result["cms"].update(
        written=True,
        version_before=version,
        version_after=new_version,
        readback_match=match,
        published=back.get("published_version") is not None and back["published_version"] >= new_version,
    )
    if not match:
        result.update(stopped_by="read-back mismatch", reason="The saved draft does not match what was sent.")
    return _done(result, start)


def _done(result: dict, start: float) -> dict:
    result["latency_s"] = round(time.perf_counter() - start, 3)
    return result
