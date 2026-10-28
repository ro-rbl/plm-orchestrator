"""Result flags for the SQL pack (plm_sql.flags), judged on Spider questions no model has answered here.

    .venv/bin/python evals/bench_sql_check.py --set rest --model qwen2.5-coder:14b   # results/bench_spider_rest__<model>.jsonl
    .venv/bin/python evals/bench_sql_check.py --simulate                              # both sets pooled, FLAGS_RULE

Sets: "rest", the 734 Spider dev questions evals/bench_sql.py's sample (SAMPLE_SEED) left out, and "test",
all 2147 Spider test questions (test.json, test_database/; in spider_data.zip, see bench_sql.py). Tasks,
prompt and grade are bench_sql.py's: the database's CREATE TABLE statements, then the question; rows
compared with the gold query's on the real database.

The shipped SQL policy is the coder alone; a query that doesn't run is reported, not escalated. The flags
read the query's result on the real database (the pack would need the user's database, opened read-only,
to use them). On the saved Spider and BIRD answers (seen, used to choose all this) the one policy ahead of
the coder was CANDIDATE: 231 vs 228 and 262 vs 254, at 105-108% compute. Other cheap-first cascades were
10-30 tasks behind and are reported here, not judged.

CANDIDATE, FLAGS_RULE and plm_sql.flags were fixed on 2026-10-27 before any model answered either set.
"""

import argparse
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import bench_sql  # noqa: E402
import run_sql  # noqa: E402
from plm.ollama import ask, unreachable  # noqa: E402
from plm_sql.controller import check  # noqa: E402
from plm_sql.flags import result_flags  # noqa: E402
from plm_sql.sandbox import run_query  # noqa: E402
from plm_sql.sqlgen import PROMPT_VERSION, build_prompt, extract_sql, split_task  # noqa: E402

BASE = bench_sql.DATA / "spider/spider_data"
SETS = ("rest", "test")
MODELS = {"4B": run_sql.SMALL, "coder": run_sql.MODELS["coder"]}
SHIPPED = "always coder"
CANDIDATE = "coder, 4B second opinion on a flag"
FLAGS_RULE = (f"{CANDIDATE} (the coder answers; when its query is flagged, the 4B answers too, and the 4B's query is "
              f"used iff it raises no flag) replaces {SHIPPED} iff, over both sets pooled, a paired bootstrap 95% "
              "interval of its score minus the shipped policy's lies entirely above 0 (accuracy first, compute reported); "
              "otherwise the pack keeps the coder alone")
SEED = 20261027


