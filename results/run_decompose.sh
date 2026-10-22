#!/bin/zsh
# Decompose-then-solve sweep (ROADMAP 3b): the 8B on aerospace intensive problems.
# Rule, cost bound and sets were committed before this ran (evals/score_decompose.py, DECOMPOSE_RULE).
# The eval set's 8B + calculator results already exist (results/run_aerospace.sh), so they aren't rerun.
cd "$(dirname "$0")/.."
with-timeout 3600 .venv/bin/python evals/run.py evals/aerospace/fresh_intensive.jsonl --model qwen3:8b --strategy tool
with-timeout 5400 .venv/bin/python evals/run.py evals/aerospace/fresh_intensive.jsonl --model qwen3:8b --strategy decompose
with-timeout 5400 .venv/bin/python evals/run.py evals/aerospace/problems.jsonl --model qwen3:8b --strategy decompose --level intensive
.venv/bin/python evals/score_decompose.py
