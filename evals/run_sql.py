"""Run one model over the SQL eval set, grade every query on the hidden data, or simulate routing.

    .venv/bin/python evals/run_sql.py --model qwen3:8b     # writes results/sql__<model>.jsonl
    .venv/bin/python evals/run_sql.py --simulate           # policies over the saved runs, and SQL_RULE
    .venv/bin/python evals/run_sql.py --model qwen3:8b --tasks evals/sql/fresh.jsonl   # results/sql_fresh__...
    .venv/bin/python evals/run_sql.py --simulate --tasks evals/sql/fresh.jsonl         # and FRESH_RULE

A query is correct when, run on the task's hidden database (evals/sql/build_tasks.py), it
returns the reference query's result: the same number of columns, and the same rows as a
multiset (as a list when the question fixes an order), numbers equal to 1 part in 10^4.
Column names don't matter. Every row also keeps the pack's key-free check (plm_sql.controller
.check: the query runs on the schema alone), which is what a policy escalates on. Resumes:
tasks already in the results file are skipped.
"""

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals/sql"))

import build_tasks  # noqa: E402
from plm.ollama import ask  # noqa: E402
from plm_sql.controller import check  # noqa: E402
from plm_sql.sandbox import run_query  # noqa: E402
from plm_sql.sqlgen import PROMPT_VERSION, build_prompt, extract_sql, split_task  # noqa: E402

TASKS = ROOT / "evals/sql/tasks.jsonl"
RESULTS = ROOT / "results"
SMALL = "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M"
MODELS = {"4B": SMALL, "8B": "qwen3:8b", "coder": "qwen2.5-coder:14b"}
PARAMS = {"4B": 4, "8B": 8, "coder": 14}
REL_TOL = 1e-4

# Fixed before the SQL sweep (results/run_sql.sh), with the pack. Each policy is a per-level chain of
# models, escalating when the key-free check fails; levels from plm_sql.levels.
CASCADE = ["4B", "8B", "coder"]
POLICIES_SQL = [
    ("always 4B", {lv: ["4B"] for lv in ("calm", "alert", "intensive")}),
    ("always 8B", {lv: ["8B"] for lv in ("calm", "alert", "intensive")}),
    ("always coder", {lv: ["coder"] for lv in ("calm", "alert", "intensive")}),
    ("cascade 4B -> 8B -> coder (pre-sweep default)", {lv: CASCADE for lv in ("calm", "alert", "intensive")}),
    ("cascade 4B -> coder", {lv: ["4B", "coder"] for lv in ("calm", "alert", "intensive")}),
    ("cascade 8B -> coder", {lv: ["8B", "coder"] for lv in ("calm", "alert", "intensive")}),
    ("routed: cascade | intensive 8B -> coder", {"calm": CASCADE, "alert": CASCADE, "intensive": ["8B", "coder"]}),
]
SQL_RULE = ("ship the cheapest policy above whose score is within 1 task of the best one's "
            "(compute = model size x generated tokens, relative to always-coder)")
SHIPPED = "cascade 4B -> coder"
# Fixed after the sweep picked SHIPPED and before any model answered evals/sql/fresh.jsonl.
FRESH_RULE = (f"the shipped policy ({SHIPPED}) is confirmed iff, on the fresh tasks with the classifier's levels, "
              "it scores within 1 task of the best policy above and costs less than always-coder; otherwise "
              "SQL_RULE's pick on the fresh set is the candidate to replace it, to be judged on further new tasks")


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def literal(v):
    if v is None:
        return "NULL"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return repr(v)


def hidden_setup():
    """schema name -> SQL that builds its hidden database: the CREATE statements and every row."""
    out = {}
    for schema, tables in build_tasks.databases().items():
        inserts = [f"INSERT INTO {t} VALUES " + ", ".join("(" + ", ".join(map(literal, row)) + ")" for row in rows) + ";"
                   for t, rows in tables.items()]
        out[schema] = {**build_tasks.SCHEMAS, **build_tasks.FRESH_SCHEMAS}[schema] + "\n" + "\n".join(inserts)
    return out


def same_value(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        return math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-9)
    return a == b


