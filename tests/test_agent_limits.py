"""Run the real graph with a fake chat model and deterministic tools."""

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from ask_hdb import agent


class LoopModel(BaseChatModel):
    batch: int = 1
    requests: int = 0
    usage: int = 10
    finish: bool = False
    finish_after: int = 0
    truncated: bool = False
    omit_usage: bool = False
    caps: list[int] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "test-loop"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests += 1
        self.caps.append(kwargs["max_tokens"])
        done = self.finish or (self.finish_after and self.requests > self.finish_after)
        calls = [] if done else [
            {"name": "price_stats", "args": {"town": "TAMPINES"},
             "id": f"call-{self.requests}-{index}", "type": "tool_call"}
            for index in range(self.batch)
        ]
        reply = AIMessage(content="Please provide the missing inputs." if done else "",
                          tool_calls=calls, usage_metadata=None if self.omit_usage else {
                              "input_tokens": self.usage, "output_tokens": 0,
                              "total_tokens": self.usage,
                          }, response_metadata={"finish_reason": "length"}
                          if self.truncated else {})
        return ChatResult(generations=[ChatGeneration(message=reply)])


@pytest.fixture(autouse=True, params=["direct", "mcp"])
def fake_sales(monkeypatch, sales, memory_mcp, request):
    monkeypatch.setenv("TOOL_SOURCE", request.param)
    monkeypatch.setattr("ask_hdb.tools.load_sales", lambda: sales)


@pytest.mark.parametrize("batch", [1, 3, 20])
def test_tool_call_cap(monkeypatch, batch):
    model = LoopModel(batch=batch)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    result = agent.ask("Keep querying sales")
    assert len(result["tool_calls"]) == agent.MAX_TOOL_CALLS
    assert result["stopped_reason"] == "tool_calls"
    assert result["answer"].startswith("stopped: limit")
    assert all(call["result"]["n_sales"] == 6 for call in result["tool_calls"])
    assert result["tokens"] == model.requests * model.usage


def test_token_limit_before_request(monkeypatch):
    model = LoopModel()
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    monkeypatch.setattr(agent, "TOKEN_BUDGET", 1)
    result = agent.ask("Query prices")
    assert result["stopped_reason"] == "tokens"
    assert model.requests == 0
    assert result["tool_calls"] == []


def test_token_limit_after_response(monkeypatch):
    model = LoopModel(usage=agent.TOKEN_BUDGET)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    result = agent.ask("Query prices")
    assert result["stopped_reason"] == "tokens"
    assert model.requests == 1
    assert result["tokens"] == agent.TOKEN_BUDGET
    assert result["tool_calls"] == []


def test_missing_usage_still_has_budget(monkeypatch):
    model = LoopModel(omit_usage=True)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    result = agent.ask("Query prices")
    assert result["tokens"] > 0
    assert result["stopped_reason"] in {"tokens", "tool_calls"}
    assert model.requests <= agent.MAX_TOOL_CALLS + 1


def test_truncated_response_stops_before_tools(monkeypatch):
    model = LoopModel(truncated=True)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    result = agent.ask("Query prices")
    assert result["stopped_reason"] == "tokens"
    assert result["tool_calls"] == []
    assert 0 < model.caps[0] < agent.TOKEN_BUDGET


def test_normal_answer_and_fresh_limits(monkeypatch):
    model = LoopModel(finish=True)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    for _ in range(2):
        result = agent.ask("Can you help?", [HumanMessage(content="Earlier question")])
        assert result["answer"] == "Please provide the missing inputs."
        assert result["stopped_reason"] is None
        assert result["tokens"] == model.usage
        assert result["tool_calls"] == []


def test_dict_history(monkeypatch):
    model = LoopModel(finish=True)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    result = agent.ask("Can you help?", [{"role": "user", "content": "Earlier question"}])
    assert result["stopped_reason"] is None


def test_realistic_usage_reaches_the_tool_cap(monkeypatch):
    # Real usage is about 4 bytes per token; bytes must not stop the agent early.
    model = LoopModel(usage=3500)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    result = agent.ask("Keep querying sales")
    assert len(result["tool_calls"]) == agent.MAX_TOOL_CALLS


def test_model_may_answer_after_last_tool_call(monkeypatch):
    model = LoopModel(finish_after=agent.MAX_TOOL_CALLS)
    monkeypatch.setattr(agent, "get_chat_model", lambda: model)
    result = agent.ask("Query prices")
    assert result["stopped_reason"] is None
    assert len(result["tool_calls"]) == agent.MAX_TOOL_CALLS
    assert result["answer"] == "Please provide the missing inputs."
