# Setup

How to run Ask HDB, set it up and build its data. The [README](../README.md) has the short version.

## Run it

```bash
cp .env.example .env     # then fill it in (see below)
uv sync
LLM_TIMEOUT=420 uv run ask-hdb serve      # http://localhost:8000
```

Or with Docker (build the data under `data/clean` first, see [docker.md](docker.md)):

```bash
docker compose up -d --build              # http://localhost:8000, this machine only
BIND_ADDR=192.168.0.10 docker compose up -d --build   # also on your home network (your LAN address)
```

The app has no login. Do not expose it to the internet without the rate limits and a model you can afford (see [docker.md](docker.md)).

## Settings (`.env`, git-ignored)

| Setting | Meaning |
|---|---|
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` | The model. Default: a local OpenAI-compatible server (Ollama, llama-server, MLX). Or a hosted provider with your own API key. |
| `LLM_CHAIN` | Models to try in order, for example Gemini, then OpenRouter, then local. |
| `LLM_TIMEOUT`, `LLM_REASONING_EFFORT` | Call timeout in seconds (420 in Docker) and the thinking setting for local models (`none`). |
| `ONEMAP_EMAIL`, `ONEMAP_PASSWORD` | OneMap login for address lookup and walking routes. Without it, lists still work and routes use the built-in OpenStreetMap router. |
| `DATAGOV_API_KEY` | Optional data.gov.sg key for the data download scripts. |
| `API_RATE_PER_MINUTE`, `API_DAILY_TOKEN_CAP`, `API_QUEUE_WAIT` | Questions per visitor per minute, the daily token cap, and how many seconds a second visitor waits for the one model slot (30 in Docker). |
| `BIND_ADDR` | Docker only: the address the port is published on. |
| `TRACING`, `LANGFUSE_*`, `TRACE_TEXT` | Optional Langfuse tracing, see below. |

## Bring your own model

Ask HDB ships no model and no API key. You run it with your own:
- **Local model (default):** any OpenAI-compatible server on your own machine, such as llama-server, Ollama or MLX on a Mac or a GPU PC. Nothing leaves your machine.
- **Your own API key:** a hosted provider (or any OpenAI-style provider through `LLM_BASE_URL`, including free tiers).
  A chat subscription does not include API access, so this uses a separate key in `.env`.
- **iOS (idea, not built):** Apple's on-device model or a small downloaded model. Small models call tools less reliably, so this needs the same test.

## Tracing

Optional Langfuse tracing (`uv sync --extra tracing`; Docker: `TRACING=1`), off unless keys are set.
One trace per question with scores `grounded`, `ungrounded_numbers`, `grounding_rewritten`, `stopped`, `tool_calls`.
Question, answer and tool data are `[redacted]` unless `TRACE_TEXT=1`. No user or session ids.

## Build the data

`data/clean` is not in Git. Build it once with the scripts, in this order:

```bash
uv run python scripts/fetch_resale.py       # resale prices from data.gov.sg
uv run python scripts/clean_resale.py
uv run python scripts/geocode_blocks.py     # block addresses via OneMap, cached
uv run python scripts/fetch_places.py       # MRT/LRT stations and primary schools
uv run python scripts/build_places.py
uv run python scripts/build_buildings.py    # 3D outlines with floors and facing (needs data/raw/property/hdb_property_information.csv from data.gov.sg)
uv run python scripts/build_block_info.py     # block facts (year, floors, units by flat type) from HDB Property Information
uv run python scripts/build_amenities.py    # bus stops and supermarkets from OpenStreetMap (Overpass)
# optional walking router: download Singapore.osm.gz from download.bbbike.org/osm/bbbike/Singapore/ into data/raw/walk/, then:
uv run python scripts/build_walk_graph.py
uv run python scripts/build_bto.py          # and build_bto_history.py
```

## Terminal commands

```bash
uv run ask-hdb ask "What are the recorded resale price statistics in TAMPINES?"
uv run ask-hdb chat                          # shows each tool call and its result; type quit to leave
uv run --no-sync ask-hdb routing             # the tool-call check
uv run --no-sync ask-hdb eval --condition agent
uv run --no-sync ask-hdb eval --condition llm-only
```

`ask-hdb eval` scores the frozen answer bank and saves JSON plus Markdown after each question. Use `--only price --verbose --limit 2`
for a small run. Held-out questions run only with `--heldout`. See [eval.md](eval.md) and [eval-results.md](eval-results.md).