def tasks(name):
    if not BASE.exists():
        sys.exit(f"{BASE} is missing: download and unzip Spider into .benchmarks/ (see evals/bench_sql.py)")
    if name == "rest":
        dev = json.load(open(BASE / "dev.json"))
        used = set(random.Random(bench_sql.SAMPLE_SEED).sample(range(len(dev)), bench_sql.SPIDER_SAMPLE))
        items = [(f"spider-{i:04d}", dev[i]) for i in range(len(dev)) if i not in used]
        folder = "database"
    else:
        items = [(f"spider-test-{i:04d}", d) for i, d in enumerate(json.load(open(BASE / "test.json")))]
        folder = "test_database"
    schemas, tables, out = {}, {}, []
    for tid, d in items:
        db = BASE / folder / d["db_id"] / f"{d['db_id']}.sqlite"
        if db not in schemas:
            schemas[db] = bench_sql.schema_sql(db)
            con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            tables[db] = [r[0] for r in con.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
            con.close()
        out.append({"id": tid, "db": str(db), "tables": tables[db], "question": d["question"],
                    "prompt": f"{schemas[db]}\n\nWrite a SQL query: {d['question']}", "reference": d["query"],
                    "ordered": bool(re.search(r"\border\s+by\b", d["query"], re.IGNORECASE))})
    return out


def results_path(name, model):
    return run_sql.RESULTS / f"bench_spider_{name}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"


def run(name, model, num_predict, timeout):
    ts = tasks(name)
    out = results_path(name, model)
    done = {r["id"] for r in run_sql.load(out)} if out.exists() else set()
    todo = [t for t in ts if t["id"] not in done]
    print(f"{model} on spider {name}: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, t in enumerate(todo, 1):
            row = {"id": t["id"], "model": model, "prompt_version": PROMPT_VERSION, "num_predict": num_predict}
            try:
                r = ask(model, build_prompt(t["prompt"]), False, num_predict, timeout)
                query = extract_sql(r["response"])
                issues, _ = check(split_task(t["prompt"]), query)
                got = run_query("", query, seconds=30, db_path=t["db"]) if query else None
                want = run_query("", t["reference"], seconds=30, db_path=t["db"])
                row.update({"response": r["response"], "eval_tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
                            "wall_s": r["wall_s"], "done_reason": r["done_reason"], "query": query, "issues": issues,
                            "flags": result_flags(t["question"], query, got, t["tables"]),
                            "n_rows": got and got["n_rows"], "gold_error": want["error"],
                            "verdict": run_sql.grade(t, got, want) if not want["error"] else "gold_error"})
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this task and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped, resume to retry")
                row.update({"response": "", "eval_tokens": 0, "prompt_tokens": 0, "wall_s": 0, "done_reason": "error",
                            "query": None, "issues": ["request failed"], "flags": ["error"], "error": f"{type(e).__name__}: {e}",
                            "verdict": "request_error"})
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {t['id']} {row['verdict']:<13} {row['eval_tokens']:>5} tok {row['wall_s']:>6.1f}s"
                  + (f"  [{', '.join(row['flags'])}]" if row["flags"] else ""), flush=True)


def outcomes(R, ids):
    """policy -> per task (correct, compute); compute = model size x generated tokens."""
    def ok(k, i):
        return R[k][i]["verdict"] == "correct"

    def cost(k, i):
        return run_sql.PARAMS[k] * R[k][i]["eval_tokens"]

    def second_opinion(i):
        if not R["coder"][i]["flags"]:
            return ok("coder", i), cost("coder", i)
        return (ok("4B", i) if not R["4B"][i]["flags"] else ok("coder", i)), cost("coder", i) + cost("4B", i)

    def cascade(i, escalate):
        if escalate(R["4B"][i]):
            return ok("coder", i), cost("4B", i) + cost("coder", i)
        return ok("4B", i), cost("4B", i)

    return {
        SHIPPED: [(ok("coder", i), cost("coder", i)) for i in ids],
        CANDIDATE: [second_opinion(i) for i in ids],
        "always 4B (reported)": [(ok("4B", i), cost("4B", i)) for i in ids],
        "4B -> coder when it doesn't run (reported)": [cascade(i, lambda r: bool(r["issues"]) or "error" in r["flags"])
                                                       for i in ids],
        "4B -> coder on any flag (reported)": [cascade(i, lambda r: bool(r["issues"] or r["flags"])) for i in ids],
        "hindsight (reported)": [(ok("coder", i) or ok("4B", i), 0) for i in ids],
    }


def simulate(resamples=2000):
    R, ids = {k: {} for k in MODELS}, []
    for name in SETS:
        ts = tasks(name)
        got = {}
        for k, m in MODELS.items():
            p = results_path(name, m)
            got[k] = {r["id"]: r for r in run_sql.load(p)} if p.exists() else {}
            if len(got[k]) < len(ts):
                sys.exit(f"no complete spider {name} results for {k} ({len(got[k])}/{len(ts)}); run results/run_sql_check.sh")
            R[k].update(got[k])
        bad = {t["id"] for t in ts if any(got[k][t["id"]]["verdict"] in ("gold_error", "request_error") for k in got)}
        print(f"spider {name}: {len(ts) - len(bad)} tasks ({len(bad)} dropped: gold query errors or a request failed)")
        ids += [t["id"] for t in ts if t["id"] not in bad]
    per = outcomes(R, ids)
    base = sum(c for _, c in per[SHIPPED])
    rng = random.Random(SEED)
    idx = [[rng.randrange(len(ids)) for _ in ids] for _ in range(resamples)]
    shipped = per[SHIPPED]
    print(f"\n{'policy':<46} {'score':>10} {'compute':>8} {'vs shipped, 95% CI':>20}")
    verdict = None
    for name, res in per.items():
        score = sum(c for c, _ in res)
        diffs = sorted(sum(res[i][0] - shipped[i][0] for i in b) for b in idx)
        dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
        if name == CANDIDATE:
            verdict = dlo > 0
        print(f"{name:<46} {score:>5}/{len(ids):<4} {sum(c for _, c in res) / base:>8.0%} "
              f"{'' if name == SHIPPED else f'{dlo:+d} to {dhi:+d}':>20}")
    print(f"\nrule: {FLAGS_RULE}")
    print(f"-> ADOPT: {CANDIDATE}" if verdict else f"-> KEEP: {SHIPPED}")
    print("\nflags vs the key (per model, pooled):")
    for k in MODELS:
        wrong = [i for i in ids if R[k][i]["verdict"] != "correct"]
        caught = sum(bool(R[k][i]["flags"]) for i in wrong)
        false = sum(bool(R[k][i]["flags"]) for i in ids if R[k][i]["verdict"] == "correct")
        by = {f: sum(f in R[k][i]["flags"] for i in wrong) for f in ("error", "empty", "huge", "nulls", "tables")}
        fa = {f: sum(f in R[k][i]["flags"] for i in ids if R[k][i]["verdict"] == "correct")
              for f in ("error", "empty", "huge", "nulls", "tables")}
        print(f"   {k:<6} wrong {len(wrong):>5}  caught {caught:>5}  false alarms {false:>4}   caught by {by}   false by {fa}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=SETS)
    ap.add_argument("--model")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--num-predict", type=int, default=1024)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    if args.simulate:
        return simulate()
    if not (args.set and args.model):
        sys.exit("--set and --model, or --simulate")
    run(args.set, args.model, args.num_predict, args.timeout)


if __name__ == "__main__":
    main()
