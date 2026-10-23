#!/bin/zsh
# CAD sweep: the three models the pack can use, on the 36 CAD problems, each part built by the kernel.
# Policies and the rule that picks among them were committed before this ran (evals/run_cad.py:
# POLICIES_CAD, CAD_RULE).
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b qwen2.5-coder:14b; do
  with-timeout 5400 .venv/bin/python evals/run_cad.py --model "$m"
done
.venv/bin/python evals/run_cad.py --simulate
