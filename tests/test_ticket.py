import pytest

from pagechange.cms import FakeCMS
from pagechange.pipeline import handle
from pagechange.ticket import comment, parse_issue, word_diff

BODY = """### Page

dental

### Part of the page

headline

### What should change

Sales wants this headline.

### New copy

_No response_
"""


def test_parse_issue_form():
    assert parse_issue(BODY) == {"page_id": "dental", "part": "headline", "request": "Sales wants this headline."}
    with pytest.raises(ValueError):
        parse_issue("just some text")


def test_word_diff():
    assert word_diff("See clearly for less", "See clearly every year") == "See clearly ~~for less~~ **every year**"


def test_comment_for_ready_and_compliance():
    def ok(t, p):
        return {
            "decision": "edit",
            "risk": "standard",
            "changes": [{"field": "headline", "new_value": "Smile more"}],
            "reason": "Done.",
        }

    c = comment(handle({"page_id": "dental", "request": "x"}, ok, FakeCMS()))
    assert c.startswith("**Draft saved, ready for approval** (standard risk)") and "| Headline |" in c

    def no(t, p):
        return {"decision": "send_to_review", "risk": "high", "changes": [], "reason": "Rates need sign-off."}

    c = comment(handle({"page_id": "dental", "request": "x"}, no, FakeCMS()))
    assert c.startswith("**Needs compliance.** The agent sent this to compliance") and "Rates need sign-off." in c
