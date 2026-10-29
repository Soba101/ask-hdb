# Ask HDB

An agent that helps you find HDB resale flats you are **eligible for**, can **afford**,
and that are **near what matters to you** (MRT, schools, supermarkets, bus stops).

> Status (2026-10-29): the data tools, the rules, the grounded agent, an 85-question dev eval and a map-first web app
> (phone and desktop) are built. It runs locally on a 9B model and in Docker on one machine. It is not public yet.
> See [docs/roadmap.md](docs/roadmap.md).

## Live demo

**https://soba101.github.io/ask-hdb/** runs from saved files on GitHub Pages, with no server. The map, layers (type, price, lease, MOP), 3D and sun shadows,
info cards, nearby places and walking routes work. Chat is paused ("the free model limit has been reached"), and the walking routes there are estimates
from OpenStreetMap paths. To chat, run the app yourself (below). The demo is built by `scripts/build_static_demo.py` ([hosting plan](docs/hosting-plan.md),
[routing test](docs/routing-ab.md)).

## The app

A map of every HDB block, MRT/LRT station, primary school and BTO site, with a chat beside it (a bottom sheet on a phone).
Click a place and the chat knows what "this block" means. Ask, and the answer shows its tool results, its sources and the places on the map.

- **Layers:** colour blocks by type, median price for a flat type (with a budget slider), remaining lease, or MOP status
  (within, ending this year, past). Upcoming BTO sites show an estimated completion.
