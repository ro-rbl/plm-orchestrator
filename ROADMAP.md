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
- [ ] Physics/mechanical: numeric with units, so it reuses `plm/numeric/` (add unit words to
      `plm/numeric/checks.py:UNIT_WORDS`, chain cues in a new `levels.py`). ~50 problems, a
      holdout, routing policies fixed before the sweep.
- SQL: queries run against a small SQLite database; the check is that the query executes
  and matches any example results, like the software pack's examples.

## 3a. Separately installable packs
- [ ] The core installs alone (everything goes to the general pack); each domain pack is its own
      package found through the `plm.packs` entry point; `plm packs install <name>` installs a pack
      and pulls its models. Design and step-by-step migration with checks: `docs/pack-packaging.md`.

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
- [ ] **Decompose, then solve, for intensive problems.** The large model lists the intermediate
      quantities with units; each is computed and checked, then combined. Test on aerospace intensive
      (8B + calculator: 47%); success = higher accuracy at a compute cost stated up front.
- [ ] **CAD pack checked by a real CAD kernel.** The model writes CadQuery or build123d code; the check
      is that it builds a valid solid with the requested dimensions (bounding box, volume) -- the check
      SKY-001 lacks. Preflight first: install size and Apple Silicon wheels of the kernel (OpenCascade).
- [ ] **Fine-tune the 4B for aerospace (LoRA, e.g. with MLX).** Train on generated problems from new
      templates, never on the 50 eval or 24 holdout problems; success = the 4B closes the alert gap
      (75% vs the 8B's 90%), which would let routing pay off in aerospace.
- Benchmark lesson: SKY-001's claims are its own, on its own benchmark. Keep holdouts written first
  and policies fixed before sweeps for anything published here.

## 4. Public benchmarks
- Code: EvalPlus (HumanEval+/MBPP+), LiveCodeBench (problems newer than the models).
- SQL: Spider or BIRD. Physics: a public set, to be chosen. Optional numeric cross-check: GSM8K.
- Hundreds of items per domain with bootstrap confidence intervals; pinned model digests,
  versioned prompts, recorded hardware; one command reproduces every number.
- Headline per domain: quality vs compute for always-small, always-large, the router, and the
  hindsight bound.

## 5. Publish
- GitHub repo, installable with `pip install` from git.
- Hugging Face dataset: our eval sets and every result file, with a dataset card; optional Space.
- Public benchmarks are referenced, not redistributed (each has its own license).
- Needs at that point: a GitHub remote and a Hugging Face token, both tested live before use.
