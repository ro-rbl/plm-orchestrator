#!/bin/zsh
# GSM8K numeric cross-check: 300 sampled problems, the 8B direct and with the calculator, the 4B with it.
# GSM_RULE was committed in evals/bench_gsm8k.py before this ran.
cd "$(dirname "$0")/.."
with-timeout 14400 .venv/bin/python evals/bench_gsm8k.py --model qwen3:8b --strategy bare
with-timeout 14400 .venv/bin/python evals/bench_gsm8k.py --model qwen3:8b --strategy tool
with-timeout 14400 .venv/bin/python evals/bench_gsm8k.py --model hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M --strategy tool
.venv/bin/python evals/bench_gsm8k.py --simulate
