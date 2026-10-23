#!/bin/zsh
# The coder with one repair of a flagged part, on the third fresh CAD set
# (rule committed before this ran: evals/score_cad_repair.py, REPAIR_RULE).
cd "$(dirname "$0")/.."
with-timeout 3600 .venv/bin/python evals/run_cad.py --model qwen2.5-coder:14b --repair --problems evals/cad/fresh3.jsonl
.venv/bin/python evals/score_cad_repair.py
