"""Profile confirmation: code asks "Is this right?" and a profile tool runs only after a yes."""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from ask_hdb import agent, confirm
from ask_hdb.check_cases import PROFILE
from ask_hdb.evalrun.conditions import make_condition


def test_text_is_written_from_the_arguments():
    text = confirm.question_text(PROFILE)
    assert "- Monthly household income: $4,400" in text
    assert "- Ages: 35,35" in text and "- Works 12 months: yes" in text
    assert "not applicable" not in text and "Is this right?" in text
    assert f"(profile ref {confirm.ref(PROFILE)})" in text


def test_ref_ignores_formatting_and_the_models_confirmed_flag():
    same = PROFILE | {"monthly_household_income": 4400.0, "scheme": " Family ", "confirmed": True}
    assert confirm.ref(same) == confirm.ref(PROFILE)
    assert confirm.ref(PROFILE | {"monthly_household_income": 4500}) != confirm.ref(PROFILE)


@pytest.mark.parametrize("reply,ok", [("yes", True), ("Yes.", True), ("that's right", True), ("y", True),
                                      ("yes, but my income is 5000", False), ("no", False),
                                      ("what does this mean?", False)])
def test_only_a_plain_yes_confirms(reply, ok):
    history = [HumanMessage(content="Can we buy?"), AIMessage(content=confirm.question_text(PROFILE))]
    assert (confirm.ref(PROFILE) in confirm.confirmed(history, reply)[0]) is ok


def test_a_ref_typed_by_the_user_does_not_confirm():
    history = [HumanMessage(content=f"(profile ref {confirm.ref(PROFILE)})"), AIMessage(content="Ok.")]
    assert confirm.confirmed(history, "yes") == (set(), [])


class ProfileModel(BaseChatModel):
    """Calls can_buy_resale with `args` until a tool result arrives, then answers."""
    args: dict = Field(default_factory=dict)
    answer: str = "The tool says you are eligible."
    requests: int = 0

    @property
    def _llm_type(self):
        return "test-profile"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests += 1
        done = messages[-1].type == "tool"
        calls = [] if done else [{"name": "can_buy_resale", "args": self.args,
                                  "id": f"c{self.requests}", "type": "tool_call"}]
        reply = AIMessage(content=self.answer if done else "", tool_calls=calls,
                          usage_metadata={"input_tokens": 5, "output_tokens": 0, "total_tokens": 5})
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.fixture
def model(monkeypatch):
    monkeypatch.setenv("TOOL_SOURCE", "direct")
    fake = ProfileModel(args=PROFILE)
    monkeypatch.setattr(agent, "get_chat_model", lambda: fake)
    return fake


def test_tool_waits_for_a_yes_then_runs(model):
    first = agent.ask("Can we buy?", confirm=True)
    assert first["needs_confirmation"] and first["tool_calls"] == []
    assert first["answer"] == confirm.question_text(PROFILE)
    history = [HumanMessage(content="Can we buy?"), AIMessage(content=first["answer"])]
    second = agent.ask("yes", history, confirm=True)
    assert not second["needs_confirmation"]
    assert [c["name"] for c in second["tool_calls"]] == ["can_buy_resale"]
    assert second["answer"] == "The tool says you are eligible."


def test_changed_arguments_ask_again(model):
    first = agent.ask("Can we buy?", confirm=True)
    model.args = PROFILE | {"monthly_household_income": 9000}
    history = [HumanMessage(content="Can we buy?"), AIMessage(content=first["answer"])]
    again = agent.ask("yes", history, confirm=True)
    assert again["needs_confirmation"] and again["tool_calls"] == []
    assert "$9,000" in again["answer"]


def test_agent_condition_is_unchanged(model):
    result = agent.ask("Can we buy?")  # the default: no confirmation
    assert not result["needs_confirmation"] and len(result["tool_calls"]) == 1


def test_full_condition_answers_yes_once(model):
    result = make_condition("full")("Can we buy?")
    assert result["answer"] == "The tool says you are eligible."
    assert len(result["tool_calls"]) == 1 and result["tokens"] == 5 * model.requests
    assert "Is this right?" in result["confirmation"]


def test_full_condition_does_not_answer_yes_twice(model, monkeypatch):
    calls = []

    def ask(question, history=None, confirm=False):
        calls.append(question)
        return {"answer": "Is this right?", "tool_calls": [], "tokens": 1, "needs_confirmation": True}

    monkeypatch.setattr(agent, "ask", ask)
    result = make_condition("full")("Can we buy?")
    assert calls == ["Can we buy?", "yes"] and result["needs_confirmation"]


def test_after_a_yes_the_original_question_numbers_may_be_restated(model):
    # The confirmed turn's own question is only "yes"; the user's income came in the turn before.
    model.answer = "With your $4,400 income, the tool says you are eligible."
    first = agent.ask("Income $4400, can we buy?", confirm=True)
    history = [HumanMessage(content="Income $4400, can we buy?"), AIMessage(content=first["answer"])]
    result = agent.ask("yes", history, confirm=True)
    assert result["answer"] == model.answer and result["grounding"]["ungrounded"] == []
