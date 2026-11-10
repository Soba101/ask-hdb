"""Policy links: fixed official pages, and a strict boundary with numeric evidence."""

from decimal import Decimal

import pytest

from ask_hdb import grounding, policy, tools
from ask_hdb.policy_sources import POLICY_URLS


def test_pages_are_the_allowlist_and_hold_no_numbers():
    assert [page["url"] for page in policy.PAGES] == list(POLICY_URLS)
    assert all(set(page) == {"url", "title", "summary"} for page in policy.PAGES)
    # Summaries are written for this project: no rule values may hide in them.
    assert not any(ch.isdigit() for page in policy.PAGES for ch in page["title"] + page["summary"])
    assert tools.policy_explain in tools.TOOLS


@pytest.mark.parametrize("topic,url", [
    ("Enhanced CPF Housing Grant for a single buyer", POLICY_URLS[6]),
    ("proximity grant to live near my parents, we are a married couple", POLICY_URLS[3]),
    ("HDB loan interest rate", POLICY_URLS[9]),
    ("how much can I borrow with an HDB housing loan", POLICY_URLS[8]),
])
def test_search_finds_the_right_page(topic, url, monkeypatch):
    monkeypatch.setattr(tools, "load_sales", lambda: pytest.fail("Policy search must not read sales"))
    result = tools.policy_explain.invoke({"topic": topic})
    assert result["tool"] == "policy_explain"
    assert result["pages"][0]["url"] == url
    assert len(result["pages"]) <= 3
    assert result == tools.policy_explain.invoke({"topic": topic})


def test_unrelated_topic_finds_nothing():
    assert tools.policy_explain.invoke({"topic": "unrelatedword"})["pages"] == []


@pytest.mark.parametrize("field,value,answer", [
    ("summary", "987654", "$987,654"),
    ("summary", "The cap is 987654 on 2026-11-10.", "$987,654 on 10 Nov 2026"),
    ("title", "987654", "$987,654"),
    ("url", "https://www.hdb.gov.sg/987654/2026-11-10", "$987,654 on 10 Nov 2026"),
])
def test_no_part_of_policy_result_grounds_numbers_or_dates(field, value, answer):
    result = {"tool": "policy_explain", "pages": [{field: value}]}
    assert grounding.evidence([result]) == (set(), set())
    assert grounding.check(answer, "Explain the rule", [result])["ungrounded"]
    assert grounding.evidence([result, {"amount": 70000}])[0] == {Decimal(70000)}


def test_name_alone_excludes_unmarked_results_and_place_labels():
    calls = [{"name": "policy_explain", "result": {"amount": 987654}},
             {"name": "ehg_amount", "result": {"amount": 70000}}]
    assert grounding.evidence(grounding.tool_results(calls))[0] == {Decimal(70000)}
    result = {"tool": "policy_explain", "label": "The grant is $987654"}
    assert grounding.check("The grant is $987654", "Explain", [result])["ungrounded"] == ["$987654"]
