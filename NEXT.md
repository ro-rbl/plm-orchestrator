# NEXT

_Updated: 2026-11-01 · branch: main · plan: ROADMAP.md · results: docs/results.md_

## Start here (next session)
Where things stand: phases 1-4 of `ROADMAP.md` are done; phase 5 (publishing) is done: public since 2026-11-05. Six packs,
each with its policy chosen by a rule committed before its results, and checked on public benchmarks where one
fits (`docs/results.md`, `.venv/bin/python evals/headline.py`):

| Pack | Ships | Public benchmark (shipped) |
|---|---|---|
| electrical | 4B + calc -> 8B + calc | none fits (own set 48/50) |
| aerospace | 8B + calc | none fits (own set 39/50) |
| physics | 4B + calc -> 8B + calc (as electrical) | SciBench 48%, TheoremQA 43%, UGPhysics 46/150 |
| software | coder 14B alone | HumanEval+ 85%, MBPP+ 72% |
| sql | coder 14B alone | Spider 76%, BIRD mini-dev 51% (EX 54.5) |
| cad | coder 14B alone | CADPrompt 14% (bbox + volume within 0.1%) |

Public (2026-11-05): https://github.com/ro-rbl/plm-orchestrator and
https://huggingface.co/datasets/rblrbl/plm-orchestrator-evals (see "Publishing" below).

**Overnight 2026-11-08 (read first):**
- Fusion: FUSE_RULE says don't build `/fuse` (fusion 18/40 = CAD alone 18/40; perfect hand-off 32/40; the numeric
  packs' calculations were right 23/40). See "Pack fusion" below for two hypotheses.
- Follow-up questions shipped (server + interactive `plm`); routing right, but one live answer repeated the
  original. See "Follow-ups" under Known bugs.
- Physics routing attempt 1: 27/30 vs the 28 required: not shipped; diff in `docs/attempts/`.
- SQL tables-flag plural fix: checked on seen answers first, moves scores by at most 1: no run, left as is.
- New: units asked as symbols ("in m/s") aren't read, so those answers go unchecked (Known bugs).
- The user's assistant re-pins `qwen3:8b`; overnight runs used `results/fusion_supervisor.sh` (waits for AC,
  unpins). Turn the assistant back on: `launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.ro.assistant.plist`.
- Waiting on the user: PyPI upload of plm-physics/software/sql + plm-core 0.1.2 (Sunday 2026-11-08 after 23:00),
  the TUI build from `mockups/tui.html`, slash commands.

Suggested order for the next session:
1. **SQL flags are built** (2026-10-30): `plm --sql-db <file>` / `PLM_SQL_DB`. Live on four Spider test
   questions, every query and path matched the benchmark's. **Routing with only `PLM_SQL_DB` fixed 2026-11-04**
   (SQLDB_RULE passed on held-out cases: 115/120 Spider dev to sql, 30/34 look-alikes unmoved, exactly the bar).
   Left as measured (fixing them needs new cases, these are now seen): advice full of the data's words goes to
   sql (dn04, dn27, dn30, dn31); "weather ... like" matched a `Likes` table; "capital of Australia" with a world
   database goes to sql (arguably right). `evals/test_sqldb_routing.py -v`. The tables flag's false alarms are
   under "SQL pack" below.
1b. **BIRD confirmation of the SQL flags policy: CONFIRMED (2026-11-01).** 1035 BIRD dev questions mini-dev
   doesn't use, CONFIRM_RULE committed in 66c3e1c before any answer: shipped 534 vs coder alone 528 (-1 to +13
   paired 95%, 112% compute), so the pack keeps the 4B second opinion. Recorded in `docs/results.md`.
   Re-check: `.venv/bin/python evals/bench_sql_check.py --simulate --sets bird`.
1c. **Dropping the SQL pack's "huge" flag: KEEP (2026-11-03).** 2999 Spider train questions, NOHUGE_RULE fixed in
   357b524 before any answer: without "huge" 2448 vs shipped 2450 (1 won, 3 lost, -6 to +2; needed >= -3), 4B calls
   432 -> 375. The flags stay as they are. Recorded in `docs/results.md`. Spider train is now seen.
   During the run the user's assistant service was stopped (`launchctl bootout`); restore it with
   `launchctl bootstrap gui/501 ~/Library/LaunchAgents/com.ro.assistant.plist` if not done yet.
