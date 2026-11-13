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
- **Pack fusion, CAD + engineering** (`evals/fusion/`, FUSE_RULE fixed before): a planner (Qwen3-8B) splits a
  problem into a calculation for a numeric pack and a part for the CAD pack. On 40 problems written for it: fusion
  18/40, the CAD pack alone 18/40 (paired 95% -8 to +8): not built. With the correct numbers handed over, the same
  plans reach 32/40; the calculation step was right on 23/40.
- **Fusion round 3** (the coder does the calculation step, FUSE3_RULE): 22/40 vs the CAD pack alone 17/40 (paired
  95% -4 to +14): not built either; with the right numbers handed over, 34/40.
- **Unit checks from the question** (UNITS2_RULE): units asked as symbols and the quantity asked now count as
  something to check; on 698 fresh SciBench answers 10 wrong answers newly caught for 1 right one flagged: shipped.
- **SQL flags confirmation on BIRD** (CONFIRM_RULE fixed before any answer): on 1035 BIRD dev questions mini-dev
  doesn't use (2025-11-06 revision; 1 dropped), the shipped policy 534 (51.6%) at 112% compute vs the coder alone
  528 (51.0%), -1 to +13 paired 95%. The rule reverts only if the coder alone is clearly ahead: confirmed, kept.
  Reported: 4B alone 357, 4B -> coder on any flag 478, hindsight 584. `results/bench_bird_rest__*`, `results/sql_confirm.log`.
- **Dropping the "huge" flag: not adopted** (NOHUGE_RULE, fixed before; non-inferiority, at most 3 of 3000 worse at
  the low end). On 2999 sampled Spider train questions: shipped 2450 (81.7%), without "huge" 2448 (1 won, 3 lost,
  -6 to +2 paired 95%), 4B asked 375 times instead of 432; coder alone 2440. The 7-1 edge on seen data didn't hold.
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

## Follow-up answer wording, set 2 (2026-11-09)
FOLLOWUP2_RULE, committed with the 100 conversations before any answer (14546bf; `evals/followup/build2.py`, keys
computed in code): ship rewrite-first (B) only if the paired bootstrap 95% of B - A is entirely above 0, else keep
today's wording (A). Result: A 75/100 (12388 tokens), B 75/100 (14872 tokens), B - A +0, 95% -12 to +12 -> **keep A**.
By pack (A/B): aerospace 25/21, electrical 24/26, physics 26/28 (reported, not decisive). Reproduce:
`.venv/bin/python evals/followup/run.py --set 2 --report`.

## General pack context window (2026-11-09)
CONTEXT_RULE, committed before measuring (8b289ec, `evals/context/measure.py`): a ~7000-token conversation with a
code word in its first message, qwen3:8b at each num_ctx. 4096: Ollama cut the prompt to 3975 tokens and the code
word was lost (5.30 GB). 8192: 5.97 GB, 16384: 6.62 GB, 32768: 7.57 GB, 40960: 8.22 GB, all recalled it -> ship,
cap 40960. Shipped as on-demand: `plm/general/controller.py:context_options` passes num_ctx (8192/16384/32768/40960)
only when chars/3 + the reply budget exceeds 4096, so short chats keep sharing the copy the user's assistant keeps
loaded. Live: the real pack recalled the code word from 6948 prompt tokens (loaded at 16384).

## Unit symbols with negative exponents (2026-11-10)
`plm/numeric/expected.py` now reads "in cm^-1", "in s^-1", "in cm⁻¹" (negative exponents, and the centi/deci
prefixes) as asked units; before, "frequency ... in cm^-1" got an inferred Hz. Replayed old vs new `check_expected`
on 5436 saved answers (2632 right; own sets, SciBench, TheoremQA, UGPhysics, units_fresh): 228 questions change
expected unit; 6 wrong answers newly caught, 2 right answers newly flagged (a bare count for "in mm^-3"; "kJ/mol"
graded right for "in mol^-1"), 2 wrong answers no longer flagged (the cm^-1 ones, flagged before only for not being
Hz). Judged against UNITS2_RULE's limits (false <= 0.5% of right: 0.08%; caught >= 2x false: 6 vs 2): passes. Note:
those limits were applied after this replay was seen, not fixed for it in advance; ships with plm-core 0.1.4.

