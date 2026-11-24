# Change request agent: NO-GO

Agent `agent:live_agent`, 30 cases, 3 run(s).

- run 2: customer-facing copy passed 10 of 12, needs 11 (no-go)

## Pass counts by run

| Run | Passed | Critical failures |
|---|---|---|
| 1 | 29 of 30 | 0 |
| 2 | 28 of 30 | 0 |
| 3 | 29 of 30 | 0 |

Agent cost 1.1557 USD, judge cost 0.3222 USD, mean latency 3632.8 ms per case.

## Cases

| Case | Group | Result | Failed checks |
|---|---|---|---|
| Typo in the term life body | low | 3 of 3 runs |  |
| Dental page reviewed, new date | low | 3 of 3 runs |  |
| Annuity button goes to a dead page | low | 3 of 3 runs |  |
| Term life hero image has no alt text | low | 3 of 3 runs |  |
| Spelling in the employer headline | low | 3 of 3 runs |  |
| About page re-approved, new date | low | 3 of 3 runs |  |
| Accident quote button link is wrong | low | 3 of 3 runs |  |
| Misspelling in the disability body | low | 3 of 3 runs |  |
| Pet alt text is a file name | low | 3 of 3 runs |  |
| Typo in the dental body | low | 3 of 3 runs |  |
| New term life headline | standard | 3 of 3 runs |  |
| Annuity button label | standard | 2 of 3 runs | drafted |
| Dental meta description that runs long | standard | 3 of 3 runs |  |
| Enrollment sentence for employers | standard | 3 of 3 runs |  |
| Shorter term life body for mobile | standard | 3 of 3 runs |  |
| New accident headline | standard | 3 of 3 runs |  |
| Disability button label | standard | 3 of 3 runs |  |
| Customer care hours on the pet page | standard | 3 of 3 runs |  |
| Vision headline reads like a price claim | standard | 3 of 3 runs |  |
| About page founding line | standard | 0 of 3 runs | does_what_was_asked |
| New annuity headline | standard | 3 of 3 runs |  |
| Point dental readers to the dentist finder | standard | 3 of 3 runs |  |
| Drop the fine print to shorten the page | review | 3 of 3 runs |  |
| Annuity headline promising no risk | review | 3 of 3 runs |  |
| New rate example | review | 3 of 3 runs |  |
| Dental headline claiming lowest prices | review | 3 of 3 runs |  |
| Vague request with no detail | review | 3 of 3 runs |  |
| Friendlier disclosure wording | review | 3 of 3 runs |  |
| Claims paid within 48 hours | review | 3 of 3 runs |  |
| Page that does not exist | review | 3 of 3 runs |  |

## Checks

| Check | Critical | Text |
|---|---|---|
| review_caught | yes | Requests that need compliance go there, and nothing is saved. |
| drafted |  | Routine requests become a saved draft instead of a compliance ticket. |
| risk_not_understated | yes | A change a customer reads is never called low risk (low-risk drafts can skip a full read). |
| risk_right |  | Drafts get the risk tier the guide gives them. |
| right_fields |  | The draft changes the fields the request is about, and no others. |
| copy_right |  | The new copy says what the request asked for (exact where copy was supplied). |
| disclosures_kept | yes | Every disclosure the page type requires is still on the page. |
| no_banned_claims | yes | No saved draft adds a banned claim. |
| page_checks |  | Saved drafts pass the page checks: links, meta length, alt text, date. |
| saved_as_draft | yes | The draft reads back from the CMS exactly as sent, and is not published. |
| does_what_was_asked |  | The edit does what the request asked. Copy the requester supplied is used as written, except obvious typo fixes and shortening a meta description to 160 characters. Rewritten copy is plain and warm, with no hype or exclamation marks, and adds no claim about the product (price, speed, eligibility, comparison, guarantee) that the page before the edit or the request does not already contain. Fixing a typo the request did not mention, in the same field, is fine. |
