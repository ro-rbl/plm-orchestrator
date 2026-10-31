#!/bin/zsh
# Confirmation of the SQL flags policy on BIRD dev's 1036 questions mini-dev doesn't use: the coder, then the 4B.
# CONFIRM_RULE was committed in evals/bench_sql_check.py before this ran. Resumes. Usage: results/run_sql_confirm.sh
cd "$(dirname "$0")/.."
for m in qwen2.5-coder:14b hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M; do
  with-timeout 28800 .venv/bin/python evals/bench_sql_check.py --set bird --model "$m" || exit $?
done
.venv/bin/python evals/bench_sql_check.py --simulate --sets bird
