# Research before starting (2026-10-19)

Web research, plus 174 Reddit post titles and openings (2023-2026) pulled from the
Arctic Shift public Reddit archive (Reddit itself blocks automated access).
Most sources are blogs and job-board summaries: treat numbers as rough signals.

## 1. What AI engineer job descriptions ask for
- Python everywhere (~82% of listings). TypeScript is a plus.
- RAG is the most requested skill (~36% of AI roles). Agents ~14% and growing.
- Agent frameworks: LangGraph plus one other (CrewAI, AutoGen, OpenAI Agents SDK, Google ADK).
- Evaluation and observability called the differentiator: golden datasets, LLM-as-judge,
  tracing with Langfuse or LangSmith.
- Tool calling, structured outputs, cost and latency tuning.
- Docker, CI/CD, a cloud. Security: prompt injection, human oversight of risky actions.
- Singapore: ~3,000 AI engineering listings. Same stack, plus Azure AI Foundry at
  enterprises, LLMOps/AgentOps, governance. Many agentic roles ask for 5+ years,
  so a junior portfolio must look production-grade.

## 2. Latest agent tech (Oct 2026)
- MCP is the standard for connecting agents to tools and data.
- A2A (agent-to-agent) protocol v1.0, April 2026, Linux Foundation.
- Multi-agent (supervisor + workers) is the main design shift.
- LLMs treated as untrusted components; deterministic guardrails + human approval.
- Hype cooling: employers want proof that agents work, not demos.

## 3. Why agents fail in production (what Ask HDB must show it handles)
- Works in a demo, breaks when deployed.
- Confident hallucination, skipped steps, tools in the wrong order.
- Unauthorised actions (a sales agent promised an unapproved discount).
- Loops and cost blow-ups.
- Hard to debug: logging is an afterthought.
- No retries or resume.
Our answers: grounding check, eval set, step limits, tracing, profile confirmation.

## 4. HDB buyers' pain points
- HDB website: a maze of links, too much information.
- Eligibility rules for schemes are a complex web.
- People pay agents about USD 3,000–12,000, partly to work this out.
- Resale portal filters by address and flat type only; no distance to schools, MRT, parks.
- Prior art: HomeMe (Berkeley MIDS 2025), an AI Q&A for HDB policies and homes.

## 5. Reddit: what HDB buyers actually ask (r/askSingapore, r/singapore)
Counted by eye from post titles, so rough.
- **COV / valuation (most common, ~10 threads with many comments).** "Is $20k COV reasonable?",
  "Is COV really based on recent transactions?", "Can I take a personal loan to pay COV?".
  Buyers compare an asking price to nearby recent sales by hand. **Strong fit for a tool.**
- **HFE letter confusion.** HDB Flat Eligibility letter is required since May 2023.
  Questions on self-employed income, payslip history, reassessment at key collection,
  rejection for overseas property, long waits (news: ~70% took over 21 days).
- **Grant eligibility edge cases.** First-timer vs second-timer, 1-year grant debarment
  after giving up a BTO, SC + foreigner / SC + PR couples, singles at 35.
- **Old leases.** "Singles who bought a flat over 40 years old, do you regret it?"
- **Price shock.** Record-price news threads get hundreds of comments ($1.1m+ resale flats).
- Note: "near MRT" searches return unrelated posts, so MRT distance is a nice extra,
  not the main pull. COV and eligibility are the main pull.

## 6. Reddit: what agent builders complain about (r/AI_Agents, r/LocalLLaMA)
- **Runaway loops and cost.** "An agent got stuck in a loop and burned $4,700 overnight"
  (116 upvotes, 77 comments). "Unmetered tool recursion burned $420 in 40 minutes".
- **Fake success.** The agent reports success when it did not succeed.
- **Errors compound.** "Each step trusts the last one's mistake."
- **Silent staleness.** Answers based on old data, with no warning.
- **Evaluation.** "When do you run evals with LangGraph?", "How do you validate generated SQL?"
- **Cheap wins people report:** inline source citations; boring, fixed output formats;
  verifying every number against the data source.
Our answers: step and cost budget per question, grounding check, "data as of" date in
every answer, the eval set.

## 7. Facts to check against official sources in week 1
- Resale dataset: data.gov.sg `d_8b84c4ee58e3cfc0ece0d773c8ca6abc` (Jan 2017 onwards).
  Open Data Licence. Rate limits enforced from 31 Dec 2025; an API key gives higher limits.
- OneMap: search/geocoding works without a token; routing needs one (getToken).
  Official docs: developers.onemap.sg.
- Income ceilings: sources disagree. A newer report (EdgeProp, Aug 2026) says the BTO
  ceiling was raised to $16,000; older guides say $14,000. Resale with no grant or HDB loan
  reportedly has no income ceiling. Enhanced CPF Housing Grant: commonly cited as up to
  $120,000 with a $9,000 family ceiling, but no 2026 confirmation found.
  **Use hdb.gov.sg as the only source for rules/*.yaml.**

## Sources
- Reddit: Arctic Shift archive search over r/askSingapore, r/singapore, r/AI_Agents,
  r/LocalLLaMA. Raw list kept outside the repo.
- Jobs and skills: aishippinglabs.com (1,000+ job descriptions), aiengineerinsights.com,
  techademy.com, digitalapplied.com, JobStreet / Foundit / Indeed / Built In Singapore listings.
- Trends: shakudo.io, machinelearningmastery.com, firecrawl.dev, arXiv 2606.20570, arXiv 2605.16471.
- Agent failures: dev.to posts (lukehinds, paul_martin_1, composiodev), mindstudio.ai,
  Union AI substack.
- HDB: ischool.berkeley.edu/projects/2025/homeme, edgeprop.sg, 99.co, propertynet.sg,
  thefinancialcoconut.com, data.gov.sg dataset pages, OneMap community docs.
