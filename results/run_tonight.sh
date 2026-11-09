#!/bin/zsh
# Tonight's chain (2026-11-08): fusion round 3, then results/run_overnight_rest.sh, under one supervisor each.
cd "$(dirname "$0")/.."
results/fusion_supervisor.sh results/run_fusion_round3.sh 05:30 >> results/fusion_round3_code.log 2>&1 || exit $?
UNLOAD_AT_END=1 results/fusion_supervisor.sh results/run_overnight_rest.sh 05:30 >> results/overnight_rest.log 2>&1
