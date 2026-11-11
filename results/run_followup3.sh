#!/bin/zsh
# Follow-up set 3 (FOLLOWUP3_RULE): A then B, both resume; report at the end.
cd "$(dirname "$0")/.."
.venv/bin/python evals/followup/run.py --set 3 --variant A || exit 1
.venv/bin/python evals/followup/run.py --set 3 --variant B || exit 1
.venv/bin/python evals/followup/run.py --set 3 --report
