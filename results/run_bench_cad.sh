#!/bin/zsh
# CADPrompt for the CAD pack: the three models on the parts whose reference builds (evals/bench_cad.py --verify).
# Policies and CADP_RULE were committed in evals/bench_cad.py before this ran.
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b qwen2.5-coder:14b; do
  with-timeout 21600 .venv/bin/python evals/bench_cad.py --model "$m"
done
.venv/bin/python evals/bench_cad.py --simulate