2. **Public since 2026-11-05.** Open: claim the PyPI names (see "Packaging"), or decide not to publish there.
3. Anything else below. Data for the public benchmarks lives in `.benchmarks/` (ignored by git); each
   `evals/bench_*.py` docstring says where to download it from, if it's missing.

Before running anything long: `pmset -g batt` (on AC?), `caffeinate -i -s -t <seconds> &`, `ollama ps`.
The Mac crashed on battery during a run on 2026-10-25; runners now stop cleanly if Ollama goes down, and resume.

## Pack fusion (`/fuse`): spike done 2026-11-07
User's design: `/fuse` at the start or end of a prompt; a planner splits a mixed problem between packs; each step lit
in the TUI's packs strip. Pairs wanted: CAD + engineering (first), SQL + software, physics + aerospace (least
promising: same calculator, it's decompose-then-solve again). Spike on 10 CAD + engineering problems
(`evals/fusion/`, written first; `results/fusion_spike.*`): CAD alone 4/10, fusion 3/10, perfect hand-off 7/10.
The 8B planned 10/10 usably; calculations were right 4/10, mostly the known prefix bug (0.0042 "mm" for 4.2 mm;
see Physics loose ends); 3 oracle misses are the CAD pack's hole bugs (one of two holes cut). Round 2 (2026-11-07,
`evals/fusion/round2.jsonl` written first, `--variant m`: calculation asked in metres, converted in code): CAD alone
3/10, fusion 6/10, perfect hand-off 7/10; calculations 8/10 (prefix bug gone; misses: a load not split between two
bolts, one absurd value); the 2 other misses are CAD hole bugs. The calc pack's `trusted` flag doesn't separate right
from wrong (10 of 12 right answers untrusted), so a fallback needs another signal (e.g. a plausible-size check).
**FUSE_RULE verdict (2026-11-08): don't build.** 40 judged problems (`evals/fusion/judged.jsonl`, rule and set
committed first in ca2cd75): fusion 18/40 = CAD alone 18/40 (paired 95% -8 to +8), at 1.8x the tokens; perfect
hand-off 32/40. Plans 39/40 usable; calculations right only 23/40 (wire voltage drop 0/3, heat conduction 0/3,
bending 1/3; fj-01 gave 7.07 m for 14.1 mm). The coder computing inside its own CadQuery program did as well or
better on drag, wing chord and disc mass (3/3 each). Hypotheses, each needing a new set: (1) the calculation step
by the coder writing a Python program (as CAD alone effectively does) instead of the numeric packs; (2) fusion only
when the plan's calculation is a kind the numeric packs get right. `results/fusion_judged_m.*`. TUI mockup: `mockups/tui.html` (ignored by git;
orange banner and part, packs strip and models strip at the bottom, active one green).
- [ ] `ollama stop qwen3:8b` before any run that uses the coder: the user's assistant service pins it.

## Packaging: loose ends
- [x] **`plm packs install` downloaded a model for real (2026-11-04):** in a throwaway venv,
      `PLM_LARGE_MODEL=qwen3:1.7b plm packs install aerospace --source packages` pulled 1.4 GB (digest verified),
      `plm packs list` showed it "pulled"; then `ollama rm qwen3:1.7b`.
