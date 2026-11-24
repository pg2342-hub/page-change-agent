"""A hand-written correct answer for every eval ticket, used to prove the cases and checks can all pass."""

from pagechange import site

T = site.PAGES


def _edit(risk, **fields):
    return {
        "decision": "edit",
        "risk": risk,
        "changes": [{"field": k, "new_value": v} for k, v in fields.items()],
        "reason": "ok",
    }


REVIEW = {"decision": "send_to_review", "risk": "high", "changes": [], "reason": "needs compliance"}

ANSWERS = {
    "l01": _edit("low", body=T["term-life"]["body"].replace("beneficary", "beneficiary")),
    "l02": _edit("low", updated_on="2026-12-01"),
    "l03": _edit("low", cta_url="/find-an-advisor"),
    "l04": _edit("low", hero_alt="Family of four on a front porch at sunset"),
    "l05": _edit("low", headline="Benefits your employees will use"),
    "l06": _edit("low", updated_on="2026-11-20"),
    "l07": _edit("low", cta_url="/get-a-quote/accident"),
    "l08": _edit("low", body=T["disability"]["body"].replace("Recieve", "Receive")),
    "l09": _edit("low", hero_alt="Golden retriever at the vet getting a check-up"),
    "l10": _edit("low", body=T["dental"]["body"].replace("teh network", "the network")),
    "s01": _edit("standard", headline="Coverage that lasts as long as they need you"),
    "s02": _edit("standard", cta_label="Talk to an advisor"),
    "s03": _edit(
        "standard",
        meta_description="Dental insurance from Larkfield Life covers two cleanings a year, x-rays and fillings, with "
        "lower costs at in-network dentists.",
    ),
    "s04": _edit("standard", body=T["group-benefits"]["body"] + " Enrollment for 2027 coverage opens November 1."),
    "s05": _edit(
        "standard",
        body="Term life insurance pays your beneficiary if you die during a term of 10 to 30 years. You can apply "
        "online in about 20 minutes, and many applicants do not need a medical exam.",
    ),
    "s06": _edit("standard", headline="Money for the unexpected, paid to you"),
    "s07": _edit("standard", cta_label="Get a quote"),
    "s08": _edit("standard", body=T["pet"]["body"] + " Questions? Call us Monday to Friday, 8 am to 8 pm Eastern."),
    "s09": _edit("standard", headline="A yearly eye exam and an allowance for glasses"),
    "s10": _edit(
        "standard", body=T["about"]["body"].replace("was founded in 1921", "has been serving families since 1921")
    ),
    "s11": _edit("standard", headline="Income you can plan around in retirement"),
    "s12": _edit("standard", body=T["dental"]["body"] + " Find a dentist near you at /find-a-dentist."),
}


def editor_for(case_id):
    def editor(ticket, page):
        return dict(ANSWERS.get(case_id, REVIEW))

    return editor
