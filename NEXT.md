# NEXT

_Updated: 2026-10-22 · branch: main · plan: ROADMAP.md_

## Start here (next session)
- Merged on `main`: **separately installable packs**, all six steps of `docs/pack-packaging.md`. The code
  is now `packages/plm-core` (import `plm`) plus `plm-electrical`, `plm-aerospace`, `plm-software`
  (`plm_<name>`), found through the `plm.packs` entry point; `plm packs list|install|remove|doctor`.
  Behavior with all packs installed is unchanged (`evals/dump_decisions.py` identical: 272 texts,
  1716 checks; routing simulations match the pre-split `main`).
- Then **decompose-then-solve** was built and measured, and **not adopted** (`ROADMAP.md` 3b; rule in
  `evals/score_decompose.py`, run log `results/decompose.log`): 5/15 vs 6/15 on fresh problems, 6/15 vs
  7/15 on the eval set's intensive ones, at 2.4x the tokens. Next, unless decided otherwise:
  1. Remaining SKY-001 ideas (`ROADMAP.md` 3b): CAD pack checked by a real kernel (preflight done, GO:
     see "CAD pack: preflight" below), or a LoRA for the 4B on aerospace.
- **An existing `.venv` from before the split has no `plm` any more** (it was on `sys.path` from the repo
  root, which no longer has `plm/`; `requirements.txt` is gone). Reinstall: `uv pip install --python
  .venv/bin/python -e packages/plm-core -e packages/plm-electrical -e packages/plm-aerospace -e packages/plm-software`.
- Local branch `separate-packs` is merged and can go: `git branch -d separate-packs`.
- Then the **physics pack** was built and swept (`ROADMAP.md` 3): everything to the 8B answering directly,
  49/50. Next after the SKY-001 ideas: the SQL pack (`ROADMAP.md` 3).

