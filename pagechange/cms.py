"""Where pages live. Contentful (the real API) for live runs and the GitHub Action, and an in-memory stand-in
with the same behaviour for tests.

Both only ever save drafts. Nothing in this repo publishes a page: publishing stays a person's click in the
CMS. The Contentful space stands in for the Adobe Experience Manager instance a large insurer would run.
"""

from __future__ import annotations

import copy
import os
import time
from typing import Any

from . import site

CONTENT_TYPE = "landingPage"
# Our field names -> Contentful field ids.
FIELD_IDS = {
    "page_type": "pageType",
    "slug": "slug",
    "title": "title",
    "headline": "headline",
    "body": "body",
    "cta_label": "ctaLabel",
    "cta_url": "ctaUrl",
    "meta_description": "metaDescription",
    "rate_note": "rateNote",
    "hero_alt": "heroAlt",
    "updated_on": "updatedOn",
    "disclosure_ids": "disclosureIds",
}
FIELDS_BACK = {v: k for k, v in FIELD_IDS.items()}


def entry_id(page_id: str) -> str:
    return f"page-{page_id}"


class CMSError(RuntimeError):
    pass


class FakeCMS:
    """In-memory pages with versions, drafts and a published flag, like Contentful's entries."""

    name = "in-memory stand-in"

    def __init__(self) -> None:
        self._pages: dict[str, dict[str, Any]] = {}
        self.reset_all()

    def reset_all(self) -> None:
        for pid in site.PAGES:
            self.reset(pid)

    def reset(self, page_id: str) -> None:
        self._pages[page_id] = {"fields": site.page(page_id), "version": 1, "published_version": None}

    def get(self, page_id: str) -> dict[str, Any]:
        if page_id not in self._pages:
            raise CMSError(f"no page {page_id!r}")
        p = self._pages[page_id]
        return {
            "fields": copy.deepcopy(p["fields"]),
            "version": p["version"],
            "published_version": p["published_version"],
        }

    def save_draft(self, page_id: str, fields: dict[str, Any], version: int) -> int:
        p = self._pages[page_id]
        if version != p["version"]:
            raise CMSError(f"version conflict on {page_id}: have {p['version']}, got {version}")
        p["fields"] = copy.deepcopy(fields)
        p["version"] += 1
        return p["version"]


