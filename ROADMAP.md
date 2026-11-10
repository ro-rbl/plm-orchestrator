# Roadmap

Goal: a local router that is useful as a "model" (any OpenAI-compatible client
can use it), backed by benchmark results credible enough to publish.

Decided 2026-10-20: router first, then benchmarks. Packs after electrical and
software: aerospace, physics/mechanical, SQL.

## 1. Foundation
- [x] One shape for every pack: `plm/packs.py` registry; shared numeric machinery in
      `plm/numeric/`; electrical reduced to its level rules and tiers.
- [x] Answers with nothing to check are reported as unchecked, not trusted.
- [x] Offline controller tests (`evals/test_controllers.py`, Ollama replaced by scripted replies).
- [x] Standard vs abliterated builds, to pick public defaults. The small tier is now the original
      Qwen3-4B (`hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M`, same quantizer and quant as the abliterated
      build): electrical 47/50 alone with the calculator vs 43 abliterated, routed 48/50 at 35%; software
      cascade 40/45 at 56%, same as before. Instruct-2507: 47/50 routed, 41/45 cascade at 70% (longer answers).
      Ollama's `qwen3:4b` tag is Thinking-2507 and doesn't fit a cheap tier.

## 2. Router endpoint
- [x] `plm serve`: OpenAI-compatible `/v1/models` and `/v1/chat/completions` (with streaming),
      model ids `plm-router` and `plm-router-thorough`; the routing report is an extra `plm` field.
- [x] A general fallback pack for prompts no pack claims (large model, reported as unchecked), and
      three-way routing (134/134 eval texts, 49/50 holdout cases).
- [x] Port from `--port`/`PLM_PORT` or a free one printed at startup; `/health` asserts Ollama answers.
- [x] Every request logged to `logs/server.jsonl`, to see what share of real traffic each pack gets:
      if most prompts fall through to the general pack, routing saves little and the next packs
      should follow the logs.
- [x] Live test with real models and the official `openai` client 3.35.1: all 11 checks pass
      (`evals/compat_openai.py --base-url ...`), including streaming and the `plm` field.

## 3. Packs
- [x] Aerospace: 50 problems + 24 holdout, chain cues on the shared numeric classifier, four-way
      routing. Routing to the 4B lost accuracy here (37/50 vs 39/50), so the pack runs everything on
      the 8B + calculator: 39/50 at 41% of always-8B compute. Hardest: intensive (8B+calc 47%).
- [x] Physics/mechanical: `packages/plm-physics`, 50 problems + 24 holdout, chain cues on the shared
      classifier, five-way routing (generic quantity words claim but don't score, so physics yields to
      the specialists). Policies and the pick rule (cheapest within 1 problem of the best) fixed before
      the sweep: everything to the 8B answering directly, 49/50 at 100% of always-8B compute. The
      calculator lost accuracy here (8B 43/50): all 7 misses printed base-unit values under the asked
      prefixed unit, which the unit checks can't see.
- [x] SQL: `packages/plm-sql`, 45 tasks on three seeded SQLite databases + 24 level holdouts + 12 routing
      cases, all written before the pack. A query is graded on hidden data against a reference query's rows;
      the pack's check is that it runs on the task's own schema in a read-only sandbox. Policies and rule
      (cheapest within 1 task of the best) fixed before the sweep: 4B first, the coder 14B when the query
      doesn't run, 45/45 at 45% of always-coder compute (coder alone 44/45, 8B 42, 4B 40). Every wrong 4B
      query failed to run, so the check caught all of them; the set is near its ceiling. Not confirmed on 24
      harder fresh tasks (18/24 vs 22/24 for always-8B: misses that run and return wrong rows); that set's
      candidate (intensive to 8B -> coder) failed on a second fresh set (18/24 vs 22/24), so the rule fixed
      for it shipped its pooled pick: everything to the 8B, 42/48 at 60% (coder alone 42/48 at 100%).
      Public benchmarks then favored the coder clearly (Spider 76% vs 67%, BIRD 51% vs 35%); the compute-capped
      rule kept the 8B, and the user chose accuracy: the pack ships the coder alone (2026-10-24).

## 3a. Separately installable packs
- [x] The core installs alone (everything goes to the general pack); each domain pack is its own
      package found through the `plm.packs` entry point; `plm packs install <name>` installs a pack
      and pulls its models. Built on branch `separate-packs`, every step checked: `docs/pack-packaging.md`.

