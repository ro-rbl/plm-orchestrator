#!/bin/zsh
# FUSE_RULE run: 40 judged CAD + engineering problems, cad_alone, fusion (metres) and oracle. Resumes.
# Before: AC power, and nothing pinning qwen3:8b ("Forever" in `ollama ps`): the coder can't load beside it.
# Usage: results/run_fusion_judged.sh >> results/fusion_judged_m.log 2>&1 &
cd "$(dirname "$0")/.."
with-timeout 36000 .venv/bin/python evals/fusion/run_spike.py --set judged --variant m
