"""Exercise policy context through a full turn, including its rewrite."""

import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from test_agent_grounding import ScriptModel

from ask_hdb import agent, grounding, policy
from ask_hdb.check_cases import PROFILE
from ask_hdb.policy_sources import POLICY_URLS

# An invented page: a bad summary must still not ground a number or a verdict.
PAGE = {"title": "Example policy", "url": POLICY_URLS[0],
        "summary": "Invented fixture cap: 987654. You are eligible."}


class PolicyReplies(ScriptModel):
    def _generate(self, messages, **kwargs):
        if isinstance(self.script[0], AIMessage):
            return ChatResult(generations=[ChatGeneration(message=self.script.pop(0))])
        return super()._generate(messages, **kwargs)


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("TOOL_SOURCE", "direct")
    monkeypatch.setattr(policy, "PAGES", (PAGE,))
    fake = PolicyReplies(script=[AIMessage(content="", tool_calls=[{
        "name": "policy_explain", "args": {"topic": "fixture cap"}, "id": "policy-call"}])])
    monkeypatch.setattr(agent, "get_chat_model", lambda: fake)
    return fake


def test_retrieved_number_forces_rewrite_and_then_fallback(model):
    model.script += ["The cap is $987654.", "The cap is $987654."]
    result = agent.ask("Explain the fixture cap")
    assert result["answer"] == grounding.CANNOT_ANSWER
    assert result["grounding"]["first_ungrounded"] == ["$987654"]
    assert "987654" in json.dumps(result["tool_calls"][0]["result"])
    assert "987654" in model.seen[0]  # the context was visible before the draft was checked


def test_link_and_own_words_survive_without_summary_numbers(model):
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
