"""Judge the feature-aware CAD check on parts it wasn't designed on, and apply its adoption rule.

    .venv/bin/python evals/score_cad_check.py                                   # v1 on cad-f*: not adopted
    .venv/bin/python evals/score_cad_check.py --set fresh2.jsonl --variant v2   # v2 on cad-g*

The size-only check (one valid solid, overall size from the task) shipped with the
CAD pack. The feature-aware check adds holes: the diameters, counts, through and
depth the task asks for (plm_cad.checks.hole_issues). It was designed on the eval
set's 108 saved programs; this scores both checks on evals/cad/fresh.jsonl, written
before the check, from the same saved measurements. Rule and sets fixed on
2026-10-23 before any fresh result existed; grading at the 0.1% tolerance set then.

v2 (variant "v2": a through hole is one no disk caps; sizes may sum three stated
sizes) came after v1's verdict and was designed on everything v1 had seen, so it is
judged the same way on a second fresh set, evals/cad/fresh2.jsonl, written before it.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import run_cad  # noqa: E402
from plm_cad import kernel  # noqa: E402
from plm_cad.checks import check  # noqa: E402

CHECK_RULE = ("the candidate check replaces the size-only one iff, over every model's programs for the fresh "
              "parts, it raises no alarm on a part graded correct, none on any fresh reference, and catches more "
              "wrong parts than the size-only check")


def main():
    fresh = ROOT / "evals/cad" / (sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "fresh.jsonl")
    variant = sys.argv[sys.argv.index("--variant") + 1] if "--variant" in sys.argv else "holes-v1"
    problems = {p["id"]: p for p in run_cad.load(fresh)}
    ref_alarms = [p["id"] for p in problems.values() if check(p["task"], *kernel.build(p["reference"]), variant=variant)]
    print(f"candidate check: {variant}, judged on {fresh.name}")
    print(f"fresh references it flags: {len(ref_alarms)} {ref_alarms}")
    totals = {"wrong": 0, "size": 0, "features": 0, "size_false": 0, "features_false": 0}
    print(f"\n{'model':<8} {'correct':>8} {'wrong':>6} {'caught: size-only':>18} {'candidate':>10} {'false alarms':>13}")
    for k, m in run_cad.MODELS.items():
        path = run_cad.results_path(m, fresh)
        if not path.exists() or len(run_cad.load(path)) < len(problems):
            sys.exit(f"no complete results on {fresh.name} for {k}; run its results/run_cad_*.sh")
        c = {"wrong": 0, "size": 0, "features": 0, "size_false": 0, "features_false": 0, "correct": 0}
        for r in run_cad.load(path):
            p = problems[r["id"]]
            right = run_cad.grade(p, r["measured"]) == "correct"
            error = r["error"] if r["measured"] is None else None
            size = bool(check(p["task"], r["measured"], error, variant="size"))
            feat = bool(check(p["task"], r["measured"], error, variant=variant))
            c["correct"] += right
            c["wrong"] += not right
            c["size"] += size and not right
            c["features"] += feat and not right
            c["size_false"] += size and right
            c["features_false"] += feat and right
        for key in totals:
            totals[key] += c[key]
        print(f"{k:<8} {c['correct']:>5}/{len(problems)} {c['wrong']:>6} {c['size']:>18} {c['features']:>10} "
              f"{c['size_false']:>6} / {c['features_false']}")
    adopt = not ref_alarms and totals["features_false"] == 0 and totals["features"] > totals["size"]
    print(f"\nall models: wrong {totals['wrong']}, caught size-only {totals['size']}, candidate "
          f"{totals['features']}; false alarms size-only {totals['size_false']}, candidate {totals['features_false']}")
    print(f"rule: {CHECK_RULE}\n-> {f'ADOPT the {variant} check' if adopt else 'keep the size-only check'}")


if __name__ == "__main__":
    main()