- [ ] **Installing a pack from a git URL or a wheel is untested.** Only local directories (editable) were
      installed live; there's no remote yet. Once there is one: `plm packs install aerospace --source
      "plm-aerospace @ git+https://<repo>#subdirectory=packages/plm-aerospace"` in a fresh venv.
- [ ] **PyPI, partly claimed (2026-11-06):** plm-core, plm-electrical, plm-aerospace, plm-cad are up (wheels;
      `uv tool install plm-core` from PyPI tested). plm-physics, plm-software, plm-sql hit PyPI's "too many new
      projects" limit (429). Resume later, from the repo root (built files in `dist/`, rebuild with
      `uv build --out-dir dist packages/plm-<name>` if gone): `uv publish dist/* --check-url https://pypi.org/simple/ --token <token>`.
      Then: per-project tokens, revoke the account-wide one (a token was pasted into a chat on 2026-11-06),
      Done 2026-11-06: outside a checkout, an official pack installs from PyPI when it's there, else GitHub (tested
      live both ways); unofficial names still need --source. Ships to PyPI users with the next plm-core release
      (0.1.0 on PyPI defaults to GitHub): 0.1.1 is on PyPI (2026-11-06; tested: `uv tool install "plm-core==0.1.1"`,
      electrical installed from PyPI by name, live 22 V). All 5 sdists uploaded 2026-11-06. Still to upload: plm-physics, plm-software, plm-sql (429 again 2026-11-06; wait 24-48 h, then the full command once; if
      still blocked, PyPI support). Until then they install from GitHub. Since 2026-11-06 a pack comes from PyPI
      only if the PyPI account ro-rbl owns it (`manage.on_pypi`), so a squatted name falls back to GitHub; this
      ships to PyPI users with plm-core 0.1.2 (build and upload with the three packs).
- [ ] **Claim scores for third-party packs are uncalibrated.** Today's are term counts tuned for three
      packs; a fourth could out-claim them. Open decision in `docs/pack-packaging.md`; decide before
      accepting a pack written by someone else.

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

## Aerospace LoRA for the 4B: measured, not adopted (2026-10-23)
Pipeline `evals/aerospace/lora_pipeline.sh` (data, train, export, judge), rule `evals/score_lora.py`, log
`results/lora.log`. On 36 fresh problems with the calculator: shipped 4B 22, control 26, tuned 28, 8B 28;
routing calm and alert to the tuned 4B: 25/36 at 69% compute (rule needed >= 27). Loose ends:
- [ ] **The LoRA overfit its templates.** Validation loss was 0.000 from step 200 of 600, since the
      validation split came from the same templates; calm answers broke the way the templates taught
      (Pa printed as kPa, a unitless ratio labeled kN, a lookup "computed" as 287.1). Next try: hold out
      whole templates for validation, stop at the best held-out loss, add lookup and conversion examples.
      Judge on new problems (ae-l-* are seen).
- [ ] **Post-hoc hypothesis: send aerospace intensive problems to the tuned 4B** (9/11 vs the 8B's 5/11 on
      ae-l-*). Chosen after seeing results; needs a new fresh set and a rule fixed first.
- [ ] **Two models left in Ollama**: `plm-qwen3-4b-aero-lora` and `plm-qwen3-4b-control` (Q8_0, about
      4.3 GB each), kept for the hypotheses above; `ollama rm` them when done. The scratch work folder
      holds the adapter (small); rebuilding needs `MLX_PY`, `LLAMACPP` and `WORK` as in the pipeline.

## Publishing (phase 5), 2026-10-25
- [x] **Pre-publish pass (2026-11-05):** no keys or tokens in any tracked file or in history. README now has a clone
      command, a caveats section (eval sets written by Claude, small sets, one Mac) and credits for every public
      benchmark; the two Spider files in `evals/router/` are credited and marked CC BY-SA 4.0 (checked on Spider's
      page). Benchmark data itself isn't redistributed; results hold model answers and ids only.
- [x] **Author email removed (2026-11-05):** history rewritten with git-filter-repo to the GitHub noreply address
      (`280029870+ro-rbl@users.noreply.github.com`, now this repo's `user.email`) and force-pushed; tree identical
      but for one redacted line. Commit IDs all changed (IDs cited in docs updated). Backup of the old history:
      `~/ClaudeCoding/plm-orchestrator-backup-20261105.bundle`. Home path in 5 logs kept (user's call).
- [x] **Hugging Face dataset refreshed (2026-11-05):** 23 new files, 5 updated, card updated (Spider router files
      CC BY-SA 4.0); re-diff against the repo shows nothing missing. Public since 2026-11-05.
- [x] **Public (2026-11-05):** GitHub repo and Hugging Face dataset made public by the user; confirmed with anonymous
      requests. Fresh install with no git credentials: `uv tool install "plm-core @ git+https://github.com/ro-rbl/plm-orchestrator#subdirectory=packages/plm-core"`,
      then `plm packs install electrical` (from GitHub) and a live question: 22 V, checked. PyPI names still unclaimed.
- [ ] **`--thorough` wasn't re-measured with the coder alone** (it was 42/45 at 228% with the old cascade).
      Resume: a thorough column in `evals/bench_code.py`, judged on new tasks.
- [ ] **Physics vs aerospace/electrical overlap on LaTeX mechanics** (lx12 "crane ... watts" -> electrical;
      25 SciBench problems -> aerospace). Same term-count overlap as plain text; fix needs new held-out cases.
- [ ] **Mac DNS (mDNSResponder) stopped resolving on 2026-10-24** while direct DNS worked; downloads used
      pinned addresses. Fix (needs the password): `sudo killall -HUP mDNSResponder`.
- [ ] **CAD: cascades 35/195 vs coder 28 on CADPrompt** (0 to +14, not clear). The check catches most wrong CAD
      parts (146-161 of 167-183; they fail to build), so a cascade judged on new parts could pay. CADPrompt asks
      in "units", not mm, so the pack's size check rarely applies; most misses are API errors (no_part).
- [ ] **No public benchmark for electrical or aerospace.** Options: problems written by someone other than Claude,
      or a textbook set with a licence that allows it.
- [ ] **The check can't see a query that runs but answers something else.** 2 of the 8B's 3 misses ran
      (`SELECT COUNT(*) AS count` with no FROM; order ids from order_items); live, the 4B answered "average
      fare per km" with `AVG(fare) / AVG(km)`, which runs, and was trusted. Ideas, each to judge on new
      tasks: flag a query that names none of the schema's tables, or one returning no rows on given sample rows.
      On the fresh sets the check caught 4 of 26 wrong queries: this is now the pack's main weakness.
      2026-10-29: result flags on a real database (`plm_sql/flags.py`) caught 194 of the coder's 668 wrong
      Spider queries, but with 170 false alarms (the tables flag: 38 caught, 86 false). Noticed after the
      verdict; tightening it needs new questions to judge. Without a database, still schema-only.
      2026-11-04: the tables flag folds plurals badly (`plm_sql/flags.py:stem`: "movies" -> "movy", "wines" ->
      "win", "courses" -> "cours"), so a question naming those tables names none; the routing claim matches
      every singular form instead (`plm_sql/claims.py:forms`). 2026-11-08, checked on seen answers before
      spending a run: matching plural forms both ways moves the policy score by at most 1 per set (Spider
      2230 -> 2229, BIRD 534 -> 534, Spider train 2450 -> 2451) and trades a few false alarms for a few catches.
      Not worth a judged run; left as is. The flag's limit is the name-matching idea, not the plurals.
- [ ] **A schema written in prose is unchecked** ("a table sales(region, month, amount)", routing case q03):
      only CREATE TABLE statements are run. Building a table from such a signature is untested.
- [ ] **Level misses** (left as measured): eval 42/45, holdout 24/24, but fresh 19/24 and fresh2 14/24, so the
      cues don't carry to new schemas well. Harmless while every level uses the 8B (only budgets differ).
      `plm_sql/levels.py`.

## Q8_0 small tier: measured, not adopted (2026-10-23)
bartowski's Qwen3-4B Q8_0 against the shipped Q4_K_M (same GGUF repo, same template), with the calculator,
on the electrical, aerospace and physics eval sets plus 36 fresh problems (`evals/<pack>/fresh_quant.jsonl`,
written first). Rule `evals/score_quant.py` QUANT_RULE, run `results/run_quant.sh`, log `results/quant.log`.
Q8_0 vs Q4_K_M: electrical 42+10 vs 47+10, aerospace 37+10 vs 32+6, physics 44+11 vs 45+11 (eval + fresh).
Disagreements 11 to 8, sign test p = 0.32, electrical -5: part 1 fails. Loose ends:
- [ ] **Q8_0 is better on aerospace only** (+9 over 62 problems), worse on electrical, where 4 of its 5 losses
      are prefix/scale slips ("0.0001592 Hz" for 5033 Hz, "0.0133 hours" for 13.3 h). Post-hoc; and even on
      aerospace, routing calm + alert to it scored 46/62, the same as the shipped 8B + calculator, at 42% vs
      40% compute, so it would not ship there either.
- [ ] **`hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q8_0` is left in Ollama** (4.3 GB, imported from the GGUF after
      `ollama pull` stalled at "pulling manifest" on hotel wifi; SHA-256 matched Hugging Face's). `ollama rm`
      it unless the aerospace idea above gets a fresh set.

## CAD pack: loose ends
- [ ] **The CAD check now sees holes, but not other features.** v1 of a hole check wasn't adopted (it flagged
      a correct L-bracket); v2, judged on a second fresh set written before it (`evals/cad/fresh2.jsonl`,
      `evals/score_cad_check.py --set fresh2.jsonl --variant v2`), was: 32 of 38 wrong parts caught to the
      size check's 25, no false alarm (size had one), coder 7 of 11 to 3. It ships. Still unchecked:
      pockets, slots, chamfers, fillets, positions (a hole in the wrong place passes). The live halfway hole
      is now reported "unverified" instead of trusted.
- [ ] **Grading tolerance was 1% for the first CAD sweep** and passed a blind hole 10 mm deep asked as 12 mm
      (0.5% of volume). It is 0.1% now; regraded, the sweep is coder 16/36 (was 17), 4B 9, 8B 6, and the
      shipped policy (always coder) doesn't change. Fresh parts, at 0.1%: coder 4/15, 4B 1/15, 8B 0/15.
- [ ] **CAD scores are low and the set is small:** 17/36 at best, on 36 parts written by Claude. Wrong
      volume is the coder's commonest miss (10), then wrong size (5). The prompt (`plm_cad/controller.py
      CAD_FORMAT`) gives no CadQuery hints; a v2 with centering and hole idioms is a hypothesis to test on
      new parts, since these 36 have been seen.
- [ ] **The CAD pack's install is 1.3 GB** (CadQuery imports VTK at load, so the VTK-free OCP build can't
      be used). build123d is half the size but the 8B wrote it 0/2 in the preflight; the coder wasn't tried.
- [ ] **CAD routing needs a request verb**, so a bare description ("A 30 mm cube with a hole") goes to
      general; only request-phrased holdout cases were routed (12/12 plus 8/8). `plm_cad/claims.py`.

## Physics: loose ends
- [ ] **The calculator forgets prefix conversions on physics.** (2026-10-26/27: a "convert to the asked unit" prompt
      was ahead on both UGPhysics sets, 53 vs 46 and 55 vs 50, but never clearly; not adopted. `evals/physics_check.py`.)
      Original note: All 7 of the 8B's calculator misses (and 3 of
      the 4B's 5) computed in base units and printed the asked prefixed unit ("5e+04 MPa" for 50 MPa, "678 MJ"
      for 0.678 MJ); the unit checks pass them (same dimension). Why physics and not electrical: its questions
      ask for kPa/kJ/MJ more. A magnitude check can't know the right size; a prompt fix ("convert to the asked
      unit before printing") changes `calc.TOOL_FORMAT` for every pack, so it needs every pack's sweep re-run.
      `results/physics.log`, `packages/plm-core/src/plm/numeric/calc.py:TOOL_FORMAT`.
- [ ] **Unit spellings the grader rejects:** "286.48 rev/min" (the 8B's only direct miss, ph-c15) and "15.0 Nm"
      (4B + calculator, ph-c10) are right numbers graded as unit errors, like "15.58 rev" above. Decide with that
      item; `plm-core: plm/numeric/answers.py:normalize_unit`. Accepting them wouldn't change the pick (8B direct
      would be 50/50).
- [ ] **Physics routing attempt 1 (2026-11-08): measured, not shipped.** PHYS_RULE (cases and rule first, 6483b5b):
      terms from the old holdout misses (speed of sound, in air, gravitational acceleration, bullet, block, string,
      stretch; electrical ignores "N of resistance") gave physics 27/30 (need 28; was 24), others 15/15, eval texts
      279/279, holdout 193/194 (was 188, but designed from it). Reverted; the diff is `docs/attempts/physics_routing_2026-11-08.diff`.
      Remaining misses: pr15 (light bulb, arguably electrical), pr17 ("projectile launched": aerospace wins the tie),
      pr20 ("2 rev/s" isn't a quantity). The pr cases are now seen: a next attempt needs new cases.
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
- [x] **Follow-ups (2026-11-08):** `plm/followup.py`, server and interactive CLI. FOLLOWUP_RULE (cases written
      first, `evals/router/followup_cases.jsonl`): 25/25 follow-ups and 15/15 new messages right, 493/493 one-message
      routings unchanged. A perfect score on cases Claude wrote for a rule Claude wrote: check real conversations
      (`logs/server.jsonl` has a `context` field). Open: answers to follow-ups weren't checked live with models yet
      (`plm` interactive: "A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?" then
      "now for 200 ohm"); a code follow-up that changes behavior keeps the original examples, which the new code
      may fail; on a CAD follow-up ("now make it 10 mm thick") the size check passes both the new part and the
      unchanged old one (checked offline 2026-11-08), so a model that ignores the change isn't caught.
      Live through `plm serve` (2026-11-08, real models): 3/3 follow-ups routed right; answers right 2/3. The
      electrical follow-up ("now for 200 ohm") came back 22 V again, marked checked: the model answered the original
      question. Next: a set of follow-up conversations with answer keys, written first, to judge the task wording.
- [ ] **Units asked as symbols aren't read** (`plm/numeric/checks.py:requested_unit`, found 2026-11-08): "in m/s",
      "in km/h", "in m/s^2" give None, so those answers are reported unchecked; only unit words ("in meters per
      second", "in volts") are recognized. Fixing it changes which answers are checked in every numeric pack, so
      re-run each pack's sweep and simulations after.

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
- Logs (`runs.jsonl`, `server.jsonl`, the server's pid/port files) go to `./logs` when that folder exists (the repo
  root here), else `~/.local/state/plm/` (2026-11-05, `plm/paths.py`; `PLM_LOG_DIR`, `PLM_LOG`). Run from the repo
  root to keep them in `logs/` here.
- **`plm` as a standalone tool (2026-11-05):** `uv tool install ./packages/plm-core` (non-editable, isolated) ran
  from a plain folder; `plm packs install aerospace` with no `--source` installed from the GitHub repo (worked
  while private via stored git credentials) and routed live. From the public git URL: tested 2026-11-05 (see Publishing).
- `with-timeout` does not pass stdin through: `with-timeout N python -m plm < file` sends an empty task (now
  refused), and `with-timeout N python - <<EOF` runs an empty script. Pass `"$(cat file)"` as an argument, or
  write the script to a file.
- Ollama's `qwen3:4b` tag is Qwen3-4B-Thinking-2507 (always reasons first; 31/50 direct answers hit the token
  cap with thinking suppressed), not the original hybrid Qwen3-4B the abliterated build comes from.
- The machine pins `qwen3:8b` in memory ("Forever" in `ollama ps`, 6.3 GB), set by something outside this repo.
  On 2026-10-31 it left the coder unable to load: requests hung with nothing returned (a run stopped on 3
  timeouts), and the coder had been generating at about 4 tok/s. `ollama stop qwen3:8b` fixed both (coder 7-11 s
  per BIRD question, was 26+). Before a long run that doesn't use the 8B: `ollama stop qwen3:8b`, then `ollama ps`.
- The abliterated 4B is no longer a default. Against its own original (same base, quantizer and quant) it
  loses 9 electrical problems answering directly and 4 with the calculator, mostly intensive ones; software
  is within noise. An earlier note here called abliterated models "fine as specialists": that came from
  comparing them with qwen2.5:3b, a different family, and doesn't hold against the original Qwen3-4B.
- Formula-first calculator prompt is not the electrical default: 48/50 at 86% compute vs 47/50 at 36%.
- Agreement (second-opinion) checks are off in electrical: one extra correct answer for 31 points of compute.
- No 0.6B is used as a tier: abliterated 24/50 electrical (direct), 7/45 software; standard qwen3:0.6b 17/50, 14/45.
- `--thorough` is opt-in, not default (see above).
- `gpt-oss:20b` (13 GB) has not been evaluated.
- **An absent pack's tasks go to whichever installed pack still claims them**, not always to general
  (with aerospace not installed, ae-c12 and ae-a20, power in kW, go to electrical). By design of claims;
  recorded in `docs/pack-packaging.md`.
- **No lint configuration in the repo.** A ruff config outside the repo flags 86 style findings (74 on the
  pre-split `main`); the 12 this work added are existing idioms (`# noqa: E402` after `sys.path` inserts)
  or deliberate (`discover()` catches any exception from a pack; `subprocess.run` checked by return code).
  `ruff check --select E9,F packages evals` is clean.
