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
- **What changed because of these:** SQL and software moved to the coder alone; physics moved from the
  8B answering directly (52/144) to the routed calculator policy; GSM8K left the general pack as it is.
