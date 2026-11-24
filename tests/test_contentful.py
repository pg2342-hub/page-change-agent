"""The Contentful client against a stand-in HTTP session that behaves like the Content Management API."""

import json

from pagechange import site
from pagechange.cms import ContentfulCMS
from pagechange.pipeline import READY, handle


class Resp:
    def __init__(self, status, body=None, headers=None):
        self.status_code, self._body, self.headers = status, body, headers or {}
        self.text = json.dumps(body) if body is not None else ""

    def json(self):
        return self._body


class FakeAPI:
    """Entries keyed by path; enforces X-Contentful-Version like the real API."""

    def __init__(self):
        self.store, self.calls = {}, []

    def request(self, method, url, json=None, headers=None, timeout=None):
        path = url.split("/environments/master", 1)[1]
        self.calls.append((method, path, dict(headers or {})))
        item = self.store.get(path)
        if method == "GET":
            return Resp(200, item) if item else Resp(404, {"message": "not found"})
        if method == "PUT":
            v = (headers or {}).get("X-Contentful-Version")
            if item and str(item["sys"]["version"]) != v:
                return Resp(409, {"message": "version mismatch"})
            if not item and path.startswith("/entries/") and "X-Contentful-Content-Type" not in headers:
                return Resp(422, {"message": "content type needed"})
            new = {"sys": {"version": (item["sys"]["version"] if item else 0) + 1}, **(json or {})}
            self.store[path] = new
            return Resp(200, new)
        return Resp(405, {})


def cms(api):
    return ContentfulCMS(token="t", space="s1", environment="master", locale="en-US", session=api)


def test_seed_then_edit_round_trip():
    api = FakeAPI()
    c = cms(api)
    c.reset("dental")
    stored = api.store["/entries/page-dental"]
    assert stored["fields"]["headline"] == {"en-US": site.PAGES["dental"]["headline"]}
    assert "heroAlt" in stored["fields"] and "rateNote" in stored["fields"]
    got = c.get("dental")
    assert got["fields"] == site.page("dental") and got["version"] == 1 and got["published_version"] is None

    def editor(t, p):
        return {
            "decision": "edit",
            "risk": "standard",
            "changes": [{"field": "headline", "new_value": "Smile more"}],
            "reason": "ok",
        }

    r = handle({"page_id": "dental", "request": "x"}, editor, c)
    assert r["label"] == READY and r["cms"]["version_after"] == 2 and r["cms"]["readback_match"]
    put = [h for m, p, h in api.calls if m == "PUT" and p == "/entries/page-dental"][-1]
    assert put["X-Contentful-Version"] == "1" and put["Authorization"] == "Bearer t"


def test_reset_existing_entry_sends_its_version():
    api = FakeAPI()
    c = cms(api)
    c.reset("pet")
    c.reset("pet")
    assert api.store["/entries/page-pet"]["sys"]["version"] == 2


def test_missing_page_reads_as_cms_error():
    import pytest

    from pagechange.cms import CMSError

    with pytest.raises(CMSError, match="no page"):
        cms(FakeAPI()).get("travel")
