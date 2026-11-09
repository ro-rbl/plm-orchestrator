#!/bin/zsh
# FUSE3_RULE run: 40 round-3 problems, cad_alone, fusion with the coder computing (variant code), oracle. Resumes.
cd "$(dirname "$0")/.."
with-timeout 36000 .venv/bin/python evals/fusion/run_spike.py --set round3 --variant code
