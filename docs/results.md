# Results on public benchmarks

Every number comes from saved answers in `results/bench_*` and is reproduced, with no model calls, by
`.venv/bin/python evals/headline.py`. Each pack's policy and adoption rule were committed before the
benchmark ran (`evals/bench_*.py`); all models run locally through Ollama at temperature 0 on a 24 GB
Apple-silicon Mac. Models: Qwen3-4B (Q4_K_M), Qwen3-8B, Qwen2.5-Coder-14B.

| Pack | Benchmark | 4B | 8B | Coder 14B | Ships | Hindsight |
|---|---|---|---|---|---|---|
| SQL | Spider dev (300 sampled) | 197/299 (66%) | 201/299 (67%) | 228/299 (76%) | 228/299 (76%): coder alone | 242/299 (81%) |
| SQL | BIRD mini-dev | 155/496 (31%) | 172/496 (35%) | 254/496 (51%) | 254/496 (51%): coder alone | 295/496 (59%) |
| Software | HumanEval+ and MBPP+ | 335/540 (62%) | 353/540 (65%) | 410/540 (76%) | 410/540 (76%): coder alone | 443/540 (82%) |
| Physics | SciBench physics | 63/144 (44%) (+calc) | 68/144 (47%) (+calc) | not run | 69/144 (48%): 4B+calc -> 8B+calc (routed) | 99/144 (69%) |
| Physics | TheoremQA physics (confirmation) | 43/112 (38%) | 47/112 (42%) (+calc) | not run | 48/112 (43%): 4B+calc -> 8B+calc (routed) | 73/112 (65%) |
| CAD | CADPrompt (195 parts) | 18/195 (9%) | 12/195 (6%) | 28/195 (14%) | 28/195 (14%): coder alone | 39/195 (20%) |
| General | GSM8K (300 sampled) | 256/300 (85%) (+calc) | 272/300 (91%) | not run | 272/300 (91%): general pack: 8B direct | 285/300 (95%) |

Model columns show each model's better strategy (direct or +calc) where both ran.

- **Ships** is the pack's current policy replayed on the same answers; **hindsight** counts a task
  right if any setup got it right, the most any router over these setups could reach.
- **Grades.** SQL: rows on the real database must equal the gold query's, same column order (stricter
  than Spider's and BIRD's official grades, which forgive column order; scores read lower). Code: the
  EvalPlus plus tests. Physics: SciBench's own rule, the number within 5% in the stated unit. GSM8K:
  exact number.
- **Dropped:** gold queries that error on their own database (Spider 1, BIRD 2) and reference solutions
  that fail their own tests (HumanEval-32, Mbpp-590). BIRD lists two questions twice; each counts once.
- **CADPrompt** (github.com/Kamel773/CAD_Code_Generation, 200 parts; 195 references build in our kernel): graded
  on bounding box and volume within 0.1%, far stricter than CADPrompt's own point-cloud metrics, so scores are
  not comparable with its paper. The cascades scored 35/195 vs the coder's 28 (0 to +14, paired 95%) at 1.5x
  compute: not clearly better, so the CAD pack keeps the coder.
- **TheoremQA physics** (112 numeric problems, unseen when SciBench chose the physics switch) confirms it:
  48 vs 46 for the old policy, at 42% of its compute.
- **No public benchmark found for electrical or aerospace** that fits (numeric, unit-bearing engineering
  problems): TheoremQA's EECS subset is signals, graphs and networking; aerospace searches found corpora only.
- **SQL result flags** (`evals/bench_sql_check.py`, FLAGS_RULE fixed before): on 2880 Spider questions no model had
  answered (733 unsampled dev, 2147 test), the coder alone 2212 (76.8%); the coder with a 4B second opinion when its
  query's result on the real database looks wrong (error, no rows, over 100 rows, all NULL, none of the question's
  tables) 2230 (77.4%), +7 to +30 paired 95%, at 105% compute: adopted. The 4B first with the coder on a flag: 1990.
  It needs the user's database, so the pack uses it only when one is given (`plm --sql-db`, `PLM_SQL_DB`).
