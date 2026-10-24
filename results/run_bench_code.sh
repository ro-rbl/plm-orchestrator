#!/bin/zsh
# Public code benchmarks for the software pack: the three models on HumanEval+ (164) and MBPP+ (378).
# Policies and CODE_RULE were committed in evals/bench_code.py before this ran.
cd "$(dirname "$0")/.."
for b in humaneval mbpp; do
  for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b qwen2.5-coder:14b; do
    with-timeout 21600 .venv/bin/python evals/bench_code.py --bench $b --model "$m"
  done
done
.venv/bin/python evals/bench_code.py --simulate
