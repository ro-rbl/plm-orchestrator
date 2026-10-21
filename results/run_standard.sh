#!/bin/zsh
# Standard (non-abliterated) Qwen3 4B and 0.6B on both packs, to decide the public defaults.
cd "$(dirname "$0")/.."
for m in qwen3:0.6b qwen3:4b; do
  for s in bare tool; do
    with-timeout 3600 .venv/bin/python evals/run.py evals/electrical/problems.jsonl --model "$m" --strategy "$s"
  done
  with-timeout 7200 .venv/bin/python evals/run_code.py evals/software/tasks.jsonl --model "$m"
done
