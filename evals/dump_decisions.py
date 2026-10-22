"""Print every routing, unit and check decision, for before/after comparisons.

    .venv/bin/python evals/dump_decisions.py > /tmp/before.txt
    ... change something that must not change behavior ...
    .venv/bin/python evals/dump_decisions.py | diff /tmp/before.txt -

One line per eval text (pack picked, unit requested, level from its own pack's
classifier) and one per saved numeric answer (issues raised by the checks).
No model calls. Used to prove refactors behavior-neutral, e.g. the migration
in docs/pack-packaging.md.
"""

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plm.aerospace.levels import classify as aerospace_classify  # noqa: E402
from plm.electrical.levels import classify as electrical_classify  # noqa: E402
from plm.numeric.checks import check, requested_unit  # noqa: E402
from plm.packs import detect  # noqa: E402
from plm.software.levels import classify as software_classify  # noqa: E402


def load(path):
    with open(ROOT / path) as f:
        return [json.loads(line) for line in f if line.strip()]


def main():
    sets = [  # (file, text field, classifier of the pack the text belongs to)
        ("evals/electrical/problems.jsonl", "question", electrical_classify),
        ("evals/electrical/holdout_levels.jsonl", "question", electrical_classify),
        ("evals/aerospace/problems.jsonl", "question", aerospace_classify),
        ("evals/aerospace/holdout_levels.jsonl", "question", aerospace_classify),
        ("evals/software/tasks.jsonl", "prompt", software_classify),
        ("evals/software/holdout_levels.jsonl", "prompt", software_classify),
        ("evals/router/detect_cases.jsonl", "text", None),
    ]
    for path, field, classify in sets:
        for r in load(path):
            text = r[field]
            level = classify(text) if classify else None
            print("TEXT", r["id"], detect(text), repr(requested_unit(text)), level)

    for pack in ("electrical", "aerospace"):
        questions = {p["id"]: p["question"] for p in load(f"evals/{pack}/problems.jsonl")}
        for f in sorted(glob.glob(str(ROOT / "results" / "**" / f"{pack}__*.jsonl"), recursive=True)):
            name = Path(f).relative_to(ROOT)
            for r in load(f):
                print("CHECK", name, r["id"], check(questions[r["id"]], r["response"]))


if __name__ == "__main__":
    main()
