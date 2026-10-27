"""A better physics check, judged on UGPhysics problems this project hasn't used.

    .venv/bin/python evals/physics_check.py --model qwen3:8b --strategy convert   # results/physcheck_ugphysics__<model>__<s>.jsonl
    .venv/bin/python evals/physics_check.py --simulate                           # current policy vs candidates, CHECK_RULE
    .venv/bin/python evals/physics_check.py --set confirm --model ... --strategy convert   # the unused problems
    .venv/bin/python evals/physics_check.py --set confirm --simulate             # CONVERT_RULE

Physics has the widest gap between what ships and the hindsight bound (SciBench 48% vs 69%), and its
misses mostly pass the checks: right unit, wrong size ("5e+04 MPa" for 50 MPa). Two candidates, both
fixed on 2026-10-25 before any model answered these problems:

    convert   the calculator prompt also says: work in SI units, then convert the final value to the
              unit the question asks for before printing. The routed policy, with these programs.
    disagree  the routed policy, but a 4B calculator answer is also checked against the 4B answering
              directly, and escalates when they disagree (plm.numeric.checks.agree), as well as on a
              failed check. Implemented exactly here, not approximated.

Data (not redistributed): UGPhysics/ugphysics on Hugging Face (English; Classical Mechanics,
Thermodynamics, Classical Electromagnetism, Wave Optics, Geometrical Optics), saved by the datasets-
server rows API into .benchmarks/ugphysics/ on 2026-10-25. Problems with a single numeric answer
("NV") and a unit; a fixed sample of SAMPLE. The prompt states the unit, the number is graded within
5% (as for SciBench).
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import plm.packs  # noqa: E402,F401
from bench_physics import clean_unit, correct  # noqa: E402
from plm.numeric import calc  # noqa: E402
from plm.numeric.answers import ANSWER_FORMAT  # noqa: E402
from plm.numeric.checks import agree, check  # noqa: E402
from plm.ollama import ask, unreachable  # noqa: E402
from plm_physics.levels import classify  # noqa: E402

DATA = ROOT / ".benchmarks/ugphysics"
SUBJECTS = ("ClassicalMechanics", "Thermodynamics", "ClassicalElectromagnetism", "WaveOptics", "GeometricalOptics")
RESULTS = ROOT / "results"
SEED, SAMPLE = 20261025, 150
MODELS = {"4B": "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M", "8B": "qwen3:8b"}
PARAMS = {"4B": 4, "8B": 8}
CONVERT_NOTE = ("Inside the program, work in SI base units, then convert the final value to the unit the "
                "question asks for (for example 5e4 Pa is 50 kPa) and print that converted number.")
FORMATS = {"bare": ANSWER_FORMAT, "tool": calc.TOOL_FORMAT, "convert": calc.TOOL_FORMAT + " " + CONVERT_NOTE}
CHECK_RULE = ("of the two candidates, the one with more problems right replaces the shipped physics policy iff a paired "
              "bootstrap 95% interval of its score minus the shipped one's lies entirely above 0 (accuracy first, "
              "compute reported); otherwise the shipped policy stays")
# Fixed on 2026-10-26 after CHECK_RULE kept the shipped policy (convert 53/150 vs 46, interval -2 to +17, at 83%
# compute) and before any model answered the confirmation set: every eligible problem the first sample didn't use.
CONVERT_RULE = ("convert replaces the shipped calculator prompt in the physics pack iff (a) on the confirmation set it "
                "scores at least as many as the shipped policy, (b) over both UGPhysics sets pooled its paired bootstrap 95% "
                "interval against the shipped policy lies entirely above 0, and (c) its compute is at most the shipped one's")
SET = "first"


def number(boxed):
    """'\\boxed{2.5 \\times 10^{3}}' -> 2500.0; None if the answer isn't one plain number."""
    m = re.fullmatch(r"\\boxed\{(.*)\}", boxed.strip(), re.S)
    s = (m[1] if m else boxed).replace(" ", "").replace("{", "").replace("}", "").replace("\\,", "")
    s = re.sub(r"\\times10\^(-?\d+)", r"e\1", s.replace("\\cdot", "\\times"))
    try:
        return float(s)
    except ValueError:
        return None


