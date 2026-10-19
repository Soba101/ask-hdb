# First agent notes

The model client, deterministic tool wrappers, bounded ReAct agent and terminal
commands are implemented. The tool-call check uses the model selected by `.env`.
It appends a pass/fail table here and writes code-computed expectations for manual
answer review. No model-derived expected numbers are used.

## Build verification

Dependency installation was attempted with the requested `uv add` command.
The execution sandbox disables network access, so the package index could not be
resolved. A writable copy of the existing package cache also lacks the required
LangChain packages. Dependencies were added to `pyproject.toml` with `uv add
--frozen`; `uv.lock` still needs regeneration in an environment with package access.

Model configured by default: `qwen3.5:9b`, local endpoint. No `LLM_*` overrides were
present in `.env` during this build. Model checks and manual answer review are
blocked by the unavailable dependencies. No live model score is claimed.
The shared GPU was not used. The planned comparison with the other local models
remains pending until those models are available and the shared GPU is free.

The pre-existing CLI had no evaluation runner. Its greeting was not an evaluation
score, so there is no comparable prior agent baseline. The new `ask-hdb eval`
command checks routing and arguments; the full answer evaluation remains planned.

Verification in the existing environment: `uv run --no-sync ruff check .` passes.
The unchanged behavior suite passes with 229 tests when the new dependency-bound
test files are excluded. Full collection fails because the new dependencies are
missing. Both requested verification commands were also attempted normally;
dependency resolution stopped them at the blocked package index. The evaluation
command was attempted with `--no-sync` and likewise cannot import its dependencies.
No new test is skipped to hide this blocker.

## Tool-call check 2026-10-20

Model: `qwen3.5:9b`

| Case | Right tool | Valid args | Cause |
|---|---|---|---|
| 1 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 2 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 3 | PASS | PASS |  |
| 4 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 5 | FAIL | FAIL | Not run: OpenAITimeoutError |
| 6 | FAIL | FAIL | Not run: OpenAITimeoutError |
| 7 | FAIL | FAIL | Not run: OpenAITimeoutError |
| 8 | FAIL | FAIL | Not run: OpenAITimeoutError |
| 9 | FAIL | FAIL | Not run: OpenAITimeoutError |
| 10 | FAIL | FAIL | Not run: OpenAITimeoutError |

Routing score: 1/10. This checks routing and arguments; answer grounding still needs manual review.

## Tool-call check 2026-10-20

Model: `qwen3.5:9b`

| Case | Right tool | Valid args | Cause |
|---|---|---|---|
| 1 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 2 | PASS | PASS |  |
| 3 | PASS | PASS |  |
| 4 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 5 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 6 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 7 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 8 | PASS | FAIL | Invalid or incorrect arguments, or unavailable data |
| 9 | PASS | PASS |  |
| 10 | PASS | PASS |  |

Routing score: 4/10. This checks routing and arguments; answer grounding still needs manual review.

## Tool-call check 2026-10-20

Model: `qwen3.5-9b-16k`

| Case | Right tool | Valid args | Cause |
|---|---|---|---|
| 1 | PASS | FAIL | town: got 'Tampines', want 'TAMPINES'; flat_type: got '4 Room', want '4 ROOM' |
| 2 | PASS | PASS |  |
| 3 | PASS | PASS |  |
| 4 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000; category: got None, want 'standard'; tool returned an error |
| 5 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000; category: got None, want 'standard'; tool returned an error |
| 6 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000; category: got None, want 'standard'; tool returned an error |
| 7 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000; category: got None, want 'standard' |
| 8 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000; category: got None, want 'standard'; tool returned an error |
| 9 | PASS | PASS |  |
| 10 | PASS | PASS |  |

Routing score: 4/10. This checks routing and arguments; answer grounding still needs manual review.

## Tool-call check 2026-10-20

Model: `qwen3.5-9b-16k`

| Case | Right tool | Valid args | Cause |
|---|---|---|---|
| 1 | PASS | PASS |  |
| 2 | PASS | PASS |  |
| 3 | PASS | PASS |  |
| 4 | PASS | PASS |  |
| 5 | PASS | FAIL | price: got None, want 600000; category: got None, want 'standard' |
| 6 | PASS | FAIL | category: got None, want 'standard' |
| 7 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000; category: got None, want 'standard' |
| 8 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000 |
| 9 | PASS | PASS |  |
| 10 | PASS | PASS |  |

Routing score: 6/10. This checks routing and arguments; answer grounding still needs manual review.

## Tool-call check 2026-10-20

Model: `qwen3.5-9b-16k`

| Case | Right tool | Valid args | Cause |
|---|---|---|---|
| 1 | PASS | PASS |  |
| 2 | PASS | PASS |  |
| 3 | PASS | PASS |  |
| 4 | PASS | FAIL | category: got None, want 'standard' |
| 5 | PASS | FAIL | price: got None, want 600000; category: got None, want 'standard' |
| 6 | PASS | PASS |  |
| 7 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000; category: got None, want 'standard' |
| 8 | PASS | FAIL | family_timers: got None, want 'both_first'; price: got None, want 600000 |
| 9 | PASS | PASS |  |
| 10 | PASS | PASS |  |

Routing score: 6/10. This checks routing and arguments; answer grounding still needs manual review.

## Week 2 result (2026-10-20), model `qwen3.5-9b-16k` on the MacBook (Ollama, thinking off)
The 5090 was busy, so `qwen3.8:27b` was NOT tested. Only one model was tested, not two.

Setup facts that mattered:
- Ollama defaults to a 4096-token context; one request with the tool schemas is about 3,200 tokens.
  Fix: `scripts/ollama/qwen3.5-9b-16k.Modelfile` (16k context).
- Thinking on: 20 to 50 s per call and sloppier arguments. Thinking off (`reasoning_effort=none`) is the default.

Tool-call check (`scripts/tool_call_check.py`, 10 prompts): right tool 10/10, right arguments 6/10.
The misses are all the model leaving out optional fields (`price`, `category`, `family_timers`)
on the rule tools. Casing ("Tampines") and bare years ("2025") were fixed in code, not in the prompt.

10 hand-written questions end to end (`scripts/run_questions.py`, answers in `eval/reports/`):
- Every question called the right tool, none hit the step or token limit, and numbers checked by eye match
  the tool results. Q1 matches the raw-data fact (892 sales, median 668,000).
- Q3 miss (fixed): the model said "in this block" when the tool had widened to street level.
  Fixed with a prompt rule to state level and sample size; the rerun now says so.
- Q4, Q5, Q7, Q8 miss: the model dropped `price` and `category`. Verdicts did not change here, but
  it can in other cases. Cause: 9B model skips optional tool fields. Next: test the 27B, make these fields required.
- Q8 answer repeated the $600,000 price from the question although the tool never received it.
- Not scored: number grounding by code (`grounding.py` is week 3).
Exit check: NOT met at 10/10. Misses are written down above.

## Review fixes (Opus review, 2026-10-20)
- Token budget counted bytes as tokens and over-counted about 3x, so a normal `find_sales` stopped the agent
  after about 4K real tokens. Now bytes are used only until the model reports real usage; budget 64K;
  `find_sales` default limit 10; chat history trimmed to 6 messages. Test added with realistic usage.
- The model may now write its answer after the 8th tool call (one last call with no tools).
- `chat` survives provider errors; tool wrapper prints the real exception to stderr.
