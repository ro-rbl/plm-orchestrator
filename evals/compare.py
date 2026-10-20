"""Re-grade result files with the current grader and print one comparison table.

    .venv/bin/python evals/compare.py evals/electrical/problems.jsonl results/electrical__*.jsonl
"""

import sys
from pathlib import Path

import grade


def row_for(problems, path):
    by_id = {p["id"]: p for p in problems}
    rows = [r for r in grade.load_jsonl(path) if r["id"] in by_id]
    acc = {}
    for lvl in ("calm", "alert", "intensive"):
        rs = [r for r in rows if r["level"] == lvl]
        acc[lvl] = sum(grade.grade_one(by_id[r["id"]], r["response"])["verdict"] == "correct" for r in rs), len(rs)
    correct = sum(c for c, _ in acc.values())
    first = rows[0] if rows else {}
    return {
        "model": first.get("model", Path(path).stem).split("/")[-1],
        "strategy": first.get("strategy", "bare"),
        "n": len(rows),
        "correct": correct,
        "acc": acc,
        "tok": sum(r["eval_tokens"] for r in rows) / max(len(rows), 1),
        "sec": sum(r["wall_s"] + r.get("program_s", 0) for r in rows) / max(len(rows), 1),
        "capped": sum(r.get("done_reason") == "length" for r in rows),
        "prog_err": sum(bool(r.get("program_error")) for r in rows),
    }


def main():
    problems = grade.load_jsonl(sys.argv[1])
    table = sorted((row_for(problems, p) for p in sys.argv[2:]), key=lambda r: (r["model"], r["strategy"]))
    print(f"{'model':<44} {'strat':<7} {'score':>7} {'calm':>6} {'alert':>6} {'inten':>6} {'tok':>5} {'sec':>5} {'cap':>4} {'prog err':>8}")
    for r in table:
        lv = " ".join(f"{c / n:>6.0%}" if n else "     -" for c, n in r["acc"].values())
        print(f"{r['model']:<44} {r['strategy']:<7} {r['correct']:>3}/{r['n']:<3} {lv} {r['tok']:>5.0f} {r['sec']:>5.1f} "
              f"{r['capped']:>4} {r['prog_err'] if r['strategy'] != 'bare' else '-':>8}")


if __name__ == "__main__":
    main()