class ContentfulCMS:
    """Contentful Content Management API. Needs CONTENTFUL_CMA_TOKEN and CONTENTFUL_SPACE_ID."""

    name = "Contentful"
    base = "https://api.contentful.com"

    def __init__(
        self,
        token: str | None = None,
        space: str | None = None,
        environment: str | None = None,
        locale: str | None = None,
        session: Any = None,
    ) -> None:
        self.token = token or os.environ["CONTENTFUL_CMA_TOKEN"]
        self.space = space or os.environ["CONTENTFUL_SPACE_ID"]
        self.environment = environment or os.environ.get("CONTENTFUL_ENVIRONMENT", "master")
        self.locale = locale or os.environ.get("CONTENTFUL_LOCALE", "en-US")
        if session is None:
            import requests

            session = requests.Session()
        self.http = session

    # -- HTTP -----------------------------------------------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.base}/spaces/{self.space}/environments/{self.environment}{path}"

    def _call(self, method: str, path: str, body: Any = None, headers: dict | None = None) -> dict:
        h = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/vnd.contentful.management.v1+json"}
        h.update(headers or {})
        for attempt in range(5):
            r = self.http.request(method, self._url(path), json=body, headers=h, timeout=30)
            if r.status_code == 429:  # rate limited: wait as told, then retry
                time.sleep(float(r.headers.get("X-Contentful-RateLimit-Reset", 1 + attempt)))
                continue
            if r.status_code >= 400:
                raise CMSError(f"{method} {path}: HTTP {r.status_code} {r.text[:300]}")
            return r.json() if r.text else {}
        raise CMSError(f"{method} {path}: still rate limited after 5 tries")

    def _to_cf(self, fields: dict[str, Any]) -> dict:
        out = {}
        for k, v in fields.items():
            if k in FIELD_IDS and v not in ("", None):
                out[FIELD_IDS[k]] = {self.locale: v}
        return out

    def _from_cf(self, cf_fields: dict) -> dict[str, Any]:
        out = {k: ("" if k not in ("disclosure_ids",) else []) for k in FIELD_IDS}
        for cid, by_locale in cf_fields.items():
            if cid in FIELDS_BACK and self.locale in by_locale:
                v = by_locale[self.locale]
                out[FIELDS_BACK[cid]] = v[:10] if cid == "updatedOn" else v
        return out

    # -- setup ----------------------------------------------------------------------------------------
    def ensure_content_type(self) -> None:
        sym, text = {"type": "Symbol"}, {"type": "Text"}
        fields = [
            {"id": "slug", "name": "Slug", "required": True, **sym},
            {"id": "pageType", "name": "Page type", "required": True, **sym},
            {"id": "title", "name": "Title", "required": True, **sym},
            {"id": "headline", "name": "Headline", **sym},
            {"id": "body", "name": "Body", **text},
            {"id": "ctaLabel", "name": "Button label", **sym},
            {"id": "ctaUrl", "name": "Button link", **sym},
            {
                "id": "metaDescription",
                "name": "Meta description",
                "validations": [{"size": {"max": site.META_MAX}}],
                **sym,
            },
            {"id": "rateNote", "name": "Rate example", **sym},
            {"id": "heroAlt", "name": "Hero image alt text", **sym},
            {"id": "updatedOn", "name": "Last updated", "type": "Date"},
            {"id": "disclosureIds", "name": "Disclosures", "type": "Array", "items": {"type": "Symbol"}},
        ]
        body = {"name": "Landing page", "displayField": "title", "fields": fields}
        path = f"/content_types/{CONTENT_TYPE}"
        try:
            current = self._call("GET", path)
            version = current["sys"]["version"]
            done = self._call("PUT", path, body, {"X-Contentful-Version": str(version)})
        except CMSError as e:
            if "HTTP 404" not in str(e):
                raise
            done = self._call("PUT", path, body)
        self._call("PUT", f"{path}/published", None, {"X-Contentful-Version": str(done["sys"]["version"])})

    def reset(self, page_id: str) -> None:
        """Put a page back to its starting copy (as a draft), creating it the first time."""
        path = f"/entries/{entry_id(page_id)}"
        body = {"fields": self._to_cf(site.page(page_id))}
        try:
            current = self._call("GET", path)
            self._call("PUT", path, body, {"X-Contentful-Version": str(current["sys"]["version"])})
        except CMSError as e:
            if "HTTP 404" not in str(e):
                raise
            self._call("PUT", path, body, {"X-Contentful-Content-Type": CONTENT_TYPE})

    def reset_all(self) -> None:
        for pid in site.PAGES:
            self.reset(pid)

    # -- the two calls the agent pipeline uses --------------------------------------------------------
    def get(self, page_id: str) -> dict[str, Any]:
        try:
            e = self._call("GET", f"/entries/{entry_id(page_id)}")
        except CMSError as err:
            if "HTTP 404" in str(err):
                raise CMSError(f"no page {page_id!r}") from err
            raise
        return {
            "fields": self._from_cf(e.get("fields", {})),
            "version": e["sys"]["version"],
            "published_version": e["sys"].get("publishedVersion"),
        }

    def save_draft(self, page_id: str, fields: dict[str, Any], version: int) -> int:
        e = self._call(
            "PUT",
            f"/entries/{entry_id(page_id)}",
            {"fields": self._to_cf(fields)},
            {"X-Contentful-Version": str(version)},
        )
        return e["sys"]["version"]
