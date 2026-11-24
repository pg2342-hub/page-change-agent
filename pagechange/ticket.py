"""Turn a GitHub issue filed from the change request form into a ticket, and a result into the issue comment."""

from __future__ import annotations

import difflib
import re

from . import site

HEADINGS = {"page": "page_id", "part of the page": "part", "what should change": "request", "new copy": "new_copy"}
NO_RESPONSE = "_No response_"


def parse_issue(body: str) -> dict:
    """Read the sections GitHub writes for an issue form (### Heading, blank line, answer)."""
    ticket: dict = {}
    for heading, text in re.findall(r"^###\s+(.+?)\s*\n(.*?)(?=^###\s|\Z)", body, flags=re.M | re.S):
        key = HEADINGS.get(heading.strip().lower())
        value = text.strip()
        if key and value and value != NO_RESPONSE:
            ticket[key] = value
    if "page_id" not in ticket or "request" not in ticket:
        raise ValueError("the issue is missing the Page or What should change section")
    ticket["page_id"] = ticket["page_id"].split()[0]
    return ticket


FIELD_NAMES = {
    "title": "Title",
    "headline": "Headline",
    "body": "Body",
    "cta_label": "Button label",
    "cta_url": "Button link",
    "meta_description": "Meta description",
    "rate_note": "Rate example",
    "hero_alt": "Hero image alt text",
    "updated_on": "Last updated",
    "disclosure_ids": "Disclosures",
}


def word_diff(old: str, new: str) -> str:
    """Inline diff for a markdown comment: removed words struck through, added words in bold."""
    a, b = str(old).split(), str(new).split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if op == "equal":
            out.append(" ".join(a[i1:i2]))
        if op in ("delete", "replace"):
            out.append("~~" + " ".join(a[i1:i2]) + "~~")
        if op in ("insert", "replace"):
            out.append("**" + " ".join(b[j1:j2]) + "**")
    return " ".join(out)


def comment(result: dict) -> str:
    t = result["ticket"]
    ready = result["label"] == "ready-for-approval"
    lines = []
    if ready:
        v = result["cms"]
        lines.append(
            f"**Draft saved, ready for approval** ({result['risk']} risk). Saved to {v['system']} as an unpublished "
            f"draft (version {v['version_before']} to {v['version_after']}), read back and matched. Publishing is "
            "still a person's click in the CMS."
        )
    else:
        who = {
            "agent": "The agent sent this to compliance",
            "guardrail": "A compliance check stopped the draft",
            "missing page": "The page does not exist",
            "no change": "The draft changed nothing",
            "read-back mismatch": "The saved draft did not match",
            "cms error": "The CMS refused the draft",
            "agent error": "The agent could not finish this request",
        }.get(result["stopped_by"], "Sent to compliance")
        saved = (
            "an unpublished draft was saved but needs checking in the CMS"
            if result["cms"].get("written")
            else "nothing was saved"
        )
        lines.append(f"**Needs compliance.** {who}; {saved}.")
    lines += ["", f"> {result['reason']}", ""]
    page = site.PAGES.get(t["page_id"])
    if page:
        lines.append(f"Page: `{page['slug']}` ({page['title']})")
    if ready:
        lines += ["", "| Field | Change |", "|---|---|"]
        for k in result["changed"]:
            lines.append(f"| {FIELD_NAMES.get(k, k)} | {word_diff(result['before'][k], result['after'][k])} |")
    if result["findings"]:
        lines += ["", "<details><summary>Checks</summary>", ""]
        for f in result["findings"]:
            mark = "pass" if f["ok"] else "FAIL"
            lines.append(f"- {mark}: {f['label']}" + (f" ({f['detail']})" if f["detail"] else ""))
        lines += ["", "</details>"]
    cost = result.get("cost_usd") or 0
    lines += [
        "",
        f"<sub>{result.get('model') or 'baseline'} · ${cost:.4f} · {result.get('latency_s', 0):.1f} s</sub>",
    ]
    return "\n".join(lines)
