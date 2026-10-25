#!/bin/zsh
# SciBench physics (fund + class, 144 problems) for the physics pack: 4B and 8B, bare and with the calculator.
# Policies and PHYS_RULE were committed in evals/bench_physics.py before this ran.
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b; do
  for s in bare tool; do
    with-timeout 14400 .venv/bin/python evals/bench_physics.py --bench "${1:-scibench}" --model "$m" --strategy $s
  done
done
.venv/bin/python evals/bench_physics.py --bench "${1:-scibench}" --simulate
