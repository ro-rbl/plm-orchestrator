# NEXT

_Updated: 2026-10-23 · branch: main · plan: ROADMAP.md_

## Start here (next session)
- Merged on `main`: **separately installable packs**, all six steps of `docs/pack-packaging.md`. The code
  is now `packages/plm-core` (import `plm`) plus `plm-electrical`, `plm-aerospace`, `plm-software`
  (`plm_<name>`), found through the `plm.packs` entry point; `plm packs list|install|remove|doctor`.
  Behavior with all packs installed is unchanged (`evals/dump_decisions.py` identical: 272 texts,
  1716 checks; routing simulations match the pre-split `main`).
- Then **decompose-then-solve** was built and measured, and **not adopted** (`ROADMAP.md` 3b; rule in
  `evals/score_decompose.py`, run log `results/decompose.log`): 5/15 vs 6/15 on fresh problems, 6/15 vs
  7/15 on the eval set's intensive ones, at 2.4x the tokens. Next, unless decided otherwise:
  1. All SKY-001 ideas are measured (`ROADMAP.md` 3b). Open hypotheses, each needing a fresh set: a LoRA v2
     (held-out templates, early stop), the tuned 4B for aerospace intensive (see "Aerospace LoRA" below).
     A Q8_0 small tier was tested and not adopted ("Q8_0 small tier" below). The SQL pack is built (below).
     The unreferenced Ollama blobs were pruned on 2026-10-23 (Ollama restarted). The CAD pack's open
     items are in "CAD pack: loose ends" (repair retry and a hole check v2 are done: one adopted, one not).
- **An existing `.venv` from before the split has no `plm` any more** (it was on `sys.path` from the repo
  root, which no longer has `plm/`; `requirements.txt` is gone). Reinstall: `uv pip install --python
  .venv/bin/python -e packages/plm-core -e packages/plm-electrical -e packages/plm-aerospace -e packages/plm-software`.
- Local branch `separate-packs` is merged and can go: `git branch -d separate-packs`.
- Then the **physics pack** was built and swept (`ROADMAP.md` 3): everything to the 8B answering directly,
  49/50. The SQL pack followed (see "SQL pack: built").

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
- [x] **The same-route control beat the shipped 4B** (26 vs 22). Tested as a Q8_0 small tier: not adopted
      (below), so the control's edge wasn't the quantization in general.
- [ ] **Two models left in Ollama**: `plm-qwen3-4b-aero-lora` and `plm-qwen3-4b-control` (Q8_0, about
      4.3 GB each), kept for the hypotheses above; `ollama rm` them when done. The scratch work folder
      holds the adapter (small); rebuilding needs `MLX_PY`, `LLAMACPP` and `WORK` as in the pipeline.

## Physics check, 2026-10-26 (`evals/physics_check.py`, `results/physics_check.log`)
- [x] Two candidates judged on 150 unseen UGPhysics problems, CHECK_RULE fixed first: **convert** (the calculator
      converts to the asked unit before printing) 53/150 vs the shipped policy's 46 at 83% of its compute, interval
      -2 to +17: not clear, so the shipped policy stays. **disagree** (escalate when 4B calc and 4B direct differ)
      46/150 at 158%: no gain.
- [x] **"convert" confirmation** (153 unused UGPhysics problems, CONVERT_RULE fixed first,
      `results/physics_check_confirm.log`): convert 55 vs shipped 50 (a: yes), pooled over 303 problems 108 vs 96 with
      interval +0 to +25 (b: not entirely above 0), and 112% of the shipped compute here (c: no). Kept the shipped prompt.
      Ahead on both sets (+7, +5) but never clearly; UGPhysics has no unused eligible problems left, so a further test
      needs another physics set, or problems written by someone else.
- [x] A crash took Ollama down mid-run; 60 calls were saved as "connection refused" rows that resuming skipped.
      They were dropped and re-run (backup of the bad file was in the session scratchpad); every other results file
      was audited: no failed calls anywhere else.
- [x] **Every runner now stops when Ollama is unreachable** (`plm.ollama.unreachable`, 11 sites in 11 files)
      instead of saving error rows a resume would skip; tested live: down server -> stops, 0 rows; missing model ->
      error rows as before.

## Publishing (phase 5), 2026-10-25
- [x] GitHub: https://github.com/ro-rbl/plm-orchestrator, **private**, `main` pushed (MIT license; home paths
      replaced by ~ in the current files, still present in older commits).
- [x] Hugging Face dataset: https://huggingface.co/datasets/rblrbl/plm-orchestrator-evals, **private**, 140 files
      (eval sets, every model answer, RESULTS.md, dataset card; no benchmark data, no CADPrompt references).
      It was public for about a minute on upload (`hf upload` created it before `hf repos create` ran) and was
      then set private; anonymous access now returns 401.
