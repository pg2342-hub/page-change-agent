from pathlib import Path

from golive_gate import GO, NO_GO, Gate, evaluate, load_cases, run_eval
from oracle import editor_for

from pagechange.cms import FakeCMS
from pagechange.pipeline import handle

EVAL = Path(__file__).resolve().parents[1] / "evals" / "tickets"


def _rule_checks():
    import sys

    sys.path.insert(0, str(EVAL))
    from checks import checks

    return checks


def test_thirty_cases_in_three_groups():
    cases = load_cases(EVAL / "cases.yml")
    groups = [c.group for c in cases]
    assert len(cases) == 30
    assert (groups.count("low"), groups.count("standard"), groups.count("review")) == (10, 12, 8)


def test_correct_answers_pass_every_rule_check():
    cases = load_cases(EVAL / "cases.yml")
    cms = FakeCMS()
    by_input = {}

    def agent(ticket):
        case = by_input[id(ticket)]
        cms.reset_all()
        return handle(ticket, editor_for(case.id), cms)

    for c in cases:
        by_input[id(c.input)] = c
    result = run_eval(agent, cases, _rule_checks(), runs=1)
    failed = {cr.case_id: cr.failed_checks or cr.error for cr in result.case_runs if not cr.passed}
    assert failed == {}
    assert evaluate(Gate.load(EVAL / "gate.yml"), result).decision == GO


def test_literal_baseline_is_blocked():
    import sys

    sys.path.insert(0, str(EVAL))
    from agent import literal_agent

    cases = load_cases(EVAL / "cases.yml")
    result = run_eval(literal_agent, cases, _rule_checks(), runs=1)
    gr = evaluate(Gate.load(EVAL / "gate.yml"), result)
    assert gr.decision == NO_GO
    crit = {c for c, _ in result.critical_failures(1)}
    assert "r07" in crit  # pasted an unsupported claims-speed promise into the body and saved it
