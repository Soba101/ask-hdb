# Ask HDB

An agent that helps you find HDB resale flats you are **eligible for**, can **afford**,
and that are **near what matters to you** (MRT, schools, parents).

> Status: Data tools, rules, agent and offline evaluation are built. The first baseline
> is run (agent beats LLM-only on numbers, not yet on eligibility verdicts). See [docs/roadmap.md](docs/roadmap.md).

## The problem

Buying an HDB resale flat in Singapore is confusing:
- Eligibility and grant rules are a web of conditions spread over many pages.
- The resale portal filters by town and flat type only. It cannot answer
  "4-room within 1 km of an MRT, under $600k, that I can get a grant for".
- Many buyers pay an agent thousands of dollars partly to work this out.

## The question

Can an agent answer real home-buying questions where **every number and every
eligibility verdict is correct and traceable**, while still feeling like a helpful chat?

## Core rule

- **The LLM talks. Code decides.**
- Eligibility, grants, loan limits, prices and distances are computed in code.
- The LLM only asks follow-up questions, picks which tools to call, and explains results.
- Every number in an answer must come from a tool result. A checker enforces this.

## What it will do (v1)

```
You:   We're a married couple, both citizens, earning $8,500 a month together.
       We want a 4-room near Tampines MRT, under $600k. What can we get?
Agent: [confirms your profile] -> [checks eligibility + grants in code]
       -> [searches recent resale prices] -> [measures distance to MRT]
       -> "You qualify for these grants: ... Recent 4-room sales within 1 km of
          Tampines MRT: median $X (N sales, last 12 months). Sources: ..."
```

## Bring your own model
Ask HDB ships no model and no API key. You run it with your own:
- **Local model (default):** any OpenAI-compatible server on your own machine, such as
  llama-server, Ollama or MLX on a Mac or a GPU PC. Nothing leaves your machine.
- **Your own API key:** OpenAI or Anthropic. A chat subscription (ChatGPT, Claude) does not
  include API access, so this uses a separate API key that you paste into `.env`.
- **iOS (idea, not built):** Apple's on-device model (Foundation Models, supports tool
  calling) or a small model downloaded to the phone. Small models call tools less reliably,
  so this needs the same tool-calling test as the desktop models.

## Terminal commands

Copy `.env.example` to `.env` and set `LLM_*` for your local server or API provider.
For a cloud provider, remove `LLM_BASE_URL` to use its default endpoint and set your API key.

```bash
uv sync
uv run ask-hdb ask "What are the recorded resale price statistics in TAMPINES?"
uv run ask-hdb chat
uv run python scripts/tool_call_check.py
uv run --no-sync ask-hdb routing
uv run --no-sync ask-hdb eval --condition agent
uv run --no-sync ask-hdb eval --condition llm-only
```

Chat shows each tool call and its result before the answer. Type `quit` to leave.
`ask-hdb routing` keeps the previous tool-call check and its week-two notes.
`ask-hdb eval` scores the frozen answer bank and saves JSON plus Markdown after each question.
Use `--only price --verbose --limit 2` for a small run. Held-out questions run only with
`--heldout`. Reports resume explicitly; existing completed results and errors are retained.
See [evaluation details](docs/eval.md) and [comparison status](docs/eval-results.md).

| Condition | Number accuracy | Verdict accuracy | Refusal accuracy | Grounding |
|---|---|---|---|---|
| LLM-only | 0.0% | 10.0% | 0.0% | 0.0% |
| Single agent | 92.3% | 40.0% | 50.0% | 85.7% |

Live baseline: 40 questions per condition, one 9B local model (qwen3.5-9b-16k on a MacBook), 2026-10-20. The agent wins on numbers but misses the verdict bar; causes are in the results doc.

## Stack (each picked to match current AI engineer job descriptions)

| Part | Choice |
|---|---|
| Language | Python, `uv`, `pytest`, `ruff` |
| Agent | LangGraph (supervisor + tool-using workers) |
| Tools | Our own MCP server (resale search, price stats, eligibility, distances) |
| Model | Local model via llama-server (OpenAI-compatible). Swappable for a cloud model |
| RAG | pgvector over HDB policy pages, used only to *explain* rules |
| Data | data.gov.sg resale prices, OneMap (geocoding, MRT, schools) |
| Tracing | Langfuse |
| UI | Streamlit |
| Deploy | Docker Compose on one small cloud VM |

## Docs

- [docs/proposal.md](docs/proposal.md): the plan, decisions, scope and risks.
- [docs/architecture.md](docs/architecture.md): how the parts fit together.
- [docs/eval.md](docs/eval.md): how we measure "correct".
- [docs/roadmap.md](docs/roadmap.md): weeks, tasks and exit checks.
- [docs/research.md](docs/research.md): what we found before starting, with sources.

## Disclaimer

This is a portfolio project, not financial or legal advice.
Always confirm eligibility and grants with HDB before you buy.

## License

MIT
