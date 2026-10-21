#!/bin/zsh
# Aerospace sweep: the two tiers of the aerospace pack, direct and with the calculator.
# Routing policies for these results were fixed beforehand (evals/simulate_routing.py --pack aerospace).
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b; do
  for s in bare tool; do
    with-timeout 3600 .venv/bin/python evals/run.py evals/aerospace/problems.jsonl --model "$m" --strategy "$s"
  done
done
