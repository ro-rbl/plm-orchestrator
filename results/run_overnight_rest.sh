#!/bin/zsh
# After fusion round 3: follow-up answers (A then B), then fresh numeric answers for UNITS2_RULE. Each step resumes.
cd "$(dirname "$0")/.."
with-timeout 7200 .venv/bin/python evals/followup/run.py --variant A || exit $?
with-timeout 7200 .venv/bin/python evals/followup/run.py --variant B || exit $?
with-timeout 10800 .venv/bin/python evals/units_fresh.py --model hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M || exit $?
with-timeout 10800 .venv/bin/python evals/units_fresh.py --model qwen3:8b || exit $?