- **SQL flags confirmation on BIRD** (CONFIRM_RULE fixed before any answer): on 1035 BIRD dev questions mini-dev
  doesn't use (2025-11-06 revision; 1 dropped), the shipped policy 534 (51.6%) at 112% compute vs the coder alone
  528 (51.0%), -1 to +13 paired 95%. The rule reverts only if the coder alone is clearly ahead: confirmed, kept.
  Reported: 4B alone 357, 4B -> coder on any flag 478, hindsight 584. `results/bench_bird_rest__*`, `results/sql_confirm.log`.
- **What changed because of these:** SQL and software moved to the coder alone; physics moved from the
  8B answering directly (52/144) to the routed calculator policy; GSM8K left the general pack as it is.

# Against published scores from other models

From `evals/compare_published.py` (retrieved 2026-10-24). Published rows are other people's runs with their own
prompts (some with chain-of-thought), mostly 2023-2024 models, so this is indicative, not a controlled comparison.

### Code: HumanEval+ and MBPP+ (EvalPlus plus tests, pass@1)

| Model | HumanEval+ | MBPP+ | Where |
|---|---|---|---|
| GPT-4o (Aug 2024) | 87.2 | 72.2 | published (EvalPlus) |
| Qwen2.5-Coder-32B-Instruct | 87.2 | 77.0 | published (EvalPlus) |
| Qwen2.5-Coder-14B (Q4_K_M) | 85.3 | 71.9 | ours, local (the software pack ships this) |
| GPT-4o mini (Jul 2024) | 83.5 | 72.2 | published (EvalPlus) |
| DeepSeek-Coder-V2-Instruct (236B MoE) | 82.3 | 75.1 | published (EvalPlus) |
| Claude 3.5 Sonnet (Jun 2024) | 81.7 | 74.3 | published (EvalPlus) |
| CodeQwen1.5-7B-Chat | 78.7 | 69.0 | published (EvalPlus) |
| Claude 3 Opus (Mar 2024) | 77.4 | 73.3 | published (EvalPlus) |
| Qwen3-8B (Q4_K_M) | 74.8 | 61.3 | ours, local |
| Llama-3-70B-Instruct | 72.0 | 69.0 | published (EvalPlus) |
| Qwen3-4B (Q4_K_M) | 71.2 | 58.1 | ours, local |
| GPT-3.5-Turbo (Nov 2023) | 70.7 | 69.7 | published (EvalPlus) |
| Llama-3-8B-Instruct | 56.7 | 54.8 | published (EvalPlus) |

### SQL: BIRD mini-dev, SQLite, execution accuracy (BIRD's EX rule)

| Model | EX | Where |
|---|---|---|
| Qwen2.5-Coder-14B (Q4_K_M) | 54.5 | ours, local, 483 questions (the SQL pack ships this) |
| GPT-4 | 47.8 | published (BIRD mini-dev README, baseline) |
| GPT-4-32k | 47.0 | published (BIRD mini-dev README, baseline) |
| GPT-4-Turbo | 45.8 | published (BIRD mini-dev README, baseline) |
| Llama-3-70B-Instruct | 40.8 | published (BIRD mini-dev README, baseline) |
| GPT-3.5-Turbo | 38.0 | published (BIRD mini-dev README, baseline) |
| Qwen3-8B (Q4_K_M) | 35.7 | ours, local, 484 questions |
| Qwen3-4B (Q4_K_M) | 35.0 | ours, local, 483 questions |
| Phi-3-medium-128k-instruct | 30.6 | published (BIRD mini-dev README, baseline) |
| Llama-3-8B-Instruct | 24.4 | published (BIRD mini-dev README, baseline) |
| Mixtral-8x7B | 21.6 | published (BIRD mini-dev README, baseline) |

- **BIRD caveat:** our EX counts 483-484 of the 500 questions: questions whose gold result exceeds the
  sandbox's 1000-row cap, or whose gold query errored or timed out, are left out. Counting every left-out
  question as wrong, over all 500: coder 52.6%, 8B 34.6%, 4B 33.8%. The coder still leads GPT-4's 47.8%.
- **Code:** the same EvalPlus plus tests and greedy decoding; our prompt is the software pack's, not EvalPlus's.
- Not compared: Spider (no matching small-model leaderboard for this setup), SciBench and GSM8K (published
  scores use different prompting, sampling and model generations).
