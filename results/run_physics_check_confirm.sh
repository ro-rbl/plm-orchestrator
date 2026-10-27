#!/bin/zsh
# Confirm "convert" on the 153 UGPhysics problems the first sample didn't use: the runs the shipped policy and convert
# need (no 4B direct). CONVERT_RULE was committed in evals/physics_check.py before this ran. Resumes.
cd "$(dirname "$0")/.."
for run in "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M tool" "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M convert" \
           "qwen3:8b tool" "qwen3:8b convert" "qwen3:8b bare"; do
  m=${run% *}; s=${run##* }
  with-timeout 14400 .venv/bin/python evals/physics_check.py --set confirm --model "$m" --strategy $s || exit 1
done
.venv/bin/python evals/physics_check.py --set confirm --simulate