def sort_key(row):
    return [(0, f"{v:.4g}") if isinstance(v, (int, float)) else (1, "") if v is None else (2, str(v)) for v in row]


def grade(task, got, want):
    if got is None:
        return "no_sql"
    if got["error"]:
        return "error"
    if len(got["columns"]) != len(want["columns"]):
        return "wrong_columns"
    if got["n_rows"] != want["n_rows"]:
        return "wrong_rows"
    a, b = got["rows"], want["rows"]
    if not task["ordered"]:
        a, b = sorted(a, key=sort_key), sorted(b, key=sort_key)
    ok = all(len(x) == len(y) and all(same_value(u, v) for u, v in zip(x, y)) for x, y in zip(a, b))
    return "correct" if ok else "wrong_rows"


def results_path(model, tasks_file=TASKS):
    stem = "" if Path(tasks_file).stem == "tasks" else "_" + Path(tasks_file).stem
    return RESULTS / f"sql{stem}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"


def run(model, num_predict, timeout, tasks_file=TASKS):
    tasks = load(tasks_file)
    setups = hidden_setup()
    out = results_path(model, tasks_file)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    todo = [t for t in tasks if t["id"] not in done]
    print(f"{model}: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, t in enumerate(todo, 1):
            row = {"id": t["id"], "level": t["level"], "model": model, "prompt_version": PROMPT_VERSION,
                   "num_predict": num_predict}
            try:
                r = ask(model, build_prompt(t["prompt"]), False, num_predict, timeout)
                query = extract_sql(r["response"])
                issues, _ = check(split_task(t["prompt"]), query)
                got = run_query(setups[t["schema"]], query, seconds=10) if query else None
                row.update({"response": r["response"], "eval_tokens": r["eval_tokens"],
                            "prompt_tokens": r["prompt_tokens"], "wall_s": r["wall_s"],
                            "done_reason": r["done_reason"], "query": query, "issues": issues,
                            "hidden": got and {k: got[k] for k in ("error", "columns", "n_rows")}})
                row["verdict"] = grade(t, got, run_query(setups[t["schema"]], t["reference"], seconds=10))
            except Exception as e:  # keep going; one bad request must not lose the run
                row.update({"response": "", "eval_tokens": 0, "prompt_tokens": 0, "wall_s": 0, "done_reason": "error",
                            "query": None, "issues": ["request failed"], "hidden": None,
                            "error": f"{type(e).__name__}: {e}", "verdict": "request_error"})
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {t['id']} {row['verdict']:<13} {row['eval_tokens']:>5} tok "
                  f"{row['wall_s']:>6.1f}s" + (f"  [{'; '.join(row['issues'])[:90]}]" if row["issues"] else ""),
                  flush=True)
    summarize(tasks, {r["id"]: r for r in load(out)})


def summarize(tasks, rows):
    by_level = defaultdict(Counter)
    for t in tasks:
        by_level[t["level"]][rows[t["id"]]["verdict"]] += 1
        by_level["ALL"][rows[t["id"]]["verdict"]] += 1
    print(f"\n{'level':<10} {'n':>3} {'correct':>8}  other verdicts")
    for lv in ("calm", "alert", "intensive", "ALL"):
        c = by_level[lv]
        print(f"{lv:<10} {sum(c.values()):>3} {c['correct']:>8}  "
              + ", ".join(f"{k} {v}" for k, v in sorted(c.items()) if k != "correct"))


