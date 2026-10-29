"""Provider choices need no server or API credentials in tests."""

import pytest

from ask_hdb import llm


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    for name in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY", "LLM_CHAIN", "GEMINI_API_KEY", "GEMINI_MODEL",
                 "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(llm, "ChatOpenAI", lambda **kwargs: ("openai", kwargs))
    monkeypatch.setattr(llm, "ChatAnthropic", lambda **kwargs: ("anthropic", kwargs))


def test_local_defaults():
    provider, options = llm.get_chat_model()
    assert provider == "openai"
    assert options["model"] == "qwen3.5-9b-16k"
    assert options["base_url"] == "http://localhost:11434/v1"
    assert options["api_key"] == "none"
    assert options["temperature"] == 0


@pytest.mark.parametrize("provider", ["local", "openai", "anthropic"])
def test_provider_switch(monkeypatch, provider, capsys):
    for name, value in {"PROVIDER": provider, "MODEL": "test-model",
                        "BASE_URL": "http://localhost:8000/v1", "API_KEY": "secret-test-key"}.items():
        monkeypatch.setenv(f"LLM_{name}", value)
    selected, options = llm.get_chat_model()
    assert selected == ("openai" if provider == "local" else provider)
    assert options["model"] == "test-model"
    assert options["base_url"] == "http://localhost:8000/v1"
    assert options["api_key"] == "secret-test-key"
    assert options["temperature"] == 0
    assert not capsys.readouterr().out


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_cloud_uses_provider_default_url(monkeypatch, provider):
    monkeypatch.setenv("LLM_PROVIDER", provider)
    _, options = llm.get_chat_model()
    assert "base_url" not in options
    assert "api_key" not in options


def test_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "unsupported")
    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        llm.get_chat_model()


def test_the_anthropic_prompt_is_marked_cacheable_and_other_providers_get_plain_text(monkeypatch):
    from ask_hdb import agent
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    block = agent._system_prompt().content[0]
    assert block["text"] == agent.SYSTEM_PROMPT and block["cache_control"] == {"type": "ephemeral"}
    monkeypatch.setenv("LLM_PROVIDER", "local")
    assert agent._system_prompt() == agent.SYSTEM_PROMPT


def test_chain_order_defaults_and_skipping_providers_without_a_key(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini, groq, local")
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    chain = llm.get_chat_model()  # no GROQ key: skipped
    assert isinstance(chain, llm.Chain) and len(chain.models) == 2
    gemini, local = chain.models
    assert gemini[1]["model"] == "gemini-3.5-flash" and "generativelanguage" in gemini[1]["base_url"]
    assert local[1]["base_url"] == "http://localhost:11434/v1"
    monkeypatch.setenv("LLM_CHAIN", "gemini:gemini-3.5-flash-lite")
    assert llm.get_chat_model()[1]["model"] == "gemini-3.5-flash-lite"  # a single provider is returned as it is


def test_chain_needs_a_usable_provider_and_known_names(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini")
    with pytest.raises(ValueError, match="no usable provider"):
        llm.get_chat_model()
    monkeypatch.setenv("LLM_CHAIN", "nope")
    with pytest.raises(ValueError, match="LLM_CHAIN entry"):
        llm.get_chat_model()


class Fake:
    def __init__(self, behaviour):
        self.behaviour, self.seen = behaviour, []

    def bind_tools(self, tools):
        return self.bind(tools=tools)

    def bind(self, **kwargs):
        from langchain_core.runnables import RunnableLambda

        def call(value):
            self.seen.append(kwargs)
            if isinstance(self.behaviour, Exception):
                raise self.behaviour
            return self.behaviour
        return RunnableLambda(call)


def test_a_rate_limit_or_timeout_moves_to_the_next_provider_and_a_bug_does_not():
    import httpx
    import openai
    request = httpx.Request("POST", "https://example.test")
    limited = openai.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    first, second = Fake(limited), Fake("from the second")
    chain = llm.Chain([first, second])
    assert chain.bind_tools(["tool"]).invoke("q") == "from the second"
    assert chain.bind(max_tokens=50).invoke("q") == "from the second" and second.seen[-1] == {"max_tokens": 50}
    timed_out = Fake(openai.APITimeoutError(request=request))
    assert llm.Chain([timed_out, Fake("ok")]).bind().invoke("q") == "ok"
    with pytest.raises(ZeroDivisionError):  # a programming error is not hidden by a fallback
        llm.Chain([Fake(ZeroDivisionError()), Fake("ok")]).bind().invoke("q")
