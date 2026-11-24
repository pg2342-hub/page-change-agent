"""The checks every draft goes through before anyone is asked to approve it.

Blocking checks send the ticket to compliance instead of writing a draft. The rest are quality checks a
reviewer sees in the issue comment.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from . import site


@dataclass
class Finding:
    id: str
    label: str
    ok: bool
    detail: str = ""
    blocking: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def changed_fields(before: dict, after: dict) -> list[str]:
    return [k for k in site.EDITABLE + site.READ_ONLY if before.get(k) != after.get(k)]


def check(page_id: str, before: dict, after: dict) -> list[Finding]:
    out: list[Finding] = []
    changed = changed_fields(before, after)

    ro = [k for k in changed if k in site.READ_ONLY]
    out.append(
        Finding(
            "read_only_untouched",
            "Disclosures, page type and URL unchanged",
            not ro,
            f"changed {', '.join(ro)}" if ro else "",
            blocking=True,
        )
    )

    required = site.REQUIRED_DISCLOSURES[after["page_type"]]
    missing = [d for d in required if d not in after.get("disclosure_ids", [])]
    out.append(
        Finding(
            "disclosures_kept",
            "Required disclosures still on the page",
            not missing,
            f"missing {', '.join(missing)}" if missing else "",
            blocking=True,
        )
    )

    new_claims = []
    for k in site.TEXT_FIELDS:
        new_claims += [p for p in site.banned_in(after.get(k, "")) if p not in site.banned_in(before.get(k, ""))]
    out.append(
        Finding(
            "no_banned_claims",
            "No banned claims added (guarantees, lowest price, no risk)",
            not new_claims,
            f"adds {', '.join(sorted(set(new_claims)))}" if new_claims else "",
            blocking=True,
        )
    )

    rate = "rate_note" in changed
    out.append(
        Finding(
            "rate_unchanged",
            "Rate example unchanged (rates need pricing and compliance sign-off)",
            not rate,
            "rate example edited" if rate else "",
            blocking=True,
        )
    )

    # Only links this edit adds or changes count; a link that was already broken is not this ticket's fault.
    new_bad = []
    if "cta_url" in changed and not site.link_ok(after.get("cta_url", "")):
        new_bad.append(after["cta_url"])
    old_body_links = set(site.internal_links(before.get("body", "")))
    new_bad += [
        u for u in site.internal_links(after.get("body", "")) if u not in old_body_links and not site.link_ok(u)
    ]
    out.append(
        Finding(
            "links_work",
            "Button and body links go to pages that exist",
            not new_bad,
            f"broken: {', '.join(new_bad)}" if new_bad else "",
        )
    )

    meta = after.get("meta_description", "")
    out.append(
        Finding(
            "meta_length",
            f"Meta description {site.META_MAX} characters or fewer",
            len(meta) <= site.META_MAX,
            f"{len(meta)} characters" if len(meta) > site.META_MAX else "",
        )
    )

    alt_changed = "hero_alt" in changed
    out.append(
        Finding(
            "alt_text",
            "Hero image has real alt text",
            site.alt_ok(after.get("hero_alt", "")) or not alt_changed,
            "" if site.alt_ok(after.get("hero_alt", "")) or not alt_changed else "alt text missing or a file name",
        )
    )

    date = after.get("updated_on", "")
    out.append(
        Finding(
            "date_format",
            "Last-updated date is a real date (YYYY-MM-DD)",
            bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", date)),
            "" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date) else f"got {date!r}",
            blocking=True,
        )
    )
    return out


def blocking_failures(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.blocking and not f.ok]
