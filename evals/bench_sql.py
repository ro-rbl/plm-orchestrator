"""Public SQL benchmarks (Spider dev, BIRD mini-dev) for the SQL pack: run, grade, simulate the policies.

    .venv/bin/python evals/bench_sql.py --bench spider --model qwen3:8b   # results/bench_spider__<model>.jsonl
    .venv/bin/python evals/bench_sql.py --bench spider --simulate         # POLICIES_SQL, 95% CIs, BENCH_RULE

The data isn't redistributed: download it into .benchmarks/ (ignored by git), as in NEXT.md:
    Spider: spider_data.zip from the official Drive link on yale-lily.github.io/spider
            (sha256 00636695dabed6b5f4b8328a16b13e069a2f16591d5efcce57660669c85b121b)
    BIRD:   minidev.zip from bird-bench.oss-cn-beijing.aliyuncs.com
            (sha256 cc48ba16838204e4e214512030cb572eeb5f7bcdd999bae4b9b6ff12ec13b92f)

Each task is what a user would paste: the database's own CREATE TABLE statements (from
sqlite_master), then the question (BIRD adds its hint, "evidence", as the benchmark intends). The
pack's key-free check runs the query on that schema alone, as in production; the grade runs it on
the real database and compares rows with the gold query's, as evals/run_sql.py does: same number
of columns in the same order, rows as a multiset (a list when the gold query has ORDER BY),
numbers to 1 part in 10^4. That is stricter than Spider's official evaluation, which also forgives
column order, so absolute scores read lower than published ones; the policies are compared on
the same grade.

Spider: a fixed sample of 300 of the 1034 dev questions (SAMPLE_SEED); BIRD: all 500 mini-dev.
Sample, policies (evals/run_sql.py POLICIES_SQL) and BENCH_RULE fixed on 2026-10-23 before any
model answered either benchmark.
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

import run_sql  # noqa: E402
from plm.ollama import ask  # noqa: E402
from plm_sql.controller import check  # noqa: E402
from plm_sql.sandbox import run_query  # noqa: E402
from plm_sql.sqlgen import PROMPT_VERSION, build_prompt, extract_sql, split_task  # noqa: E402

DATA = ROOT / ".benchmarks"
SAMPLE_SEED, SPIDER_SAMPLE = 20261023, 300
SHIPPED = "always 8B"
BENCH_RULE = (f"the benchmark supports the shipped SQL policy ({SHIPPED}) unless another policy in POLICIES_SQL beats it "
              "with a paired bootstrap 95% interval of the score difference entirely above 0, at no more than its "
              "compute + 10 points; the cheapest such policy is then the candidate, to be judged on the other benchmark")


def schema_sql(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rows = con.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL "
                       "AND name NOT LIKE 'sqlite_%' ORDER BY rowid").fetchall()
    return ";\n".join(r[0].strip() for r in rows) + ";"


def tasks(bench):
    if bench == "spider":
        base = DATA / "spider/spider_data"
        dev = json.load(open(base / "dev.json"))
        picked = sorted(random.Random(SAMPLE_SEED).sample(range(len(dev)), SPIDER_SAMPLE))
        items = [(f"spider-{i:04d}", dev[i]["db_id"], dev[i]["question"], dev[i]["query"]) for i in picked]
        db_path = lambda db: base / "database" / db / f"{db}.sqlite"  # noqa: E731
    else:
        base = DATA / "bird/minidev/MINIDEV"
        dev = json.load(open(base / "mini_dev_sqlite.json"))
        items = [(f"bird-{d['question_id']:04d}", d["db_id"],
                  d["question"] + (f" Hint: {d['evidence']}" if d.get("evidence") else ""), d["SQL"]) for d in dev]
        db_path = lambda db: base / "dev_databases" / db / f"{db}.sqlite"  # noqa: E731
    if not base.exists():
        sys.exit(f"{base} is missing: download and unzip the benchmark into .benchmarks/ (see this file's docstring)")
    schemas = {}
    out = []
    for tid, db, question, gold in items:
        if db not in schemas:
            schemas[db] = schema_sql(db_path(db))
        out.append({"id": tid, "db": str(db_path(db)), "prompt": f"{schemas[db]}\n\nWrite a SQL query: {question}",
                    "reference": gold, "ordered": bool(re.search(r"\border\s+by\b", gold, re.IGNORECASE))})
    return out


def results_path(bench, model):
    return run_sql.RESULTS / f"bench_{bench}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"


def run(bench, model, num_predict, timeout):
    ts = tasks(bench)
    out = results_path(bench, model)
    done = {r["id"] for r in run_sql.load(out)} if out.exists() else set()
    todo = [t for t in ts if t["id"] not in done]
    print(f"{model} on {bench}: {len(todo)} to run, {len(done)} already in {out}")
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
                            "gold_error": want["error"], "verdict": run_sql.grade(t, got, want) if not want["error"] else "gold_error"})
            except Exception as e:  # keep going; one bad request must not lose the run
                row.update({"response": "", "eval_tokens": 0, "prompt_tokens": 0, "wall_s": 0, "done_reason": "error",
                            "query": None, "issues": ["request failed"], "error": f"{type(e).__name__}: {e}",
                            "verdict": "request_error"})
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {t['id']} {row['verdict']:<13} {row['eval_tokens']:>5} tok {row['wall_s']:>6.1f}s"
                  + (f"  [{'; '.join(row['issues'])[:80]}]" if row["issues"] else ""), flush=True)


def simulate(bench, resamples=2000):
    ts = tasks(bench)
    R = {}
    for k, m in run_sql.MODELS.items():
        p = results_path(bench, m)
        R[k] = {r["id"]: r for r in run_sql.load(p)} if p.exists() else {}
        if len(R[k]) < len(ts):
            sys.exit(f"no complete {bench} results for {k} ({len(R[k])}/{len(ts)}); run results/run_bench_sql.sh")
    gold_bad = {t["id"] for t in ts if any(R[k][t["id"]]["verdict"] == "gold_error" for k in R)}
    ts = [t for t in ts if t["id"] not in gold_bad]
    from plm_sql.levels import classify
    levels = {t["id"]: classify(t["prompt"])[0] for t in ts}

    def outcome(pol):
        """per task: (correct, spend) for one policy."""
        res = []
        for t in ts:
            chain, spend = pol[levels[t["id"]]], 0
            for i, k in enumerate(chain):
                spend += run_sql.PARAMS[k] * R[k][t["id"]]["eval_tokens"]
                if not R[k][t["id"]]["issues"] or i == len(chain) - 1:
                    break
            res.append((R[k][t["id"]]["verdict"] == "correct", spend))
        return res

    per = {name: outcome(pol) for name, pol in run_sql.POLICIES_SQL}
    base = sum(s for _, s in per["always coder"])
    rng = random.Random(SAMPLE_SEED)
    idx = [[rng.randrange(len(ts)) for _ in ts] for _ in range(resamples)]
    shipped = per[SHIPPED]
    print(f"{bench}: {len(ts)} tasks ({len(gold_bad)} dropped: the gold query errors here)\n")
    print(f"{'policy':<48} {'score':>8} {'95% CI':>13} {'compute':>8} {'vs shipped, 95% CI':>22}")
    candidates = []
    for name, res in per.items():
        score = sum(c for c, _ in res)
        cost = sum(s for _, s in res) / base
        boots = sorted(sum(res[i][0] for i in b) for b in idx)
        diffs = sorted(sum(res[i][0] - shipped[i][0] for i in b) for b in idx)
        lo, hi = boots[int(0.025 * resamples)], boots[int(0.975 * resamples)]
        dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
        ship_cost = sum(s for _, s in shipped) / base
        if name != SHIPPED and dlo > 0 and cost <= ship_cost + 0.10:
            candidates.append((cost, name))
        print(f"{name:<48} {score:>4}/{len(ts):<3} {lo / len(ts):>5.0%}-{hi / len(ts):<5.0%} {cost:>8.0%} "
              f"{'' if name == SHIPPED else f'{dlo:+d} to {dhi:+d}':>22}")
    print(f"\nrule: {BENCH_RULE}")
    print(f"-> CANDIDATE: {min(candidates)[1]}" if candidates else f"-> SUPPORTS: {SHIPPED}")
    print("\nkey-free check vs the key:")
    for k in R:
        wrong = [t["id"] for t in ts if R[k][t["id"]]["verdict"] != "correct"]
        caught = sum(bool(R[k][tid]["issues"]) for tid in wrong)
        false = sum(bool(R[k][t["id"]]["issues"]) and R[k][t["id"]]["verdict"] == "correct" for t in ts)
        print(f"   {k:<6} wrong {len(wrong):>4}  caught {caught:>4}  false alarms {false:>3}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", choices=["spider", "bird"], required=True)
    ap.add_argument("--model")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--num-predict", type=int, default=1024)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    if args.simulate:
        return simulate(args.bench)
    if not args.model:
        sys.exit("--model or --simulate")
    run(args.bench, args.model, args.num_predict, args.timeout)


if __name__ == "__main__":
    main()