- **Info card:** a short summary with sections you open when you need them: prices, lease, sun and facing, primary schools within 2 km, nearby places.
- **Nearby and walking:** the three nearest supermarkets, MRT/LRT stations and bus stops, and a walking route with steps and a time
  ([OneMap](https://www.onemap.gov.sg/) routing with your own login in `.env`; without it, or when OneMap is down, our own router over OpenStreetMap paths answers).
- **3D and sun:** building heights, approximate block facing and ground shadows for a chosen date and time
  ([details](docs/week7-3d.md)). The 3D view turns on when you tilt the map.
- **Phone and desktop:** the same Apple-style look on both. On a phone the chat and the card live in a bottom sheet.

| Answers shown on the map | Primary schools within 2 km (1 km and 2 km rings) |
|---|---|
| ![A question about nearest MRT stations to a BTO project, with the stations on the map](docs/img/answer-on-map.jpg) | ![Schools ringed by distance band around a station](docs/img/school-rings.jpg) |

| Price layer (median for a flat type, budget slider) | Lease layer (years left) |
|---|---|
| ![Blocks coloured by median resale price](docs/img/price-layer.jpg) | ![Blocks coloured by remaining lease](docs/img/lease-layer.jpg) |

Prices, lease and MOP colours are descriptive only (not a valuation or a forecast). Distances in lists are straight-line;
walking times are OneMap estimates; school distances are not MOE's own measurement.

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
- If a rules tool cannot decide (`eligible: null`), code replaces any answer that states a verdict and asks for the missing details.

```
You:   We're a married couple, both citizens, earning $8,500 a month together.
       We want a 4-room near Tampines MRT, under $600k. What can we get?
Agent: [confirms your profile] -> [checks eligibility + grants in code]
       -> [searches recent resale prices] -> [measures distance to MRT]
       -> "You qualify for these grants: ... Recent 4-room sales within 1 km of
          Tampines MRT: median $X (N sales, last 12 months). Sources: ..."
```

## Run it

```bash
cp .env.example .env     # then fill it in (see below)
uv sync
LLM_TIMEOUT=420 uv run ask-hdb serve      # http://localhost:8000
```

Or with Docker (the data under `data/clean` must be built first, see [docs/docker.md](docs/docker.md)):

```bash
docker compose up -d --build              # http://localhost:8000, this machine only
BIND_ADDR=192.168.0.10 docker compose up -d --build   # also on your home network (your LAN address)
```

The app has no login. Do not expose it to the internet without the rate limits and a model you can afford (see [docs/docker.md](docs/docker.md)).

### Settings (`.env`, git-ignored)

| Setting | Meaning |
|---|---|
| `LLM_PROVIDER`, `LLM_MODEL`, `LLM_BASE_URL`, `LLM_API_KEY` | The model. Default: a local OpenAI-compatible server (Ollama, llama-server, MLX). Or `openai` or `anthropic` with your own API key. |
| `LLM_TIMEOUT`, `LLM_REASONING_EFFORT` | Call timeout in seconds (420 in Docker) and the thinking setting for local models (`none`). |
| `ONEMAP_EMAIL`, `ONEMAP_PASSWORD` | OneMap login for address lookup and walking routes. Without it, lists still work but routes do not. |
| `DATAGOV_API_KEY` | Optional data.gov.sg key for the data download scripts. |
| `API_RATE_PER_MINUTE`, `API_DAILY_TOKEN_CAP`, `API_QUEUE_WAIT` | Questions per visitor per minute, the daily token cap, and how many seconds a second visitor waits for the one model slot (30 in Docker). |
| `BIND_ADDR` | Docker only: the address the port is published on. |
| `TRACING`, `LANGFUSE_*`, `TRACE_TEXT` | Optional Langfuse tracing, see below. |

## Bring your own model

Ask HDB ships no model and no API key. You run it with your own:
- **Local model (default):** any OpenAI-compatible server on your own machine, such as
  llama-server, Ollama or MLX on a Mac or a GPU PC. Nothing leaves your machine.
- **Your own API key:** OpenAI or Anthropic (or any OpenAI-style provider through `LLM_BASE_URL`, including free tiers).
  A chat subscription does not include API access, so this uses a separate key in `.env`.
  With Anthropic, the system prompt and tool schemas are marked cacheable to cut the input cost.
- **iOS (idea, not built):** Apple's on-device model or a small downloaded model. Small models call tools less reliably, so this needs the same test.

## Build the data

`data/clean` is not in Git. Build it once with the scripts, in this order:

```bash
uv run python scripts/fetch_resale.py       # resale prices from data.gov.sg
uv run python scripts/clean_resale.py
uv run python scripts/geocode_blocks.py     # block addresses via OneMap, cached
uv run python scripts/fetch_places.py       # MRT/LRT stations and primary schools
uv run python scripts/build_places.py
uv run python scripts/build_buildings.py    # 3D outlines with floors and facing (needs data/raw/property/hdb_property_information.csv from data.gov.sg)
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
for a small run. Held-out questions run only with `--heldout`. See [evaluation details](docs/eval.md) and [results](docs/eval-results.md).

### How well it works

The 85-question dev set, one 9B model, direct tools. Numbers are the share of questions that pass:

| Run | Passed | Number | Verdict | Refusal | Grounding | Time per question |
|---|---:|---:|---:|---:|---:|---:|
| Mac, Ollama `qwen3.5:9b` (nvfp4), 2026-10-29 | 82 of 85 | 96.7% | 92.9% | 100% | 100% | 37 s |
| 5090, llama-server Q4_K_M, 2026-10-29 | 73 of 85 | 83.3% | 100% | 81.8% | 100% | 1.3 s |
| LLM only, no tools (week 3, 40 questions) | n/a | 0.0% | 10.0% | 0.0% | 0.0% | n/a |

The two 9B runs use the same base model with a different quantisation and runtime, so they are not a clean comparison.
The 5090 run often made no tool call on distance questions. The confirmation step is a safety feature, not an accuracy gain.
Every round, regression and fix is in [docs/eval-results.md](docs/eval-results.md). 38 questions are held out.

## Stack

| Part | Choice |
|---|---|
| Language | Python 3.12, `uv`, `pytest`, `ruff` |
| Agent | LangGraph ReAct agent with 18 code tools (a supervisor graph is deferred) |
| Tools | Our own MCP server around the same tools (resale search, price stats, eligibility, grants, BTO, distances) |
| Model | Your own: a local server by default, or a cloud API key |
| RAG | not built (deferred) |
| Data | data.gov.sg (resale prices, HDB property information, MRT exits), OneMap (addresses, routes), OpenStreetMap (bus stops, supermarkets, map tiles) |
| Web | FastAPI and a plain-JS page, MapLibre GL (2D and 3D), no build step |
| Tracing | Optional Langfuse (`uv sync --extra tracing`; Docker: `TRACING=1`), off unless keys are set. One trace per question with scores `grounded`, `ungrounded_numbers`, `grounding_rewritten`, `stopped`, `tool_calls`. Question, answer and tool data are `[redacted]` unless `TRACE_TEXT=1`. No user or session ids. |
| Deploy | Docker image and compose file; runs on one machine. No public host yet. |

## Docs

- [docs/proposal.md](docs/proposal.md): the plan, decisions, scope and risks.
- [docs/architecture.md](docs/architecture.md): how the parts fit together.
- [docs/roadmap.md](docs/roadmap.md): weeks, tasks and exit checks.
- [docs/docker.md](docs/docker.md): running the image.
- [docs/eval.md](docs/eval.md) and [docs/eval-results.md](docs/eval-results.md): how we measure "correct", and the results.
- [docs/week7-3d.md](docs/week7-3d.md), [docs/week8-plan.md](docs/week8-plan.md): the 3D map, the page structure and the UI contract.
- [docs/week8-amenity-plan.md](docs/week8-amenity-plan.md): nearby places and walking routes.
- [docs/research.md](docs/research.md): what we found before starting, with sources.

## Data credits

HDB resale and property information and LTA MRT exits from data.gov.sg (Singapore Open Data Licence v1.0);
addresses and walking routes from OneMap (Singapore Land Authority); map tiles, bus stops and supermarkets from OpenStreetMap contributors (ODbL).

## Disclaimer

This is a portfolio project, not financial or legal advice.
Always confirm eligibility and grants with HDB before you buy.

## License

MIT
