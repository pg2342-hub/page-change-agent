"""Rule checks on one handled change request (the pipeline's result, not just the model's reply).

Writing a draft that should have gone to compliance, losing a disclosure, adding a banned claim, calling a
customer-facing edit low risk, or a draft that was not saved as written blocks go-live on one failure.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from golive_gate import FAIL, NA, PASS, CheckSet, Verdict

from pagechange import site

checks = CheckSet()
READY = "ready-for-approval"


def v(ok, reason=""):
    return Verdict(PASS, "") if ok else Verdict(FAIL, reason)


def is_edit(case):
    return case.expected["decision"] == "edit"


@checks.check("review_caught", text="Requests that need compliance go there, and nothing is saved.", critical=True)
def review_caught(case, out):
    if is_edit(case):
        return NA
    return v(out["label"] != READY and not out["cms"]["written"], "saved a draft that should have gone to compliance")


@checks.check("drafted", text="Routine requests become a saved draft instead of a compliance ticket.")
def drafted(case, out):
    if not is_edit(case):
        return NA
    return v(out["label"] == READY, f"sent to compliance ({out['stopped_by']}): {out['reason'][:120]}")


@checks.check(
    "risk_not_understated",
    text="A change a customer reads is never called low risk (low-risk drafts can skip a full read).",
    critical=True,
)
def risk_not_understated(case, out):
    if out["label"] != READY or case.expected.get("risk") != "standard":
        return NA
    return v(out["risk"] != "low", "called a customer-facing copy change low risk")


@checks.check("risk_right", text="Drafts get the risk tier the guide gives them.")
def risk_right(case, out):
    if out["label"] != READY or not is_edit(case):
        return NA
    return v(out["risk"] == case.expected["risk"], f"risk {out['risk']}, should be {case.expected['risk']}")


@checks.check("right_fields", text="The draft changes the fields the request is about, and no others.")
def right_fields(case, out):
    if out["label"] != READY or not is_edit(case):
        return NA
    got, want = sorted(out["changed"]), sorted(case.expected["fields"])
    return v(got == want, f"changed {got}, should be {want}")


@checks.check("copy_right", text="The new copy says what the request asked for (exact where copy was supplied).")
def copy_right(case, out):
    if out["label"] != READY or not is_edit(case):
        return NA
    after, exp = out["after"], case.expected
    for field, want in (exp.get("equals") or {}).items():
        if after[field] != want:
            return Verdict(FAIL, f"{field} is {after[field]!r}, should be {want!r}")
    for field, words in (exp.get("contains") or {}).items():
        for w in words:
            if w.lower() not in after[field].lower():
                return Verdict(FAIL, f"{field} lacks {w!r}")
    for field, words in (exp.get("not_contains") or {}).items():
        for w in words:
            if w.lower() in after[field].lower():
                return Verdict(FAIL, f"{field} still has {w!r}")
    return Verdict(PASS, "")


@checks.check("disclosures_kept", text="Every disclosure the page type requires is still on the page.", critical=True)
def disclosures_kept(case, out):
    after = out["after"]
    if after is None:
        return NA
    missing = [d for d in site.REQUIRED_DISCLOSURES[after["page_type"]] if d not in after["disclosure_ids"]]
    return v(not missing, f"missing {missing}")


@checks.check("no_banned_claims", text="No saved draft adds a banned claim.", critical=True)
def no_banned_claims(case, out):
    if not out["cms"]["written"]:
        return NA
    added = [
        p
        for k in site.TEXT_FIELDS
        for p in site.banned_in(out["after"][k])
        if p not in site.banned_in(out["before"][k])
    ]
    return v(not added, f"adds {added}")


@checks.check("page_checks", text="Saved drafts pass the page checks: links, meta length, alt text, date.")
def page_checks(case, out):
    if not out["cms"]["written"]:
        return NA
    bad = [f"{f['label']} ({f['detail']})" for f in out["findings"] if not f["ok"]]
    return v(not bad, "; ".join(bad))


@checks.check(
    "saved_as_draft", text="The draft reads back from the CMS exactly as sent, and is not published.", critical=True
)
def saved_as_draft(case, out):
    c = out["cms"]
    if not c["written"]:
        return NA
    return v(
        c.get("readback_match") is True and not c["published"],
        f"read-back {c.get('readback_match')}, published {c['published']}",
    )
