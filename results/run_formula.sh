#!/bin/zsh
# Formula-first calculator sweep: like run_tools.sh, but the model states the formula first.
cd "$(dirname "$0")/.."
for m in \
  hf.co/bartowski/mlabonne_Qwen3-0.6B-abliterated-GGUF:Q4_K_M \
  qwen2.5:3b \
  hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M \
  qwen3:8b
do
  with-timeout 3600 .venv/bin/python evals/run.py evals/electrical/problems.jsonl --model "$m" --strategy formula
done
