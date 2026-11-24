"""A small invented insurer website: ten product pages, the disclosure library, and the rules every edit must keep.

Larkfield Life is made up. The page copy, rates and disclosure wording are written for this repo; they
follow the shape of real insurer pages (a product page with a rate example, a call to action, and fine
print at the bottom) without copying any real company's text.
"""

from __future__ import annotations

import copy
import re

BRAND = "Larkfield Life"
SITE = "https://larkfieldlife.example"

# Fields an editor (or the agent) may change. Disclosures and page type are read-only here: changing them
# goes through the compliance team, never through a change request.
EDITABLE = (
    "title",
    "headline",
    "body",
    "cta_label",
    "cta_url",
    "meta_description",
    "rate_note",
    "hero_alt",
    "updated_on",
)
READ_ONLY = ("page_type", "slug", "disclosure_ids")
TEXT_FIELDS = ("title", "headline", "body", "cta_label", "meta_description", "rate_note", "hero_alt")
META_MAX = 160

DISCLOSURES = {
    "D-GEN": "Insurance products are issued by Larkfield Life Insurance Company, Example City, and are subject to "
    "the terms, conditions and exclusions of the policy.",
    "D-STATE": "Products and features are not available in all states.",
    "D-TERM": "Rate examples are illustrative. Your premium depends on age, health, coverage amount and term, and is "
    "set after underwriting.",
    "D-ANN": "Annuities are not bank deposits, are not FDIC insured, and may lose value. Guarantees are subject to the "
    "claims-paying ability of the issuing company.",
    "D-DENT": "Dental plans include waiting periods, frequency limits and exclusions. See the plan summary for "
    "details.",
    "D-DIS": "Benefits are paid after the elimination period and are subject to the definition of disability in the "
    "policy.",
}

# What every page of a type must carry. A change request can never remove one.
REQUIRED_DISCLOSURES = {
    "term_life": ("D-GEN", "D-STATE", "D-TERM"),
    "annuity": ("D-GEN", "D-STATE", "D-ANN"),
    "dental": ("D-GEN", "D-DENT"),
    "vision": ("D-GEN",),
    "disability": ("D-GEN", "D-STATE", "D-DIS"),
    "accident": ("D-GEN", "D-STATE"),
    "pet": ("D-GEN", "D-STATE"),
    "group_benefits": ("D-GEN",),
    "about": (),
}

# Claims a financial services marketing page may not make. Matched case-insensitively as whole phrases.
BANNED_PHRASES = (
    "guaranteed approval",
    "guaranteed returns",
    "guaranteed best",
    "lowest price",
    "lowest prices",
    "lowest rates",
    "best rates",
    "best price",
    "cheapest",
    "risk-free",
    "risk free",
    "no risk",
    "zero risk",
    "never lose",
    "100% safe",
    "always approved",
)

# Internal pages that exist on the site, so a link to anything else is broken.
EXTRA_SLUGS = ("/find-an-advisor", "/find-a-dentist", "/get-a-quote", "/get-a-quote/accident", "/claims", "/contact")

