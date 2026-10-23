"""Judge the feature-aware CAD check on parts it wasn't designed on, and apply its adoption rule.

    .venv/bin/python evals/score_cad_check.py

The size-only check (one valid solid, overall size from the task) shipped with the
CAD pack. The feature-aware check adds holes: the diameters, counts, through and
depth the task asks for (plm_cad.checks.hole_issues). It was designed on the eval
set's 108 saved programs; this scores both checks on evals/cad/fresh.jsonl, written
before the check, from the same saved measurements. Rule and sets fixed on
2026-10-23 before any fresh result existed; grading at the 0.1% tolerance set then.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import run_cad  # noqa: E402
from plm_cad import kernel  # noqa: E402
from plm_cad.checks import check  # noqa: E402

FRESH = ROOT / "evals/cad/fresh.jsonl"
CHECK_RULE = ("the feature-aware check replaces the size-only one iff, over every model's programs for the fresh "
              "parts, it raises no alarm on a part graded correct, none on any fresh reference, and catches more "
              "wrong parts than the size-only check")


def main():
    problems = {p["id"]: p for p in run_cad.load(FRESH)}
    ref_alarms = [p["id"] for p in problems.values() if check(p["task"], *kernel.build(p["reference"]))]
    print(f"fresh references flagged by the feature-aware check: {len(ref_alarms)} {ref_alarms}")
    totals = {"wrong": 0, "size": 0, "features": 0, "size_false": 0, "features_false": 0}
    print(f"\n{'model':<8} {'correct':>8} {'wrong':>6} {'caught: size-only':>18} {'feature-aware':>14} {'false alarms':>13}")
    for k, m in run_cad.MODELS.items():
        path = run_cad.results_path(m, FRESH)
        if not path.exists() or len(run_cad.load(path)) < len(problems):
            sys.exit(f"no complete fresh results for {k}; run results/run_cad_fresh.sh")
        c = {"wrong": 0, "size": 0, "features": 0, "size_false": 0, "features_false": 0, "correct": 0}
        for r in run_cad.load(path):
            p = problems[r["id"]]
            right = run_cad.grade(p, r["measured"]) == "correct"
            error = r["error"] if r["measured"] is None else None
            size = bool(check(p["task"], r["measured"], error, holes=False))
            feat = bool(check(p["task"], r["measured"], error))
            c["correct"] += right
            c["wrong"] += not right
            c["size"] += size and not right
            c["features"] += feat and not right
            c["size_false"] += size and right
            c["features_false"] += feat and right
        for key in totals:
            totals[key] += c[key]
        print(f"{k:<8} {c['correct']:>5}/{len(problems)} {c['wrong']:>6} {c['size']:>18} {c['features']:>14} "
              f"{c['size_false']:>6} / {c['features_false']}")
    adopt = not ref_alarms and totals["features_false"] == 0 and totals["features"] > totals["size"]
    print(f"\nall models: wrong {totals['wrong']}, caught size-only {totals['size']}, feature-aware "
          f"{totals['features']}; false alarms size-only {totals['size_false']}, feature-aware {totals['features_false']}")
    print(f"rule: {CHECK_RULE}\n-> {'ADOPT the feature-aware check' if adopt else 'keep the size-only check'}")


if __name__ == "__main__":
    main()
