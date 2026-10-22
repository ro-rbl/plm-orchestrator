#!/bin/zsh
# Unit-aware calculator sweep (ROADMAP 3b): both numeric packs, both tier models.
# Policies and the adoption rule were committed before this ran (evals/simulate_routing.py, UNITS_RULE).
cd "$(dirname "$0")/.."
for set in electrical aerospace; do
  for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b; do
    with-timeout 3600 .venv/bin/python evals/run.py evals/$set/problems.jsonl --model "$m" --strategy units
  done
done