PAGES = {
    "term-life": {
        "page_type": "term_life",
        "slug": "/life-insurance/term",
        "title": "Term Life Insurance",
        "headline": "Protect the people who count on you",
        "body": "Term life insurance pays a set amount to your beneficary if you die during the term you choose, "
        "from 10 to 30 years. Most people pick a term that lasts until the kids are grown or the mortgage is "
        "paid off. You can apply online in about 20 minutes, and many applicants do not need a medical exam.",
        "cta_label": "Get a quote",
        "cta_url": "/get-a-quote",
        "meta_description": "Term life insurance from Larkfield Life: coverage for 10 to 30 years, an online "
        "application, and many plans with no medical exam.",
        "rate_note": "Example: $18 a month for $250,000 of 20-year coverage, healthy 30-year-old non-smoker.",
        "hero_alt": "",
        "updated_on": "2026-03-02",
        "disclosure_ids": ["D-GEN", "D-STATE", "D-TERM"],
    },
    "annuities": {
        "page_type": "annuity",
        "slug": "/retirement/annuities",
        "title": "Fixed Annuities",
        "headline": "Turn savings into income for retirement",
        "body": "A fixed annuity grows your savings at a set rate for a period you choose, then can pay you an "
        "income for life. It can sit alongside a 401(k) or IRA. Talk to a financial professional about whether "
        "an annuity fits your plans before you buy.",
        "cta_label": "Contact an advisor",
        "cta_url": "/contact-advisor",
        "meta_description": "Fixed annuities from Larkfield Life: grow savings at a set rate, then turn them "
        "into retirement income.",
        "rate_note": "Current 5-year fixed rate: 4.10% for new contracts of $25,000 or more.",
        "hero_alt": "Retired couple reviewing papers at a kitchen table",
        "updated_on": "2026-09-15",
        "disclosure_ids": ["D-GEN", "D-STATE", "D-ANN"],
    },
    "dental": {
        "page_type": "dental",
        "slug": "/benefits/dental",
        "title": "Dental Insurance",
        "headline": "Dental coverage for cleanings, fillings and more",
        "body": "Our dental plans cover two cleanings a year, x-rays and fillings, with lower costs when you use a "
        "dentist in teh network. Larger work such as crowns is covered after a waiting period.",
        "cta_label": "See plans",
        "cta_url": "/get-a-quote",
        "meta_description": "Dental insurance from Larkfield Life covers cleanings, x-rays and fillings, with "
        "lower costs in network.",
        "rate_note": "Plans from $24 a month for an individual.",
        "hero_alt": "Smiling patient in a dentist's chair",
        "updated_on": "2026-01-20",
        "disclosure_ids": ["D-GEN", "D-DENT"],
    },
    "vision": {
        "page_type": "vision",
        "slug": "/benefits/vision",
        "title": "Vision Insurance",
        "headline": "See clearly for less",
        "body": "Vision coverage includes a yearly eye exam and an allowance toward glasses or contact lenses at "
        "thousands of eye doctors and retailers.",
        "cta_label": "See plans",
        "cta_url": "/get-a-quote",
        "meta_description": "Vision insurance from Larkfield Life: a yearly eye exam and an allowance for glasses "
        "or contacts.",
        "rate_note": "Plans from $9 a month for an individual.",
        "hero_alt": "Child trying on glasses",
        "updated_on": "2026-02-11",
        "disclosure_ids": ["D-GEN"],
    },
    "disability": {
        "page_type": "disability",
        "slug": "/benefits/disability",
        "title": "Disability Insurance",
        "headline": "Income protection if you cannot work",
        "body": "Disability insurance replaces part of your paycheck if an illness or injury keeps you from "
        "working. Recieve a monthly benefit after the elimination period you choose, for as long as the policy "
        "says.",
        "cta_label": "Learn more",
        "cta_url": "/get-a-quote",
        "meta_description": "Disability insurance from Larkfield Life replaces part of your income if illness "
        "or injury keeps you from working.",
        "rate_note": "Most plans replace 50% to 60% of earnings.",
        "hero_alt": "Nurse talking with a patient",
        "updated_on": "2026-05-04",
        "disclosure_ids": ["D-GEN", "D-STATE", "D-DIS"],
    },
    "accident": {
        "page_type": "accident",
        "slug": "/benefits/accident",
        "title": "Accident Insurance",
        "headline": "Cash benefits when an accident happens",
        "body": "Accident insurance pays you directly for covered injuries such as fractures, burns and emergency "
        "room visits, so you can use the money however you need.",
        "cta_label": "Get a quote",
        "cta_url": "/quote/accident",
        "meta_description": "Accident insurance from Larkfield Life pays cash benefits for covered injuries.",
        "rate_note": "Plans from $11 a month.",
        "hero_alt": "Teenager with an arm in a cast at a soccer field",
        "updated_on": "2026-04-09",
        "disclosure_ids": ["D-GEN", "D-STATE"],
    },
    "pet": {
        "page_type": "pet",
        "slug": "/benefits/pet",
        "title": "Pet Insurance",
        "headline": "Vet bills covered, so you can focus on them",
        "body": "Pet insurance helps pay for vet visits for accidents and illnesses for dogs and cats of any age.",
        "cta_label": "Get a quote",
        "cta_url": "/get-a-quote",
        "meta_description": "Pet insurance from Larkfield Life helps pay vet bills for accidents and illnesses.",
        "rate_note": "Plans from $15 a month for cats and $28 a month for dogs.",
        "hero_alt": "IMG_4471.jpg",
        "updated_on": "2026-06-30",
        "disclosure_ids": ["D-GEN", "D-STATE"],
    },
    "group-benefits": {
        "page_type": "group_benefits",
        "slug": "/employers/benefits",
        "title": "Benefits for Employers",
        "headline": "Benefits your employes will use",
        "body": "Offer dental, vision, disability and life coverage through one carrier, with one bill and one "
        "enrollment site. Plans are available for employers with 2 or more employees.",
        "cta_label": "Talk to sales",
        "cta_url": "/contact",
        "meta_description": "Group benefits from Larkfield Life: dental, vision, disability and life coverage "
        "for employers with 2 or more employees.",
        "rate_note": "",
        "hero_alt": "Team meeting around a conference table",
        "updated_on": "2026-08-18",
        "disclosure_ids": ["D-GEN"],
    },
    "about": {
        "page_type": "about",
        "slug": "/about",
        "title": "About Larkfield Life",
        "headline": "Here for families for more than a century",
        "body": "Larkfield Life was founded in 1921 to help working families plan for the unexpected. Today we "
        "serve customers across the country with life, retirement and workplace benefits.",
        "cta_label": "Contact us",
        "cta_url": "/contact",
        "meta_description": "About Larkfield Life, founded in 1921 to help working families plan for the unexpected.",
        "rate_note": "",
        "hero_alt": "Historic photo of the first Larkfield Life office",
        "updated_on": "2025-11-03",
        "disclosure_ids": [],
    },
    "claims": {
        "page_type": "about",
        "slug": "/claims",
        "title": "File a Claim",
        "headline": "Start a claim online or by phone",
        "body": "You can start most claims online. Have the policy number and the date of the event ready. Our "
        "claims team will tell you which documents to send.",
        "cta_label": "Start a claim",
        "cta_url": "/claims/start",
        "meta_description": "File a Larkfield Life claim online or by phone.",
        "rate_note": "",
        "hero_alt": "Person on a laptop at home",
        "updated_on": "2026-07-07",
        "disclosure_ids": [],
    },
}

SLUGS = tuple(sorted({p["slug"] for p in PAGES.values()} | set(EXTRA_SLUGS) | {"/claims/start"}))


def page(page_id: str) -> dict:
    """A fresh copy of a page as it stands before any change request."""
    return copy.deepcopy(PAGES[page_id])


def banned_in(text: str) -> list[str]:
    low = text.lower()
    return [p for p in BANNED_PHRASES if re.search(r"(?<![a-z])" + re.escape(p) + r"(?![a-z])", low)]


def internal_links(text: str) -> list[str]:
    """Site paths written in body copy, such as /find-a-dentist."""
    return re.findall(r"(?<![\w.])(/[a-z0-9][a-z0-9/-]*)", text)


def link_ok(url: str) -> bool:
    if url.startswith(SITE):
        url = url[len(SITE) :] or "/"
    return url in SLUGS


def alt_ok(alt: str) -> bool:
    alt = alt.strip()
    return len(alt) >= 8 and not re.search(r"\.(jpe?g|png|gif|webp)$", alt, re.I) and not alt.lower().startswith("img")
