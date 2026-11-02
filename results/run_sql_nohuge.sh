#!/bin/zsh
# Dropping the SQL pack's "huge" flag, judged on 3000 sampled Spider train questions: the coder on all of them,
# then the 4B only where the coder's query raised a flag. NOHUGE_RULE was committed in evals/bench_sql_check.py
# before this ran. Resumes. Usage: results/run_sql_nohuge.sh >> results/sql_nohuge.log 2>&1 &
cd "$(dirname "$0")/.."
with-timeout 43200 .venv/bin/python evals/bench_sql_check.py --set train --model qwen2.5-coder:14b --timeout 900 || exit $?
with-timeout 14400 .venv/bin/python evals/bench_sql_check.py --set train --model hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M --timeout 900 --only-flagged || exit $?
.venv/bin/python evals/bench_sql_check.py --simulate-nohuge
