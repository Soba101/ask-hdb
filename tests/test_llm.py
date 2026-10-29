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
    monkeypatch.setattr(llm, "ChatGoogleGenerativeAI", lambda **kwargs: ("google", kwargs))
    monkeypatch.setenv("LLM_CHAIN", "gemini, groq, local, openrouter")
    monkeypatch.setenv("GEMINI_API_KEY", "g-test")
    monkeypatch.setenv("OPENROUTER", "or-test")  # the key variable name used in the owner's .env
    chain = llm.get_chat_model()  # no GROQ key: skipped
    kinds = [member.model[0] for member in chain.members]
    assert kinds == ["google", "openai", "openai"]
    gemini, local, router = (member.model[1] for member in chain.members)
    assert gemini["model"] == "gemini-3.5-flash-lite" and local["base_url"] == "http://localhost:11434/v1"
    assert router["base_url"] == "https://openrouter.ai/api/v1" and router["model"] == "openrouter/free"
    monkeypatch.setenv("LLM_CHAIN", "gemini:gemini-3.5-flash")
    assert llm.get_chat_model().members[0].model[1]["model"] == "gemini-3.5-flash"


def test_chain_needs_a_usable_provider_and_known_names(monkeypatch):
    monkeypatch.setenv("LLM_CHAIN", "gemini")
    with pytest.raises(ValueError, match="no usable provider"):
        llm.get_chat_model()
    monkeypatch.setenv("LLM_CHAIN", "nope")
    with pytest.raises(ValueError, match="LLM_CHAIN entry"):
        llm.get_chat_model()


class Fake:
    def __init__(self, behaviour):
        self.behaviour, self.calls = behaviour, []

    def bind_tools(self, tools):
        return self

    def invoke(self, messages, config=None, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


def test_errors_move_to_the_next_provider_and_settings_use_each_clients_names():
    import httpx
    import openai
    request = httpx.Request("POST", "https://example.test")
    limited = openai.RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    first, second = Fake(limited), Fake("from the second")
    chain = llm.Chain([llm.Member(first), llm.Member(second, {"max_tokens": "max_output_tokens"})])
    assert chain.bind_tools(["tool"]).bind(max_tokens=50).invoke("q") == "from the second"
    assert first.calls == [{"max_tokens": 50}] and second.calls == [{"max_output_tokens": 50}]
    assert llm.Chain([llm.Member(Fake(openai.APITimeoutError(request=request))), llm.Member(Fake("ok"))]).bind().invoke("q") == "ok"
    google = llm.ChatGoogleGenerativeAIError("quota")
    assert llm.Chain([llm.Member(Fake(google)), llm.Member(Fake("ok"))]).bind().invoke("q") == "ok"
    outage = ValueError({"message": "Upstream error from Nvidia: overloaded", "code": 503})
    assert llm.Chain([llm.Member(Fake(outage)), llm.Member(Fake("ok"))]).bind().invoke("q") == "ok"
    with pytest.raises(ValueError, match="plain"):  # an ordinary ValueError is a bug, not an outage
        llm.Chain([llm.Member(Fake(ValueError("plain"))), llm.Member(Fake("ok"))]).bind().invoke("q")
    with pytest.raises(ZeroDivisionError):  # a programming error is not hidden by a fallback
        llm.Chain([llm.Member(Fake(ZeroDivisionError())), llm.Member(Fake("ok"))]).bind().invoke("q")
    with pytest.raises(openai.RateLimitError):  # when every provider fails, the last error is raised
        llm.Chain([llm.Member(Fake(limited))]).bind().invoke("q")


def test_a_used_up_minute_skips_to_the_next_provider_and_a_sole_provider_waits(monkeypatch):
    slow = llm.Member(Fake("from slow"), rpm=2)
    other = llm.Member(Fake("from other"))
    chain = llm.Chain([slow, other])
    assert [chain.bind().invoke("q") for _ in range(3)] == ["from slow", "from slow", "from other"]
    assert 0 < slow.wait() <= 60
    slept = []
    monkeypatch.setattr(llm.time, "sleep", slept.append)
    only = llm.Member(Fake("late"), rpm=1)
    only.note()
    assert llm.Chain([only]).bind().invoke("q") == "late" and slept and slept[0] > 0
    assert llm.Member(Fake("x")).wait() == 0  # no budget set: never waits