## Packaging: loose ends
- [ ] **`plm packs install` has never downloaded a model for real.** The pull code ran live only on a model
      already present (`qwen3:0.6b`: Ollama re-verified it). Resume, in a throwaway venv, with a small model
      you don't have (~1.4 GB): `PLM_LARGE_MODEL=qwen3:1.7b <venv>/bin/plm packs install aerospace --source
      packages`, check `plm packs list` shows it pulled, then `ollama rm qwen3:1.7b`.
- [ ] **Installing a pack from a git URL or a wheel is untested.** Only local directories (editable) were
      installed live; there's no remote yet. Once there is one: `plm packs install aerospace --source
      "plm-aerospace @ git+https://<repo>#subdirectory=packages/plm-aerospace"` in a fresh venv.
- [ ] **Package names are unclaimed on PyPI** (all four 404 on 2026-10-22): installing a pack where
      `plm-core` isn't installed could fetch someone else's `plm-core`. Claim the names when publishing
      (ROADMAP phase 5); `docs/pack-packaging.md` "Risks".
- [ ] **Claim scores for third-party packs are uncalibrated.** Today's are term counts tuned for three
      packs; a fourth could out-claim them. Open decision in `docs/pack-packaging.md`; decide before
      accepting a pack written by someone else.
- [ ] **With a broken pack installed, `plm "<task>"` prints a Python traceback**, ending in a clear
      RuntimeError that names `plm packs remove <name>`. A one-line message would be friendlier:
      `packages/plm-core/src/plm/__main__.py` (catch around `from plm.packs import ...`) and the same in `server.py`.

## Decompose-then-solve: loose ends
- [ ] **Step prompt v1 shows the unit "A" in its example, and the 8B copied it** in all 12 fallbacks
      (6 per set: unitless or km steps printed "A"), so 40% of problems never finished decomposing.
      Kept as measured. A v2 (an example in the step's own unit) is a hypothesis: finished
      decompositions were still 1 behind the calculator on each set, so expect no gain. Judging it needs
      new problems, since `evals/aerospace/fresh_intensive.jsonl` has now been seen. Resume:
      `packages/plm-core/src/plm/numeric/decompose.py:step_prompt`, then write fresh problems first.
- [ ] **The step check is dimension-only.** Wrong plan formulas give absurd values with the right units
      (preflight ae-i06: 3.3e9 MW), and given values restated as steps can come back wrong (ae-i02:
      -10000 kg propellant) without being caught. `decompose.py:step_issue`.
## CAD pack: preflight (2026-10-22, no CAD code yet)
Live on this Mac (arm64, Python 3.13, throwaway uv venvs in the session scratchpad):

| Dependency | Result | Evidence |
|---|---|---|
| CadQuery wheels for arm64 / cp313 | GREEN | `cadquery-ocp` 7.9.3.1.1 prebuilt, no source build; install 463 s on plane wifi |
| Install size | GREEN, heavy | venv 1.3 GB, of which VTK (rendering, not needed to check) 598 MB, OCP 225 MB |
| Kernel builds and measures a solid | GREEN | 40x30x10 box with an 8 mm hole: valid, bbox exact, volume 11497.345 = hand value |
| Runs isolated (`python -I`, empty cwd) | GREEN | as above; needs `-I` without `-S` (site-packages), like the units calculator |
| Import time per check process | GREEN | 1.6-2.4 s warm; the first run after install took 55 s (one-time library load) |
| The 8B writes CadQuery | GREEN for the check, 1/2 parts | plate with hole: exact bbox and volume; tube: invalid workplane name -> ValueError, which a check catches |
| build123d (`cadquery-ocp-novtk`, no VTK) | GREEN | build123d 0.13.0 on OCP 8.0.1: venv 586 MB, no VTK; same box valid, bbox and volume exact; warm import 1.28 s (26 s first run) |
| The 8B writes build123d | RED so far, 0/2 parts | API misuse: `extrude(5)` without `amount=`, lowercase `cylinder`; same parts as the CadQuery probe |

Verdict: **GO.** Both kernels build and measure solids exactly. Trade-off: build123d is half the size
(586 MB vs 1.3 GB), but the 8B wrote CadQuery 1/2 and build123d 0/2 (2 parts: far too few to decide).
Options: CadQuery with the full install, or `cadquery` on `cadquery-ocp-novtk` if that combination works
(untested). Ship the kernel only as a dependency of an optional
`plm-cad` pack. Next: give the 8B the same parts in build123d (the probe script's pattern: ask, run under
`python -I` with the bbox/volume epilogue), then write the CAD eval set (parts with computed bbox and volume)
before any pack code.

## Physics: loose ends
- [ ] **The calculator forgets prefix conversions on physics.** All 7 of the 8B's calculator misses (and 3 of
      the 4B's 5) computed in base units and printed the asked prefixed unit ("5e+04 MPa" for 50 MPa, "678 MJ"
      for 0.678 MJ); the unit checks pass them (same dimension). Why physics and not electrical: its questions
      ask for kPa/kJ/MJ more. A magnitude check can't know the right size; a prompt fix ("convert to the asked
      unit before printing") changes `calc.TOOL_FORMAT` for every pack, so it needs every pack's sweep re-run.
      `results/physics.log`, `packages/plm-core/src/plm/numeric/calc.py:TOOL_FORMAT`.
- [ ] **Unit spellings the grader rejects:** "286.48 rev/min" (the 8B's only direct miss, ph-c15) and "15.0 Nm"
      (4B + calculator, ph-c10) are right numbers graded as unit errors, like "15.58 rev" above. Decide with that
      item; `plm-core: plm/numeric/answers.py:normalize_unit`. Accepting them wouldn't change the pick (8B direct
      would be 50/50).
- [ ] **Physics holdout routing misses, left unfixed on purpose:** pho-c6 ("speed of sound ... at 20 °C") and
      pho-a4 (pendulum with "gravitational acceleration") go to aerospace, pho-i2 ("600 N of resistance") to
      electrical, pho-i3 (bullet into a hanging block) to general. Fixing them needs fresh cases to judge.
      Resume: `.venv/bin/python evals/test_detect.py -v`.
- [ ] **Physics problems often end a sentence with a number**, which the shared counter misses (the known
      `NUMBER` bug below): 7 of the 50 alert problems classify as calm. Harmless under the shipped policy
      (every level goes to the 8B), but fixing the counter changes every pack's levels.
- [ ] **The dump baseline changed** with physics (its texts and saved answers are added; g13/g40 and the new
      routing cases moved) and with the decompose results (15 more CHECK lines from `aerospace__*__decompose`). Save a new one before the next refactor:
      `.venv/bin/python evals/dump_decisions.py > <scratch>/decisions.before`.

## Known bugs / weaknesses
- [ ] **Units strategy as a second opinion (untested).** A units program catches 60-73% of wrong
      answers but is wrong itself too often to be the answer. Hypothesis: run it beside the plain
      calculator and escalate only when the two disagree. Policy must be fixed before measuring, and
      replayed from saved results first: `evals/simulate_routing.py` supports verifiers (`(model, verifier)`
      steps), so it costs no model calls to try. Watch compute: it doubles calls on every problem.
- [ ] **Class-task examples are hard to imitate.** The `(lambda c: (c.put(1, 1), ..., c.get(1))[-1])(LRUCache(2))`
      style in `evals/software/build_tasks.py` (sw-i01, sw-i13, sw-i15) led the 8B to write 7/8 malformed tests
      for LRUCache; `plm_software/testgen.py:is_broken_test` hides them, it doesn't fix them. Changing the style
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
      to accept count nouns; `plm-core: plm/numeric/answers.py:LITERAL_UNITS`.
- [ ] **The shared number counter misses a number that ends a sentence** ("a pressure ratio of 10."), so a
      problem can count one input short (ae-a13). Calm/alert confusions only so far; fixing it changes the
      electrical classifier too, so re-run `evals/eval_levels.py` for every pack. `plm-core: plm/numeric/levels.py:NUMBER`.
- [ ] **Electrical/aerospace overlap is decided by counting domain terms**, tested on 3 cases only
      (detect_cases a06, e06, e07). `plm_electrical/claims.py`, `plm_aerospace/claims.py`, priorities in each `manifest.py`.
- [ ] **Server: packs see only the last user message.** A follow-up like "now do it for 200 ohm" loses the
      earlier question and goes wherever the follow-up alone points. `plm-core: plm/server.py:parse_request`.

## Unverified
- [ ] **Every problem, task, label and reference solution was written by Claude.** Holdouts guard against tuning
      the classifiers to the test, not against author bias. Needs problems written by someone else.
- [ ] **Electrical answer key formulas were only hand-checked by Claude.** Spot-check ~10 `solution` fields in
      `evals/electrical/build_problems.py`.
- [ ] **Small samples.** 50 electrical problems, 45 code tasks; differences of 1-2 between policies are noise.
- [ ] **Timing columns are unreliable.** The Mac was swapping hard during the sweeps (16 GB swap, 102 s model
      loads; 4.3 GB and 294 s/problem in the decompose sweep's last run). Token counts are the cost measure. Before any timing run: `sysctl vm.swapusage` and `ollama ps`.
- [ ] **Formula-first and generated-test policies in the simulations were added after their results were seen**
      (marked in `evals/simulate_routing.py`); the software routing policies were fixed in advance.
- [ ] **Pack auto-detection** (each pack's `claims.py`, picked by `plm/pack.py:pick`) is verified on the 184 eval texts (all correct) and 88
      holdout cases labeled before the rules they test: 85/88 independently (gas-dynamics terms added for 5
      eval-set misses also fixed 2 holdout cases, so the later 87/88 is not independent). Real traffic will
      differ; `logs/server.jsonl` records every routing decision, so check it after real use.

## Tooling notes
- Logs (`logs/runs.jsonl`, `logs/server.jsonl`, the server's pid/port files) are relative to the working
  directory since the split; run from the repo root to keep them in `logs/` here (`PLM_LOG_DIR`, `PLM_LOG`).
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
- SQL pack: next (ROADMAP.md, phase 3).
- **An absent pack's tasks go to whichever installed pack still claims them**, not always to general
  (with aerospace not installed, ae-c12 and ae-a20, power in kW, go to electrical). By design of claims;
  recorded in `docs/pack-packaging.md`.
- **No lint configuration in the repo.** A ruff config outside the repo flags 86 style findings (74 on the
  pre-split `main`); the 12 this work added are existing idioms (`# noqa: E402` after `sys.path` inserts)
  or deliberate (`discover()` catches any exception from a pack; `subprocess.run` checked by return code).
  `ruff check --select E9,F packages evals` is clean.