- [ ] **Going public is the user's call:** `gh repo edit ro-rbl/plm-orchestrator --visibility public
      --accept-visibility-change-consequences` and, for the dataset, `HfApi().update_repo_settings(...,
      private=False)`. Then check `pip install "plm-core @ git+https://github.com/ro-rbl/plm-orchestrator#subdirectory=packages/plm-core"`
      in a fresh venv (untested while private), and claim the PyPI names if publishing there.

## SQL pack: built (2026-10-23)
`packages/plm-sql`; eval set `evals/sql/build_tasks.py` (45 tasks, 3 seeded databases, 24 level holdouts, 12
routing cases), sweep `results/run_sql.sh`, log `results/sql.log`. Ships 4B first, the coder when the query
doesn't run: 45/45 at 45% of always-coder compute. Loose ends:
- [x] **Policy settled on two fresh sets: everything to the 8B.** The eval-set pick (4B -> coder, 45/45) was
      not confirmed on `evals/sql/fresh.jsonl` (FRESH_RULE: 18/24 vs 22/24); that set's candidate (intensive
      8B -> coder) failed on `evals/sql/fresh2.jsonl` (FRESH2_RULE: 18/24 vs 22/24 for the coder), so the rule
      shipped SQL_RULE's pick over both pooled: always 8B, 42/48 at 60% (coder 42/48 at 100%). Logs
      `results/sql_fresh.log`, `results/sql_fresh2.log`. Each rule was committed before its set ran.
- [x] **SQL now ships the coder alone (user's choice, 2026-10-24).** Public benchmarks (`evals/bench_sql.py`,
      `results/bench_spider.log`, `results/bench_bird_verdict.log`): coder Spider 76% / BIRD 51%, 8B 67% / 35%.
      The compute-capped BENCH_RULE/BIRD_RULE kept the 8B; the user chose accuracy at 1.5-1.8x compute.
- [x] **HumanEval+ and MBPP+ for the software pack** (`evals/bench_code.py`, `results/bench_code.log`): CODE_RULE
      adopted the coder alone, 410/540 vs the cascade's 387 (+6 to +40). Shipped 2026-10-24.
- [ ] **`--thorough` wasn't re-measured with the coder alone** (it was 42/45 at 228% with the old cascade).
      Resume: a thorough column in `evals/bench_code.py`, judged on new tasks.
- [x] **SciBench physics** (`evals/bench_physics.py`, `results/bench_physics.log`): PHYS_RULE adopted 4B+calc
      escalating to 8B+calc, 69/144 vs 52 for the old 8B-direct policy, at 48% of its compute. On our own
      50-problem set this policy scored 44/50 vs 49/50: the public set wins (larger, written by others).
- [x] **LaTeX is read as plain text** (`plm/latex.py`, in routing, unit checks and numeric levels). LATEX_RULE:
      held-out LaTeX cases 12 -> 19/20, no decision on plain text changed. SciBench physics now routes 73/144
      to physics (was 30); 41 still go to general (most ask for no unit), 25 to aerospace (mechanics terms).
- [ ] **Physics vs aerospace/electrical overlap on LaTeX mechanics** (lx12 "crane ... watts" -> electrical;
      25 SciBench problems -> aerospace). Same term-count overlap as plain text; fix needs new held-out cases.
- [ ] **Mac DNS (mDNSResponder) stopped resolving on 2026-10-24** while direct DNS worked; downloads used
      pinned addresses. Fix (needs the password): `sudo killall -HUP mDNSResponder`.
- [x] **GSM8K** (`evals/bench_gsm8k.py`, `results/bench_gsm8k.log`): 8B direct 272/300 vs 8B+calc 261 (-21 to -1,
      paired 95%): on everyday arithmetic the calculator costs accuracy. The general pack stays; no candidate.
- [x] **TheoremQA physics** confirms the switch; **CADPrompt** keeps the coder (`results/bench_theoremqa.log`,
      `results/bench_cad.log`, `docs/results.md`).
- [ ] **CAD: cascades 35/195 vs coder 28 on CADPrompt** (0 to +14, not clear). The check catches most wrong CAD
      parts (146-161 of 167-183; they fail to build), so a cascade judged on new parts could pay. CADPrompt asks
      in "units", not mm, so the pack's size check rarely applies; most misses are API errors (no_part).
- [ ] **No public benchmark for electrical or aerospace.** Options: problems written by someone other than Claude,
      or a textbook set with a licence that allows it.
- [ ] **Phase 4 next: then numeric cross-checks (GSM8K, optional), and
      the headline table (always-small, always-large, router, hindsight per domain) for publishing.
- [ ] **The SQL policy now has no unseen set behind it.** Both fresh sets were used to choose it (the second
      by a rule fixed first, but pooled with the first). A third fresh set, or Spider/BIRD, would test it.
- [ ] **Which model is best flipped between the fresh sets** (8B 22 vs coder 20, then coder 22 vs 8B 20): on
      24 tasks, 2 tasks is noise. The pooled tie (42 each) went to the 8B on compute alone.
- [ ] **The eval set is near its ceiling** (coder alone 44/45, 4B 40); the fresh set is harder (20/24) and
      reversed the ranking. Spider/BIRD (`ROADMAP.md` 4) would test the routing properly.
- [ ] **The check can't see a query that runs but answers something else.** 2 of the 8B's 3 misses ran
      (`SELECT COUNT(*) AS count` with no FROM; order ids from order_items); live, the 4B answered "average
      fare per km" with `AVG(fare) / AVG(km)`, which runs, and was trusted. Ideas, each to judge on new
      tasks: flag a query that names none of the schema's tables, or one returning no rows on given sample rows.
      On the fresh sets the check caught 4 of 26 wrong queries: this is now the pack's main weakness.
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

## Aerospace LoRA for the 4B: preflight (2026-10-23)
Live on this Mac (24 GB, arm64), throwaway venv in the session scratchpad:

| Dependency | Result | Evidence |
|---|---|---|
| MLX LoRA tooling | GREEN | `mlx-lm` 0.32.2 on the GPU; `mlx-community/Qwen3-4B-4bit` (base `Qwen/Qwen3-4B`, the shipped 4B's original) loads and answers in 2.7 s |
| Download | GREEN, slow | 2.8 GB in 53 min tonight (one stall at 20 min, resumed) |
| LoRA training | GREEN | 10 iterations, rank 8, 4 layers, on 8 template examples (not eval or holdout): adapter saved, loads, generates |
| Adapter straight into Ollama (`ADAPTER`) | RED | Ollama 0.33: "no Modelfile or safetensors files found", three tries; MLX names weights `lora_a/lora_b`, not PEFT's |
| Fused safetensors into Ollama | RED | `ollama create` from the fused, dequantized model: "unsupported architecture Qwen3ForCausalLM" |
| Fused -> llama.cpp GGUF -> Ollama | GREEN | `mlx_lm fuse --dequantize`, then `convert_hf_to_gguf.py` (needed `extra_special_tokens` dropped from the fused tokenizer config: mlx-lm writes a list, the converter's transformers wants a dict), then `ollama create -q q4_K_M`: 2.5 GB, stops cleanly, chat template embedded, `plm.ollama.chat` works |

Verdict: **GO** via fuse -> GGUF. Not proven: that the tokenizer edit is harmless beyond short answers (13
special tokens dropped from one config), training time for a real run, and that LoRA helps at all.
Cleanup owed: about **16 GB of unreferenced Ollama blobs** from the failed imports (created 04:44-04:50
on 2026-10-23); Ollama prunes them when its server restarts. Next: a template generator for aerospace
problems (new templates, never the 50 eval or 24 holdout problems), a rule fixed first (does the tuned
4B close the alert gap: 75% vs the 8B's 90%), and a fresh aerospace set to judge it.

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
`plm-cad` pack. Done since: the pack is built (`ROADMAP.md` 3b).

## CAD pack: loose ends
- [ ] **The CAD check now sees holes, but not other features.** v1 of a hole check wasn't adopted (it flagged
      a correct L-bracket); v2, judged on a second fresh set written before it (`evals/cad/fresh2.jsonl`,
      `evals/score_cad_check.py --set fresh2.jsonl --variant v2`), was: 32 of 38 wrong parts caught to the
      size check's 25, no false alarm (size had one), coder 7 of 11 to 3. It ships. Still unchecked:
      pockets, slots, chamfers, fillets, positions (a hole in the wrong place passes). The live halfway hole
      is now reported "unverified" instead of trusted.
- [x] **Repair retry: built, measured, not adopted.** One retry of a flagged part with its program and the
      check's finding (`plm_cad/controller.py repair_prompt`, `repairs: 0`). Preflight on the seen set fixed
      0 of 15 (v1: 8 repairs were the same program; v2, a mechanical fix, still 7). On cad-h*, written first
      (`evals/score_cad_repair.py`): 0 of 9 repairs fixed, 1.56x tokens. At temperature 0 the coder can't
      repair its CadQuery from this feedback. Untested next steps, if wanted: a different repairer (the 8B
      with thinking on), or sampling instead of temperature 0, each judged on new parts.
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
- **An absent pack's tasks go to whichever installed pack still claims them**, not always to general
  (with aerospace not installed, ae-c12 and ae-a20, power in kW, go to electrical). By design of claims;
  recorded in `docs/pack-packaging.md`.
- **No lint configuration in the repo.** A ruff config outside the repo flags 86 style findings (74 on the
  pre-split `main`); the 12 this work added are existing idioms (`# noqa: E402` after `sys.path` inserts)
  or deliberate (`discover()` catches any exception from a pack; `subprocess.run` checked by return code).
  `ruff check --select E9,F packages evals` is clean.
