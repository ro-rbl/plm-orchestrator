#!/bin/zsh
# Follow-up set 2 (FOLLOWUP2_RULE): A then B, both resume; report at the end.
cd "$(dirname "$0")/.."
.venv/bin/python evals/followup/run.py --set 2 --variant A || exit 1
.venv/bin/python evals/followup/run.py --set 2 --variant B || exit 1
.venv/bin/python evals/followup/run.py --set 2 --report
