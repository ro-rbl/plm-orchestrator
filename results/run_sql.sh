#!/bin/zsh
# SQL sweep: the three models on the 45 SQL tasks. Policies and the rule that picks among them
# were committed before this ran (evals/run_sql.py: POLICIES_SQL, SQL_RULE).
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b qwen2.5-coder:14b; do
  with-timeout 3600 .venv/bin/python evals/run_sql.py --model "$m"
done
.venv/bin/python evals/run_sql.py --simulate
