"""CADPrompt (200 text-to-CAD parts) for the CAD pack: build references, run models, grade, simulate.

    .venv/bin/python evals/bench_cad.py --verify                     # every reference builds; matches CADPrompt's data
    .venv/bin/python evals/bench_cad.py --model qwen2.5-coder:14b    # results/bench_cadprompt__<model>.jsonl
    .venv/bin/python evals/bench_cad.py --simulate                   # POLICIES_CAD, 95% CIs, CADP_RULE

Data (not redistributed; the repo states no license): github.com/Kamel773/CAD_Code_Generation, folder
CADPrompt (from "Generating CAD Code with Vision-Language Models for 3D Designs", 2024), downloaded
2026-10-24 into .benchmarks/cadprompt/: per part, a description with specific measurements, the
CadQuery program that made the ground truth, and its measured properties.

The task is the description with measurements (what a user would type), sent through the CAD pack's
prompt and kernel exactly as in production. The reference is the part's own CadQuery program built in
the same kernel (its export call replaced by `result = <part>`). Graded as evals/run_cad.py grades our
own set: one valid solid whose bounding box (extents sorted) and volume match the reference's within
REL_TOL. CADPrompt's own metrics are point-cloud distances, so scores aren't comparable with its paper.
Policies (run_cad.POLICIES_CAD) and CADP_RULE, accuracy first, fixed on 2026-10-24 before any model ran.
"""

import argparse
import ast
import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from plm.ollama import ask, unreachable  # noqa: E402
from plm_cad import kernel  # noqa: E402
from plm_cad.checks import check  # noqa: E402
from plm_cad.controller import CAD_FORMAT, PROMPT_VERSION  # noqa: E402
from run_cad import MODELS, PARAMS, POLICIES_CAD  # noqa: E402

DATA = ROOT / ".benchmarks/cadprompt"
RESULTS = ROOT / "results"
REFS = RESULTS / "bench_cadprompt_references.json"
REL_TOL = 0.001
SHIPPED = "always coder"
CADP_RULE = ("the policy with the most parts right replaces the CAD pack's shipped one (always coder) iff a paired "
             "bootstrap 95% interval of its score minus the shipped one's lies entirely above 0 (accuracy first, "
             "compute reported)")
SEED = 20261024


def reference_code(code):
    """The part's CadQuery program with its export replaced by `result = <the exported part>`."""
    m = re.search(r"cq\.exporters\.export\(\s*([A-Za-z_]\w*)", code)
    if not m:
        return None
    lines = [ln for ln in code.splitlines() if "exporters.export" not in ln]
    return strip_hints("\n".join(lines)) + f"\nresult = {m[1]}\n"


def strip_hints(code):
    """The program without type annotations or its typing import: 34 references annotate with
    typing.List/Tuple, which the kernel's import screen refuses; annotations never change the part."""
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            node.returns = None
            for a in node.args.args + node.args.kwonlyargs + node.args.posonlyargs:
                a.annotation = None
    body = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "typing":
            continue
        if isinstance(node, ast.AnnAssign):
            if node.value is None:
                continue
            node = ast.copy_location(ast.Assign(targets=[node.target], value=node.value), node)
        body.append(node)
    tree.body = body
    return ast.unparse(ast.fix_missing_locations(tree))


def parts():
    if not DATA.exists():
        sys.exit(f"{DATA} is missing: download it as this file's docstring says")
    out = []
    for d in sorted(p for p in DATA.iterdir() if p.is_dir()):
        task = (d / "Natural_Language_Descriptions_Prompt_with_specific_measurements.txt").read_text().strip()
        out.append({"id": f"cadp-{d.name}", "task": task, "code": (d / "Python_Code.py").read_text(),
                    "truth": json.loads((d / "Ground_Truth.json").read_text())["Ground_Truth"]})
    return out


def grade(measured, ref):
    if measured is None:
        return "no_part"
    if not measured["valid"] or measured["solids"] != 1:
        return "invalid"
    if not all(math.isclose(a, b, rel_tol=REL_TOL, abs_tol=1e-9) for a, b in zip(measured["bbox"], ref["bbox"])):
        return "wrong_size"
    if not math.isclose(measured["volume"], ref["volume"], rel_tol=REL_TOL, abs_tol=1e-9):
        return "wrong_volume"
    return "correct"