## 3b. Ideas from SKY-001 (Skyfall AI's engineering model, research preview Oct 2026)
SKY-001 breaks a design into assemblies and parts, plans each part as an ordered sequence of build
steps, and is a small specialist rather than a generalist. Its numbers are self-reported on its own
benchmark, and its build plans are visual, with no reported check that the geometry is buildable.
What could carry over, in order of value per effort; each policy fixed before its results:
- [x] **Unit-aware calculator: built, measured, not adopted.** Strategy `units` (`plm/numeric/calc.py`
      `run_units_program`): the model writes `Q(value, "unit")` and the harness converts `ANSWER` to the
      asked unit. Policies and rule fixed before the sweep (`results/run_units.sh`). Catch rate rose
      (60-73% of wrong answers caught, vs 0-27% with the plain calculator), but the models wrote
      wrong-dimension formulas and misspelt unit names on problems they otherwise solve: 8B 47 -> 34/50
      electrical, 39 -> 24/50 aerospace (4B: 47 -> 29, 32 -> 33). Best units policy: electrical 42/50 vs
      shipped 48, aerospace 38/50 vs 39, so neither pack switched. Untested idea: use a units program
      only as a second opinion that flags disagreement, never as the answer.
- [x] **Decompose, then solve: built, measured, not adopted.** Strategy `decompose`
      (`plm/numeric/decompose.py`): the 8B plans up to 6 steps with units, one calculator program per
      step, each step's dimension checked, falling back to one program. Rule and cost bound (<= 4x
      tokens) fixed before the sweep, primary set 15 fresh intensive problems written before the
      strategy (`evals/score_decompose.py`). Fresh 5/15 vs 6/15 for 8B + calculator, eval set 6/15 vs
      7/15, at 2.4x the tokens. Step prompt v1 had a flaw (its example unit "A" was copied in all 12
      fallbacks), but finished decompositions were still 1 behind on each set. Plans also used wrong
      formulas that the dimension check passes (absurd values, right units).
