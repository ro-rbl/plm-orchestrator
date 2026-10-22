# NEXT

_Updated: 2026-10-21 · branch: main · plan: ROADMAP.md_

## Start here (next session)
- Phase 3 aerospace is merged (`main`). Next, in this order unless decided otherwise:
  1. **Separately installable packs**: `docs/pack-packaging.md` has the design and a six-step migration,
     each step with its check. Start a branch, save the baseline with `evals/dump_decisions.py`, then step 1.
  2. **SKY-001 ideas**, starting with the unit-aware calculator: `ROADMAP.md` section 3b.
  3. **Physics/mechanical pack**: `ROADMAP.md` section 3.

## Known bugs / weaknesses
- [ ] **Class-task examples are hard to imitate.** The `(lambda c: (c.put(1, 1), ..., c.get(1))[-1])(LRUCache(2))`
      style in `evals/software/build_tasks.py` (sw-i01, sw-i13, sw-i15) led the 8B to write 7/8 malformed tests
      for LRUCache; `plm/software/testgen.py:is_broken_test` hides them, it doesn't fix them. Changing the style
      changes the prompts, so re-run `results/run_software.sh` and `results/run_testgen.sh` afterwards.
- [ ] **Generated tests are wrong 9-17% of the time** (e.g. `two_sum([1, 3, 5, 7], 8) == [0, 2]`), which is why
      `--thorough` costs 228%. Ideas not yet tested: fewer tests, escalate only on 2+ failures, drop a test that
      every candidate fails. Measure on a fresh task set, not the 45 tasks already used to compare writers.
- [ ] **Example-only checks pass about 1 in 4 wrong solutions** (14 of 63 in the sweep; live case: 4B's
      `bisect`-based two_sum on unsorted input). Documented, not fixed; `--thorough` is the current mitigation.
- [ ] **Conceptual questions with a number and an electrical unit go to the electrical pack.** Holdout miss:
      "What does a 10 amp fuse protect against?" (`evals/router/detect_cases.jsonl` g36) gets a forced numeric
      answer. Left unfixed on purpose: fitting the rule to a holdout miss would make the holdout meaningless.
      Resume: `.venv/bin/python evals/test_detect.py -v`; any fix needs fresh cases to judge it.
- [ ] **Aerospace: routing to a small model doesn't pay, and intensive problems are hard.** The 4B is weaker
      than on electrical (75% vs 90% on alert), so the pack sends everything to the 8B + calculator. Every
      model missed the normal-shock, two-stage, Breguet and compressor-power problems. Hypothesis, chosen
      after seeing the results: calm-only to the 4B (40/50 at 37%). Test it on fresh problems before using it.
- [ ] **Unitless answers with a descriptive noun count as unit errors.** "15.58 rev" for a unitless count
      (ae-i15, both 8B runs) fails the grader and the live check, though the number is right. Decide whether
      to accept count nouns; `plm/numeric/answers.py:LITERAL_UNITS`.
- [ ] **The shared number counter misses a number that ends a sentence** ("a pressure ratio of 10."), so a
      problem can count one input short (ae-a13). Calm/alert confusions only so far; fixing it changes the
      electrical classifier too, so re-run `evals/eval_levels.py` for every pack. `plm/numeric/levels.py:NUMBER`.
- [ ] **Electrical/aerospace overlap is decided by counting domain terms**, tested on 3 cases only
      (detect_cases a06, e06, e07). `plm/packs.py:detect`.
- [ ] **Server: packs see only the last user message.** A follow-up like "now do it for 200 ohm" loses the
      earlier question and goes wherever the follow-up alone points. `plm/server.py:parse_request`.

## Unverified
- [ ] **Every problem, task, label and reference solution was written by Claude.** Holdouts guard against tuning
      the classifiers to the test, not against author bias. Needs problems written by someone else.
- [ ] **Electrical answer key formulas were only hand-checked by Claude.** Spot-check ~10 `solution` fields in
      `evals/electrical/build_problems.py`.
- [ ] **Small samples.** 50 electrical problems, 45 code tasks; differences of 1-2 between policies are noise.
- [ ] **Timing columns are unreliable.** The Mac was swapping hard during the sweeps (16 GB swap, 102 s model
      loads). Token counts are the cost measure. Before any timing run: `sysctl vm.swapusage` and `ollama ps`.
- [ ] **Formula-first and generated-test policies in the simulations were added after their results were seen**
      (marked in `evals/simulate_routing.py`); the software routing policies were fixed in advance.
- [ ] **Pack auto-detection** (`plm/packs.py:detect`) is verified on the 184 eval texts (all correct) and 88
      holdout cases labeled before the rules they test: 85/88 independently (gas-dynamics terms added for 5
      eval-set misses also fixed 2 holdout cases, so the later 87/88 is not independent). Real traffic will
      differ; `logs/server.jsonl` records every routing decision, so check it after real use.

## Tooling notes
- `with-timeout` does not pass stdin through: `with-timeout N python -m plm < file` sends an empty task (now
  refused), and `with-timeout N python - <<EOF` runs an empty script. Pass `"$(cat file)"` as an argument, or
  write the script to a file.
- Ollama's `qwen3:4b` tag is Qwen3-4B-Thinking-2507 (always reasons first; 31/50 direct answers hit the token
  cap with thinking suppressed), not the original hybrid Qwen3-4B the abliterated build comes from.
- The machine pins `qwen3:8b` in memory ("Forever" in `ollama ps`, 6.3 GB), set by something outside this repo;
  with it, swap sits around 11 GB during sweeps.

## Deferred by choice
- The abliterated 4B is no longer a default. Against its own original (same base, quantizer and quant) it
  loses 9 electrical problems answering directly and 4 with the calculator, mostly intensive ones; software
  is within noise. An earlier note here called abliterated models "fine as specialists": that came from
  comparing them with qwen2.5:3b, a different family, and doesn't hold against the original Qwen3-4B.
- Formula-first calculator prompt is not the electrical default: 48/50 at 86% compute vs 47/50 at 36%.
- Agreement (second-opinion) checks are off in electrical: one extra correct answer for 31 points of compute.
- No 0.6B is used as a tier: abliterated 24/50 electrical (direct), 7/45 software; standard qwen3:0.6b 17/50, 14/45.
- `--thorough` is opt-in, not default (see above).
- `gpt-oss:20b` (13 GB) has not been evaluated.
- Physics/mechanical and SQL packs: next (ROADMAP.md, phase 3).
