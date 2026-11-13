#!/bin/zsh
# Follow-up set 6 (FOLLOWUP6_RULE): S (shipped), L (large model, whole conversation), B (qwen3:8b alone). Resumes.
cd "$(dirname "$0")/.."
for v in S L B; do .venv/bin/python evals/followup/run6.py --variant $v > /dev/null || exit 1; echo "variant $v done $(date +%H:%M)"; done
echo "=== FINAL ==="
.venv/bin/python evals/followup/run6.py --report
echo "=== END ==="
