"""Provider choices need no server or API credentials in tests."""

import pytest

from ask_hdb import llm


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    monkeypatch.setattr(llm, "load_dotenv", lambda: None)
    for name in ("LLM_PROVIDER", "LLM_MODEL", "LLM_BASE_URL", "LLM_API_KEY"):
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
