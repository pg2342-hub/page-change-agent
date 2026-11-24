"""Agents for the ticket eval. Each one runs the full pipeline (read page, propose, check, save, read back).

- recorded_agent: replays the last live run from recordings/ (no keys; CI and the demo use this)
- live_agent:     Claude now, against Contentful when CONTENTFUL_CMA_TOKEN is set (else the in-memory stand-in)
- literal_agent:  the no-model baseline the eval must block
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from golive_gate import Response

from pagechange.baseline import literal_editor
from pagechange.cms import FakeCMS
from pagechange.pipeline import handle
from pagechange.recorded import ROOT, Tape, recording, replay
from pagechange.site import PAGES

TAPE = Tape(ROOT / "tickets_agent.jsonl")
_live = None
_fake = FakeCMS()


def _as_response(result):
    return Response(result, cost_usd=result.get("cost_usd", 0.0))


def _fresh(cms, page_id):
    """Every ticket starts from the page's starting copy, so runs do not leak into each other."""
    if page_id in PAGES:
        cms.reset(page_id)


def recorded_agent(ticket):
    return _as_response(replay(TAPE)(ticket))


def live_agent(ticket):
    global _live
    if _live is None:  # built on first use, so importing this file needs no keys
        from pagechange.claude import ClaudeEditor
        from pagechange.cms import ContentfulCMS

        cms = ContentfulCMS() if os.environ.get("CONTENTFUL_CMA_TOKEN") else FakeCMS()
        editor = ClaudeEditor()

        def run(t):
            _fresh(cms, t["page_id"])
            return handle(t, editor, cms)

        _live = recording(run, TAPE)
    return _as_response(_live(ticket))


def literal_agent(ticket):
    _fresh(_fake, ticket["page_id"])
    return _as_response(handle(ticket, literal_editor, _fake))
