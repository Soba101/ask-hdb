"""Find the official HDB page for a policy topic. Links only: no HDB text is stored.

hdb.gov.sg refuses automated fetching, and HDB asks for written approval before others reuse
its material. So each page has a title and a short summary written for this project that says
what the page covers. They are search hints, not rule facts, and hold no rule values: numbers come from the rules tools.
"""

import math
import re
from collections import Counter

from ask_hdb.policy_sources import BASE, POLICY_URLS

FAMILY, SINGLE = f"{BASE}/couples-and-families", f"{BASE}/singles"
PAGES = (
    {"url": FAMILY, "title": "HDB: grant and loan eligibility for couples and families",
     "summary": "Overview for couples and families buying a flat: who can buy, citizenship, "
                "household, income ceiling and first-timer rules, and which grants and loans apply."},
    {"url": f"{FAMILY}/cpf-housing-grants", "title": "HDB: CPF Housing Grant for families (resale)",
     "summary": "The CPF Housing Grant for couples and families who buy a resale flat: who qualifies, "
                "how flat size and household status affect it, and how it is paid into CPF."},
    {"url": f"{FAMILY}/enhanced-cpf-housing-grant", "title": "HDB: Enhanced CPF Housing Grant (EHG) for families",
     "summary": "The Enhanced CPF Housing Grant for first-timer couples and families, new or resale: "
                "income ceiling, work history, remaining lease and how the amount depends on income."},
    {"url": f"{FAMILY}/proximity-housing-grant", "title": "HDB: Proximity Housing Grant (PHG) for families",
     "summary": "The Proximity Housing Grant for married couples and families who buy a resale flat to live with or near "
                "their parents or child: conditions, distance and who counts as family."},
    {"url": SINGLE, "title": "HDB: grant and loan eligibility for singles",
     "summary": "Overview for single buyers: minimum age, the single and joint singles schemes, "
                "income ceiling, which flats singles can buy and which grants and loans apply."},
    {"url": f"{SINGLE}/cpf-housing-grant", "title": "HDB: CPF Housing Grant for singles (resale)",
     "summary": "The CPF Housing Grant for singles who buy a resale flat: who qualifies, flat size, "
                "joint singles, and how it is paid into CPF."},
    {"url": f"{SINGLE}/enhanced-cpf-housing-grant", "title": "HDB: Enhanced CPF Housing Grant (EHG) for singles",
     "summary": "The Enhanced CPF Housing Grant for first-timer singles, new or resale: income ceiling, "
                "work history, remaining lease and how the amount depends on income."},
    {"url": f"{SINGLE}/proximity-housing-grant", "title": "HDB: Proximity Housing Grant (PHG) for singles",
     "summary": "The Proximity Housing Grant for singles who buy a resale flat to live with or near "
                "their parents: conditions and distance."},
    {"url": f"{BASE}/housing-loan/housing-loan-from-hdb", "title": "HDB: housing loan from HDB",
     "summary": "The HDB housing loan: eligibility, income ceiling, the HFE letter, "
                "how much you can borrow, loan tenure, and previous housing loans."},
    {"url": POLICY_URLS[-1], "title": "HDB: housing loan interest rate",
     "summary": "The HDB housing loan interest rate: the current rate, how it relates to the "
                "CPF Ordinary Account rate, and when it can change."},
)
STOP_WORDS = {"a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "for", "from", "how",
              "i", "in", "is", "it", "me", "my", "of", "on", "or", "our", "the", "to", "we", "what",
              "with", "you", "your"}


def tokens(text):
    # Simple shared tokenisation keeps indexing and queries consistent.
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in STOP_WORDS]


class PageIndex:
    """Small BM25 index using only word counts and document lengths."""

    def __init__(self, rows):
        self.rows = rows
        self.counts = [Counter(tokens(row["title"] + " " + row["summary"])) for row in rows]
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
        # Stable ties make repeat queries reproducible. Unrelated pages are not useful.
        ranked = sorted(scores, key=lambda pair: (-pair[0], pair[1]))
        return [dict(self.rows[i]) for score, i in ranked if score > 0][:3]


def policy_explain(topic):
    """Up to three official pages for the topic, marked so grounding never uses them."""
    return {"tool": "policy_explain", "pages": PageIndex(PAGES).search(topic)}


def public_result(result):
    """The browser receives page names and links."""
    return {"sources": [{"title": row["title"], "url": row["url"]} for row in result.get("pages", [])],
            **({"error": result["error"]} if "error" in result else {})}
