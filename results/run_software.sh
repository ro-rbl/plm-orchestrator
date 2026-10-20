#!/bin/zsh
# Software-pack sweep: every candidate specialist on the 45 code tasks.
cd "$(dirname "$0")/.."
for m in \
  hf.co/bartowski/mlabonne_Qwen3-0.6B-abliterated-GGUF:Q4_K_M \
  hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M \
  qwen3:8b \
  qwen2.5-coder:14b
do
  with-timeout 7200 .venv/bin/python evals/run_code.py evals/software/tasks.jsonl --model "$m"
done
