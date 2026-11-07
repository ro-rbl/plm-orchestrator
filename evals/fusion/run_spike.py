"""Fusion spike: can a small local model plan a CAD + engineering problem into a calculation and a part?

    .venv/bin/python evals/fusion/run_spike.py           # resumes; results/fusion_spike.jsonl
    .venv/bin/python evals/fusion/run_spike.py --report

Three setups per problem (evals/fusion/spike.jsonl):
    cad_alone   the CAD pack gets the whole problem (today's behavior)
    fusion      PLANNER (qwen3:8b) splits it into a question for one numeric pack and a CAD task with a {value}
                slot; the pack answers (its own checks apply), the value in mm fills the slot, the CAD pack models it
    oracle      the planner's CAD task with the correct value filled in: how good fusion could be with perfect
                calculations, to tell planning and calculation misses from CAD misses
Grade: the CAD grader (bbox and volume within 0.1%). A feasibility spike on 10 problems: no adoption rule.
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import pint  # noqa: E402
from run_cad import grade  # noqa: E402

from plm import packs  # noqa: E402
from plm.ollama import ask  # noqa: E402

PROBLEMS = Path(__file__).parent / "spike.jsonl"
OUT = ROOT / "results/fusion_spike.jsonl"
PLANNER = "qwen3:8b"
NUMERIC = ("physics", "electrical", "aerospace")
UREG = pint.UnitRegistry()

PLAN_PROMPT = """You split an engineering design problem into two steps for two specialists.

Step 1, a calculation, goes to one of these packs:
  physics     mechanics, stress, pressure, density and mass, pendulums, fluids
  electrical  resistance, resistivity, current, current density, voltage, power
  aerospace   flight, lift, drag, atmosphere, rockets, orbits
Write it as a complete, self-contained question that gives every number it needs and asks for ONE length,
in millimeters ("... Give the answer in mm.").

Step 2, the part, goes to the CAD pack. Write the full description of the part to model, with every
dimension written out, and the literal text {value} where the length from step 1 goes (it will be
replaced by the number of millimeters, e.g. "a plate {value} mm thick").

Answer with JSON only, no other text:
{"pack": "<physics|electrical|aerospace>", "question": "<step 1>", "cad_task": "<step 2, containing {value}>"}

Problem:
"""


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def parse_plan(text):
    """The planner's JSON, or (None, why)."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None, "no JSON"
    try:
        plan = json.loads(m.group(0))
    except ValueError as e:
        return None, f"bad JSON: {e}"
    if plan.get("pack") not in NUMERIC:
        return None, f"pack {plan.get('pack')!r} isn't a numeric pack"
    if not plan.get("question") or "{value}" not in (plan.get("cad_task") or ""):
        return None, "missing question, or cad_task without {value}"
    return plan, None


def to_mm(answer):
    """A numeric pack's answer as millimeters, or (None, why)."""
    if not answer:
        return None, "no answer"
    try:
        q = UREG.Quantity(answer["value"], answer["unit"] or "mm")
        return q.to("mm").magnitude, None
    except Exception as e:  # any pint failure means "not a length we can use"
        return None, f"answer {answer} isn't a length: {type(e).__name__}"


def cad(task):
    r = packs.PACKS["cad"].solve(task)
    measured = r["answer"]["measured"] if r["answer"] else None
    return {"task": task, "measured": measured, "trusted": r["trusted"], "tokens": r["tokens"],
            "seconds": round(r["seconds"], 1), "code": r["answer"] and r["answer"]["code"]}


def run_one(p, setup):
    start = time.time()
    if setup == "cad_alone":
        c = cad(p["task"])
        return {"verdict": grade(p, c["measured"]), "cad": c, "tokens": c["tokens"]}
    r = ask(PLANNER, PLAN_PROMPT + p["task"], False, 1024, 600)
    plan, why = parse_plan(r["response"])
    row = {"plan_text": r["response"], "plan": plan, "plan_tokens": r["eval_tokens"], "tokens": r["eval_tokens"]}
    if not plan:
        return row | {"verdict": "bad_plan", "why": why, "seconds": round(time.time() - start, 1)}
    if setup == "oracle":
        value = p["dim_mm"]
    else:
        n = packs.PACKS[plan["pack"]].solve(plan["question"])
        value, why = to_mm(n["answer"])
        row |= {"calc": {"answer": n["answer"], "trusted": n["trusted"], "tokens": n["tokens"], "value_mm": value},
                "calc_ok": value is not None and abs(value - p["dim_mm"]) <= 1e-3 * p["dim_mm"]}
        row["tokens"] += n["tokens"]
        if value is None:
            return row | {"verdict": "bad_calc", "why": why, "seconds": round(time.time() - start, 1)}
    c = cad(plan["cad_task"].replace("{value}", f"{value:.6g}"))
    row["tokens"] += c["tokens"]
    return row | {"cad": c, "verdict": grade(p, c["measured"]), "seconds": round(time.time() - start, 1)}


def report():
    rows = load(OUT)
    by = {}
    for r in rows:
        by.setdefault(r["setup"], {})[r["id"]] = r
    ids = [p["id"] for p in load(PROBLEMS)]
    print(f"{'problem':<7} {'cad_alone':<13} {'fusion':<13} {'oracle':<13} plan pack / calc")
    for i in ids:
        f = by.get("fusion", {}).get(i, {})
        calc = f.get("calc", {})
        print(f"{i:<7} {by.get('cad_alone', {}).get(i, {}).get('verdict', '-'):<13} {f.get('verdict', '-'):<13} "
              f"{by.get('oracle', {}).get(i, {}).get('verdict', '-'):<13} {(f.get('plan') or {}).get('pack', '-')} / "
              f"{'ok' if f.get('calc_ok') else (calc.get('value_mm') and round(calc['value_mm'], 3)) or '-'}")
    for s in ("cad_alone", "fusion", "oracle"):
        got = by.get(s, {})
        print(f"{s:<10} correct {sum(r['verdict'] == 'correct' for r in got.values())}/{len(got)}  "
              f"tokens {sum(r.get('tokens', 0) for r in got.values())}")
    f = by.get("fusion", {}).values()
    print(f"fusion: usable plans {sum(r['verdict'] != 'bad_plan' for r in f)}/{len(f)}, "
          f"right calculations {sum(bool(r.get('calc_ok')) for r in f)}/{len(f)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report()
    done = {(r["id"], r["setup"]) for r in load(OUT)} if OUT.exists() else set()
    problems = load(PROBLEMS)
    with OUT.open("a") as f:
        for setup in ("cad_alone", "fusion", "oracle"):
            for p in problems:
                if (p["id"], setup) in done:
                    continue
                try:
                    row = run_one(p, setup)
                except Exception as e:  # keep going; one bad problem must not lose the run
                    row = {"verdict": "error", "why": f"{type(e).__name__}: {e}"}
                row = {"id": p["id"], "setup": setup} | row
                f.write(json.dumps(row) + "\n")
                f.flush()
                print(f"{setup:<10} {p['id']} {row['verdict']:<13} {row.get('why', '')}", flush=True)
    report()


if __name__ == "__main__":
    main()
