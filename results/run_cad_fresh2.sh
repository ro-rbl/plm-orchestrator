#!/bin/zsh
# The three CAD models on the second fresh set, to judge the hole check's v2
# (rule committed before this ran: evals/score_cad_check.py, CHECK_RULE, --variant v2).
cd "$(dirname "$0")/.."
for m in hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M qwen3:8b qwen2.5-coder:14b; do
  with-timeout 3600 .venv/bin/python evals/run_cad.py --model "$m" --problems evals/cad/fresh2.jsonl
done
.venv/bin/python evals/score_cad_check.py --set fresh2.jsonl --variant v2
