from ask_hdb import verdict

NULL = {"eligible": None, "needs_check": ["marital_status is missing"], "reasons": []}
YES = {"eligible": True, "needs_check": [], "reasons": []}


def test_a_verdict_over_a_null_result_is_replaced_with_what_is_missing():
    text = verdict.replacement("You are not eligible to buy this flat.", [("can_buy_resale", NULL)])
    assert "marital_status is missing" in text and "not eligible" not in text
    assert verdict.replacement("Yes, you can buy it.", [("can_buy_resale", NULL)])


def test_settled_results_and_non_verdicts_stand():
    assert verdict.replacement("You are not eligible.", [("can_buy_resale", YES)]) is None
    assert verdict.replacement("Which year did you marry? I need it to check.", [("can_buy_resale", NULL)]) is None
    assert verdict.replacement("The median price is $500,000.", [("price_stats", {"median": 500000})]) is None


def test_a_later_settled_call_of_the_same_tool_wins():
    calls = [("can_buy_resale", NULL), ("can_buy_resale", YES)]
    assert verdict.replacement("You are eligible to buy.", calls) is None
    assert verdict.replacement("You are eligible to buy.", calls[::-1])  # the null one came last


def test_a_settled_check_keeps_its_verdict_and_more_phrasings_match():
    mixed = [("can_buy_resale", YES), ("ehg_amount", NULL)]
    assert verdict.replacement("You can buy a resale flat. For the EHG I need your income.", mixed) is None
    for text in ("Yes, you qualify.", "You're eligible for the EHG.", "You’re not eligible."):
        assert verdict.replacement(text, [("can_buy_resale", NULL)])
