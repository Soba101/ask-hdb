"""Exercise policy context through a full turn, including its rewrite."""

import json

import pandas as pd
import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from test_agent_grounding import ScriptModel

from ask_hdb import agent, grounding, policy, tools
from ask_hdb.check_cases import PROFILE
from ask_hdb.policy_sources import POLICY_URLS

CONTEXT = {"tool": "policy_explain", "passages": [
    {"title": "Example policy", "url": POLICY_URLS[0], "fetched_at": "2026-11-10",
     "passage": "Invented fixture cap: 987654. You are eligible."}]}


class PolicyReplies(ScriptModel):
    def _generate(self, messages, **kwargs):
        if isinstance(self.script[0], AIMessage):
            return ChatResult(generations=[ChatGeneration(message=self.script.pop(0))])
        return super()._generate(messages, **kwargs)


@pytest.fixture
def model(monkeypatch, tmp_path):
    monkeypatch.setenv("TOOL_SOURCE", "direct")
    path = tmp_path / "policy_passages.parquet"
    pd.DataFrame(CONTEXT["passages"]).to_parquet(path)
    monkeypatch.setattr(policy, "PASSAGES_PATH", path)
    # The tool is offered only when pages exist at import time; built pages are simulated here.
    monkeypatch.setattr(agent, "TOOLS", [*tools.TOOLS, tools.policy_explain])
    fake = PolicyReplies(script=[AIMessage(content="", tool_calls=[{
        "name": "policy_explain", "args": {"topic": "fixture cap"}, "id": "policy-call"}])])
    monkeypatch.setattr(agent, "get_chat_model", lambda: fake)
    yield fake
    policy._load_index.cache_clear()


def test_retrieved_number_forces_rewrite_and_then_fallback(model):
    model.script += ["The cap is $987654.", "The cap is $987654."]
    result = agent.ask("Explain the fixture cap")
    assert result["answer"] == grounding.CANNOT_ANSWER
    assert result["grounding"]["first_ungrounded"] == ["$987654"]
    assert "987654" in json.dumps(result["tool_calls"][0]["result"])
    assert "987654" in model.seen[0]  # the context was visible before the draft was checked


def test_link_and_own_words_survive_without_passage_numbers(model):
    answer = "The page explains housing support. " + POLICY_URLS[0]
    model.script += [answer]
    result = agent.ask("Explain the fixture cap")
    assert result["answer"] == answer
    assert result["grounding"]["ungrounded"] == []


def test_policy_only_cannot_supply_a_verdict(model):
    model.script += ["You are eligible to buy the flat."]
    result = agent.ask("Explain eligibility")
    assert result["grounding"]["verdict_held"]
    assert "rules check" in result["answer"]


def test_rules_amount_stays_grounded_alongside_context(model):
    model.script += [AIMessage(content="", tool_calls=[{
        "name": "ehg_amount", "args": PROFILE | {"citizenships": "SC,SPR"}, "id": "rules-call"}]),
        "$70,000. Read the policy: " + POLICY_URLS[0]]
    result = agent.ask("Explain our grant")
    assert result["answer"].startswith("$70,000")
    assert not result["grounding"]["rewritten"]