def problems():
    if not DATA.exists():
        sys.exit(f"{DATA} is missing: fetch it as this file's docstring says")
    pool = []
    for subject in SUBJECTS:
        for r in map(json.loads, open(DATA / f"{subject}.jsonl")):
            if r["answer_type"] != "NV" or r["is_multiple_answer"] or not r["unit"]:
                continue
            value, unit = number(r["answers"]), clean_unit(r["unit"].replace("\\text", "\\mathrm"))
            if value is None or not unit:
                continue
            pool.append({"id": f"ug-{subject}-{r['index']}", "question": f"{r['problem'].strip()} Give the answer in {unit}.",
                         "answer": value})
    first = sorted(random.Random(SEED).sample(pool, SAMPLE), key=lambda p: p["id"])
    if SET == "first":
        return first
    used = {p["id"] for p in first}
    return sorted((p for p in pool if p["id"] not in used), key=lambda p: p["id"])


def results_path(model, strategy):
    tag = "" if SET == "first" else f"_{SET}"
    return RESULTS / f"physcheck_ugphysics{tag}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}__{strategy}.jsonl"


def run(model, strategy, timeout):
    ps = problems()
    out = results_path(model, strategy)
    done = {r["id"] for r in map(json.loads, open(out))} if out.exists() else set()
    todo = [p for p in ps if p["id"] not in done]
    num_predict = 1536 if strategy == "bare" else 1024
    print(f"{model} {strategy} on UGPhysics: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, p in enumerate(todo, 1):
            row = {"id": p["id"], "model": model, "strategy": strategy, "num_predict": num_predict}
            try:
                r = ask(model, f"{p['question']}\n\n{FORMATS[strategy]}", False, num_predict, timeout)
                output = r["response"]
                if strategy != "bare":
                    code = calc.extract_program(output)
                    output, row["program_error"] = calc.run_program(code) if code else ("", "no code block")
                row.update({"model_response": r["response"], "response": output, "eval_tokens": r["eval_tokens"],
                            "wall_s": r["wall_s"], "done_reason": r["done_reason"]})
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this problem and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped at {p['id']}, resume to retry")
                row.update({"response": "", "error": f"{type(e).__name__}: {e}", "eval_tokens": 0, "wall_s": 0,
                            "done_reason": "error"})
            row["issues"] = check(p["question"], row["response"])
            row["correct"] = correct(row["response"], p["answer"])
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {p['id']} {'correct' if row['correct'] else 'wrong':<8} {row['eval_tokens']:>5} tok "
                  f"{row['wall_s']:>6.1f}s" + (f"  [{'; '.join(row['issues'])[:60]}]" if row["issues"] else ""), flush=True)


RUNS = [("4B", "bare"), ("4B", "tool"), ("4B", "convert"), ("8B", "bare"), ("8B", "tool"), ("8B", "convert")]


def simulate(resamples=2000):
    ps = problems()
    R = {}
    for key, strategy in RUNS:
        path = results_path(MODELS[key], strategy)
        R[(key, strategy)] = {r["id"]: r for r in map(json.loads, open(path))} if path.exists() else {}
        if len(R[(key, strategy)]) < len(ps):
            sys.exit(f"no complete results for {key} {strategy}; run results/run_physics_check.sh")
    levels = {p["id"]: classify(p["question"])[0] for p in ps}

    def policy(p, calc_strategy, verify):
        """The shipped shape: calm/alert 4B+calc -> 8B+calc, intensive 8B+calc -> 8B direct. (correct, spend)."""
        pid, q = p["id"], p["question"]
        if levels[pid] == "intensive":
            chain = [("8B", calc_strategy), ("8B", "bare")]
        else:
            chain = [("4B", calc_strategy), ("8B", calc_strategy)]
        spend = 0
        for i, step in enumerate(chain):
            row = R[step][pid]
            spend += PARAMS[step[0]] * row["eval_tokens"]
            last = i == len(chain) - 1
            if last or row["issues"]:
                if last:
                    return row["correct"], spend
                continue
            if verify and step[0] == "4B":
                spend += PARAMS["4B"] * R[("4B", "bare")][pid]["eval_tokens"]
                if not agree(q, row["response"], R[("4B", "bare")][pid]["response"]):
                    continue
            return row["correct"], spend
        raise AssertionError("unreachable")

    per = {"shipped (calc, escalate on failed check)": [policy(p, "tool", False) for p in ps],
           "candidate convert": [policy(p, "convert", False) for p in ps],
           "candidate disagree": [policy(p, "tool", True) for p in ps]}
    for (key, strategy) in RUNS:
        per[f"always {key} {strategy}"] = [(R[(key, strategy)][p["id"]]["correct"],
                                            PARAMS[key] * R[(key, strategy)][p["id"]]["eval_tokens"]) for p in ps]
    n = len(ps)
    rng = random.Random(SEED)
    idx = [[rng.randrange(n) for _ in range(n)] for _ in range(resamples)]
    shipped = per["shipped (calc, escalate on failed check)"]
    base = sum(s for _, s in shipped)
    print(f"UGPhysics sample: {n} problems\n\n{'policy':<44} {'score':>8} {'95% CI':>12} {'compute':>8} {'vs shipped, 95% CI':>20}")
    lows = {}
    for name, res in per.items():
        score = sum(c for c, _ in res)
        boots = sorted(sum(res[i][0] for i in b) for b in idx)
        diffs = sorted(sum(res[i][0] - shipped[i][0] for i in b) for b in idx)
        lo, hi = boots[int(0.025 * resamples)], boots[int(0.975 * resamples)]
        dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
        lows[name] = (score, dlo)
        print(f"{name:<44} {score:>3}/{n:<4} {lo / n:>5.0%}-{hi / n:<5.0%} {sum(s for _, s in res) / base:>8.0%} "
              f"{'' if res is shipped else f'{dlo:+d} to {dhi:+d}':>20}")
    best = max(("candidate convert", "candidate disagree"), key=lambda k: lows[k][0])
    print(f"\nrule: {CHECK_RULE}")
    print(f"-> ADOPT: {best}" if lows[best][1] > 0 else f"-> KEEP: the shipped policy (best candidate: {best})")


