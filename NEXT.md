# NEXT

_Updated: 2026-10-20 · branch: stronger-code-checks (not merged) · last code commit: 370f428_

## Blocking
- [ ] **`stronger-code-checks` is not merged into `main`.** All gates green as of 370f428
      (grader 271/271, checks 140/140, calc, sandbox, testgen self-tests, 45/45 references, ruff clean).
      Resume: `git checkout main && git merge --ff-only stronger-code-checks`

## Before adding more packs
- [ ] **Electrical modules live at the top of `plm/`, while software has its own `plm/software/`.**
      Move `levels.py`, `checks.py`, `calc.py`, `controller.py` into `plm/electrical/` so every pack has
      the same shape. Check: all self-tests in README "Tests" still pass and
      `.venv/bin/python evals/simulate_routing.py` still prints `47/50  36%` for `routed: 4B+tool | 8B+tool`.

## Known bugs / weaknesses
- [ ] **Electrical answers go unchecked when the question names no unit.** `plm/checks.py:requested_unit()`
      returns None, so `check()` returns [] and the CLI reports the answer as verified. Found through the
      empty-task bug (now refused in `plm/__main__.py:run_one`). Resume: decide whether "nothing to check"
      should print as unverified; `plm/checks.py` and `plm/__main__.py:print_answer`.
- [ ] **Class-task examples are hard to imitate.** The `(lambda c: (c.put(1, 1), ..., c.get(1))[-1])(LRUCache(2))`
      style in `evals/software/build_tasks.py` (sw-i01, sw-i13, sw-i15) led the 8B to write 7/8 malformed tests
      for LRUCache; `plm/software/testgen.py:is_broken_test` hides them, it doesn't fix them. Changing the style
      changes the prompts, so re-run `results/run_software.sh` and `results/run_testgen.sh` afterwards.
- [ ] **Generated tests are wrong 9-17% of the time** (e.g. `two_sum([1, 3, 5, 7], 8) == [0, 2]`), which is why
      `--thorough` costs 228%. Ideas not yet tested: fewer tests, escalate only on 2+ failures, drop a test that
      every candidate fails. Measure on a fresh task set, not the 45 tasks already used to compare writers.
- [ ] **Example-only checks pass about 1 in 4 wrong solutions** (14 of 63 in the sweep; live case: 4B's
      `bisect`-based two_sum on unsorted input). Documented, not fixed; `--thorough` is the current mitigation.

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
- [ ] **Pack auto-detection** (`plm/__main__.py:SOFTWARE_TASK`) is verified only on the 134 eval texts.

## Tooling notes
- `with-timeout` does not pass stdin through: `with-timeout N python -m plm < file` sends an empty task (now
  refused). Pass `"$(cat file)"` as an argument instead.

## Deferred by choice
- Formula-first calculator prompt is not the electrical default: 48/50 at 86% compute vs 47/50 at 36%.
- Agreement (second-opinion) checks are off in electrical: one extra correct answer for 31 points of compute.
- The 0.6B is not used as a tier in either pack: 24/50 electrical, 7/45 software.
- `--thorough` is opt-in, not default (see above).
- `gpt-oss:20b` (13 GB) has not been evaluated.
- Aerospace and other domain packs: next.
