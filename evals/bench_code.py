"""Public code benchmarks (HumanEval+, MBPP+) for the software pack: run, grade, simulate the policies.

    .venv/bin/python evals/bench_code.py --bench humaneval --model qwen3:8b   # results/bench_humaneval__<model>.jsonl
    .venv/bin/python evals/bench_code.py --bench mbpp --model qwen3:8b
    .venv/bin/python evals/bench_code.py --simulate                         # both benchmarks, 95% CIs, CODE_RULE
    .venv/bin/python evals/bench_code.py --verify                           # every reference solution passes its grade

Data (not redistributed): evalplus/humanevalplus and evalplus/mbppplus from Hugging Face, saved by
the datasets-server rows API as .benchmarks/code/{humanevalplus,mbppplus}.jsonl (164 and 378 tasks).

A task is what a user would paste. HumanEval+: its prompt (signature and docstring). MBPP+: its
description plus its first example assert, the usual MBPP convention. The software pack writes the
code (plm_software.codegen prompt) and its key-free check runs as in production: the code loads,
defines the function, and passes the examples the task shows (HumanEval docstrings show none in a
form the pack parses, so there it checks loading only). The grade runs the EvalPlus "plus" tests in
a separate `python -I` process (they need numpy, which the pack's sandbox doesn't allow).

Policies, CODE_RULE and the grade were fixed on 2026-10-24 before any model answered either
benchmark. CODE_RULE puts accuracy first, as the user chose for the SQL pack.
"""

import argparse
import json
import random
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plm.ollama import ask, unreachable  # noqa: E402
from plm_software.codegen import PROMPT_VERSION, build_prompt, extract_code  # noqa: E402
from plm_software.controller import parse_task  # noqa: E402
from plm_software.sandbox import run_tests  # noqa: E402

DATA = ROOT / ".benchmarks/code"
RESULTS = ROOT / "results"
MODELS = {"4B": "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M", "8B": "qwen3:8b", "coder": "qwen2.5-coder:14b"}
PARAMS = {"4B": 4, "8B": 8, "coder": 14}
POLICIES = {  # escalate along the chain when the pack's key-free check fails; the last answer is kept
    "always 4B": ["4B"], "always 8B": ["8B"], "always coder": ["coder"],
    "cascade 4B -> 8B -> coder (shipped)": ["4B", "8B", "coder"],
    "cascade 4B -> coder": ["4B", "coder"], "cascade 8B -> coder": ["8B", "coder"],
}
SHIPPED = "cascade 4B -> 8B -> coder (shipped)"
CODE_RULE = ("over both benchmarks pooled, the policy with the most tasks right replaces the shipped cascade iff a "
             "paired bootstrap 95% interval of its score minus the shipped cascade's lies entirely above 0 (accuracy "
             "first, compute reported); ties for the most right go to the cheaper policy")
SEED = 20261024
# --verify on 2026-10-24: these references fail their own plus tests, so the tasks are dropped from scoring.
REFERENCE_FAILS = {"HumanEval-32", "Mbpp-590"}


def tasks(bench):
    path = DATA / ("humanevalplus.jsonl" if bench == "humaneval" else "mbppplus.jsonl")
    if not path.exists():
        sys.exit(f"{path} is missing: fetch it as this file's docstring says")
    out = []
    for r in map(json.loads, open(path)):
        if bench == "humaneval":
            out.append({"id": r["task_id"].replace("/", "-"), "text": r["prompt"], "entry": r["entry_point"],
                        "test": r["test"] + f"\ncheck({r['entry_point']})\n",
                        "reference": r["prompt"] + r["canonical_solution"]})
        else:
            entry = re.search(r"assert\s+(?:not\s+)?\(?\s*(?:set\()?\s*(?:math\.isclose\()?\s*(\w+)\(", r["test_list"][0])
            out.append({"id": f"Mbpp-{r['task_id']}", "text": f"{r['prompt']}\n{r['test_list'][0]}",
                        "entry": entry[1] if entry else None, "test": r["test"], "reference": r["code"]})
    return out


