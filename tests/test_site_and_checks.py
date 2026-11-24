from pagechange import compliance, site


def test_every_page_carries_its_required_disclosures_and_a_short_meta():
    for pid, p in site.PAGES.items():
        assert set(site.REQUIRED_DISCLOSURES[p["page_type"]]) <= set(p["disclosure_ids"]), pid
        assert len(p["meta_description"]) <= site.META_MAX, pid
        assert not any(site.banned_in(p[k]) for k in site.TEXT_FIELDS), pid


def test_banned_phrases_match_whole_phrases_only():
    assert site.banned_in("Guaranteed returns with zero risk") == ["guaranteed returns", "zero risk"]
    assert site.banned_in("No risky business") == []
    assert site.banned_in("the cheapest plan") == ["cheapest"]


def test_links_and_alt_text():
    assert site.link_ok("/find-a-dentist") and site.link_ok("https://larkfieldlife.example/claims")
    assert not site.link_ok("/contact-advisor")
    assert not site.alt_ok("IMG_4471.jpg") and not site.alt_ok("") and site.alt_ok("Child trying on glasses")


def _after(pid, **changes):
    before = site.page(pid)
    return before, {**before, **changes}


def test_blocking_checks():
    before, after = _after("annuities", headline="Guaranteed returns with zero risk")
    assert [f.id for f in compliance.blocking_failures(compliance.check("annuities", before, after))] == [
        "no_banned_claims"
    ]
    before, after = _after("term-life", disclosure_ids=["D-GEN"])
    ids = [f.id for f in compliance.blocking_failures(compliance.check("term-life", before, after))]
    assert ids == ["read_only_untouched", "disclosures_kept"]
    before, after = _after("term-life", rate_note="Example: $12 a month")
    assert [f.id for f in compliance.blocking_failures(compliance.check("term-life", before, after))] == [
        "rate_unchanged"
    ]


def test_existing_broken_link_is_not_this_edits_fault_but_a_new_one_is():
    before, after = _after("annuities", headline="Income for retirement")
    assert all(f.ok for f in compliance.check("annuities", before, after))
    before, after = _after("dental", body=site.PAGES["dental"]["body"] + " See /dentist-finder.")
    bad = [f for f in compliance.check("dental", before, after) if not f.ok]
    assert [f.id for f in bad] == ["links_work"] and "/dentist-finder" in bad[0].detail


def test_meta_and_alt_checks():
    before, after = _after("dental", meta_description="x" * 161, hero_alt="IMG_1.png")
    bad = {f.id for f in compliance.check("dental", before, after) if not f.ok}
    assert bad == {"meta_length", "alt_text"}
