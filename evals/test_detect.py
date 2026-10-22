"""Score plm.packs.detect: which pack a task is sent to.

    .venv/bin/python evals/test_detect.py [-v]

Three sets: the electrical and software eval texts (known while the rule was
written), and evals/router/detect_cases.jsonl, whose labels were written before
the electrical rule and are never used to tune it.
"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plm.packs import detect  # noqa: E402


def load(path, field, pack=None):
    with open(ROOT / path) as f:
        rows = [json.loads(line) for line in f if line.strip()]
    return [(r["id"], r[field], pack or r["pack"]) for r in rows]


def score(name, items, verbose):
    wrong = [(i, want, detect(text), text) for i, text, want in items if detect(text) != want]
    pairs = Counter((want, detect(text)) for _, text, want in items)
    print(f"{name}: {len(items) - len(wrong)}/{len(items)} routed to the labeled pack")
    for (want, got), n in sorted(pairs.items()):
        if want != got:
            print(f"   {n} x {want} -> {got}")
    if verbose:
        for i, want, got, text in wrong:
            print(f"   miss {i}: want {want}, got {got}: {text[:90]}")
    return len(wrong)


def main():
    verbose = "-v" in sys.argv
    known = (load("evals/electrical/problems.jsonl", "question", "electrical")
             + load("evals/electrical/holdout_levels.jsonl", "question", "electrical")
             + load("evals/software/tasks.jsonl", "prompt", "software")
             + load("evals/software/holdout_levels.jsonl", "prompt", "software")
             + load("evals/aerospace/problems.jsonl", "question", "aerospace")
             + load("evals/physics/problems.jsonl", "question", "physics"))
    misses = score("eval-set texts (known while writing the rule)", known, verbose)
    holdout = (load("evals/router/detect_cases.jsonl", "text")
               + load("evals/aerospace/holdout_levels.jsonl", "question", "aerospace")
               + load("evals/physics/holdout_levels.jsonl", "question", "physics"))
    score("holdout cases (labels written before the rule they test)", holdout, verbose)
    sys.exit(1 if misses else 0)  # the eval texts must all route correctly; the holdout is reported


if __name__ == "__main__":
    main()
