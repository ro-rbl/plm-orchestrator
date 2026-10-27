"""Run one model over the CAD eval set, build every part with the kernel, and grade it; or simulate routing.

    .venv/bin/python evals/run_cad.py --model qwen3:8b       # writes results/cad__<model>.jsonl
    .venv/bin/python evals/run_cad.py --model qwen3:8b --problems evals/cad/fresh.jsonl   # results/cad_fresh__...
    .venv/bin/python evals/run_cad.py --simulate             # policies over the saved runs, and CAD_RULE
    .venv/bin/python evals/run_cad.py --model qwen2.5-coder:14b --repair --problems ...   # first answer, then
                                                             # one repair of a flagged part (results ...__repair)

A part is correct when it is one valid solid whose bounding box (extents sorted, so
orientation is free) and volume are within the problem's tolerance of the key.
Every row also keeps the pack's key-free check (plm_cad.checks), which is what a
policy escalates on. Resumes: problems already in the results file are skipped.
"""

import argparse
import json
import math
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plm.ollama import ask, unreachable  # noqa: E402
from plm_cad import kernel  # noqa: E402
from plm_cad.checks import check  # noqa: E402
from plm_cad.controller import CAD_FORMAT, PROMPT_VERSION  # noqa: E402

PROBLEMS = ROOT / "evals/cad/problems.jsonl"
RESULTS = ROOT / "results"
SMALL = "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M"
MODELS = {"4B": SMALL, "8B": "qwen3:8b", "coder": "qwen2.5-coder:14b"}
PARAMS = {"4B": 4, "8B": 8, "coder": 14}

# Fixed before the CAD sweep (results/run_cad.sh), with the pack. Each policy is a per-level chain of
# models, escalating when the key-free check fails; levels from plm_cad.levels.
CASCADE = ["4B", "8B", "coder"]
POLICIES_CAD = [
    ("always 4B", {lv: ["4B"] for lv in ("calm", "alert", "intensive")}),
    ("always 8B", {lv: ["8B"] for lv in ("calm", "alert", "intensive")}),
    ("always coder", {lv: ["coder"] for lv in ("calm", "alert", "intensive")}),
    ("cascade 4B -> 8B -> coder (pre-sweep default)", {lv: CASCADE for lv in ("calm", "alert", "intensive")}),
    ("cascade 8B -> coder", {lv: ["8B", "coder"] for lv in ("calm", "alert", "intensive")}),
    ("routed: cascade | intensive 8B -> coder", {"calm": CASCADE, "alert": CASCADE, "intensive": ["8B", "coder"]}),
]
CAD_RULE = ("ship the cheapest policy above whose score is within 1 problem of the best one's "
            "(compute = model size x generated tokens, relative to always-coder)")


