"""Judge the CAD repair retry and apply its adoption rule.

    .venv/bin/python evals/score_cad_repair.py                         # the fresh set: decides
    .venv/bin/python evals/score_cad_repair.py --set problems.jsonl    # the eval set: preflight, seen

The coder answers each part; when the shipped check (plm_cad.checks, variant v2) flags
it, it gets one retry showing its program and what the check found
(plm_cad.controller.repair_prompt). The final answer is the repair if it passes the
check, else the first answer. Rule and set fixed on 2026-10-23, before any result on
evals/cad/fresh3.jsonl, which was written before the repair existed.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import run_cad  # noqa: E402

CODER = "qwen2.5-coder:14b"
REPAIR_RULE = ("the CAD pack gives the coder one repair of a flagged part iff, on the fresh set, its final "
               "answers get more parts right than its first answers, no part its first answer had right ends "
               "wrong, and it costs at most 1.5x the first answers' generated tokens")


def main():
    name = sys.argv[sys.argv.index("--set") + 1] if "--set" in sys.argv else "fresh3.jsonl"
    path = ROOT / "evals/cad" / name
    problems = run_cad.load(path)
    rows = {r["id"]: r for r in run_cad.load(run_cad.results_path(CODER, path, repair=True))} \
        if run_cad.results_path(CODER, path, repair=True).exists() else {}
    if len(rows) < len(problems) or any("error" in r for r in rows.values()):
        sys.exit(f"incomplete repair results on {name}; run results/run_cad_repair.sh")
    first_ok = final_ok = lost = repaired = tried = first_tok = total_tok = 0
    for p in problems:
        r = rows[p["id"]]
        first, rep = r["first"], r["repair"]
        final = rep if rep and not rep["issues"] else first
        first_ok += first["verdict"] == "correct"
        final_ok += final["verdict"] == "correct"
        lost += first["verdict"] == "correct" and final["verdict"] != "correct"
        tried += rep is not None
        repaired += rep is not None and final is rep
        first_tok += first["tokens"]
        total_tok += first["tokens"] + (rep["tokens"] if rep else 0)
        if rep:
            print(f"  {p['id']}: first {first['verdict']:<12} repair {rep['verdict']:<12} "
                  f"{'kept' if final is rep else 'dropped (still flagged)'}")
    ratio = total_tok / first_tok
    print(f"\n{name}: {len(problems)} parts; first answers right {first_ok}, final {final_ok}; "
          f"repairs tried {tried}, kept {repaired}; right answers lost {lost}; cost {ratio:.2f}x")
    if name == "fresh3.jsonl":
        adopt = final_ok > first_ok and lost == 0 and ratio <= 1.5
        print(f"rule: {REPAIR_RULE}\n-> {'ADOPT one repair' if adopt else 'no repair'}")


if __name__ == "__main__":
    main()
