# page-change-agent

[![CI](https://github.com/pg2342-hub/page-change-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/pg2342-hub/page-change-agent/actions/workflows/ci.yml)

Demo page: https://pranavgudise.dev/page-change-agent/ (the change request queue from a recorded live run, with every draft's before and after; no install needed)

An AI agent that turns website change requests into reviewed CMS drafts. A marketing team files a change as a GitHub issue. A Claude agent reads the page from the CMS, drafts the edit, checks it against the site's compliance rules, saves it as an **unpublished draft**, reads it back, and replies on the issue with a before and after diff and a label. Anything risky goes to compliance instead. Publishing stays a person's click in the CMS.

The CMS is [Contentful](https://www.contentful.com/) (its Content Management API). The website is a made-up insurer with ten product pages, rate examples and the disclosures each page type must carry.

## How a ticket moves

| Step | What happens | Where |
|---|---|---|
| File | An issue form: page, part of the page, what should change, new copy if any. Only people with write access trigger the agent. | `.github/ISSUE_TEMPLATE/change-request.yml` |
| Draft | Claude (`claude-opus-5-5`, structured output) reads the ticket and the page and either proposes field edits with a risk tier (low or standard) or sends the request to compliance with a reason. | `pagechange/claude.py`, `pagechange/editor_guide.md` |
| Check | Rules the model cannot talk past. A blocking failure stops the draft before anything is saved: a disclosure, the page type or URL changed; a required disclosure missing; a banned claim added (guarantees, lowest price, no risk); the rate example edited. Quality checks: links go to real pages, meta description 160 characters or fewer, real alt text, a real date. | `pagechange/compliance.py` |
| Save | An unpublished draft through the Contentful Management API, sent with the page's version so two edits cannot overwrite each other, then read back and compared field by field. | `pagechange/cms.py`, `pagechange/pipeline.py` |
| Reply | A comment with the diff, the checks and the cost, plus a `ready-for-approval` (and `risk:low` or `risk:standard`) or `needs-compliance` label. | `pagechange/ticket.py`, `.github/workflows/handle-ticket.yml` |

Low-risk drafts (typos, dates, alt text, a button link moved to an existing page) are the ones a team could later publish after a sampled check. Every customer-facing wording change is standard risk and goes through the customer's normal review chain, compliance included where their rules require it, with the agent's check results attached.

## The eval

30 change requests (`evals/tickets/cases.yml`): 10 low-risk fixes, 12 customer-facing copy changes, and 8 that must go to compliance (drop the fine print, a "guaranteed returns with zero risk" headline, a new rate, "lowest prices", a vague "fix the page", friendlier disclosure wording, "we pay claims within 48 hours", a page that does not exist). Each runs 3 times through the whole pipeline, graded by [golive-gate](https://github.com/pg2342-hub/golive-gate): rule checks for routing, risk tier, fields, copy, disclosures, banned claims, page checks and the saved draft, and a Claude judge for whether the draft does what was asked in the site's voice.

Critical failures (one is a no-go): a draft saved for a request that needed compliance, a lost disclosure, a banned claim saved, customer copy called low risk, or a draft that does not read back as sent.

**Baseline the eval must block:** a literal editor that pastes the supplied copy where the form says and calls everything low risk (`pagechange/baseline.py`). It saves "We pay approved claims within 48 hours." as the disability page body, so the eval says no-go.

## Run it

```
pip install -e ".[dev]"
pytest -q                                             # no network, no keys
golive run evals/tickets/golive.baseline.yml          # literal baseline: NO-GO
golive run evals/tickets/golive.yml                   # replays the recorded live run: no keys needed
python scripts/build_demo.py                          # rebuild docs/ from the recording
```

Live, against your own Contentful space (free plan is enough):

```
export ANTHROPIC_API_KEY=... CONTENTFUL_CMA_TOKEN=... CONTENTFUL_SPACE_ID=...
page-change-agent seed --yes                          # content type + the ten pages, as drafts
GOLIVE_LIVE=1 golive run evals/tickets/golive.live.yml
```

## Set up the GitHub side

- Secrets: `ANTHROPIC_API_KEY`, `CONTENTFUL_CMA_TOKEN`. Variable: `CONTENTFUL_SPACE_ID`.
- **Record a live run** (Actions tab) seeds the space, runs the 30 tickets 3 times live, refuses a partial or failing run, rebuilds the demo page from the recording and publishes it.
- File an issue from the **Page change request** form to watch the agent answer it. The form applies the `change-request` label, which the record run creates (or run `gh label create change-request` once).
- Requests run one at a time. GitHub keeps only one waiting run, so if several arrive at once only the newest waits; edit a skipped issue's request text to run it again.

## Limits

- The website, its rates and its disclosure rules are invented. A real deployment starts from the customer's own content model and compliance rules.
- Contentful stands in for the CMS; enterprise sites often run Adobe Experience Manager, which needs its own connector behind the same two calls (`get`, `save_draft`).
- Which edits count as low risk should be agreed with the customer's compliance team and checked on their real tickets first.
