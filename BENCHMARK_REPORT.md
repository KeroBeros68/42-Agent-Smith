# Model Benchmark Report

![SWE-bench banner](https://miro.medium.com/v2/resize:fit:1100/format:webp/1*swC3McOWbd6uZsUCqQmG3g.png)

## 1. Models and tests

- **Models / providers compared:** (free tiers only)

  | Model | Provider | Access |
  |---|---|---|
  | codestral-latest | Mistral AI | `api.mistral.ai/v1` |
  | ministral-8b-latest | Mistral AI | `api.mistral.ai/v1` |
  | gemini-3.1-flash-lite | Google Gemini | `generativelanguage.googleapis.com` |
  | gemini-3.5-flash-lite | Google Gemini | `generativelanguage.googleapis.com` |
  | gemini-3.8-flash | Google Gemini | `generativelanguage.googleapis.com` |
  | dots-3-note-preview:free | OpenRouter · dots-studio | `openrouter.ai/api/v1` |
  | nemotron-3.5-lightning:free | OpenRouter · NVIDIA | `openrouter.ai/api/v1` |
  | kimi-k3 | NVIDIA NIM | `integrate.api.nvidia.com` |

> 8 models across **4 independent providers**, so a single quota wall cannot stall the whole grid.

- **Tested on** (5 SWE-bench Verified instances, 4 distinct repositories):

  | Task | Repository | Domain | Test runner |
  |---|---|---|---|
  | `sympy__sympy-14711` | sympy/sympy | symbolic math — `Vector` arithmetic | sympy `bin/test` |
  | `sympy__sympy-18189` | sympy/sympy | symbolic math — diophantine solvers | sympy `bin/test` |
  | `django__django-15104` | django/django | web framework — migration autodetector | unittest |
  | `pydata__xarray-4629` | pydata/xarray | scientific arrays — merge semantics | pytest |
  | `scikit-learn__scikit-learn-13439` | scikit-learn/scikit-learn | ML — pipeline parameter validation | pytest |

**Why these tasks.** Three reasons, all aimed at not letting a model coast on one familiar codebase:

1. **Diversity and inclusion <3.** The tasks are from four different and unrelated codebases, with different specialisations. Therefore, a model cannot rely on its knowledge of a single domain to have a higher ranking than the other ones.
2. **Three different test-runner conventions.** sympy's own `bin/test`, Django's `unittest`, and `pytest` produce three different pass/fail wordings. The agent must interpret all of them from raw stdout — this exercises the sandbox's feedback loop, not just the model.
3. **A difficulty spread.** All five are SWE-bench Verified (human-validated), and the grid deliberately mixes quieter tasks (`django__django-15104`, `pydata__xarray-4629`) with harder ones (`sympy__sympy-14711`, `sympy__sympy-18189`) so the report shows where models separate rather than a wall of identical outcomes.

## 2. Results Table

Grid: **8 models × 5 tasks = 40 runs** (every model ran every task). All 40 `solution.json` files are in [`docs/benchmarks/models_outputs/`](docs/benchmarks/models_outputs/).

« Pass/Fail » is what the model's own run recorded (pass when it calls the final_answer() function). « Moulinette » provided in the subject and verifies that the generated patch is correct with `uv run moulinette_eval validate swebench <task.json> <solution.json>`: correctness (patch applied in a clean SWE-bench container and graded) **and** metrics (iterations ≤ 30, input ≤ 300,000, output ≤ 10,000, time ≤ 900 s). A cell passes only when both steps pass. **All 40 cells were re-validated this way; only 16 pass.**

### sympy__sympy-14711

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| codestral-latest | ❌ Fail | ❌ Fail | 17 | 303,486 | 8,588 | 143.0 s |
| dots-3-note-preview | ❌ Fail | ❌ Fail | 25 | 168,959 | 10,046 | 156.2 s |
| gemini-3.1-flash-lite | ❌ Fail | ❌ Fail | 20 | 176,791 | 10,057 | 132.8 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 21 | 256,790 | 1,311 | 60.2 s |
| gemini-3.8-flash | ❌ Fail | ❌ Fail | 3 | 5,845 | 1,503 | 79.3 s |
| kimi-k3 | ❌ Fail | ❌ Fail | 0 | 0 | 0 | 15.4 s |
| ministral-8b-latest | ❌ Fail | ❌ Fail | 7 | 32,300 | 2,632 | 56.7 s |
| nemotron-3.5-lightning | ❌ Fail | ❌ Fail | 1 | 1,559 | 13,787 | 316.0 s |

### sympy__sympy-18189

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| codestral-latest | ❌ Fail | ❌ Fail | 18 | 146,422 | 10,247 | 117.4 s |
| dots-3-note-preview | ✅ Pass | ✅ Pass | 15 | 119,719 | 2,195 | 92.2 s |
| gemini-3.1-flash-lite | ❌ Fail | ✅ Pass | 22 | 143,203 | 6,104 | 117.0 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 9 | 153,213 | 1,019 | 87.8 s |
| gemini-3.8-flash | ❌ Fail | ❌ Fail | 21 | 320,613 | 27,734 | 553.7 s |
| kimi-k3 | ❌ Fail | ❌ Fail | 0 | 0 | 0 | 15.6 s |
| ministral-8b-latest | ❌ Fail | ❌ Fail | 14 | 321,733 | 10,776 | 209.0 s |
| nemotron-3.5-lightning | ❌ Fail | ❌ Fail | 8 | 61,683 | 10,643 | 273.1 s |

### django__django-15104

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| codestral-latest | ❌ Fail | ❌ Fail | 14 | 105,486 | 10,391 | 121.2 s |
| dots-3-note-preview | ✅ Pass | ✅ Pass | 6 | 35,741 | 1,141 | 53.4 s |
| gemini-3.1-flash-lite | ✅ Pass | ✅ Pass | 9 | 57,869 | 1,707 | 51.7 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 6 | 40,103 | 553 | 40.1 s |
| gemini-3.8-flash | ✅ Pass | ✅ Pass | 9 | 95,710 | 1,813 | 157.6 s |
| kimi-k3 | ❌ Fail | ❌ Fail | 0 | 0 | 0 | 16.1 s |
| ministral-8b-latest | ✅ Pass | ✅ Pass | 14 | 75,264 | 1,572 | 66.2 s |
| nemotron-3.5-lightning | ✅ Pass | ✅ Pass | 6 | 48,921 | 7,988 | 290.4 s |

### pydata__xarray-4629

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| codestral-latest | ✅ Pass | ✅ Pass | 9 | 137,026 | 6,208 | 108.6 s |
| dots-3-note-preview | ❌ Fail | ❌ Fail | 30 | 107,255 | 4,770 | 115.4 s |
| gemini-3.1-flash-lite | ❌ Fail | ❌ Fail | 2 | 6,421 | 1,710 | 19.3 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 6 | 42,222 | 358 | 52.1 s |
| gemini-3.8-flash | ❌ Fail | ❌ Fail | 7 | 34,990 | 1,129 | 90.2 s |
| kimi-k3 | ❌ Fail | ❌ Fail | 0 | 0 | 0 | 15.2 s |
| ministral-8b-latest | ✅ Pass | ✅ Pass | 6 | 36,455 | 787 | 37.5 s |
| nemotron-3.5-lightning | ❌ Fail | ❌ Fail | 3 | 6,795 | 20,181 | 628.0 s |

### scikit-learn__scikit-learn-13439

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| codestral-latest | ✅ Pass | ✅ Pass | 9 | 77,607 | 1,454 | 49.2 s |
| dots-3-note-preview | ✅ Pass | ✅ Pass | 12 | 75,704 | 1,309 | 55.8 s |
| gemini-3.1-flash-lite | ❌ Fail | ❌ Fail | 2 | 13,393 | 9,671 | 52.5 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 9 | 69,618 | 565 | 55.8 s |
| gemini-3.8-flash | ❌ Fail | ❌ Fail | 14 | 95,749 | 1,149 | 259.3 s |
| kimi-k3 | ❌ Fail | ❌ Fail | 0 | 0 | 0 | 15.6 s |
| ministral-8b-latest | ❌ Fail | ❌ Fail | 19 | 333,454 | 9,808 | 178.9 s |
| nemotron-3.5-lightning | ❌ Fail | ❌ Fail | 1 | 1,783 | 13,256 | 347.9 s |

Moulinette failure reasons, by cause:

- **Budget overruns (metrics INVALID).** `output > 10,000`: codestral (django 10,391; sympy-18189 10,247), dots-3-note-preview (sympy-14711 10,046), gemini-3.1-flash-lite (sympy-14711 10,057), gemini-3.8-flash (sympy-18189 27,734), ministral (sympy-18189 10,776), and **all four of nemotron's failures** (xarray 20,181; scikit-learn 13,256; sympy-14711 13,787; sympy-18189 10,643). `input > 300,000`: codestral (sympy-14711 303,486), gemini-3.8-flash (sympy-18189 320,613), ministral (scikit-learn 333,454; sympy-18189 321,733).
- **Patch does not resolve the issue (correctness FAILED, metrics VALID).** dots-3-note-preview (xarray), gemini-3.1-flash-lite (xarray, scikit-learn), gemini-3.8-flash (xarray, scikit-learn, sympy-14711), ministral (sympy-14711). Metrics were fine — the submitted patch simply does not fix the bug in a clean container.
- **No patch at all.** kimi-k3 failed all 5 tasks with an empty solution: the provider returned HTTP 429 on every attempt, so the agent never received a single LLM response (0 steps, 0 tokens).
- **The agent's self-report never lies about success — but it does miss it once.** Across all 40 runs, **not a single run self-reported ✅ Pass while the moulinette disagreed**: every self-reported success is a moulinette success. The reverse happened once — **gemini-3.1-flash-lite × `sympy__sympy-18189` reports ❌ Fail while the moulinette grades it ✅ Pass**: the patch is correct, but the agent never observed a green `run_tests()` in its own trace, so its success heuristic stayed `False` (see §4). The heuristic is conservative rather than optimistic, which is the safe direction — it costs a pass, never a false claim.

## 3. Provider Reliability

| Model | Avg response time / request | Retries | Availability |
|---|---|---|---|
| codestral-latest | 5.82 s | 0 | 100% (5/5) |
| ministral-8b-latest | 6.66 s | 0 | 80% (4/5) |
| gemini-3.1-flash-lite | 5.52 s | 3 | 100% (5/5) |
| gemini-3.5-flash-lite | 2.73 s | 0 | 100% (5/5) |
| gemini-3.8-flash | 18.57 s | 23 | 40% (2/5) |
| dots-3-note-preview | 3.45 s | 1 | 100% (5/5) |
| nemotron-3.5-lightning | 92.96 s | 0 | 100% (5/5) |
| kimi-k3 | — | 0 | 0% (0/5) |

> *Avg response time* = mean `StepMetrics.request_time_ms` over every step that returned, across all 5 tasks. *Retries* = sum of `StepMetrics.retries`. *Availability* = share of the 5 tasks that completed without a provider/rate-limit error.

Notes:

- **All providers used are free tiers**, and every key is loaded from environment variables — no key is hard-coded.
- **kimi-k3 could not be measured at all.** Every one of its 5 tasks died at the first LLM call with `RateLimitError: Error code: 429 - Too Many Requests` (NVIDIA NIM). With 0 steps recorded, it contributes no latency and no retries — its `retries: 0` means "never reached the API", not "the API was healthy". It is excluded from the latency average.
- **gemini-3.8-flash is the least reliable available provider**: 23 retries and 3 of 5 tasks killed by `LLM call failed`. Its successful calls are also ~3× slower than its sibling gemini-3.5-flash-lite.
- **nemotron-3.5-lightning is reliable but extremely slow**: 100% availability, yet ~93 s per request (34× gemini-3.5-flash-lite) — it never hit a rate limit, it just takes a long time.
- Retries are counted per step as recorded in `solution.json`; a task killed before its first successful call records `0` retries by construction.

## 4. Intermediary Metrics (at least 2)

Both metrics are measured from the `solution.json` step traces (sandbox_input / sandbox_output), manually — no tooling was added to the agent. Only runs that produced a patch (exploration) or reached a green test run followed by `final_answer` (discipline) can be measured; the rest are « — ».

### Exploration efficiency

Step at which the agent first reads or edits a file that appears in its final patch (first `read_file` / `edit_file` on that file).

| Model | sympy-14711 | sympy-18189 | django-15104 | xarray-4629 | scikit-learn-13439 |
|---|---|---|---|---|---|
| codestral-latest | — | — | — | 2 | 2 |
| dots-3-note-preview | — | 3 | 2 | — | 2 |
| gemini-3.1-flash-lite | — | 6 | 3 | 2 | 2 |
| gemini-3.5-flash-lite | 7 | 2 | 2 | 1 | 3 |
| gemini-3.8-flash | — | — | 2 | — | — |
| kimi-k3 | — | — | — | — | — |
| ministral-8b-latest | — | — | 2 | 2 | — |
| nemotron-3.5-lightning | — | — | 2 | — | — |

### Submission discipline

Agent iterations between the step where `run_tests()` first reports a clean run and the `final_answer` step — **0 is ideal**.

| Model | sympy-14711 | sympy-18189 | django-15104 | xarray-4629 | scikit-learn-13439 |
|---|---|---|---|---|---|
| codestral-latest | — | — | — | 1 | 3 |
| dots-3-note-preview | — | 2 | 2 | — | 2 |
| gemini-3.1-flash-lite | — | — | 2 | — | — |
| gemini-3.5-flash-lite | 2 | 2 | 2 | 2 | 2 |
| gemini-3.8-flash | — | — | 2 | — | — |
| kimi-k3 | — | — | — | — | — |
| ministral-8b-latest | — | — | 2 | 2 | — |
| nemotron-3.5-lightning | — | — | 1 | — | — |

The « partial progress » metric (step at which test failures first decrease vs a baseline) is **not measurable** on this grid: the agents call `run_tests()` at most twice, nearly always once, and never take an initial failure baseline before editing — so there is no "decreasing failures" series to read.

Two observations the tables support:

- **Everyone converges on the patched file fast.** Where a patch exists, the first touch of the file that ends up in the patch happens at step 1–3 for most models — double digits only for `gemini-3.5-flash-lite × sympy-14711` (step 7, after a wrong-file detour) and `gemini-3.1-flash-lite × sympy-18189` (step 6). Cheap exploration is not where models differ.
- **Submitting promptly is the norm, but "2" is the recurring value.** Nearly every measurable run spends exactly 2 extra iterations after the first green test — almost always `get_patch()` then `final_answer()`. The two best values are `codestral-latest × xarray` (1) and `nemotron × django` (1), i.e. the agent that folds `get_patch()` into its reasoning instead of spending a whole step on it.
- **The — columns are the real signal.** They mark runs whose trace never reaches a green test run *and* a submission. `gemini-3.1-flash-lite × sympy-18189` is the striking case: it **passed the moulinette** while showing « — » for both metrics, because it submitted a correct patch without ever observing a passing `run_tests()`. Its self-reported `success: false` is therefore a false negative of the agent's own heuristic, not a failure of the model.

## 5. Ablation Study

### Setup

Three before/after comparisons of a **single** change each, on the **same tasks and the same model** — `deepseek/deepseek-v4-flash` (as a development test model), served by DeepSeek's own first-party API (`https://api.deepseek.com/beta`, key from `DEEPSEEK_API_KEY`) — on three tasks: `sympy__sympy-14711`, `django__django-15104`, `pydata__xarray-4629`.

| Config | The one thing that changes | Control |
|---|---|---|
| **C0 baseline** | nothing — reference run | — |
| **C1 prompt** | the loop injects a bare `"Solve this bug."` user message instead of leaving the full system prompt to do the work | full system prompt (tool docs + worked example) |
| **C2 tools** | `search_code`, `search_function_or_class_definition_in_code`, `find_references` are **unregistered** from the MCP server, so they vanish from the dynamically generated sandbox manual | all 9 tools exposed |
| **C3 params** | `--max-iterations 10` | `--max-iterations 30` |

All 12 runs were produced in an isolated copy of the repository, then re-graded with the moulinette, same as §2.

### Results

| Config | Task | Self-reported | Moulinette | Iterations | Input tokens | Output tokens | Time |
|---|---|---|---|---|---|---|---|
| baseline | sympy-14711 | ✅ Pass | ✅ Pass | 9 | 107,646 | 9,621 | 70.6 s |
| baseline | django-15104 | ✅ Pass | ✅ Pass | 6 | 36,611 | 882 | 38.5 s |
| baseline | xarray-4629 | ✅ Pass | ✅ Pass | 6 | 39,784 | 740 | 30.5 s |
| prompt | sympy-14711 | ❌ Fail | ❌ Fail | 1 | 1,575 | 65,546 | 260.9 s |
| prompt | django-15104 | ✅ Pass | ✅ Pass | 6 | 36,665 | 715 | 25.7 s |
| prompt | xarray-4629 | ❌ Fail | ❌ Fail | 24 | 302,492 | 5,512 | 72.0 s |
| tools | sympy-14711 | ✅ Pass | ✅ Pass | 13 | 73,104 | 5,389 | 71.9 s |
| tools | django-15104 | ✅ Pass | ✅ Pass | 7 | 37,817 | 619 | 26.5 s |
| tools | xarray-4629 | ✅ Pass | ✅ Pass | 7 | 38,181 | 689 | 30.1 s |
| params | sympy-14711 | ❌ Fail | ❌ Fail | 9 | 76,685 | 13,044 | 67.3 s |
| params | django-15104 | ✅ Pass | ✅ Pass | 6 | 36,022 | 512 | 25.2 s |
| params | xarray-4629 | ✅ Pass | ✅ Pass | 10 | 92,337 | 1,440 | 31.4 s |

Aggregated per config (mean over the 3 tasks):

| Config | Passed (moulinette) | Avg iterations | Avg input tokens | Avg output tokens | Avg time |
|---|---|---|---|---|---|
| baseline | **3 / 3** | 7.0 | 61,347 | 3,748 | 46.5 s |
| prompt | **1 / 3** | 10.3 | 113,577 | 23,924 | 119.5 s |
| tools | **3 / 3** | 9.0 | 49,701 | 2,233 | 42.8 s |
| params | **2 / 3** | 8.3 | 68,348 | 4,999 | 41.3 s |

### What each comparison shows

- **C1 — the prompt is load-bearing, and removing it is catastrophic, not gradual.** With the bare `"Solve this bug."` message the model still passes the easy Django task, but on sympy it emits a *single* 65,546-token response (6.5× the 10,000 limit) containing no tool call at all — 1 iteration, 0 exploration, 0 `run_tests()`. On xarray it runs 24 iterations and burns 302,492 input tokens (over the 300,000 cap) for nothing. This is the exact failure mode §V.1 warns about: an agent that does not know its tools cannot use them, and every iteration spent is wasted. **A system prompt that documents the tools and shows a worked loop is not decoration — it is what makes the loop function.**
- **C2 — the code-search tools are a convenience, not a lifeline.** Removing all three search tools costs **nothing** in pass rate (3/3) and costs almost nothing in resources: avg 42.8 s vs 46.5 s baseline, and *fewer* input tokens (49,701 vs 61,347). It does cost iterations — sympy goes 9 → 13 — because the model falls back to `list_files` + `read_file` to hunt for the symbol instead of `search_code`. So the search tools buy **step efficiency**, not correctness: worth keeping, but the agent degrades gracefully without them.
- **C3 — the iteration budget is a real constraint, not slack.** Cutting the cap from 30 to 10 flips `sympy-14711` from pass to fail: the run stops at the cap with 9 iterations and 13,044 output tokens, over the output budget, without converging. On the two tasks it still solves, the budget bite is visible — xarray goes 6 → 10 iterations and 39,784 → 92,337 input tokens, i.e. the same result reached with noticeably more work per iteration. A 30-iteration ceiling is genuinely needed for the harder half of this task set.

Taken together, the three ablations rank the components by how much the agent depends on them: **prompt ≫ iteration budget > search tools**.

## 6. Conclusions

Aggregated over the 5 tasks (every model ran every task). « Avg » means per task. Wall-clock times in seconds.

| Model | Tasks passed | Tasks passed (moulinette) | Avg iterations | Avg input tokens | Avg output tokens | Avg wall-clock time | Avg time / iteration |
|---|---|---|---|---|---|---|---|
| codestral-latest | 2 / 5 | 2 / 5 | 13.4 | 154,005 | 7,378 | 107.9 s | 8.1 s |
| ministral-8b-latest | 2 / 5 | 2 / 5 | 12.0 | 159,841 | 5,115 | 109.7 s | 9.1 s |
| gemini-3.1-flash-lite | 1 / 5 | 2 / 5 | 11.0 | 79,535 | 5,850 | 74.7 s | 6.8 s |
| **gemini-3.5-flash-lite** | **5 / 5** | **5 / 5** | 10.2 | 112,389 | 761 | 59.2 s | 5.8 s |
| gemini-3.8-flash | 1 / 5 | 1 / 5 | 10.8 | 110,581 | 6,666 | 228.0 s | 21.1 s |
| kimi-k3 | 0 / 5 | 0 / 5 | — | — | — | 15.6 s | — |
| dots-3-note-preview | 3 / 5 | 3 / 5 | 17.6 | 101,476 | 3,892 | 94.6 s | 5.4 s |
| nemotron-3.5-lightning | 1 / 5 | 1 / 5 | 3.8 | 24,148 | 13,171 | 371.1 s | 97.6 s |

Takeaways:

- **gemini-3.5-flash-lite is the model to keep.** It is the **only** model the moulinette confirms on all 5 tasks (5/5), and it does it while being the fastest (59.2 s/task) and by far the most economical in output (761 tokens/task — 10× under the next best). Its traces show why: many small `read_file` steps ($\approx$2.7 s/request, 5.8 s/iteration) instead of one large generation. It is also the only model that never overran a single budget on any task.
- **kimi-k3 is unusable and must be disregarded.** 0/5 with 0 steps on every task: NVIDIA NIM returned HTTP 429 on the very first call each time. This is a provider-availability result, not a model-capability one — on this grid we literally never observed the model think.
- **nemotron-3.5-lightning must be disregarded on cost.** 1/5, ~371 s per task and ~98 s per *iteration* (17× gemini-3.5-flash-lite), and all four of its failures are the same failure: a single oversized generation blowing the 10,000-output-token ceiling (up to 20,181). It is a slow, verbose model on a budgeted benchmark. Coupled with the fact that it is free-tier on OpenRouter, it is not a candidate for a quota-limited pipeline.
- **gemini-3.8-flash is disregarded on reliability.** 1/5, 40% availability, 23 retries, three tasks killed mid-run by `LLM call failed`, and the slowest successful calls among Gemini models (18.6 s/request). Its sibling `gemini-3.1-flash-lite` is more interesting: it also scores 1/5 self-reported but **2/5 moulinette**, and on `sympy__sympy-18189` it produced a **correct patch it failed to recognise as correct** — a real ceiling on the agent's own success heuristic (§4), not on the model.
- **Mistral's two models tie, and both lose to output budget.** codestral-latest and ministral-8b-latest each pass 2/5, both at ~108 s/task. Their failures share one signature: they keep generating past the 10,000-output-token limit (codestral: 2 tasks; ministral: 1 task + 1 input overrun at 333,454 tokens). Correctness was not the blocker — the budget was.
- **dots-3-note-preview is the best of the rest.** 3/5, 94.6 s/task, and the fastest per iteration (5.4 s) — but it is the one model that burned an iteration budget spinning (`xarray`: 30 iterations, no patch) and its rate-limit exposure on OpenRouter free tier is a real risk for a full exam run.

> **Preferred model: `gemini/gemini-3.5-flash-lite`** — the only model moulinette-verified on all 5 tasks, the fastest per task, the cheapest in output tokens, and the one that respects every §VI.1.2 budget on every task. Runner-up for a second provider slot: **`mistral/codestral-latest`**, for the strongest correctness among the models that miss the budget (2/5 with metrics-valid patches once overrun tasks are excluded).


![42Mulhouse](https://raw.githubusercontent.com/sousampere/sousampere/refs/heads/main/42mulhouse.png)
