"""Offline passage search. Text explains rules; it never supplies rule values."""

import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import pandas as pd

from ask_hdb.policy_sources import POLICY_URLS

PASSAGES_PATH = Path(__file__).resolve().parents[2] / "data/clean/policy_passages.parquet"
STOP_WORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "how",
              "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "the", "to", "we", "what",
              "with", "you", "your"}


def tokens(text):
    # Simple shared tokenisation keeps indexing and queries consistent.
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in STOP_WORDS]


class PassageIndex:
    """Small BM25 index using only word counts and document lengths."""

    def __init__(self, rows):
        self.rows = rows
        self.counts = [Counter(tokens(row["title"] + " " + row["passage"])) for row in rows]
        self.lengths = [sum(count.values()) for count in self.counts]
        self.average = sum(self.lengths) / len(rows) if rows else 1
        self.frequency = Counter(word for count in self.counts for word in count)

    def search(self, question):
        query = set(tokens(question))
        scores = []
        for i, count in enumerate(self.counts):
            score = 0
            for word in query & count.keys():
                inverse = math.log(1 + (len(self.rows) - self.frequency[word] + .5)
                                   / (self.frequency[word] + .5))
                normal = 1.5 * (.25 + .75 * self.lengths[i] / (self.average or 1))
                score += inverse * count[word] * 2.5 / (count[word] + normal)
            scores.append((score, i))
        # Stable ties make repeat queries reproducible. Unrelated text is not useful context.
        ranked = sorted(scores, key=lambda pair: (-pair[0], pair[1]))
        return [dict(self.rows[i]) for score, i in ranked if score > 0][:3]


@lru_cache(maxsize=1)
def _load_index(path, modified):
    # The file stamp refreshes the index after a rebuild, with no network at answer time.
    rows = pd.read_parquet(path, columns=["url", "title", "fetched_at", "passage"]).to_dict("records")
    if any(row["url"] not in POLICY_URLS or any(not isinstance(v, str) for v in row.values())
           for row in rows):
        raise ValueError("Invalid policy passages; rebuild the policy pages")
    return PassageIndex(rows)


def policy_explain(topic):
    """Return context only, marked so even direct grounding checks can exclude it."""
    result = {"tool": "policy_explain", "passages": []}
    try:
        stamp = PASSAGES_PATH.stat()
    except FileNotFoundError:
        return {**result, "error": "policy pages not built; run scripts/build_policy_pages.py"}
    index = _load_index(PASSAGES_PATH, (stamp.st_mtime_ns, stamp.st_size))
    return {**result, "passages": index.search(topic)}


def public_result(result):
    """The browser receives source names and links, never the stored text."""
    return {"sources": [{"title": row["title"], "url": row["url"]}
                        for row in result.get("passages", [])],
            **({"error": result["error"]} if "error" in result else {})}