def load(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def grade(problem, measured):
    if measured is None:
        return "no_part"
    if not measured["valid"] or measured["solids"] != 1:
        return "invalid"
    tol = problem["rel_tol"]
    if not all(math.isclose(a, b, rel_tol=tol) for a, b in zip(measured["bbox"], problem["bbox"])):
        return "wrong_size"
    if not math.isclose(measured["volume"], problem["volume"], rel_tol=tol):
        return "wrong_volume"
    return "correct"


def results_path(model, problems_file=PROBLEMS, repair=False):
    stem = "" if Path(problems_file).stem == "problems" else "_" + Path(problems_file).stem
    return RESULTS / f"cad{stem}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}{'__repair' if repair else ''}.jsonl"


def run_repair(model, num_predict, timeout, problems_file):
    """First answer, then one repair if the check flags it; both kept, graded against the key."""
    from plm_cad import controller
    problems = load(problems_file)
    out = results_path(model, problems_file, repair=True)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    todo = [p for p in problems if p["id"] not in done]
    print(f"{model} with repair: {len(todo)} to run, {len(done)} already in {out}")

    def keep(step, p):
        return {k: step[k] for k in ("code", "measured", "issues", "tokens", "prompt_tokens", "seconds", "model_text")} | {
            "verdict": grade(p, step["measured"])}

    with out.open("a") as f:
        for i, p in enumerate(todo, 1):
            row = {"id": p["id"], "level": p["level"], "model": model, "prompt_version": controller.PROMPT_VERSION,
                   "repair_prompt_version": controller.REPAIR_PROMPT_VERSION, "num_predict": num_predict}
            try:
                first = controller.attempt(p["task"], model, num_predict, timeout)
                row["first"] = keep(first, p)
                row["repair"] = None
                if first["issues"]:
                    fixed = controller.attempt(p["task"], model, num_predict, timeout,
                                               controller.repair_prompt(p["task"], first))
                    row["repair"] = keep(fixed, p)
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this task and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped, resume to retry")
                row["error"] = f"{type(e).__name__}: {e}"
            f.write(json.dumps(row) + "\n")
            f.flush()
            rep = row.get("repair")
            print(f"[{i}/{len(todo)}] {p['id']} first {row.get('first', {}).get('verdict', 'error'):<12}"
                  + (f" repair {rep['verdict']:<12} {'passes check' if not rep['issues'] else 'still flagged'}"
                     if rep else ""), flush=True)


def run(model, num_predict, timeout, problems_file=PROBLEMS):
    problems = load(problems_file)
    out = results_path(model, problems_file)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    todo = [p for p in problems if p["id"] not in done]
    print(f"{model}: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, p in enumerate(todo, 1):
            row = {"id": p["id"], "level": p["level"], "model": model, "prompt_version": PROMPT_VERSION,
                   "num_predict": num_predict}
            try:
                r = ask(model, f"{p['task']}\n\n{CAD_FORMAT}", False, num_predict, timeout)
                code = kernel.extract_program(r["response"])
                t = time.time()
                measured, error = kernel.build(code) if code else (None, "no code block")
                row.update({"response": r["response"], "eval_tokens": r["eval_tokens"],
                            "prompt_tokens": r["prompt_tokens"], "wall_s": r["wall_s"],
                            "done_reason": r["done_reason"], "code": code, "measured": measured, "error": error,
                            "build_s": time.time() - t, "issues": check(p["task"], measured, error)})
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this task and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped, resume to retry")
                row.update({"response": "", "eval_tokens": 0, "prompt_tokens": 0, "wall_s": 0,
                            "done_reason": "error", "code": None, "measured": None,
                            "error": f"{type(e).__name__}: {e}", "issues": ["request failed"]})
            row["verdict"] = grade(p, row["measured"])
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {p['id']} {row['verdict']:<12} {row['eval_tokens']:>5} tok "
                  f"{row['wall_s']:>6.1f}s" + (f"  [{'; '.join(row['issues'])[:90]}]" if row["issues"] else ""),
                  flush=True)
    summarize(problems, {r["id"]: r for r in load(out)})


def summarize(problems, rows):
    by_level = defaultdict(Counter)
    for p in problems:
        by_level[p["level"]][rows[p["id"]]["verdict"]] += 1
        by_level["ALL"][rows[p["id"]]["verdict"]] += 1
    print(f"\n{'level':<10} {'n':>3} {'correct':>8}  other verdicts")
    for lv in ("calm", "alert", "intensive", "ALL"):
        c = by_level[lv]
        print(f"{lv:<10} {sum(c.values()):>3} {c['correct']:>8}  "
              + ", ".join(f"{k} {v}" for k, v in sorted(c.items()) if k != "correct"))


def simulate():
    from plm_cad.levels import classify
    problems = load(PROBLEMS)
    R = {k: {r["id"]: r for r in load(results_path(m))} for k, m in MODELS.items() if results_path(m).exists()}
    missing = [k for k in MODELS if k not in R or len(R[k]) < len(problems)]
    if missing:
        sys.exit(f"no complete CAD results for {', '.join(missing)} yet; run results/run_cad.sh")
    levels = {p["id"]: classify(p["task"])[0] for p in problems}
    # grade from the saved measurements with the current keys, so a tolerance change regrades old runs
    for k in R:
        for p in problems:
            R[k][p["id"]]["verdict"] = grade(p, R[k][p["id"]]["measured"])
    cost = {k: {pid: PARAMS[k] * r["eval_tokens"] for pid, r in R[k].items()} for k in R}
    base = sum(cost["coder"].values())
    print(f"{'policy (levels from plm_cad.levels)':<48} {'score':>6} {'compute':>8} {'escalated':>10}")
    measured = []
    for name, pol in POLICIES_CAD:
        score = spend = escalated = 0
        for p in problems:
            chain = pol[levels[p["id"]]]
            for i, k in enumerate(chain):
                spend += cost[k][p["id"]]
                if not R[k][p["id"]]["issues"] or i == len(chain) - 1:
                    break
            score += R[k][p["id"]]["verdict"] == "correct"
            escalated += i > 0
        measured.append((name, score, spend / base))
        print(f"{name:<48} {score:>3}/{len(problems)} {spend / base:>8.0%} {escalated:>10}")
    best = max(s for _, s, _ in measured)
    chosen = min((m for m in measured if m[1] >= best - 1), key=lambda m: m[2])
    print(f"\nrule: {CAD_RULE}\n-> {chosen[0]} ({chosen[1]}/{len(problems)} at {chosen[2]:.0%})")
    print("\nkey-free check vs the key:")
    print(f"   {'model':<6} {'wrong':>6} {'caught':>7} {'false alarms':>13}")
    for k in R:
        wrong = [pid for pid, r in R[k].items() if r["verdict"] != "correct"]
        caught = sum(bool(R[k][pid]["issues"]) for pid in wrong)
        false = sum(bool(r["issues"]) and r["verdict"] == "correct" for r in R[k].values())
        print(f"   {k:<6} {len(wrong):>6} {caught:>7} {false:>13}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--repair", action="store_true", help="also one repair of a flagged first answer")
    ap.add_argument("--problems", default=PROBLEMS, help="problem file (default: the eval set)")
    ap.add_argument("--num-predict", type=int, default=1024, help="max generated tokens per problem")
    ap.add_argument("--timeout", type=int, default=300, help="seconds per request")
    args = ap.parse_args()
    if args.simulate:
        return simulate()
    if not args.model:
        sys.exit("--model or --simulate")
    if args.repair:
        return run_repair(args.model, args.num_predict, args.timeout, args.problems)
    run(args.model, args.num_predict, args.timeout, args.problems)


if __name__ == "__main__":
    main()
