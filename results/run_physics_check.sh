#!/bin/zsh
# Physics check candidates on 150 UGPhysics problems: 4B and 8B, direct, calculator, and calculator with the
# convert-to-the-asked-unit note. Candidates and CHECK_RULE were committed in evals/physics_check.py before this ran.
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b; do
  for s in tool convert bare; do
    with-timeout 14400 .venv/bin/python evals/physics_check.py --model "$m" --strategy $s
  done
done
.venv/bin/python evals/physics_check.py --simulate