def verify():
    refs, problems = {}, []
    for p in parts():
        code = reference_code(p["code"])
        measured, error = kernel.build(code) if code else (None, "no export call to replace")
        if measured is None or not measured["valid"] or measured["solids"] != 1:
            problems.append((p["id"], error or "not one valid solid"))
            continue
        t = p["truth"]  # CADPrompt's own measurements (from its exported mesh)
        theirs = sorted([t["Width_mm"], t["Height_mm"], t["Depth_mm"]])
        if not all(math.isclose(a, b, rel_tol=0.01, abs_tol=1e-6) for a, b in zip(measured["bbox"], theirs)):
            problems.append((p["id"], f"bbox {measured['bbox']} vs CADPrompt's {theirs}"))
        refs[p["id"]] = {"bbox": measured["bbox"], "volume": measured["volume"]}
    REFS.write_text(json.dumps(refs, indent=1))
    print(f"{len(refs)} of {len(parts())} references build as one valid solid; written to {REFS.name}")
    for pid, why in problems:
        print("  ", pid, str(why)[:120])


def results_path(model):
    return RESULTS / f"bench_cadprompt__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"


def run(model, num_predict, timeout):
    refs = json.loads(REFS.read_text())
    ps = [p for p in parts() if p["id"] in refs]
    out = results_path(model)
    done = {r["id"] for r in map(json.loads, open(out))} if out.exists() else set()
    todo = [p for p in ps if p["id"] not in done]
    print(f"{model} on CADPrompt: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, p in enumerate(todo, 1):
            row = {"id": p["id"], "model": model, "prompt_version": PROMPT_VERSION, "num_predict": num_predict}
            try:
                r = ask(model, f"{p['task']}\n\n{CAD_FORMAT}", False, num_predict, timeout)
                code = kernel.extract_program(r["response"])
                measured, error = kernel.build(code) if code else (None, "no code block")
                row.update({"response": r["response"], "eval_tokens": r["eval_tokens"], "wall_s": r["wall_s"],
                            "done_reason": r["done_reason"], "code": code, "measured": measured, "error": error,
                            "issues": check(p["task"], measured, error)})
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this task and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped, resume to retry")
                row.update({"response": "", "eval_tokens": 0, "wall_s": 0, "done_reason": "error", "code": None,
                            "measured": None, "error": f"{type(e).__name__}: {e}", "issues": ["request failed"]})
            row["verdict"] = grade(row["measured"], refs[p["id"]])
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {p['id']} {row['verdict']:<12} {row['eval_tokens']:>5} tok {row['wall_s']:>6.1f}s"
                  + (f"  [{'; '.join(row['issues'])[:70]}]" if row["issues"] else ""), flush=True)


def simulate(resamples=2000):
    from plm_cad.levels import classify
    refs = json.loads(REFS.read_text())
    ps = [p for p in parts() if p["id"] in refs]
    R = {}
    for k, m in MODELS.items():
        path = results_path(m)
        R[k] = {r["id"]: r for r in map(json.loads, open(path))} if path.exists() else {}
        if len(R[k]) < len(ps):
            sys.exit(f"no complete CADPrompt results for {k} ({len(R[k])}/{len(ps)}); run results/run_bench_cad.sh")
    levels = {p["id"]: classify(p["task"])[0] for p in ps}
    per = {}
    for name, pol in POLICIES_CAD:
        res = []
        for p in ps:
            chain, spend = pol[levels[p["id"]]], 0
            for i, k in enumerate(chain):
                spend += PARAMS[k] * R[k][p["id"]]["eval_tokens"]
                if not R[k][p["id"]]["issues"] or i == len(chain) - 1:
                    break
            res.append((R[k][p["id"]]["verdict"] == "correct", spend))
        per[name] = res
    n = len(ps)
    rng = random.Random(SEED)
    idx = [[rng.randrange(n) for _ in range(n)] for _ in range(resamples)]
    base = sum(s for _, s in per[SHIPPED])
    shipped = per[SHIPPED]
    print(f"CADPrompt: {n} parts\n\n{'policy':<48} {'score':>8} {'95% CI':>12} {'compute':>8} {'vs shipped, 95% CI':>20}")
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
    print(f"\nrule: {CADP_RULE}")
    print(f"-> ADOPT: {best}" if best != SHIPPED and dlo > 0 else f"-> KEEP: {SHIPPED} (most right: {best})")
    print("\nkey-free check vs the key:")
    for k in R:
        wrong = [p["id"] for p in ps if R[k][p["id"]]["verdict"] != "correct"]
        caught = sum(bool(R[k][pid]["issues"]) for pid in wrong)
        false = sum(bool(R[k][p["id"]]["issues"]) and R[k][p["id"]]["verdict"] == "correct" for p in ps)
        print(f"   {k:<6} wrong {len(wrong):>4}  caught {caught:>4}  false alarms {false:>3}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--num-predict", type=int, default=1024)
    ap.add_argument("--timeout", type=int, default=300)
    args = ap.parse_args()
    if args.verify:
        return verify()
    if args.simulate:
        return simulate()
    if not args.model:
        sys.exit("--model, --verify or --simulate")
    run(args.model, args.num_predict, args.timeout)


if __name__ == "__main__":
    main()
