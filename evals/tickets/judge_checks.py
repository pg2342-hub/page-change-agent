"""Rule checks plus one Claude judge for what a rule cannot state: does the draft do what was asked, in the
site's voice, without a new product claim.

The judge runs live (and records each reply) when GOLIVE_LIVE=1 and replays the recording otherwise, so CI
and the demo page need no API key.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from checks import checks as rule_checks
from golive_gate import NA, CheckSet, judge_check

from pagechange.recorded import ROOT, Tape, recording_judge, replay_judge
from pagechange.ticket import FIELD_NAMES

JUDGE_TAPE = Tape(ROOT / "tickets_judge.jsonl")
_judge = None


def judge(prompt):
    global _judge
    if _judge is None:
        if os.environ.get("GOLIVE_LIVE") == "1":
            from golive_gate import ClaudeJudge

            _judge = recording_judge(ClaudeJudge(model="claude-opus-5-5", effort="low"), JUDGE_TAPE)
        else:
            _judge = replay_judge(JUDGE_TAPE)
    return _judge(prompt)


checks = CheckSet(rule_checks)


def _render_case(case):
    t = case.input
    s = f"Change request for the {t['page_id']} page of an insurer's website: {t['request']}"
    if t.get("new_copy"):
        s += f"\nCopy supplied by the requester: {t['new_copy']}"
    return s


def _render_output(out):
    rows = [
        f"{FIELD_NAMES.get(k, k)}\n  before: {out['before'][k]}\n  after:  {out['after'][k]}" for k in out["changed"]
    ]
    return "\n".join(rows)


_fulfils = judge_check(
    "does_what_was_asked",
    "The edit does what the request asked. Copy the requester supplied is used as written, except obvious typo "
    "fixes and shortening a meta description to 160 characters. Rewritten copy is plain and warm, with no hype "
    "or exclamation marks, and adds no claim about the product (price, speed, eligibility, comparison, "
    "guarantee) that the before text or the request does not already contain. Fixing a typo the request did not "
    "mention, in the same field, is fine.",
    judge=judge,
    render_case=_render_case,
    render_output=_render_output,
)


@checks.check("does_what_was_asked", text=_fulfils.text)
def does_what_was_asked(case, out):
    if not out["cms"]["written"]:
        return NA
    return _fulfils.run(case, out)
