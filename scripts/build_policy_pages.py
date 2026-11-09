"""Fetch the fixed official page list. Run explicitly; never during a chat."""

import argparse
import hashlib
import math
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx
import pandas as pd

from ask_hdb.policy import PASSAGES_PATH
from ask_hdb.policy_sources import POLICY_URLS, validate_url

RAW_PATH = PASSAGES_PATH.parents[1] / "raw/policy_pages"


class PageText(HTMLParser):
    """Leave scripts and page furniture out of the search index."""

    SKIP = frozenset({"script", "style", "nav", "header", "footer", "noscript", "svg", "template"})
    VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.title, self.body, self.main = [], [], [], []

    def handle_starttag(self, tag, attrs):
        if tag not in self.VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.stack:
            self.stack = self.stack[:len(self.stack) - 1 - self.stack[::-1].index(tag)]

    def handle_data(self, data):
        if "title" in self.stack:
            self.title.append(data)
        elif not self.SKIP.intersection(self.stack) and "head" not in self.stack:
            self.body.append(data)
            if "main" in self.stack or "article" in self.stack:
                self.main.append(data)


def parse_page(html):
    parser = PageText()
    parser.feed(html)
    tidy = lambda parts: " ".join(" ".join(parts).split())
    return tidy(parser.title), tidy(parser.main or parser.body)


def split_passages(text):
    words = text.split()
    # Balance the tail across chunks so a full page has no tiny last passage.
    count = max(1, math.ceil(len(words) / 150))
    size = math.ceil(len(words) / count)
    return [" ".join(words[start:start + size]) for start in range(0, len(words), size)] if size else []


def fetch_page(client, url):
    if url not in POLICY_URLS:
        raise ValueError("Policy URL is not in the fixed allowlist")
    for _ in range(6):
        # Check before sending, including every redirect. Automatic redirects stay off.
        validate_url(url)
        response = client.get(url, follow_redirects=False)
        if response.is_redirect:
            url = urljoin(url, response.headers["location"])
            continue
        response.raise_for_status()
        if "text/html" not in response.headers.get("content-type", "").lower():
            raise ValueError("Policy page must be HTML")
        return response.text
    raise ValueError("Too many policy page redirects")


def build(*, output=PASSAGES_PATH, raw=RAW_PATH, client=None):
    if client is None:
        with httpx.Client(timeout=30) as session:
            return build(output=output, raw=raw, client=session)
    rows = []
    raw = Path(raw)
    raw.mkdir(parents=True, exist_ok=True)
    for url in POLICY_URLS:
        html = fetch_page(client, url)
        fetched_at = datetime.now(UTC).isoformat()
        # Raw files stay local and can be inspected without another download.
        (raw / (hashlib.sha256(url.encode()).hexdigest() + ".html")).write_text(html)
        title, text = parse_page(html)
        if not title or not text:
            raise ValueError(f"No title or page text at {url}")
        rows.extend({"url": url, "title": title, "fetched_at": fetched_at, "passage": passage}
                    for passage in split_passages(text))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".parquet.tmp")
    pd.DataFrame(rows, columns=["url", "title", "fetched_at", "passage"]).to_parquet(temporary, index=False)
    temporary.replace(output)
    return len(rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=PASSAGES_PATH)
    args = parser.parse_args()
    print(f"Wrote {build(output=args.output)} passages to {args.output}")
