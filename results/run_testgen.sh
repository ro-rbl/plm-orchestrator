#!/bin/zsh
# Test-writer sweep: each writer generates extra tests for all 45 code tasks, then
# every saved candidate solution is checked against them (no model calls).
cd "$(dirname "$0")/.."
for w in \
  hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M \
  qwen3:8b \
  qwen2.5-coder:14b
do
  with-timeout 7200 .venv/bin/python evals/gen_tests.py gen --writer "$w"
done
with-timeout 3600 .venv/bin/python evals/gen_tests.py check