def simulate(tasks_file=TASKS):
    from plm_sql.levels import classify
    tasks = load(tasks_file)
    paths = {k: results_path(m, tasks_file) for k, m in MODELS.items()}
    R = {k: {r["id"]: r for r in load(p)} for k, p in paths.items() if p.exists()}
    missing = [k for k in MODELS if k not in R or len(R[k]) < len(tasks)]
    if missing:
        sys.exit(f"no complete SQL results for {', '.join(missing)} on {Path(tasks_file).name} yet; run results/run_sql.sh")
    levels = {t["id"]: classify(t["prompt"])[0] for t in tasks}
    cost = {k: {tid: PARAMS[k] * r["eval_tokens"] for tid, r in R[k].items()} for k in R}
    base = sum(cost["coder"].values())
    print(f"{'policy (levels from plm_sql.levels)':<48} {'score':>6} {'compute':>8} {'escalated':>10}")
    measured = []
    for name, pol in POLICIES_SQL:
        score = spend = escalated = 0
        for t in tasks:
            chain = pol[levels[t["id"]]]
            for i, k in enumerate(chain):
                spend += cost[k][t["id"]]
                if not R[k][t["id"]]["issues"] or i == len(chain) - 1:
                    break
            score += R[k][t["id"]]["verdict"] == "correct"
            escalated += i > 0
        measured.append((name, score, spend / base))
        print(f"{name:<48} {score:>3}/{len(tasks)} {spend / base:>8.0%} {escalated:>10}")
    best = max(s for _, s, _ in measured)
    chosen = min((m for m in measured if m[1] >= best - 1), key=lambda m: m[2])
    print(f"\nrule: {SQL_RULE}\n-> {chosen[0]} ({chosen[1]}/{len(tasks)} at {chosen[2]:.0%})")
    if Path(tasks_file).stem == "fresh":
        shipped = next(m for m in measured if m[0] == SHIPPED)
        confirmed = shipped[1] >= best - 1 and shipped[2] < 1
        print(f"\nrule: {FRESH_RULE}\nshipped {shipped[1]}/{len(tasks)} at {shipped[2]:.0%}, best {best}/{len(tasks)}")
        print(f"-> CONFIRMED: keep {SHIPPED}" if confirmed else f"-> NOT CONFIRMED: candidate {chosen[0]}")
    print("\nkey-free check vs the key:")
    print(f"   {'model':<6} {'wrong':>6} {'caught':>7} {'false alarms':>13}")
    for k in R:
        wrong = [tid for tid, r in R[k].items() if r["verdict"] != "correct"]
        caught = sum(bool(R[k][tid]["issues"]) for tid in wrong)
        false = sum(bool(r["issues"]) and r["verdict"] == "correct" for r in R[k].values())
        print(f"   {k:<6} {len(wrong):>6} {caught:>7} {false:>13}")


def self_test():
    """The grader against known answers: each reference is correct, and broken copies of it are not."""
    tasks, setups, fails, total = load(TASKS) + load(TASKS.with_name("fresh.jsonl")), hidden_setup(), [], 0

    def expect(t, query, want):
        nonlocal total
        total += 1
        got = grade(t, run_query(setups[t["schema"]], query, seconds=10),
                    run_query(setups[t["schema"]], t["reference"], seconds=10))
        if got != want:
            fails.append(f"{t['id']}: {query[:70]!r} graded {got}, want {want}")

    for t in tasks:
        ref = t["reference"]
        expect(t, ref, "correct")
        expect(t, f"SELECT *, 1 FROM ({ref})", "wrong_columns")
        expect(t, f"SELECT * FROM ({ref}) LIMIT 0", "wrong_rows")
        expect(t, ref.replace("SELECT", "SELEC", 1), "error")
        if t["ordered"] and t["rows"] > 1:  # the same rows in another order
            expect(t, f"WITH r AS ({ref}) SELECT * FROM r ORDER BY 1 {'ASC' if 'DESC' in ref else 'DESC'}", "wrong_rows")
        elif not t["ordered"] and t["rows"] > 1:  # order doesn't matter when the question doesn't fix one
            expect(t, f"WITH r AS ({ref}) SELECT * FROM r ORDER BY 1 DESC", "correct")
    for f in fails:
        print("FAIL", f)
    print(f"self-test: {total - len(fails)}/{total} checks passed")
    sys.exit(1 if fails else 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--self-test", action="store_true", help="check the grader on the references, no model calls")
    ap.add_argument("--tasks", default=TASKS, help="task file (default: the eval set)")
    ap.add_argument("--num-predict", type=int, default=1024, help="max generated tokens per task")
    ap.add_argument("--timeout", type=int, default=300, help="seconds per request")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.simulate:
        return simulate(args.tasks)
    if not args.model:
        sys.exit("--model or --simulate")
    run(args.model, args.num_predict, args.timeout, args.tasks)


if __name__ == "__main__":
    main()
