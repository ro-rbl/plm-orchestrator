#!/bin/zsh
# Baseline sweep: every tier model, bare (no tools), thinking off.
cd "$(dirname "$0")/.."
for m in \
  hf.co/bartowski/mlabonne_Qwen3-0.6B-abliterated-GGUF:Q4_K_M \
  qwen2.5:3b \
  qwen3:8b \
  hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M
do
  with-timeout 3600 .venv/bin/python evals/run.py evals/electrical/problems.jsonl --model "$m"
done