def grade(code, task, timeout=60):
    """'pass' if the code passes the task's plus tests, else why not."""
    if not code:
        return "no_code"
    with tempfile.TemporaryDirectory() as cwd:
        script = Path(cwd) / "t.py"
        script.write_text(code + "\n\n" + task["test"])
        try:
            p = subprocess.run([sys.executable, "-I", str(script)], cwd=cwd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return "timeout"
    return "pass" if p.returncode == 0 else ("fail" if "AssertionError" in p.stderr else "error")


def key_free_issues(code, task):
    """The software pack's own check (plm_software.controller.attempt): loads, defines the entry, passes examples."""
    if code is None:
        return ["no code block"]
    parsed = parse_task(task["text"])
    entry = parsed["entry"] or task["entry"]
    result = run_tests(code, ([f"callable({entry})"] if entry else []) + parsed["examples"])
    if result["error"]:
        return [result["error"]]
    return [f"failed: {t}" for t, _ in result["failures"]]


def results_path(bench, model):
    return RESULTS / f"bench_{bench}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"


def run(bench, model, num_predict, timeout):
    ts = tasks(bench)
    out = results_path(bench, model)
    done = {r["id"] for r in map(json.loads, open(out))} if out.exists() else set()
    todo = [t for t in ts if t["id"] not in done]
    print(f"{model} on {bench}: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, t in enumerate(todo, 1):
            row = {"id": t["id"], "model": model, "prompt_version": PROMPT_VERSION, "num_predict": num_predict}
            try:
                parsed = parse_task(t["text"])
                r = ask(model, build_prompt(parsed), False, num_predict, timeout)
                code = extract_code(r["response"], parsed["entry"] or t["entry"] or "")
                row.update({"response": r["response"], "eval_tokens": r["eval_tokens"], "wall_s": r["wall_s"],
                            "done_reason": r["done_reason"], "code": code, "issues": key_free_issues(code, t),
                            "verdict": grade(code, t)})
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this task and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped, resume to retry")
                row.update({"response": "", "eval_tokens": 0, "wall_s": 0, "done_reason": "error", "code": None,
                            "issues": ["request failed"], "error": f"{type(e).__name__}: {e}", "verdict": "request_error"})
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {t['id']} {row['verdict']:<8} {row['eval_tokens']:>5} tok {row['wall_s']:>6.1f}s"
                  + (f"  [{'; '.join(row['issues'])[:70]}]" if row["issues"] else ""), flush=True)


def simulate(resamples=2000):
    per, n_tasks = {name: [] for name in POLICIES}, {}
    for bench in ("humaneval", "mbpp"):
        ts = [t for t in tasks(bench) if t["id"] not in REFERENCE_FAILS]
        R = {}
        for k, m in MODELS.items():
            p = results_path(bench, m)
            R[k] = {r["id"]: r for r in map(json.loads, open(p))} if p.exists() else {}
            if len(R[k]) < len(ts):
                sys.exit(f"no complete {bench} results for {k} ({len(R[k])}/{len(ts)}); run results/run_bench_code.sh")
        n_tasks[bench] = len(ts)
        print(f"{bench}: {len(ts)} tasks")
        for name, chain in POLICIES.items():
            res = []
            for t in ts:
                spend = 0
                for i, k in enumerate(chain):
                    spend += PARAMS[k] * R[k][t["id"]]["eval_tokens"]
                    if not R[k][t["id"]]["issues"] or i == len(chain) - 1:
                        break
                res.append((R[k][t["id"]]["verdict"] == "pass", spend))
            per[name] += res
            base = sum(PARAMS["coder"] * R["coder"][t["id"]]["eval_tokens"] for t in ts)
            print(f"   {name:<38} {sum(c for c, _ in res):>4}/{len(ts):<4} {sum(c for c, _ in res) / len(ts):>5.0%}"
                  f"  compute {sum(s for _, s in res) / base:>5.0%}")
        for k in R:
            wrong = [t["id"] for t in ts if R[k][t["id"]]["verdict"] != "pass"]
            caught = sum(bool(R[k][tid]["issues"]) for tid in wrong)
            false = sum(bool(R[k][t["id"]]["issues"]) and R[k][t["id"]]["verdict"] == "pass" for t in ts)
            print(f"   check, {k:<6} wrong {len(wrong):>4}  caught {caught:>4}  false alarms {false:>3}")
    n = len(per[SHIPPED])
    rng = random.Random(SEED)
    idx = [[rng.randrange(n) for _ in range(n)] for _ in range(resamples)]
    base = sum(s for _, s in per["always coder"])
    print(f"\npooled ({n} tasks)\n{'policy':<38} {'score':>9} {'95% CI':>12} {'compute':>8} {'vs shipped, 95% CI':>20}")
    shipped = per[SHIPPED]
    rows = []
    for name, res in per.items():
        score = sum(c for c, _ in res)
        boots = sorted(sum(res[i][0] for i in b) for b in idx)
        diffs = sorted(sum(res[i][0] - shipped[i][0] for i in b) for b in idx)
        lo, hi = boots[int(0.025 * resamples)], boots[int(0.975 * resamples)]
        dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
        cost = sum(s for _, s in res) / base
        rows.append((score, -cost, name, dlo))
        print(f"{name:<38} {score:>4}/{n:<4} {lo / n:>5.0%}-{hi / n:<5.0%} {cost:>8.0%} "
              f"{'' if name == SHIPPED else f'{dlo:+d} to {dhi:+d}':>20}")
    score, _, best, dlo = max(rows)
    print(f"\nrule: {CODE_RULE}")
    print(f"-> ADOPT: {best}" if best != SHIPPED and dlo > 0 else f"-> KEEP: {SHIPPED} (most right: {best})")


def verify():
    for bench in ("humaneval", "mbpp"):
        ts = tasks(bench)
        bad = [(t["id"], v) for t in ts if (v := grade(t["reference"], t)) != "pass"]
        no_entry = [t["id"] for t in ts if not (parse_task(t["text"])["entry"] or t["entry"])]
        flagged = [t["id"] for t in ts if key_free_issues(t["reference"], t)]
        print(f"{bench}: {len(ts) - len(bad)}/{len(ts)} references pass their grade {bad[:5]}; "
              f"no entry found {len(no_entry)} {no_entry[:5]}; pack check flags {len(flagged)} references {flagged[:5]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bench", choices=["humaneval", "mbpp"])
    ap.add_argument("--model")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--num-predict", type=int, default=1536)
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    if args.verify:
        return verify()
    if args.simulate:
        return simulate()
    if not (args.bench and args.model):
        sys.exit("--bench and --model, or --simulate, or --verify")
    run(args.bench, args.model, args.num_predict, args.timeout)


if __name__ == "__main__":
    main()
