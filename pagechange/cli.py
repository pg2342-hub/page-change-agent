"""page-change-agent: handle one change request issue.

    page-change-agent handle --issue-body issue.md --out out/

Writes out/comment.md and out/labels.txt (one label per line) for the workflow to post. Uses Contentful
when CONTENTFUL_CMA_TOKEN is set, else the in-memory stand-in. Calls Claude (needs ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .pipeline import handle
from .ticket import comment, parse_issue


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="page-change-agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("handle", help="handle one change request issue")
    h.add_argument("--issue-body", required=True, help="file holding the issue body")
    h.add_argument("--out", default="out")
    s = sub.add_parser("seed", help="create the content type and reset every page in Contentful")
    s.add_argument("--yes", action="store_true", help="really overwrite the pages' drafts")
    args = ap.parse_args(argv)

    if args.cmd == "seed":
        from .cms import ContentfulCMS

        if not args.yes:
            print("This overwrites the drafts of every page in the space. Re-run with --yes.")
            return 2
        cms = ContentfulCMS()
        cms.ensure_content_type()
        cms.reset_all()
        print(f"Seeded {cms.space}/{cms.environment}")
        return 0

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    try:
        ticket = parse_issue(Path(args.issue_body).read_text())
    except ValueError as e:
        (out / "comment.md").write_text(f"Could not read this request: {e}. Please use the change request form.")
        (out / "labels.txt").write_text("needs-compliance\n")
        return 0

    from .claude import ClaudeEditor
    from .cms import ContentfulCMS, FakeCMS

    cms = ContentfulCMS() if os.environ.get("CONTENTFUL_CMA_TOKEN") else FakeCMS()
    try:
        result = handle(ticket, ClaudeEditor(), cms)
    except Exception as err:  # noqa: BLE001  any failure still gets a reply on the issue
        result = {
            "ticket": ticket,
            "label": "needs-compliance",
            "risk": "high",
            "stopped_by": "agent error",
            "reason": f"{type(err).__name__}: {err}",
            "cms": {"system": cms.name, "written": False, "published": False},
            "findings": [],
            "latency_s": 0.0,
        }
    (out / "comment.md").write_text(comment(result))
    labels = [result["label"]] + ([f"risk:{result['risk']}"] if result["label"] == "ready-for-approval" else [])
    (out / "labels.txt").write_text("\n".join(labels) + "\n")
    (out / "result.json").write_text(json.dumps(result, indent=2))
    print(comment(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
