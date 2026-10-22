"""The agent checks its answer's numbers, asks for one rewrite, then gives up honestly."""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from ask_hdb import agent, grounding

CALL = object()  # a scripted reply that calls price_stats for Tampines (6 sales)


class ScriptModel(BaseChatModel):
    script: list = Field(default_factory=list)
    seen: list = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "test-script"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(messages[-1].content)
        step = self.script.pop(0)
        calls = [{"name": "price_stats", "args": {"town": "TAMPINES"},
                  "id": f"call-{len(self.seen)}", "type": "tool_call"}] if step is CALL else []
        reply = AIMessage(content="" if step is CALL else step, tool_calls=calls, usage_metadata={
            "input_tokens": 10, "output_tokens": 0, "total_tokens": 10})
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.fixture
def model(monkeypatch, sales):
    monkeypatch.setenv("TOOL_SOURCE", "direct")
    monkeypatch.setattr("ask_hdb.tools.load_sales", lambda: sales)
    fake = ScriptModel()
    monkeypatch.setattr(agent, "get_chat_model", lambda: fake)
    return fake


def test_grounded_answer_is_kept(model):
    model.script = [CALL, "Tampines had 6 sales."]
    result = agent.ask("How many Tampines sales?")
    assert result["answer"] == "Tampines had 6 sales."
    assert result["grounding"]["rewritten"] is False
    assert model.script == []  # no rewrite request was made


def test_one_rewrite_fixes_the_answer(model):
    model.script = [CALL, "6 sales, median $999,999.", "Tampines had 6 sales."]
    result = agent.ask("How many Tampines sales?")
    assert result["answer"] == "Tampines had 6 sales."
    assert result["grounding"]["first_ungrounded"] == ["$999,999"]
    assert result["grounding"]["replaced"] is False
    assert "$999,999" in model.seen[-1]  # the rewrite request names the bad number


def test_second_failure_gives_honest_answer(model):
    model.script = [CALL, "Median $999,999.", "Median $888,888."]
    result = agent.ask("Median in Tampines?")
    assert result["answer"] == grounding.CANNOT_ANSWER
    assert result["grounding"]["replaced"] is True
    assert result["stopped_reason"] is None
    assert len(model.seen) == 3  # exactly one rewrite, never a second


def test_rewrite_may_call_a_tool(model):
    model.script = ["There were 6 sales.", CALL, "Tampines had 6 sales."]
    result = agent.ask("How many Tampines sales?")
    assert result["answer"] == "Tampines had 6 sales."
    assert len(result["tool_calls"]) == 1


def test_empty_rewrite_is_not_an_answer(model):
    model.script = ["Median $999,999.", ""]
    assert agent.ask("Median?")["answer"] == grounding.CANNOT_ANSWER


def test_decline_without_numbers_is_kept(model):
    model.script = ["I cannot predict future prices; I only help with resale and BTO questions."]
    result = agent.ask("Will prices rise in 5 years?")
    assert result["answer"].startswith("I cannot predict")
    assert result["tool_calls"] == [] and len(model.seen) == 1


def test_question_numbers_may_be_restated(model):
    model.script = ["For your $600,000 flat I need your age before checking."]
    result = agent.ask("Is $600000 ok for a 4-room?")
    assert result["grounding"]["ungrounded"] == []
    assert len(model.seen) == 1


def test_limit_during_rewrite_keeps_grounding_keys(model, monkeypatch):
    monkeypatch.setattr(agent, "MAX_TOOL_CALLS", 1)
    model.script = [CALL, "Median $999,999.", CALL]  # the rewrite asks for a tool past the cap
    result = agent.ask("Median in Tampines?")
    assert result["stopped_reason"] == "tool_calls"
    assert result["grounding"]["rewritten"] is True and result["grounding"]["replaced"] is False
    assert result["grounding"]["first_ungrounded"] == ["$999,999"]


# q_refuse_005 (held-out, week 5): a no-tool request for details mentioned a rule number ("12").
ASKS = "Please provide your age and citizenship. Have you worked for the past 12 months?"


def test_clarification_rewrite_asks_for_details_without_numbers(model):
    model.script = [ASKS, "Please provide your age, citizenship and work history."]
    result = agent.ask("Can I buy a resale flat? Ask me for the missing details.")
    assert result["answer"] == "Please provide your age, citizenship and work history."
    assert "state no numbers" in model.seen[-1]  # the rewrite request is the clarification one


def test_clarification_is_kept_not_replaced(model):
    model.script = [ASKS, ASKS]
    result = agent.ask("Can I buy a resale flat? Ask me for the missing details.")
    assert result["answer"] == ASKS
    assert result["grounding"]["ungrounded"] == ["12"]  # still reported, never hidden
    assert result["grounding"]["kept_clarification"] is True and result["grounding"]["replaced"] is False


@pytest.mark.parametrize("draft", [
    "You need 12 months of work.",                       # a fact, not a question
    "You are not eligible below 35. What is your age?",  # a verdict
    "Is your income above $4,000?",                      # a money amount
    "Is the ceiling 14000 for you? Please provide your age.",  # a large number
    # A decline that ends with an offer must not be rewritten into a request for details (q_refuse_008: "95").
    "I cannot advise on loans; 95 of 100 buyers differ. Please provide a block ID for past sales.",
])
def test_facts_verdicts_and_amounts_are_still_replaced(model, draft):
    model.script = [draft, draft]
    assert agent.ask("Can I buy?")["answer"] == grounding.CANNOT_ANSWER


def test_clarification_after_a_tool_call_is_still_replaced(model):
    model.script = [CALL, ASKS, ASKS]
    assert agent.ask("How many Tampines sales?")["answer"] == grounding.CANNOT_ANSWER
