#!/bin/zsh
# Follow-up set 4 (FOLLOWUP4_RULE, SI_RULE): C, D, E, F (shared cache), the si regression, then both reports. Resumes.
cd "$(dirname "$0")/.."
for v in C D E F; do .venv/bin/python evals/followup/run4.py --variant $v > /dev/null || exit 1; echo "variant $v done"; done
.venv/bin/python evals/si_regression.py || exit 1
echo "=== FINAL ==="
.venv/bin/python evals/followup/run4.py --report
.venv/bin/python evals/si_regression.py --report
echo "=== END ==="
