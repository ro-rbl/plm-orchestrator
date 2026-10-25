"""Public physics benchmark (SciBench, its two physics textbooks) for the physics pack: run, grade, simulate.

    .venv/bin/python evals/bench_physics.py --model qwen3:8b --strategy bare   # results/bench_scibench__<model>[__tool].jsonl
    .venv/bin/python evals/bench_physics.py --simulate                         # POLICIES_PHYSICS, 95% CIs, PHYS_RULE
    .venv/bin/python evals/bench_physics.py --bench theoremqa --model qwen3:8b # TheoremQA physics, then --simulate:
                                                                               # TQA_RULE, the confirmation

Data (not redistributed): xw27/scibench from Hugging Face, saved by the datasets-server rows API as
.benchmarks/numeric/scibench.jsonl (692 problems; 2026-10-24). Only its physics sources are used:
"fund" (Halliday, Fundamentals of Physics, 81) and "class" (classical mechanics, 63), 144 problems.

As in SciBench's own evaluation, the prompt states the answer's unit and the grade compares the
number only, within 5% relative error; the problem text keeps its LaTeX. The physics pack's
key-free check (plm.numeric.checks.check) runs on every answer, as a policy escalates on it.
Strategies: bare (the model answers directly) and tool (it writes a calculator program), as in
the physics sweep (results/run_physics.sh). Policies are the physics pack's (simulate_routing.py
POLICIES_PHYSICS); PHYS_RULE, accuracy first as the user chose for SQL and code, was fixed on
2026-10-24 before any model answered.
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

import plm.packs  # noqa: E402,F401  (loads every pack, and with it its unit words)
from plm.numeric import calc  # noqa: E402
from plm.numeric.answers import ANSWER_FORMAT, parse_answer  # noqa: E402
from plm.numeric.checks import check  # noqa: E402
from plm.ollama import ask  # noqa: E402
from plm_physics.levels import classify  # noqa: E402
from simulate_routing import POLICIES_PHYSICS  # noqa: E402

DATA = ROOT / ".benchmarks/numeric/scibench.jsonl"
# TheoremQA (wenhuchen/TheoremQA theoremqa_test.json on GitHub, 800 problems; 2026-10-24): its physics
# problems with a numeric answer (float or integer) and no picture. The question states its own unit.
TQA_DATA = ROOT / ".benchmarks/theoremqa/test.json"
BENCH = "scibench"
RESULTS = ROOT / "results"
SOURCES = ("fund", "class")
REL_TOL = 0.05
MODELS = {"4B": "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M", "8B": "qwen3:8b"}
PARAMS = {"4B": 4, "8B": 8}
SHIPPED = "always 8B (bare)"
PHYS_RULE = ("the policy with the most problems right replaces the physics pack's shipped one (always 8B, bare) iff a "
             "paired bootstrap 95% interval of its score minus the shipped one's lies entirely above 0 (accuracy first, "
             "compute reported); ties for the most right go to the cheaper policy")
SEED = 20261024
# Fixed after SciBench switched the physics pack and before any model answered TheoremQA.
TQA_RULE = ("the switch is confirmed unless always 8B (bare), the physics pack's old policy, beats the shipped policy "
            "on TheoremQA physics with a paired bootstrap 95% interval entirely above 0; if it does, the pack reverts")
SHIPPED_NOW = "+ escalate on failed check (pre-sweep default)"


def clean_unit(u):
    """'$\\mathrm{~m} / \\mathrm{s}^2$' -> 'm/s^2'."""
    u = re.sub(r"\\mathrm\{([^}]*)\}", r"\1", u or "").replace("$", "").replace("~", "").replace("\\cdot", "*")
    u = re.sub(r"\^\{([^}]*)\}", r"^\1", u).replace("\\mu", "µ").replace("^\\circ", "°").replace("{", "").replace("}", "")
    return re.sub(r"\s+", "", u)


def problems():
    if BENCH == "theoremqa":
        if not TQA_DATA.exists():
            sys.exit(f"{TQA_DATA} is missing: fetch it as this file's docstring says")
        return [{"id": f"tqa-{x['id']}", "question": x["Question"].strip(), "answer": float(x["Answer"])}
                for x in json.load(open(TQA_DATA)) if x["field"] == "Physics"
                and x["Answer_type"] in ("float", "integer") and x["Picture"] in (None, "None")]
    if not DATA.exists():
        sys.exit(f"{DATA} is missing: fetch it as this file's docstring says")
    out = []
    for r in map(json.loads, open(DATA)):
        if r["source"] in SOURCES:
            unit = clean_unit(r["unit"])
            ask_unit = f" Give the answer in {unit}." if unit else " The answer is a pure number (unitless)."
            out.append({"id": f"sb-{r['source']}-{r['problemid'].strip()}", "question": r["problem_text"].strip() + ask_unit,
                        "answer": float(r["answer_number"])})
    return out


def correct(output, answer):
    parsed = parse_answer(output)
    if parsed is None:
        return False
    value = parsed[0]
    return abs(value - answer) <= REL_TOL * abs(answer) if answer else abs(value) < 1e-9


def results_path(model, strategy):
    return RESULTS / f"bench_{BENCH}__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}{'' if strategy == 'bare' else '__' + strategy}.jsonl"


def run(model, strategy, timeout):
    ps = problems()
    out = results_path(model, strategy)
    done = {r["id"] for r in map(json.loads, open(out))} if out.exists() else set()
    todo = [p for p in ps if p["id"] not in done]
    num_predict = 1536 if strategy == "bare" else 1024
    print(f"{model} {strategy} on {BENCH} physics: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, p in enumerate(todo, 1):
            row = {"id": p["id"], "model": model, "strategy": strategy, "num_predict": num_predict}
            try:
                fmt = ANSWER_FORMAT if strategy == "bare" else calc.TOOL_FORMAT
                r = ask(model, f"{p['question']}\n\n{fmt}", False, num_predict, timeout)
                output = r["response"]
                if strategy == "tool":
                    code = calc.extract_program(output)
                    output, row["program_error"] = calc.run_program(code) if code else ("", "no code block")
                row.update({"model_response": r["response"], "response": output, "eval_tokens": r["eval_tokens"],
                            "wall_s": r["wall_s"], "done_reason": r["done_reason"]})
            except Exception as e:  # keep going; one bad request must not lose the run
                row.update({"response": "", "error": f"{type(e).__name__}: {e}", "eval_tokens": 0, "wall_s": 0,
                            "done_reason": "error"})
            row["issues"] = check(p["question"], row["response"])
            row["correct"] = correct(row["response"], p["answer"])
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {p['id']} {'correct' if row['correct'] else 'wrong':<8} {row['eval_tokens']:>5} tok "
                  f"{row['wall_s']:>6.1f}s" + (f"  [{'; '.join(row['issues'])[:70]}]" if row["issues"] else ""), flush=True)


def simulate(resamples=2000):
    ps = problems()
    R = {}
    for key, strategy in (("4B", "bare"), ("4B+tool", "tool"), ("8B", "bare"), ("8B+tool", "tool")):
        p = results_path(MODELS[key.split("+")[0]], strategy)
        R[key] = {r["id"]: r for r in map(json.loads, open(p))} if p.exists() else {}
        if len(R[key]) < len(ps):
            sys.exit(f"no complete {BENCH} results for {key} ({len(R[key])}/{len(ps)}); run results/run_bench_physics.sh")
    levels = {p["id"]: classify(p["question"])[0] for p in ps}
    per = {}
    for name, pol in POLICIES_PHYSICS:
        res = []
        for p in ps:
            steps, spend = pol[levels[p["id"]]], 0
            for i, (k, verifier) in enumerate(steps):  # verifiers (disagreement checks) are approximated as plain escalation
                spend += PARAMS[k.split("+")[0]] * R[k][p["id"]]["eval_tokens"]
                if not R[k][p["id"]]["issues"] or i == len(steps) - 1:
                    break
            res.append((R[k][p["id"]]["correct"], spend))
        per[name.strip()] = res
    n = len(ps)
    rng = random.Random(SEED)
    idx = [[rng.randrange(n) for _ in range(n)] for _ in range(resamples)]
    base = sum(s for _, s in per[SHIPPED])
    shipped = per[SHIPPED]
    print(f"{BENCH} physics ({n} problems)\n")
    print(f"{'policy':<48} {'score':>8} {'95% CI':>12} {'compute':>8} {'vs shipped, 95% CI':>20}")
    rows = []
    for name, res in per.items():
        score = sum(c for c, _ in res)
        boots = sorted(sum(res[i][0] for i in b) for b in idx)
        diffs = sorted(sum(res[i][0] - shipped[i][0] for i in b) for b in idx)
        lo, hi = boots[int(0.025 * resamples)], boots[int(0.975 * resamples)]
        dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
        cost = sum(s for _, s in res) / base
        rows.append((score, -cost, name, dlo))
        print(f"{name:<48} {score:>3}/{n:<4} {lo / n:>5.0%}-{hi / n:<5.0%} {cost:>8.0%} "
              f"{'' if name == SHIPPED else f'{dlo:+d} to {dhi:+d}':>20}")
    score, _, best, dlo = max(rows)
    if BENCH == "theoremqa":
        old, new = per[SHIPPED], per[SHIPPED_NOW]
        diffs = sorted(sum(old[i][0] - new[i][0] for i in b) for b in idx)
        print(f"\nrule: {TQA_RULE}\nold minus shipped, 95% CI: {diffs[int(0.025 * resamples)]:+d} to "
              f"{diffs[int(0.975 * resamples)]:+d}")
        print("-> REVERT to always 8B (bare)" if diffs[int(0.025 * resamples)] > 0 else "-> CONFIRMED: keep the switch")
    else:
        print(f"\nrule: {PHYS_RULE}")
        print(f"-> ADOPT: {best}" if best != SHIPPED and dlo > 0 else f"-> KEEP: {SHIPPED} (most right: {best})")
    print("\nkey-free check vs the key:")
    for k in R:
        wrong = [p["id"] for p in ps if not R[k][p["id"]]["correct"]]
        caught = sum(bool(R[k][pid]["issues"]) for pid in wrong)
        false = sum(bool(R[k][p["id"]]["issues"]) and R[k][p["id"]]["correct"] for p in ps)
        print(f"   {k:<8} wrong {len(wrong):>4}  caught {caught:>4}  false alarms {false:>3}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--strategy", choices=["bare", "tool"], default="bare")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--bench", choices=["scibench", "theoremqa"], default="scibench")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    global BENCH
    BENCH = args.bench
    if args.simulate:
        return simulate()
    if not args.model:
        sys.exit("--model or --simulate")
    run(args.model, args.strategy, args.timeout)


if __name__ == "__main__":
    main()
