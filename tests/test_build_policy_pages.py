"""The builder uses invented HTML and a local transport, never the real sites."""

from datetime import datetime
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import httpx
import pandas as pd
import pytest
import yaml

from ask_hdb.policy_sources import POLICY_URLS, validate_url

ROOT = Path(__file__).resolve().parents[1]
spec = spec_from_file_location("build_policy_pages", ROOT / "scripts/build_policy_pages.py")
builder = module_from_spec(spec)
spec.loader.exec_module(builder)
HTML = (Path(__file__).parent / "fixtures/policy_page.html").read_text()


def test_html_cleanup_and_balanced_passages():
    title, text = builder.parse_page(HTML)
    assert title == "Example policy & support"
    assert all(word not in text for word in ("Hidden", "Header", "Navigation", "Footer"))
    passages = builder.split_passages(text)
    assert " ".join(passages) == text
    assert all(80 <= len(p.split()) <= 150 for p in passages)
    assert builder.split_passages("") == []
    assert builder.split_passages("Short page.") == ["Short page."]


def test_fixed_allowlist_reuses_rule_sources():
    sources = set()

    def walk(node):
        if isinstance(node, dict):
            if "source" in node:
                sources.add(node["source"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    for path in (ROOT / "rules").rglob("*.yaml"):
        walk(yaml.safe_load(path.read_text()))
    assert set(POLICY_URLS) <= sources
    assert len(POLICY_URLS) == len(set(POLICY_URLS))
    assert all(validate_url(url) == url for url in POLICY_URLS)
    assert validate_url("https://www.cpf.gov.sg/example")


@pytest.mark.parametrize("url", [
    "https://example.com", "https://www.hdb.gov.sg.evil.test/page",
    "https://hdb.gov.sg@evil.test/page", "http://www.hdb.gov.sg/page",
    "https://www.hdb.gov.sg:8080/page", "https://user@www.hdb.gov.sg/page",
    "file:///tmp/page", "//www.hdb.gov.sg/page",
])
def test_refuse_other_domains_and_unsafe_urls(url):
    with pytest.raises(ValueError):
        validate_url(url)


def test_build_writes_local_raw_and_parquet(tmp_path):
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

    output, raw = tmp_path / "policy.parquet", tmp_path / "raw"
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        count = builder.build(output=output, raw=raw, client=client)
    frame = pd.read_parquet(output)
    assert count == len(frame) and count > len(POLICY_URLS)
    assert requests == list(POLICY_URLS)
    assert list(frame.columns) == ["url", "title", "fetched_at", "passage"]
    assert set(frame.url) == set(POLICY_URLS)
    assert all(datetime.fromisoformat(value).tzinfo is not None for value in frame.fetched_at)
    assert len(list(raw.glob("*.html"))) == len(POLICY_URLS)


def test_redirect_is_checked_before_request_and_unlisted_start_refused():
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.test/page"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError, match="official"):
            builder.fetch_page(client, POLICY_URLS[0])
        with pytest.raises(ValueError, match="allowlist"):
            builder.fetch_page(client, "https://www.hdb.gov.sg/unlisted")
    assert requests == [POLICY_URLS[0]]


def test_official_redirect_and_non_html_response():
    def respond(request):
        if str(request.url) == POLICY_URLS[0]:
            return httpx.Response(302, headers={"location": "https://www.cpf.gov.sg/example"})
        return httpx.Response(200, text=HTML, headers={"content-type": "text/html"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        assert builder.fetch_page(client, POLICY_URLS[0]) == HTML
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
            200, headers={"content-type": "application/pdf"}))) as client, pytest.raises(ValueError, match="HTML"):
        builder.fetch_page(client, POLICY_URLS[0])
