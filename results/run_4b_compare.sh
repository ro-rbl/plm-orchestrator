#!/bin/zsh
# Fair 4B comparators for the abliterated Qwen3-4B (same runs it had):
#   original Qwen3-4B, same quantizer and quant (bartowski Q4_K_M): does abliteration matter?
#   Qwen3-4B-Instruct-2507: the current standard non-thinking 4B, candidate public default.
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:4b-instruct-2507-q4_K_M; do
  for s in bare tool; do
    with-timeout 3600 .venv/bin/python evals/run.py evals/electrical/problems.jsonl --model "$m" --strategy "$s"
  done
  with-timeout 7200 .venv/bin/python evals/run_code.py evals/software/tasks.jsonl --model "$m"
done
