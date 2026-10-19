# Ask HDB: proposal

## Why this project
- Portfolio piece #2, next to Whisperwick.
- Whisperwick shows: multi-agent simulation, a deterministic engine, careful evaluation.
- Ask HDB adds what job descriptions ask for most and Whisperwick lacks:
  RAG, a mainstream agent framework (LangGraph), MCP, tracing, and a deployed product.
- Same story across both projects: **agents you can trust because they are checked.**

## Who it is for
- First-time HDB resale buyers in Singapore (couples, families, singles 35+).
- People who know roughly what they want but not what they qualify for or can afford.

## Decisions

| Topic | Decision |
|---|---|
| Purpose | Portfolio project, built to look production-grade |
| Time | 6 weeks, side-project pace |
| Scope v1 | Resale flats only. No BTO, no EC, no private property |
| Profiles v1 | Citizen couples and families, citizen singles 35+. Others: "not supported yet" |
| Agent framework | LangGraph |
| Tools | Own MCP server. The agent uses it |
| Model | Local first (llama-server, OpenAI-compatible). Cloud model as a switch for the demo |
| Rules | Versioned YAML with source URL and `as_of` date. Never in prompts |
| RAG | Only to quote and explain policy text. Never to decide eligibility |
| Numbers | Only from tool results. Enforced by a grounding checker |
| Cost safety | Hard limit on steps and tokens per question. Stops and says so |
| Human in the loop | Agent shows the buyer profile it understood and asks "Is this right?" before computing |
| UI | Streamlit chat page |
| Deploy | Docker Compose, one small VM, public demo link |

## In scope (v1)
- Eligibility to buy a resale flat, for the v1 profiles.
- Grants: CPF Housing Grant (family), Enhanced CPF Housing Grant, Proximity Housing Grant.
- Affordability: rough max loan from income (HDB loan and bank loan limits), budget check.
- Resale price search and stats by town, flat type, storey, lease left, date range.
- **Price check against recent sales** (the most common Reddit worry: COV).
  "Is $620k fair for this 4-room?" -> recent sales in the same block and nearby blocks,
  with similar storey and lease. This is a comparison of past sales, **not** a valuation.
- Eligibility answers are framed as a **pre-check before applying for the HFE letter**,
  which is HDB's official decision.
- Distance from a block to the nearest MRT, chosen primary schools, or a given address.
- Explanations that quote HDB policy text with a link.

## Out of scope (v1)
- BTO and EC applications, ballots, priority schemes.
- Ethnic Integration Policy (EIP) and SPR quota checks. Needs HDB's own e-service.
- Price prediction ("will prices go up?") and predicting the official valuation. Past sales only.
- Advice on whether to buy. The agent refuses and says why.
- Logging in to HDB or CPF, or filling in any form.

## Success (checked in docs/eval.md)
- Eligibility and grant verdicts: **≥ 95% correct** on the eval set.
- Price and distance answers: **≥ 90% exactly right** (within rounding).
- Grounding: **100%** of numbers in answers come from tool results.
- The agent clearly beats an LLM-only baseline (no tools) on every measure.
- A stranger can use the public demo with no instructions.

## Main risks
| Risk | What we do |
|---|---|
| Rules change or our reading of them is wrong | Versioned rule files with sources. Tests use HDB's own worked examples |
| Local model is weak at tool calling | Week 2 checks this early. Fall back to a cloud model for the demo |
| OneMap or data.gov.sg rate limits | Cache to disk. Register for an API key |
| Straight-line distance is not walking distance | Say "straight-line" in every answer. Walking routes later, if time |
| Scope creep (BTO, EIP, prediction) | Out of scope list above. Park ideas in roadmap "later" |
| Looks like a toy | Eval table, tracing screenshots and a live link in the README |

## Prior art
- **HomeMe** (UC Berkeley MIDS capstone, 2025): AI Q&A over HDB policies and homes.
  Ask HDB differs by computing eligibility and numbers in code, with an eval set to prove it.
- HDB's own resale portal and flat portal: filters by town and flat type only.
- Property sites (PropertyGuru, 99.co): listings, but no eligibility or grant reasoning.
