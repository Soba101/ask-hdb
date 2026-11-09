"""Offline retrieval and its strict boundary with numeric evidence."""

from decimal import Decimal

import pandas as pd
import pytest

from ask_hdb import grounding, policy, tools
from ask_hdb.policy_sources import POLICY_URLS


@pytest.fixture
def passages(tmp_path, monkeypatch):
    path = tmp_path / "policy_passages.parquet"
    monkeypatch.setattr(policy, "PASSAGES_PATH", path)
    rows = [{"url": POLICY_URLS[i], "title": title, "fetched_at": "2026-11-10T00:00:00+00:00",
             "passage": text} for i, (title, text) in enumerate([
                 ("Family purchase", "Family citizenship and household details."),
                 ("Housing grants", "Housing grants support a household purchase."),
                 ("Enhanced CPF Housing Grant", "Enhanced CPF Housing Grant income work history."),
                 ("Proximity Housing Grant", "Proximity support for living with parents."),
             ])]
    pd.DataFrame(rows).to_parquet(path, index=False)
    yield rows
    policy._load_index.cache_clear()


def test_retrieval_returns_relevant_top_three_and_metadata(passages, monkeypatch):
    monkeypatch.setattr(tools, "load_sales", lambda: pytest.fail("Policy search must not read sales"))
    result = tools.policy_explain.invoke({"topic": "Enhanced CPF Housing Grant support household"})
    assert result["tool"] == "policy_explain"
    assert len(result["passages"]) == 3
    assert result["passages"][0] == passages[2]
    assert result == tools.policy_explain.invoke({"topic": "Enhanced CPF Housing Grant support household"})
    assert all(set(row) == {"url", "title", "fetched_at", "passage"} for row in result["passages"])
    assert tools.policy_explain.invoke({"topic": "unrelatedword"})["passages"] == []


def test_missing_pages_is_clear_and_does_not_load_sales(tmp_path, monkeypatch):
    monkeypatch.setattr(policy, "PASSAGES_PATH", tmp_path / "absent.parquet")
    monkeypatch.setattr(tools, "load_sales", lambda: pytest.fail("No sales load"))
    result = tools.policy_explain.invoke({"topic": "grant"})
    assert "policy pages not built" in result["error"]
    assert result["passages"] == []


def test_invalid_source_in_local_index_is_rejected(passages):
    passages[0]["url"] = "https://evil.test/page"
    pd.DataFrame(passages).to_parquet(policy.PASSAGES_PATH)
    assert "error" in tools.policy_explain.invoke({"topic": "grant"})


@pytest.mark.parametrize("field,value,answer", [
    ("passage", "987654", "$987,654"),
    ("passage", "The cap is 987654 on 2026-11-10.", "$987,654 on 10 Nov 2026"),
    ("title", "987654", "$987,654"),
    ("url", "https://www.hdb.gov.sg/987654/2026-11-10", "$987,654 on 10 Nov 2026"),
    ("fetched_at", "2026-11-10", "10 Nov 2026"),
])
def test_no_part_of_policy_result_grounds_numbers_or_dates(field, value, answer):
    result = {"tool": "policy_explain", "passages": [{field: value}]}
    assert grounding.evidence([result]) == (set(), set())
    assert grounding.check(answer, "Explain the rule", [result])["ungrounded"]
    assert grounding.evidence([result, {"amount": 70000}])[0] == {Decimal(70000)}


def test_name_alone_excludes_unmarked_results_and_place_labels():
    calls = [{"name": "policy_explain", "result": {"amount": 987654}},
             {"name": "ehg_amount", "result": {"amount": 70000}}]
    assert grounding.evidence(grounding.tool_results(calls))[0] == {Decimal(70000)}
    result = {"tool": "policy_explain", "label": "The grant is $987654"}
    assert grounding.check("The grant is $987654", "Explain", [result])["ungrounded"] == ["$987654"]
