"""Build docs/index.html from the recorded live run (and the baseline), in the shared demo look.

    python scripts/build_demo.py              # from recordings/ (what CI and Pages use)
    python scripts/build_demo.py --preview    # layout check only: hand-written answers, written to /tmp

Every number on the page comes from the graded run. The shared header and footer come from demo_chrome.chrome().
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evals" / "tickets"
sys.path[:0] = [str(ROOT), str(EVAL), str(ROOT / "scripts"), str(ROOT / "tests")]

from demo_chrome import chrome  # noqa: E402
from golive_gate import Gate, evaluate, load_cases, run_eval  # noqa: E402

from pagechange import site  # noqa: E402
from pagechange.ticket import FIELD_NAMES  # noqa: E402

REPO = "page-change-agent"
e = html.escape
WHO = {
    "agent": "The agent sent it to compliance",
    "guardrail": "A compliance check stopped the draft",
    "missing page": "No such page on the site",
    "no change": "The draft changed nothing",
    "read-back mismatch": "The saved draft did not match",
    "cms error": "The CMS refused the draft",
}
PARTS = {"low": "Low risk", "standard": "Customer-facing copy", "review": "Needs compliance"}


def graded(preview: bool):
    cases = load_cases(EVAL / "cases.yml")
    gate = Gate.load(EVAL / "gate.yml")
    from checks import checks as rule_checks

    if preview:
        from oracle import editor_for

        from pagechange.cms import FakeCMS
        from pagechange.pipeline import handle

        cms, by = FakeCMS(), {id(c.input): c for c in cases}

        def agent(t):
            cms.reset_all()
            r = handle(t, editor_for(by[id(t)].id), cms)
            r.update(model="preview", cost_usd=0.0)
            return r

        res = run_eval(agent, cases, rule_checks, runs=3)
    else:
        from agent import recorded_agent
        from judge_checks import checks

        res = run_eval(recorded_agent, cases, checks, runs=3)
    from agent import literal_agent

    base = run_eval(literal_agent, cases, rule_checks, runs=1)
    return cases, res, evaluate(gate, res), base, evaluate(gate, base), gate


def strip(cases, res, label):
    crit = {c for r in range(1, res.runs + 1) for c, _ in _crit(res, r)}
    cells, passed = [], 0
    for i, c in enumerate(cases):
        runs = res.for_case(c.id)
        ok = all(cr.passed for cr in runs)
        passed += ok
        kind = "crit" if c.id in crit else ("pass" if ok else "fail")
        word = {"pass": "passed", "fail": "failed", "crit": "failed with a critical error"}[kind]
        cells.append(
            f'<a class="cell {kind}" href="#t-{c.id}" data-case="{c.id}" aria-label="{e(label)} ticket {i + 1} {word}"></a>'
        )
    return "".join(cells), passed, len(crit)


def _crit(res, run):
    out = []
    for a, b in res.critical_failures(run):
        out.append((a, b) if a in {cr.case_id for cr in res.case_runs} else (b, a))
    return out


def diff_html(old, new):
    import difflib

    a, b = str(old).split(), str(new).split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if op == "equal":
            out.append(e(" ".join(a[i1:i2])))
        if op in ("delete", "replace"):
            out.append(f"<del>{e(' '.join(a[i1:i2]))}</del>")
        if op in ("insert", "replace"):
            out.append(f"<ins>{e(' '.join(b[j1:j2]))}</ins>")
    return " ".join(out)


def ticket_payload(cases, res):
    items = []
    for c in cases:
        runs = res.for_case(c.id)
        r = runs[0].output
        t = c.input
        page = site.PAGES.get(t["page_id"])
        verdicts = []
        for cr in runs:
            verdicts.append(
                {
                    "run": cr.run,
                    "passed": cr.passed,
                    "failed": [f"{k}: {v.reason}" for k, v in cr.verdicts.items() if v.result == "fail"],
                }
            )
        stable = len({(x.output["label"], tuple(x.output["changed"])) for x in runs}) == 1
        items.append(
            {
                "id": c.id,
                "group": c.group,
                "title": c.title,
                "page": page["slug"] if page else f"/{t['page_id']} (does not exist)",
                "part": t.get("part", ""),
                "request": t["request"],
                "new_copy": t.get("new_copy", ""),
                "label": r["label"],
                "risk": r["risk"],
                "stopped_by": r["stopped_by"],
                "who": WHO.get(r["stopped_by"] or "", ""),
                "reason": r["reason"],
                "changes": [
                    {"field": FIELD_NAMES.get(k, k), "diff": diff_html(r["before"][k], r["after"][k])}
                    for k in r["changed"]
                ]
                if r["label"] == "ready-for-approval"
                else [],
                "findings": [{"label": f["label"], "ok": f["ok"], "detail": f["detail"]} for f in r["findings"]],
                "cms": r["cms"],
                "cost": r.get("cost_usd") or 0.0,
                "latency": r.get("agent_latency_s") or r["latency_s"],
                "model": r.get("model", ""),
                "runs": verdicts,
                "stable": stable,
            }
        )
    return items


def route_counts(res):
    """Where all 90 tickets went, for the signature chart."""
    n = {"low": 0, "standard": 0, "agent": 0, "guardrail": 0, "other": 0}
    for cr in res.case_runs:
        o = cr.output
        if o["label"] == "ready-for-approval":
            n[o["risk"]] += 1
        elif o["stopped_by"] in ("agent", "missing page"):
            n["agent"] += 1
        elif o["stopped_by"] == "guardrail":
            n["guardrail"] += 1
        else:
            n["other"] += 1
    return n


def chart(n, total):
    """Horizontal bar split to scale: where every handled ticket ended up."""
    segs = [
        ("low", "Draft, low risk", "var(--green)", "var(--paper)"),
        ("standard", "Draft, customer-facing", "var(--green-wash)", "var(--green-deep)"),
        ("agent", "Sent to compliance by the agent", "var(--ink)", "var(--paper)"),
        ("guardrail", "Stopped by a check", "url(#hatch)", "var(--ink)"),
        ("other", "Other", "var(--rule)", "var(--ink)"),
    ]
    w, x, bars, keys = 1000, 0.0, [], []
    for k, label, fill, txt in segs:
        if not n[k]:
            continue
        width = w * n[k] / total
        bars.append(
            f'<rect x="{x:.1f}" y="0" width="{width:.1f}" height="56" fill="{fill}" stroke="var(--ink)" stroke-width="1"/>'
            + (
                f'<text x="{x + width / 2:.1f}" y="35" text-anchor="middle" fill="{txt}">{n[k]}</text>'
                if width > 36
                else ""
            )
        )
        keys.append(
            f'<li><i style="background:{fill if not fill.startswith("url") else "repeating-linear-gradient(45deg,var(--ink) 0 2px,transparent 2px 6px)"}"></i>{label} <b>{n[k]}</b></li>'
        )
        x += width
    return (
        f'<svg class="route" viewBox="0 0 {w} 56" role="img" aria-label="Where {total} handled tickets went">'
        '<defs><pattern id="hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">'
        '<rect width="6" height="6" fill="var(--paper)"/><rect width="2" height="6" fill="var(--ink)"/></pattern></defs>'
        + "".join(bars)
        + f'</svg><ul class="rkey">{"".join(keys)}</ul>'
    )


def build(preview: bool) -> str:
    cases, res, gr, base, bgr, gate = graded(preview)
    items = ticket_payload(cases, res)
    s_cells, s_pass, s_crit = strip(cases, res, "Claude agent")
    b_cells, b_pass, b_crit = strip(cases, base, "Literal baseline")
    n = route_counts(res)
    total = len(res.case_runs)
    cost = sum(cr.cost_usd for cr in res.case_runs) / max(total, 1)
    lat = [cr.output.get("agent_latency_s") or 0 for cr in res.case_runs]
    lat_med = sorted(lat)[len(lat) // 2] if lat else 0
    model = next((cr.output.get("model") for cr in res.case_runs if cr.output.get("model")), "")
    written = sum(1 for cr in res.case_runs if cr.output["cms"]["written"])
    matched = sum(1 for cr in res.case_runs if cr.output["cms"].get("readback_match"))
    published = sum(1 for cr in res.case_runs if cr.output["cms"]["published"])
    cms_name = next((cr.output["cms"]["system"] for cr in res.case_runs), "")
    badge = lambda d: (
        '<span class="gate go">GO</span>'
        if d == "go"
        # noqa: E731
        else ('<span class="gate part">PARTIAL</span>' if d == "partial" else '<span class="gate nogo">NO-GO</span>')
    )
    rules = "; ".join(
        f"{r.name.split(' (')[0]} {('all' if r.all_must_pass else r.min_pass)} of {sum(1 for c in cases if c.group in r.groups)}"
        for r in gate.rules
    )
    data = json.dumps(items).replace("</", "<\\/")
    page = TEMPLATE
    subs = {
        "{{DATA}}": data,
        "{{S_CELLS}}": s_cells,
        "{{S_PASS}}": str(s_pass),
        "{{S_CRIT}}": str(s_crit),
        "{{S_GATE}}": badge(gr.decision),
        "{{B_CELLS}}": b_cells,
        "{{B_PASS}}": str(b_pass),
        "{{B_CRIT}}": str(b_crit),
        "{{B_GATE}}": badge(bgr.decision),
        "{{RULES}}": e(rules),
        "{{CHART}}": chart(n, total),
        "{{TOTAL}}": str(total),
        "{{COST}}": f"${cost:.4f}",
        "{{LAT}}": f"{lat_med:.1f} s",
        "{{MODEL}}": e(model or "Claude"),
        "{{WRITTEN}}": str(written),
        "{{MATCHED}}": str(matched),
        "{{PUBLISHED}}": str(published),
        "{{CMS}}": e(cms_name),
        "{{GUARD_LINE}}": "The agent routed every risky request itself, so the compliance checks never had to stop a draft."
        if n["guardrail"] == 0
        else f"Checks stopped {n['guardrail']} drafts the agent tried to make, before anything was saved.",
        "{{READBACK}}": "Every saved draft was unpublished and read back exactly"
        if matched == written and published == 0
        else "Not every saved draft read back cleanly",
    }
    for k, v in subs.items():
        page = page.replace(k, v)
    return chrome(page, REPO)


TEMPLATE = (ROOT / "scripts" / "demo_template.html").read_text(encoding="utf-8")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true")
    args = ap.parse_args()
    out = Path("/tmp/page-change-preview/index.html") if args.preview else ROOT / "docs" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(args.preview), encoding="utf-8")
    (out.parent / ".nojekyll").touch()
    print(f"wrote {out}")
