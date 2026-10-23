"""Score a pack's level classifier against hand labels.

    .venv/bin/python evals/eval_levels.py                    # electrical: main set + holdout
    .venv/bin/python evals/eval_levels.py --pack software    # software
    .venv/bin/python evals/eval_levels.py --pack aerospace   # aerospace
    .venv/bin/python evals/eval_levels.py --pack physics     # physics
    .venv/bin/python evals/eval_levels.py --pack cad         # CAD
    .venv/bin/python evals/eval_levels.py -v                 # also list every miss

The holdout labels were written before the rules and are never used to tune them.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import grade  # noqa: E402
from plm_aerospace import levels as aerospace_levels  # noqa: E402
from plm_cad import levels as cad_levels  # noqa: E402
from plm_electrical import levels as electrical_levels  # noqa: E402
from plm_physics import levels as physics_levels  # noqa: E402
from plm_software import levels as software_levels  # noqa: E402

LEVELS = ("calm", "alert", "intensive")
# pack -> (classifier, text field, main set, holdout)
PACKS = {
    "electrical": (electrical_levels.classify, "question", "evals/electrical/problems.jsonl",
                   "evals/electrical/holdout_levels.jsonl"),
    "software": (software_levels.classify, "prompt", "evals/software/tasks.jsonl",
                 "evals/software/holdout_levels.jsonl"),
    "aerospace": (aerospace_levels.classify, "question", "evals/aerospace/problems.jsonl",
                  "evals/aerospace/holdout_levels.jsonl"),
    "physics": (physics_levels.classify, "question", "evals/physics/problems.jsonl",
                "evals/physics/holdout_levels.jsonl"),
    "cad": (cad_levels.classify, "task", "evals/cad/problems.jsonl", "evals/cad/holdout_levels.jsonl"),
}


def evaluate(name, items, classify, field, verbose):
    confusion = {(a, b): 0 for a in LEVELS for b in LEVELS}
    misses = []
    for it in items:
        got, reason = classify(it[field])
        confusion[(it["level"], got)] += 1
        if got != it["level"]:
            misses.append((it["id"], it["level"], got, reason))
    right = sum(confusion[(lv, lv)] for lv in LEVELS)
    under = sum(confusion[(a, b)] for a in LEVELS for b in LEVELS if LEVELS.index(b) < LEVELS.index(a))
    print(f"\n{name}: {right}/{len(items)} exact, {under} under-routed (sent too low)")
    print(f"{'label \\ got':<12}" + "".join(f"{lv:>10}" for lv in LEVELS))
    for a in LEVELS:
        print(f"{a:<12}" + "".join(f"{confusion[(a, b)]:>10}" for b in LEVELS))
    if verbose:
        for m in misses:
            print("  miss", *m)


def main():
    verbose = "-v" in sys.argv
    pack = sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else "electrical"
    classify, field, main_set, holdout = PACKS[pack]
    print(f"pack: {pack}")
    evaluate("main set (rules may be tuned here)", grade.load_jsonl(ROOT / main_set), classify, field, verbose)
    evaluate("holdout (never tuned on)", grade.load_jsonl(ROOT / holdout), classify, field, verbose)


if __name__ == "__main__":
    main()
