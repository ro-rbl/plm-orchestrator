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
- [ ] Standard `qwen3:4b` / `qwen3:0.6b` vs the abliterated builds on both packs, to pick public defaults.

## 2. Router endpoint
- `plm serve`: OpenAI-compatible `/v1/models` and `/v1/chat/completions` (with streaming),
  one model id `plm-router`. The routing report travels in an extra response field.
- A general fallback pack for prompts no pack claims (large model, reported as unchecked).
- Port from config/env, or a free one printed at startup. Health check asserts on the body.
- Log what share of real traffic each pack gets: if most prompts fall through to the
  general pack, routing saves little and the packs to build next should follow the logs.

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
