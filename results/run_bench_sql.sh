#!/bin/zsh
# Public SQL benchmarks for the SQL pack: the three models on Spider (300 sampled dev questions), then
# BIRD mini-dev (500). Sample, policies and BENCH_RULE were committed in evals/bench_sql.py before this ran.
# Usage: results/run_bench_sql.sh spider|bird
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b qwen2.5-coder:14b; do
  with-timeout 21600 .venv/bin/python evals/bench_sql.py --bench "$1" --model "$m"
done
.venv/bin/python evals/bench_sql.py --bench "$1" --simulate
