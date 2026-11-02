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
FLAGS_RULE adopted CANDIDATE on 2026-10-29 (2230/2880 vs 2212, +7 to +30).

Confirmation on a second benchmark: "bird", the 1036 questions of BIRD dev (the 2025-11-06 revision,
birdsql/bird_sql_dev_20251106 on Hugging Face; questions only, its 11 databases are mini-dev's) that
mini-dev doesn't use (mini-dev's question_ids are dev's). The question gets its hint ("evidence"), as in
bench_sql.py. CONFIRM_RULE was fixed on 2026-10-31 before any model answered it:
    .venv/bin/python evals/bench_sql_check.py --set bird --model qwen2.5-coder:14b
    .venv/bin/python evals/bench_sql_check.py --simulate --sets bird

Dropping the "huge" flag (more than 100 rows): "train", 3000 questions sampled (TRAIN_SEED) from Spider's
train_spider.json (7000; its 140 databases are in no dev or test set; train_others.json's 6 older databases
are left out). On the seen sets (rest + test + bird, 3915 questions) the second opinion without "huge" scored
2770 vs 2764 (7 tasks won, 1 lost) and asked the 4B 551 times instead of 678. The gain sought is fewer
false alarms and 4B calls at the same accuracy, not a higher score (8 disagreements in 3915 can't show one),
so NOHUGE_RULE is a non-inferiority rule, unlike FLAGS_RULE. Both policies are scored on the same answers:
the candidate's flags are the saved ones minus "huge". The 4B runs only where the coder's query raised a
shipped flag (--only-flagged), the only tasks where either policy asks it. Caveat: Spider's train split is
the likeliest of its splits to be in the models' training data. NOHUGE_RULE was fixed on 2026-11-01
before any model answered the set:
    results/run_sql_nohuge.sh                                   # coder on all 3000, then the 4B where flagged
    .venv/bin/python evals/bench_sql_check.py --simulate-nohuge
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
SETS = ("rest", "test")  # FLAGS_RULE's sets, pooled; "bird" is CONFIRM_RULE's
BIRD = bench_sql.DATA / "bird"
MODELS = {"4B": run_sql.SMALL, "coder": run_sql.MODELS["coder"]}
SHIPPED = "always coder"
CANDIDATE = "coder, 4B second opinion on a flag"
FLAGS_RULE = (f"{CANDIDATE} (the coder answers; when its query is flagged, the 4B answers too, and the 4B's query is "
              f"used iff it raises no flag) replaces {SHIPPED} iff, over both sets pooled, a paired bootstrap 95% "
              "interval of its score minus the shipped policy's lies entirely above 0 (accuracy first, compute reported); "
              "otherwise the pack keeps the coder alone")
CONFIRM_RULE = (f"the adopted policy ({CANDIDATE}) is confirmed on the BIRD dev questions mini-dev doesn't use unless "
                f"{SHIPPED} beats it there with a paired bootstrap 95% interval of the score difference entirely above 0; "
                "if it does, the SQL pack reverts to the coder alone")
SEED = 20261027
TRAIN_SEED, TRAIN_SAMPLE = 20261101, 3000
NOHUGE = f"{CANDIDATE}, without the huge flag"
NOHUGE_RULE = (f"{NOHUGE} (the same policy, with \"huge\" left out of both models' flags) replaces the shipped flags iff, "
               f"on the {TRAIN_SAMPLE} sampled Spider train questions, the lower end of a paired bootstrap 95% interval of "
               f"its score minus the shipped policy's ({CANDIDATE}) is at least -{TRAIN_SAMPLE // 1000} (no more than 0.1% "
               "of the tasks worse) and it asks the 4B fewer times; otherwise the pack keeps all five flags")


def tasks(name):
    if name == "bird":
        dev_file, base = BIRD / "dev_20251106/dev_20251106.json", BIRD / "minidev/MINIDEV"
        if not (dev_file.exists() and base.exists()):
            sys.exit(f"{dev_file} or {base} is missing: data/dev_20251106-00000-of-00001.json from "
                     "huggingface.co/datasets/birdsql/bird_sql_dev_20251106, saved as that name, and mini-dev (bench_sql.py)")
        mini = {d["question_id"] for d in json.load(open(base / "mini_dev_sqlite.json"))}
        items = [(f"bird-dev-{d['question_id']:04d}",
                  {"db_id": d["db_id"], "query": d["SQL"],
                   "question": d["question"] + (f" Hint: {d['evidence']}" if d.get("evidence") else "")})
                 for d in json.load(open(dev_file)) if d["question_id"] not in mini]
        folder, root = "dev_databases", base
    elif not BASE.exists():
        sys.exit(f"{BASE} is missing: download and unzip Spider into .benchmarks/ (see evals/bench_sql.py)")
    if name == "train":
        if not BASE.exists():
            sys.exit(f"{BASE} is missing: download and unzip Spider into .benchmarks/ (see evals/bench_sql.py)")
        train = json.load(open(BASE / "train_spider.json"))
        pick = sorted(random.Random(TRAIN_SEED).sample(range(len(train)), TRAIN_SAMPLE))
        items = [(f"spider-train-{i:04d}", train[i]) for i in pick]
        folder, root = "database", BASE
    elif name == "rest":
        dev = json.load(open(BASE / "dev.json"))
        used = set(random.Random(bench_sql.SAMPLE_SEED).sample(range(len(dev)), bench_sql.SPIDER_SAMPLE))
        items = [(f"spider-{i:04d}", dev[i]) for i in range(len(dev)) if i not in used]
        folder, root = "database", BASE
    elif name == "test":
        items = [(f"spider-test-{i:04d}", d) for i, d in enumerate(json.load(open(BASE / "test.json")))]
        folder, root = "test_database", BASE
    schemas, tables, out = {}, {}, []
    for tid, d in items:
        db = root / folder / d["db_id"] / f"{d['db_id']}.sqlite"
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
    if name == "bird":
        return run_sql.RESULTS / f"bench_bird_rest__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"
    return run_sql.RESULTS / f"bench_spider_{name}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"


def run(name, model, num_predict, timeout, only_flagged=False):
    ts = tasks(name)
    if only_flagged:  # only where the coder's saved query raised a flag: the only tasks a second opinion asks about
        coder = results_path(name, MODELS["coder"])
        flagged = {r["id"]: bool(r["flags"]) for r in run_sql.load(coder)} if coder.exists() else {}
        if len(flagged) < len(ts):
            sys.exit(f"--only-flagged needs the coder's complete results on {name} ({len(flagged)}/{len(ts)})")
        ts = [t for t in ts if flagged[t["id"]]]
    out = results_path(name, model)
    done = {r["id"] for r in run_sql.load(out)} if out.exists() else set()
    todo = [t for t in ts if t["id"] not in done]
    print(f"{model} on {name}: {len(todo)} to run, {len(done)} already in {out}")
    timeouts = 0
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
                if isinstance(e, TimeoutError):  # not saved, so a resume retries it; a run of them means a sleeping Mac
                    timeouts += 1
                    print(f"[{i}/{len(todo)}] {t['id']} timed out, not saved ({timeouts} in a row)", flush=True)
                    if timeouts >= 3:
                        sys.exit("3 requests in a row timed out (did the Mac sleep?); stopped, resume to retry")
                    continue
                row.update({"response": "", "eval_tokens": 0, "prompt_tokens": 0, "wall_s": 0, "done_reason": "error",
                            "query": None, "issues": ["request failed"], "flags": ["error"], "error": f"{type(e).__name__}: {e}",
                            "verdict": "request_error"})
            timeouts = 0
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


def simulate(sets=SETS, resamples=2000):
    R, ids = {k: {} for k in MODELS}, []
    for name in sets:
        ts = tasks(name)
        got = {}
        for k, m in MODELS.items():
            p = results_path(name, m)
            got[k] = {r["id"]: r for r in run_sql.load(p)} if p.exists() else {}
            if len(got[k]) < len(ts):
                sys.exit(f"no complete {name} results for {k} ({len(got[k])}/{len(ts)}); run results/run_sql_check.sh")
            R[k].update(got[k])
        bad = {t["id"] for t in ts if any(got[k][t["id"]]["verdict"] in ("gold_error", "request_error") for k in got)}
        print(f"{name}: {len(ts) - len(bad)} tasks ({len(bad)} dropped: gold query errors or a request failed)")
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
            reverts = dhi < 0  # the coder alone beats the candidate: interval of candidate - coder entirely below 0
        print(f"{name:<46} {score:>5}/{len(ids):<4} {sum(c for _, c in res) / base:>8.0%} "
              f"{'' if name == SHIPPED else f'{dlo:+d} to {dhi:+d}':>20}")
    if tuple(sets) == SETS:
        print(f"\nrule: {FLAGS_RULE}")
        print(f"-> ADOPT: {CANDIDATE}" if verdict else f"-> KEEP: {SHIPPED}")
    elif tuple(sets) == ("bird",):
        print(f"\nrule: {CONFIRM_RULE}")
        print(f"-> REVERT to {SHIPPED}" if reverts else f"-> CONFIRMED: {CANDIDATE}")
    print("\nflags vs the key (per model, pooled):")
    for k in MODELS:
        wrong = [i for i in ids if R[k][i]["verdict"] != "correct"]
        caught = sum(bool(R[k][i]["flags"]) for i in wrong)
        false = sum(bool(R[k][i]["flags"]) for i in ids if R[k][i]["verdict"] == "correct")
        by = {f: sum(f in R[k][i]["flags"] for i in wrong) for f in ("error", "empty", "huge", "nulls", "tables")}
        fa = {f: sum(f in R[k][i]["flags"] for i in ids if R[k][i]["verdict"] == "correct")
              for f in ("error", "empty", "huge", "nulls", "tables")}
        print(f"   {k:<6} wrong {len(wrong):>5}  caught {caught:>5}  false alarms {false:>4}   caught by {by}   false by {fa}")


def simulate_nohuge(resamples=2000):
    ts = tasks("train")
    R = {k: {r["id"]: r for r in run_sql.load(results_path("train", m))} if results_path("train", m).exists() else {}
         for k, m in MODELS.items()}
    if len(R["coder"]) < len(ts):
        sys.exit(f"no complete train results for the coder ({len(R['coder'])}/{len(ts)}); run results/run_sql_nohuge.sh")
    need = [t["id"] for t in ts if R["coder"][t["id"]]["flags"]]
    if missing := [i for i in need if i not in R["4B"]]:
        sys.exit(f"the 4B hasn't answered {len(missing)} flagged train tasks; run results/run_sql_nohuge.sh")
    bad = {i for i in R["coder"] if R["coder"][i]["verdict"] in ("gold_error", "request_error")
           or (i in R["4B"] and R["4B"][i]["verdict"] == "request_error")}
    ids = [t["id"] for t in ts if t["id"] not in bad]
    print(f"train: {len(ids)} tasks ({len(bad)} dropped: gold query errors or a request failed)")

    def ok(k, i):
        return R[k][i]["verdict"] == "correct"

    def policy(drop):
        def flags(r):
            return [f for f in r["flags"] if f not in drop]
        out, asked = [], 0
        for i in ids:
            c = run_sql.PARAMS["coder"] * R["coder"][i]["eval_tokens"]
            if not flags(R["coder"][i]):
                out.append((ok("coder", i), c))
                continue
            asked += 1
            b = R["4B"][i]
            out.append((ok("4B", i) if not flags(b) else ok("coder", i), c + run_sql.PARAMS["4B"] * b["eval_tokens"]))
        return out, asked

    coder = [(ok("coder", i), run_sql.PARAMS["coder"] * R["coder"][i]["eval_tokens"]) for i in ids]
    shipped, asked_s = policy(())
    cand, asked_c = policy(("huge",))
    base = sum(c for _, c in coder)
    rng = random.Random(SEED)
    idx = [[rng.randrange(len(ids)) for _ in ids] for _ in range(resamples)]
    print(f"\n{'policy':<60} {'score':>10} {'compute':>8} {'4B asked':>9} {'vs shipped, 95% CI':>20}")
    lo = None
    for name, res, asked in ((SHIPPED + " (reported)", coder, 0), (CANDIDATE + " (shipped)", shipped, asked_s),
                             (NOHUGE, cand, asked_c)):
        diffs = sorted(sum(res[i][0] - shipped[i][0] for i in b) for b in idx)
        dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
        if res is cand:
            lo = dlo
        print(f"{name:<60} {sum(c for c, _ in res):>5}/{len(ids):<4} {sum(c for _, c in res) / base:>8.0%} {asked:>9} "
              f"{'' if res is shipped else f'{dlo:+d} to {dhi:+d}':>20}")
    won = sum(c and not s for (c, _), (s, _) in zip(cand, shipped))
    lost = sum(s and not c for (c, _), (s, _) in zip(cand, shipped))
    print(f"\nwithout huge vs shipped: {won} won, {lost} lost")
    print(f"rule: {NOHUGE_RULE}")
    adopt = lo >= -(TRAIN_SAMPLE // 1000) and asked_c < asked_s
    print(f"-> ADOPT: {NOHUGE}" if adopt else f"-> KEEP: {CANDIDATE} with all five flags")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=(*SETS, "bird", "train"))
    ap.add_argument("--sets", nargs="+", choices=(*SETS, "bird"), default=list(SETS), help="--simulate: sets to pool")
    ap.add_argument("--model")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--simulate-nohuge", action="store_true", help="NOHUGE_RULE on the train set")
    ap.add_argument("--only-flagged", action="store_true", help="answer only tasks the coder's saved query flagged")
    ap.add_argument("--num-predict", type=int, default=1024)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    if args.simulate:
        return simulate(args.sets)
    if args.simulate_nohuge:
        return simulate_nohuge()
    if not (args.set and args.model):
        sys.exit("--set and --model, or --simulate")
    run(args.set, args.model, args.num_predict, args.timeout, args.only_flagged)


if __name__ == "__main__":
    main()
