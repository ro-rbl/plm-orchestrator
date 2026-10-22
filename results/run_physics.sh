#!/bin/zsh
# Physics sweep: the two tiers, direct and with the calculator, on the 50 physics problems.
# Policies and the rule that picks among them were committed before this ran
# (evals/simulate_routing.py: POLICIES_PHYSICS, PHYSICS_RULE).
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b; do
  for s in bare tool; do
    with-timeout 3600 .venv/bin/python evals/run.py evals/physics/problems.jsonl --model "$m" --strategy "$s"
  done
done
.venv/bin/python evals/simulate_routing.py --pack physics --checks
