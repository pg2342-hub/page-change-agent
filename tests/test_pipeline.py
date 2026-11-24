import pytest

from pagechange.baseline import literal_editor
from pagechange.cms import CMSError, FakeCMS
from pagechange.pipeline import COMPLIANCE, READY, handle


def editor(decision="edit", risk="standard", **fields):
    def e(ticket, page):
        return {
            "decision": decision,
            "risk": risk,
            "changes": [{"field": k, "new_value": v} for k, v in fields.items()],
            "reason": "r",
            "_meta": {"cost_usd": 0.01, "model": "m", "latency_s": 1.0},
        }

    return e


def test_a_clean_edit_is_saved_as_a_draft_and_read_back():
    cms = FakeCMS()
    r = handle({"page_id": "vision", "request": "x"}, editor(headline="A yearly eye exam, glasses covered"), cms)
    assert r["label"] == READY and r["changed"] == ["headline"]
    assert r["cms"] == {
        "system": "in-memory stand-in",
        "written": True,
        "published": False,
        "version_before": 1,
        "version_after": 2,
        "readback_match": True,
    }
    assert cms.get("vision")["fields"]["headline"] == "A yearly eye exam, glasses covered"
    assert r["cost_usd"] == 0.01


def test_guardrail_stops_a_banned_claim_and_saves_nothing():
    cms = FakeCMS()
    r = handle({"page_id": "dental", "request": "x"}, editor(headline="The lowest prices in the country"), cms)
    assert r["label"] == COMPLIANCE and r["stopped_by"] == "guardrail" and not r["cms"]["written"]
    assert cms.get("dental")["version"] == 1


def test_agent_referral_and_missing_page():
    cms = FakeCMS()
    r = handle({"page_id": "pet", "request": "x"}, editor("send_to_review", "high"), cms)
    assert r["stopped_by"] == "agent" and r["label"] == COMPLIANCE
    r = handle({"page_id": "travel", "request": "x"}, editor(headline="Trips"), cms)
    assert r["stopped_by"] == "missing page" and r["before"] is None


def test_an_edit_that_changes_nothing_is_not_saved():
    cms = FakeCMS()
    r = handle({"page_id": "pet", "request": "x"}, literal_editor, cms)
    assert r["stopped_by"] == "no change" and not r["cms"]["written"]


def test_version_conflict_is_refused():
    cms = FakeCMS()
    with pytest.raises(CMSError):
        cms.save_draft("pet", cms.get("pet")["fields"], version=7)


class FlakyCMS(FakeCMS):
    def get(self, page_id):
        got = super().get(page_id)
        if got["version"] > 1:
            got["fields"]["headline"] = "something else"
        return got


def test_a_draft_that_reads_back_wrong_goes_to_compliance():
    r = handle({"page_id": "vision", "request": "x"}, editor(headline="New"), FlakyCMS())
    assert r["label"] == COMPLIANCE and r["stopped_by"] == "read-back mismatch" and r["cms"]["readback_match"] is False


def test_an_edit_the_agent_calls_high_risk_goes_to_compliance():
    cms = FakeCMS()
    r = handle({"page_id": "vision", "request": "x"}, editor(risk="high", headline="New headline"), cms)
    assert r["label"] == COMPLIANCE and r["stopped_by"] == "agent" and not r["cms"]["written"]


def test_a_cms_refusal_is_reported_not_raised():
    class Refusing(FakeCMS):
        def save_draft(self, *a, **k):
            raise CMSError("409 version conflict")

    r = handle({"page_id": "vision", "request": "x"}, editor(headline="New headline"), Refusing())
    assert r["label"] == COMPLIANCE and r["stopped_by"] == "cms error" and "409" in r["reason"]


def test_a_bad_date_is_blocked_before_it_reaches_the_cms():
    r = handle({"page_id": "vision", "request": "x"}, editor(updated_on="next Tuesday"), FakeCMS())
    assert r["stopped_by"] == "guardrail" and not r["cms"]["written"]
