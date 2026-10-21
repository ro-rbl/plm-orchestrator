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
- Aerospace, then physics/mechanical: numeric with units, so they reuse `plm/numeric/`
  (add unit words to `plm/numeric/checks.py:UNIT_WORDS`). ~50 problems, a holdout,
  routing policies fixed before the sweep.
- SQL: queries run against a small SQLite database; the check is that the query executes
  and matches any example results, like the software pack's examples.

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
