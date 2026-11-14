#!/bin/zsh
# Follow-up set 7 (FOLLOWUP7_RULE): S (the repo today), A (S + ROOT_ANCHOR), B (qwen3:8b alone). Resumes.
cd "$(dirname "$0")/.."
for v in S A B; do .venv/bin/python evals/followup/run7.py --variant $v > /dev/null || exit 1; echo "variant $v done $(date +%H:%M)"; done
echo "=== FINAL ==="
.venv/bin/python evals/followup/run7.py --report
echo "=== END ==="
