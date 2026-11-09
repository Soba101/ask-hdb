# Policy explanations with source links

`policy_explain(topic)` searches a local BM25 index and returns up to three relevant
passages. Each contains `title`, `url`, `fetched_at` and `passage`. No download or
external search happens during an answer. The index uses plain Python word counts;
there are no new dependencies. This uses the existing single agent and tool path.

HDB's terms ask for written approval before others reuse its materials. Stored
passages are context for the model only. Explain in original words; never quote
passages. The web source pane shows only a page title and link. The server removes
passages and fetched dates from policy tool events before sending them to the browser,
and the page renders named source links instead of a raw result panel. Raw HTML and
cleaned passages stay in git-ignored data directories. Do not commit fetched text.

Numbers, thresholds and verdicts still come from rules and data tools. Both the
agent and eval remove `policy_explain` calls from grounding evidence by tool name.
The result also carries `tool: policy_explain`; the grounding walker ignores that
entire object, including titles, URLs, dates and passage text. Policy content also
cannot supply place labels that hide numeric claims. The verdict check holds a
policy-only eligibility answer until a rules tool has settled the check.

## Build and refresh

Run explicitly from the repository with the usual environment:

```bash
PYTHONPATH=src uv run python scripts/build_policy_pages.py
```

The builder fetches only the fixed list below, saves HTML in `data/raw/policy_pages/`,
strips scripts and page navigation, and splits text into roughly 80–150 word
passages. Short pages remain short. It writes `data/clean/policy_passages.parquet`
with `url`, `title`, `fetched_at` and `passage`. The URL is the original rule source;
the fetched date is a UTC timestamp for that download. Redirects are checked before
each request and may stay only on official HDB or CPF HTTPS hosts. It refuses other
domains and non-HTML responses. The previous parquet stays in place if a build fails.

Rebuild explicitly to refresh content. The file timestamp refreshes the cached
search index. If the file is absent, the tool returns `policy pages not built`;
the remaining tools and app keep working. Tests use invented local HTML and temporary
parquet files. No official page text is stored in test fixtures.

## Fixed URL allowlist

These HTML URLs already appear as sources in `rules/2026-10.yaml`. PDF sources and
the transport factsheet are excluded. No CPF page is in the current rules, so none
is fetched. The domain guard permits only `hdb.gov.sg`, `www.hdb.gov.sg`,
`cpf.gov.sg` and `www.cpf.gov.sg`; adding a source requires changing the fixed list
in `src/ask_hdb/policy_sources.py` and reviewing its rule source.

- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families/cpf-housing-grants
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families/enhanced-cpf-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/couples-and-families/proximity-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles/cpf-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles/enhanced-cpf-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/singles/proximity-housing-grant
- https://www.hdb.gov.sg/buying-a-flat/flat-grant-and-loan-eligibility/housing-loan/housing-loan-from-hdb
- https://www.hdb.gov.sg/managing-my-home/finances/loan-matters/interest-rate

## Eval checks

Development cases `q_grants_013`, `q_grants_014`, `q_grants_015` and
`q_eligibility_013` cover family EHG, family CPF Housing Grant, living with parents
under PHG, and unmarried singles buying resale. They retain the existing numeric
or verdict expectation and add `expect.expected_url`. A pass needs the exact source
URL in the answer and no ungrounded numbers anywhere, even after the right amount.
Tests append an invented passage-only amount to otherwise correct answers and
verify failure for every case. No held-out question was changed.
