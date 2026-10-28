#!/bin/zsh
# SQL result flags (plm_sql.flags): the 4B and the coder on Spider's 734 unused dev questions, then all 2147
# Spider test questions. CANDIDATE and FLAGS_RULE were committed in evals/bench_sql_check.py before this ran.
# Resumes: answered questions are skipped. Usage: results/run_sql_check.sh
cd "$(dirname "$0")/.."
for s in rest test; do
  for m in qwen2.5-coder:14b hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M; do
    with-timeout 28800 .venv/bin/python evals/bench_sql_check.py --set "$s" --model "$m" || exit $?
  done
done
.venv/bin/python evals/bench_sql_check.py --simulate
