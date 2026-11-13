#!/bin/zsh
# Night of 2026-11-13. Each step resumes; the supervisor stops everything at the deadline.
# 1 FOLLOWUP5_RULE (S, R)  2 single models alone on set 5  3 si on the public physics benchmarks  4 the 8B thinking.
cd "$(dirname "$0")/.."
py=.venv/bin/python
for v in S R; do $py evals/followup/run5.py --variant $v > /dev/null || exit 1; echo "set 5 variant $v done $(date +%H:%M)"; done
echo "=== FOLLOWUP5 ==="; $py evals/followup/run5.py --report
for m in qwen3:8b qwen2.5-coder:14b; do $py evals/followup/baselines5.py --model $m > /dev/null || exit 1; echo "baseline $m done $(date +%H:%M)"; done
echo "=== BASELINES ==="; $py evals/followup/baselines5.py --report
$py evals/bench_si.py > /dev/null || exit 1
echo "=== BENCH SI ==="; $py evals/bench_si.py --report
$py evals/followup/baselines5.py --model qwen3:8b --think > /dev/null || exit 1
echo "=== BASELINES WITH THINKING ==="; $py evals/followup/baselines5.py --report
echo "=== END ==="