def confirm(resamples=2000):
    """CONVERT_RULE: the shipped policy and convert on the confirmation set, and over both sets pooled."""
    global SET

    def outcomes():
        ps = problems()
        R = {}
        for key, strategy in (("4B", "tool"), ("4B", "convert"), ("8B", "bare"), ("8B", "tool"), ("8B", "convert")):
            path = results_path(MODELS[key], strategy)
            R[(key, strategy)] = {r["id"]: r for r in map(json.loads, open(path))} if path.exists() else {}
            if len(R[(key, strategy)]) < len(ps):
                sys.exit(f"no complete {SET} results for {key} {strategy}; run results/run_physics_check.sh {SET}")
        out = {}
        for name, calc_strategy in (("shipped", "tool"), ("convert", "convert")):
            res = []
            for p in ps:
                intensive = classify(p["question"])[0] == "intensive"
                chain = [("8B", calc_strategy), ("8B", "bare")] if intensive else [("4B", calc_strategy), ("8B", calc_strategy)]
                first = R[chain[0]][p["id"]]
                spend = PARAMS[chain[0][0]] * first["eval_tokens"]
                row = first if not first["issues"] else R[chain[1]][p["id"]]
                if first["issues"]:
                    spend += PARAMS[chain[1][0]] * row["eval_tokens"]
                res.append((row["correct"], spend))
            out[name] = res
        return out

    SET = "confirm"
    new = outcomes()
    SET = "first"
    old = outcomes()
    SET = "confirm"
    pooled = {k: old[k] + new[k] for k in new}
    n, rng = len(pooled["shipped"]), random.Random(SEED)
    diffs = sorted(sum(pooled["convert"][i][0] - pooled["shipped"][i][0] for i in (rng.randrange(n) for _ in range(n)))
                   for _ in range(resamples))
    dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
    score = {k: sum(c for c, _ in v) for k, v in new.items()}
    cost = {k: sum(s for _, s in v) for k, v in new.items()}
    print(f"confirmation set: {len(new['shipped'])} problems; shipped {score['shipped']}, convert {score['convert']}; "
          f"convert compute {cost['convert'] / cost['shipped']:.0%} of shipped")
    print(f"pooled with the first set ({n} problems): shipped {sum(c for c, _ in pooled['shipped'])}, convert "
          f"{sum(c for c, _ in pooled['convert'])}; convert minus shipped, 95% CI {dlo:+d} to {dhi:+d}")
    ok = score["convert"] >= score["shipped"] and dlo > 0 and cost["convert"] <= cost["shipped"]
    print(f"\nrule: {CONVERT_RULE}\n(a) {score['convert'] >= score['shipped']}  (b) {dlo > 0}  "
          f"(c) {cost['convert'] <= cost['shipped']}")
    print("-> ADOPT: convert" if ok else "-> KEEP: the shipped calculator prompt")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--strategy", choices=list(FORMATS), default="bare")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--set", choices=["first", "confirm"], default="first")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    global SET
    SET = args.set
    if args.simulate:
        return confirm() if SET == "confirm" else simulate()
    if not args.model:
        sys.exit("--model or --simulate")
    run(args.model, args.strategy, args.timeout)


if __name__ == "__main__":
    main()
