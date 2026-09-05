# Model Benchmark Report

## 1. Models and 

- **Models / providers compared:** (free tiers only)
  | Model | Provider |
  |---|---|
  | huggingface/Qwen/Qwen3.8-27B | Huggingface |
  | openrouter/nvidia/nemotron-3-ultra-550b-a55b:free | OpenRouter |
  | openrouter/minimax/minimax-m3:free | OpenRouter |
  | openrouter/inclusionai/ling-3.0-flash-fin:free | OpenRouter |
  | openrouter/minimax/minimax-m2.7:free | OpenRouter |
- **Tested on:**
  - `sympy__sympy-14711`
  - `django__django-15104`
  - `pydata__xarray-4629`

**These test were used because they vary from one to another.**

## 2. Results Table

Grid: 5 models × 3 tasks (each model runs every task).

### sympy__sympy-14711

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| Qwen/Qwen3.8-27B | True | 18 | 188 742 | 6650 | 856 |
| minimax-m3 | — | — | — | — | — |
| laguna-s-2.1 | — | — | — | — | — |
| inkling | — | — | — | — | — |
| ling-3.0-flash-fin | — | — | — | — | — |

### django__django-15104

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| Qwen/Qwen3.8-27B | — | — | — | — | — |
| minimax-m3 | — | — | — | — | — |
| laguna-s-2.1 | — | — | — | — | — |
| inkling | — | — | — | — | — |
| ling-3.0-flash-fin | — | — | — | — | — |

### pydata__xarray-4629

| Model | Pass/Fail | Iterations | Total input tokens | Total output tokens | Wall-clock time |
|---|---|---|---|---|---|
| Qwen/Qwen3.8-27B | — | — | — | — | — |
| minimax-m3 | — | — | — | — | — |
| laguna-s-2.1 | — | — | — | — | — |
| inkling | — | — | — | — | — |
| ling-3.0-flash-fin | — | — | — | — | — |

## 3. Provider Reliability

| Model | Avg response time / request | Retries | Availability |
|---|---|---|---|
| nemotron-3-ultra-550b-a55b | — | — | — |
| minimax-m3 | — | — | — |
| laguna-s-2.1 | — | — | — |
| inkling | — | — | — |
| ling-3.0-flash-fin | — | — | — |

## 4. Intermediary Metrics (at least 2)

| Metric | sympy-14711 | sympy-13480 | xarray-4629 |
|---|---|---|---|
| Exploration: step first reads/edits file in final patch | — | — | — |
| Partial progress: step test failures first decrease | — | — | — |
| Submission discipline: steps between "tests pass" and `final_answer` | — | — | — |

## 5. Ablation Study

Planned: system prompt with worked debugging example vs. bare "solve this bug" prompt, same model, same 3 tasks.

Result: —

## 6. Conclusions

To be written once runs are complete and data is in.
