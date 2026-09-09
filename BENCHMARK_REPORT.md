# Model Benchmark Report

![SWE-bench banner](https://www.swebench.com/SWE-bench/assets/figures/swellama_banner_nobg.svg)

## 1. Models and tests

- **Models / providers compared:** (free tiers only)
  | Model | Provider |
  |---|---|
  | openrouter/dots-studio/dots-3-note-preview:free | OpenRouter · Dots Studio |
  | gemini/gemini-3-flash-preview | Google Gemini |
  | gemini/gemini-3.5-flash-lite | Google Gemini |
  | openrouter/inclusionai/ling-3.0-flash-fin:free | OpenRouter · InclusionAI |
  | openrouter/nvidia/nemotron-3-ultra-550b-a55b:free | OpenRouter · NVIDIA |
- **Tested on:**
  - `sympy__sympy-14711`
  - `django__django-15104`
  - `pydata__xarray-4629`

**These are different tasks from different codebases. Using a model on various codebases ensure that it's performing on a codebase it was well trained on.**

## 2. Results Table

Grid: 5 models × 3 tasks (each model runs every task).

« Pass/Fail » is the result recorded by the model's own run. « Moulinette » is an independent re-grade with `uv run moulinette_eval validate swebench <task.json> <solution.json>`: correctness (patch applied in a clean SWE-bench container and graded) **and** metrics (iterations ≤ 30, input ≤ 300,000, output ≤ 10,000, time ≤ 900 s). A cell passes only when both steps pass.

### sympy__sympy-14711

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| dots-3-note-preview | ❌ Fail | ❌ Fail | 11 | 30,284 | 1,678 | 159.5 s |
| gemini-3-flash-preview | ❌ Fail | ❌ Fail | 1 | 1,624 | 35,003 | 278.3 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 19 | 80,858 | 1,057 | 53.1 s |
| ling-3.0-flash-fin | ❌ Fail | ❌ Fail | 30 | 70,494 | 1,298 | 127.0 s |
| nemotron-3-ultra-550b-a55b | ❌ Fail | ❌ Fail | 15 | 305,743 | 3,299 | 871.3 s |

### django__django-15104

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| dots-3-note-preview | ❌ Fail | ❌ Fail | 15 | 37,852 | 1,271 | 196.0 s |
| gemini-3-flash-preview | ❌ Fail | ❌ Fail | 1 | 2,638 | 35,992 | 224.7 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 7 | 42,501 | 489 | 55.1 s |
| ling-3.0-flash-fin | ❌ Fail | ❌ Fail | 30 | 102,341 | 1,494 | 131.7 s |
| nemotron-3-ultra-550b-a55b | ✅ Pass | ❌ Fail | 7 | 61,895 | 9,095 | 526.1 s |

### pydata__xarray-4629

| Model | Pass/Fail | Moulinette | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|---|
| dots-3-note-preview | ✅ Pass | ✅ Pass | 16 | 103,497 | 2,675 | 453.6 s |
| gemini-3-flash-preview | ❌ Fail | ❌ Fail | 2 | 11,348 | 74,341 | 493.9 s |
| gemini-3.5-flash-lite | ✅ Pass | ✅ Pass | 14 | 178,159 | 1,967 | 270.6 s |
| ling-3.0-flash-fin | ✅ Pass | ✅ Pass | 10 | 58,400 | 1,266 | 349.8 s |
| nemotron-3-ultra-550b-a55b | ❌ Fail | ❌ Fail | 3 | 15,102 | 10,817 | 583.2 s |

Moulinette failure reasons, per task:

- **dots-3-note-preview** (sympy, django): empty solution — the run was rate-limited and never submitted a patch; metrics valid.
- **gemini-3-flash-preview** (all): empty solution *and* metrics invalid — a single huge generation (~35–74k output tokens) blows the 10,000-token limit.
- **ling-3.0-flash-fin** (sympy, django): empty solution — hit the 30-iteration cap without submitting; metrics valid.
- **nemotron-3-ultra-550b-a55b** (sympy): empty solution; metrics invalid (input 305,743 > 300,000). (xarray): metrics invalid (output 10,817 > 10,000).
- **nemotron-3-ultra-550b-a55b** (django): the notable mismatch — its trace reports `success`, but the moulinette shows the patch does not apply cleanly in a fresh container → `RESOLVED_NO`.

## 3. Provider Reliability

| Model | Avg response time / request | Retries | Availability |
|---|---|---|---|
| dots-3-note-preview | 9.26 s | 252 | 33% |
| gemini-3-flash-preview | 161.71 s | 2 | 100% |
| gemini-3.5-flash-lite | 1.50 s | 28 | 100% |
| ling-3.0-flash-fin | 1.03 s | 0 | 100% |
| nemotron-3-ultra-550b-a55b | 57.85 s | 9 | 100% |

> Note : We chose providers/models that are specially reliable. The only reiability problems that can be encountered during tests are rate-limit API errors. In this case, the test is cancelled and the error is reported in the results.

> *Availability* = share of the 3 tasks that ran to completion without a provider/rate-limit error. Only `dots-3-note-preview` was affected: the OpenRouter free-tier daily limit cancelled 2 of its 3 tasks (with 252 retries recorded overall).

## 4. Intermediary Metrics (at least 2)

Two process metrics, measured per model from the `solution.json` step traces. Only runs that produced a final patch (exploration) or submitted via `final_answer` (discipline) can be measured; failed runs are marked « — ».

### Exploration efficiency

Step at which the model first reads/edits the file that ends up in its final patch (first `read_file`/`edit_file` on that file).

| Model | sympy-14711 | django-15104 | xarray-4629 |
|---|---|---|---|
| dots-3-note-preview | — | — | 6 |
| gemini-3-flash-preview | — | — | — |
| gemini-3.5-flash-lite | 3 | 3 | 2 |
| ling-3.0-flash-fin | — | — | 1 |
| nemotron-3-ultra-550b-a55b | — | 2 | — |

### Submission discipline

Agent iterations between the step where the tests first pass (`run_tests()` showing no failure) and `final_answer` — 0 is ideal. Failed runs that never submit are « — ».

| Model | sympy-14711 | django-15104 | xarray-4629 |
|---|---|---|---|
| dots-3-note-preview | — | — | 1 |
| gemini-3-flash-preview | — | — | — |
| gemini-3.5-flash-lite | 1 | 1 | 5 |
| ling-3.0-flash-fin | — | — | 2 |
| nemotron-3-ultra-550b-a55b | — | 0 | — |

The « partial progress » metric (step at which test failures first decrease) was dropped: every run calls `run_tests()` only once, at the end, with no initial failure baseline — so it is not measurable from these traces.

## 5. Ablation Study

System prompt with worked debugging example vs. bare "solve this bug" prompt, same model, same 3 tasks.

### Before a bare "solve this bug" prompt

The model run smoothly, even tho different APIs can have rate limits that makes the results look bad.

### After a bare "solve this bug" prompt

All models are unable to use a single tool, because they aren't aware of what tool is available. Therefore, they work for nothing.

## 6. Conclusions

Aggregated over the 3 tasks (every model ran every task). « Avg » means per task. Wall-clock times in seconds.

| Model | Tasks passed | Tasks passed (moulinette) | Avg iterations | Avg input tokens | Avg output tokens | Avg wall-clock time | Avg time / iteration |
|---|---|---|---|---|---|---|---|
| dots-3-note-preview | 1 / 3 | 1 / 3 | 14.0 | 57,211 | 1,875 | 269.7 s | 18.6 s |
| gemini-3-flash-preview | 0 / 3 | 0 / 3 | 1.3 | 5,203 | 48,445 | 332.3 s | 250.0 s |
| gemini-3.5-flash-lite | 3 / 3 | 3 / 3 | 13.3 | 100,506 | 1,171 | 126.3 s | 10.0 s |
| ling-3.0-flash-fin | 1 / 3 | 1 / 3 | 23.3 | 77,078 | 1,353 | 202.8 s | 14.5 s |
| nemotron-3-ultra-550b-a55b | 1 / 3 | 0 / 3 | 8.3 | 127,580 | 7,737 | 660.2 s | 109.2 s |

Takeaways:

- **gemini-3.5-flash-lite** is the only model the moulinette confirms on all 3 tasks, and does it with the lowest wall-clock time (≈126 s/task) and tiny output (≈1.2k output tokens/task) — it explores through many small `read_file` calls instead of dumping one huge generation.
- **nemotron-3-ultra-550b-a55b** reports django as passed but is the only model whose self-reported success does **not** survive the moulinette (0/3 verified): its patch fails to apply cleanly in a fresh container → `RESOLVED_NO`. It is also the heaviest and slowest (≈660 s and ≈128k input tokens per task); its sympy run alone burned 305k input tokens and 871 s without converging, and exceeds the input-token limit.
- **gemini-3-flash-preview** solves nothing (0/3): it emits a single massive response (≈48k output tokens/task, over the 10k limit) and barely runs the sandbox loop (≈1 iteration), so it never reaches a verified `final_answer`.
- **ling-3.0-flash-fin** hits the iteration cap on both of its failures (30 + 30), spinning without converging.
- **dots-3-note-preview** is the only model with provider reliability problems: rate-limited on 2 of 3 tasks (the single rate-limit-free run, xarray, is moulinette-verified).

> **Preferred model:** gemini-3.5-flash-lite — the only model whose results are confirmed by the moulinette on all three tasks, while also being the fastest and cheapest.

![42Mulhouse](https://raw.githubusercontent.com/sousampere/sousampere/refs/heads/main/42mulhouse.png)