## Physics routing attempt 2 (2026-11-10)
PHYS2_RULE, the 60 new cases (`evals/router/physics_cases2.jsonl`) and the baseline committed first (c731906); the
attempt was fixed in that commit as attempt 1's reverted diff plus its three named leftovers ("launched", "rev/s",
radiating black body). Baseline physics 33/40, others 18/20. With the change: physics 37/40 (needed 36), others
18/20, eval texts 279/279, holdout 193/194 (was 188) -> ship. The baseline misses were printed once before the
attempt was committed (disclosed in the test). Still missed: an orbit question (aerospace), Carnot efficiency and a
half-life fraction (general); ISA density and nozzle expansion (aerospace) go to physics.
`.venv/bin/python evals/test_physics_routing2.py -v`.

## Follow-up wording, set 3: variant C ships (2026-11-10)
FOLLOWUP3_RULE and 90 new conversations committed first (8eae9eb; `evals/followup/build3.py`). C = rewrite first only
when the follow-up asks for a quantity of another dimension than the earlier question; else today's wording (A).
A 47/90 (12619 tokens), B (always rewrite) 58/90 (15613), C 51/90 (13357). C - A +4, paired 95% +1 to +8 -> ship C.
By kind (A/B/C): value 30/36/30 of 42, quantity 1/6/5 of 28, unit 12/13/12 of 16, two changes 4/3/4 of 4.
Shipped as `plm.followup.phrase` (server, CLI, interface); the rewrite runs only for a new kind of quantity, and
falls back to today's task if it fails. Live (fresh conversation): "and its kinetic energy, in joules?" after a
momentum question was rewritten to a full question and answered 24 J. `.venv/bin/python evals/followup/run.py --set 3 --report`.

## Unit prefixes in code, and general-pack routing for follow-ups (set 4, 2026-11-12)
Rules, 83 new conversations and both fixes (off) committed first (8496f10); `evals/followup/run4.py`,
`evals/si_regression.py`. C = shipped pipeline, D = C + ROUTE_FIX, E = D + si, F = C + si.
C 66/83, D 66/83, E 74/83, F 74/83. FOLLOWUP4_RULE: D - C +0 (95% -3 to +3) -> ROUTE_FIX not shipped (messages to
general fell 10 -> 3, but the general pack's prose answers, graded leniently, were already right). SI_RULE: (a) F - C
+8 (95% +4 to +13) pass; (b) own-set problems whose text has a prefix (66 of 150), si off -> on: electrical 23 -> 23,
aerospace 14 -> 16, physics 14 -> 19 (+7, need >= -2) pass -> `plm.numeric.si` shipped (ENABLED = True). By kind
with si: value 38/39, unit 16/16, two 4/5, quantity 16/23. Live: "A 2.4 kW oven runs on 230 V ... in milliamperes?"
gave 10.43 mA with si off (marked trusted) and 10434.8 mA with it on.

## Follow-ups, set 5: always-rewrite, and single models alone (2026-11-13)
Set (80 conversations, `evals/followup/build5.py`), FOLLOWUP5_RULE and the comparison's method committed first
(7f04a97). Shipped plm 0.1.4 (S) 69/80, always-rewrite (R) 64/80; R - S -5, paired 95% -12 to +2 -> keep shipped.
Single models as plain chatbots on the same conversations (`evals/followup/baselines5.py`; whole conversation in
one prompt, the packs' ANSWER format, no router, calculator, checks or rewrite): qwen3:8b 76/80, qwen2.5-coder:14b
75/80, qwen3:8b with thinking 54/55 (partial, stopped by the 05:30 deadline). Paired against plm: 8B alone +7 (95%
+1 to +13), coder alone +6 (-1 to +13); these intervals were computed after the results, no rule was fixed for them.
By kind (plm / 8B alone): value 36/39 of 41, quantity 12/17 of 18, unit 14/14, two changes 7/6 of 7. Tokens: plm
9281, 8B alone 12061, coder alone 19821. On follow-up conversations the packs currently cost accuracy.

## Unit prefixes on the public physics benchmarks (2026-11-13)
`evals/bench_si.py`, method fixed first (7f04a97): the shipped physics pack on the 105 SciBench, TheoremQA and
UGPhysics (first sample) problems whose text has a unit prefix, si off -> on: SciBench 18 -> 17 of 29, TheoremQA
11 -> 12 of 36, UGPhysics 10 -> 12 of 40; total +2 (limit for turning it off: below -3) -> si stays on.