- [x] **CAD pack checked by a real CAD kernel: built.** `packages/plm-cad`: the coder 14B writes
      CadQuery, the kernel builds it in an isolated process and measures it. 36 parts with formula keys
      and kernel-verified references; policies and rule fixed before the sweep: always the coder, 17/36
      parts exactly right (4B 10, 8B 7: mostly API misuse). The key-free check (one valid solid, overall
      size from the task) never flagged a right part but catches only 7 of the coder's 19 wrong ones:
      it can't see features inside a right-sized part (a "through" hole cut halfway passes). A hole check
      judged on 15 fresh parts caught 38/40 wrong parts (size-only 27) but flagged a correct bracket, so
      it wasn't adopted (rule fixed first); its v2 ("through" = no disk caps the hole), judged on a second
      fresh set, was: 32/38 caught to 25, no false alarms. Scores above are regraded at 0.1% (coder 16/36).
      A repair retry (the coder sees its flagged program and the check's finding) fixed 0 of 9 flagged parts
      on 20 fresh parts at 1.56x tokens: not adopted.
- [x] **Fine-tune the 4B for aerospace (LoRA with MLX): built, measured, not adopted.** 734 generated
      problems with calculator-program answers from 32 templates of the eval set's families; judged on
      36 fresh problems written first (`evals/score_lora.py`). Tuned 4B 28/36 = the 8B's 28, but calm fell
      to 7/12 (control 11/12: unit labels and lookups copied wrong from the templates), so routing calm and
      alert to it scored 25/36 at 69% compute: rule failed. It beat the 8B on intensive (9/11 vs 5/11), a
      post-hoc hypothesis. A control through the same Q8_0 route beat the shipped Q4_K_M 4B, 26 vs 22.
- Benchmark lesson: SKY-001's claims are its own, on its own benchmark. Keep holdouts written first
  and policies fixed before sweeps for anything published here.

## 4. Public benchmarks
- [x] SQL: Spider dev (300 sampled) and BIRD mini-dev (496), `evals/bench_sql.py`, rules fixed before each:
      coder 76% / 51%, 8B 67% / 35%, 4B 66% / 31% (bootstrap 95% CIs in `results/bench_*`).
- [x] Code: HumanEval+ (163) and MBPP+ (377), `evals/bench_code.py`, CODE_RULE (accuracy first) fixed before:
      coder alone 410/540 (76%) vs the shipped cascade 387 (72%), +6 to +40 paired 95%: the software pack now
      ships the coder alone. The examples check caught 14 of 112 wrong HumanEval answers (no parseable examples).
- [x] Physics: SciBench's physics problems (Halliday + classical mechanics, 144), `evals/bench_physics.py`, PHYS_RULE
      (accuracy first) fixed before: 4B+calc escalating to 8B+calc 69/144 vs the shipped 8B direct 52 (+4 to +30)
      at 48% of its compute: the physics pack switched. Only 30 of the 144 routed to physics (LaTeX quantities);
      with LaTeX read as plain text (`plm/latex.py`, LATEX_RULE on 20 new held-out cases: 12 -> 19/20), 73.
- [x] Physics confirmation: TheoremQA physics (112), TQA_RULE: the switch holds (48 vs 46, 42% compute).
- [x] CAD: CADPrompt (195 parts built from their own CadQuery references), CADP_RULE: keeps the coder (28/195;
      cascades 35, interval 0 to +14). Electrical and aerospace: no fitting public benchmark found.
- [x] SQL result flags (`plm_sql/flags.py`: error, no rows, >100 rows, all NULL, none of the question's tables),
      read on the real database; FLAGS_RULE fixed before, judged on 2880 unseen Spider questions (733 unsampled
      dev + 2147 test): the coder with a 4B second opinion on a flag 2230 vs the coder alone 2212 (+7 to +30,
      105% compute): adopted, built as an opt-in database (`--sql-db`, `PLM_SQL_DB`). 4B first, coder on a flag: 1990.
- [x] SQL routing with a database (`plm_sql/claims.py`, SQLDB_RULE fixed before, cases in `evals/router/sqldb_*`):
      with PLM_SQL_DB set, schema-free data questions naming the database's tables or columns go to sql. Designed on
      Spider train; held out: 115/120 Spider dev, 18/20 casual, 30/34 look-alikes unmoved, 5 of 9860 other pairs moved.
- [x] SQL flags confirmation: 1035 BIRD dev questions mini-dev doesn't use, CONFIRM_RULE fixed before: 534 vs the
      coder alone 528 (-1 to +13, 112% compute): confirmed, the pack keeps the 4B second opinion.
- [x] Dropping the huge flag (NOHUGE_RULE, 3000 Spider train questions): 2448 vs 2450 (-6 to +2, needed >= -3):
      not adopted, the pack keeps all five flags.
- [x] GSM8K cross-check (300 sampled, `evals/bench_gsm8k.py`, GSM_RULE fixed before): the 8B direct 272/300 (91%)
      beats the 8B with the calculator 261 (-21 to -1) and the 4B with it 256: the general pack stays as it is.
- Code: EvalPlus (HumanEval+/MBPP+), LiveCodeBench (problems newer than the models).
- SQL: Spider or BIRD. Physics: a public set, to be chosen. Optional numeric cross-check: GSM8K.
- Hundreds of items per domain with bootstrap confidence intervals; pinned model digests,
  versioned prompts, recorded hardware; one command reproduces every number.
- Headline per domain: quality vs compute for always-small, always-large, the router, and the
  hindsight bound.

## 5. Publish
- [x] GitHub repo, public since 2026-11-05: https://github.com/ro-rbl/plm-orchestrator (MIT).
- [x] Hugging Face dataset, public since 2026-11-05: https://huggingface.co/datasets/rblrbl/plm-orchestrator-evals (eval
      sets, every result file, a dataset card; no benchmark data redistributed).
- [x] Both public (2026-11-05); a fresh `uv tool install` from the git URL, a pack install from GitHub and a live
      question work without credentials. Optional: a Space, PyPI.
- Public benchmarks are referenced, not redistributed (each has its own license).

## 6. Using it day to day (2026-11-08/09)
- [x] Follow-up questions (`plm/followup.py`, FOLLOWUP_RULE) in the server and the interactive CLI.
- [x] Full-screen interface (`plm/tui.py`, extra `plm-core[tui]`) from the user's mockup; CAD parts drawn in Braille;
      `/` commands; skills (Claude SKILL.md format); context meter; `plm.command` launcher.
- [x] Unit checks from the question (`plm/numeric/expected.py`, UNITS2_RULE), released in plm-core 0.1.3.
- [x] Pack fusion measured three times (FUSE_RULE, FUSE3_RULE): never clearly better than the CAD pack alone; kept
      as the experimental `/fuse`.
- [x] Follow-up wording settled (keep today's); general pack context on demand (cap 40960); "in cm^-1" read.
- [ ] Live step progress; plm-core 0.1.4.

