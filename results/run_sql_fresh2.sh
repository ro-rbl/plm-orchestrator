#!/bin/zsh
# SQL second fresh set: the three models on 24 new tasks, to judge the candidate (FRESH2_RULE in
# evals/run_sql.py, committed with the tasks before this ran).
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b qwen2.5-coder:14b; do
  with-timeout 3600 .venv/bin/python evals/run_sql.py --model "$m" --tasks evals/sql/fresh2.jsonl
done
.venv/bin/python evals/run_sql.py --simulate --tasks evals/sql/fresh2.jsonl
