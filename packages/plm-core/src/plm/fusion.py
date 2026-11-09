"""Experimental pack fusion for CAD + engineering problems (the TUI's /fuse; not used by routing).

A planner (qwen3:8b) splits a problem into a calculation that yields one length and a CAD task with a {value}
slot; the coder answers the calculation through the numeric packs' calculator step, in metres, the value is
converted to mm in code, and the CAD pack models the part. Measured (evals/fusion/, FUSE3_RULE, 2026-11-08):
22/40 against the CAD pack alone's 17/40, paired 95% -4 to +14: not clearly better, so it isn't routed to
automatically; with the right numbers handed over the same plans reached 34/40.
"""

import json
import re
import time

from plm.numeric.answers import parse_answer
from plm.numeric.checks import ureg
from plm.numeric.controller import attempt
from plm.ollama import ask
from plm.packs import PACKS

PLANNER = "qwen3:8b"
CALCULATOR = "qwen2.5-coder:14b"
PLAN_PROMPT = """You split an engineering design problem into two steps for two specialists.

Step 1, a calculation, goes to one of these packs:
  physics     mechanics, stress, pressure, density and mass, pendulums, fluids
  electrical  resistance, resistivity, current, current density, voltage, power
  aerospace   flight, lift, drag, atmosphere, rockets, orbits
Write it as a complete, self-contained question that gives every number it needs and asks for ONE length,
in meters ("... Give the answer in m.").

Step 2, the part, goes to the CAD pack. Write the full description of the part to model, with every
dimension written out, and the literal text {value} where the length from step 1 goes (it will be
replaced by the number of millimeters, e.g. "a plate {value} mm thick").

Answer with JSON only, no other text:
{"pack": "<physics|electrical|aerospace>", "question": "<step 1>", "cad_task": "<step 2, containing {value}>"}

Problem:
"""


def plan(problem, timeout=600):
    """(plan dict, planner step) or (None, why)."""
    start = time.time()
    r = ask(PLANNER, PLAN_PROMPT + problem, False, 1024, timeout)
    step = {"model": PLANNER, "strategy": None, "tokens": r["eval_tokens"], "seconds": time.time() - start,
            "model_text": r["response"], "issues": [], "role": "planner"}
    m = re.search(r"\{.*\}", r["response"], re.DOTALL)
    try:
        p = json.loads(m.group(0)) if m else None
    except ValueError:
        p = None
    if not p or not p.get("question") or "{value}" not in (p.get("cad_task") or ""):
        step["issues"] = ["the planner didn't return a usable plan"]
        return None, step
    return p, step


def solve(problem, timeout=600):
    """A result shaped like a pack's (pack "cad"), with every step: planner, calculation, CAD."""
    start = time.time()
    p, plan_step = plan(problem, timeout)
    steps = [plan_step]
    if p is None:
        r = PACKS["cad"].solve(problem, timeout=timeout)  # no plan: the CAD pack alone, as without /fuse
        r["steps"] = steps + r["steps"]
        r["fusion"] = {"fell_back": "no usable plan"}
        r["tokens"] += plan_step["tokens"]
        return r
    calc = attempt(p["question"], CALCULATOR, "tool", 1024, timeout)
    calc["role"] = "calculation"
    steps.append(calc)
    parsed = parse_answer(calc["output"])
    try:
        value = ureg.Quantity(parsed[0], parsed[1] or "m").to("mm").magnitude if parsed else None
    except Exception:  # an answer that isn't a length
        value = None
    if value is None or value <= 0:
        r = PACKS["cad"].solve(problem, timeout=timeout)
        r["steps"] = steps + r["steps"]
        r["fusion"] = {"plan": p, "fell_back": f"the calculation gave no usable length ({calc['output'].strip()[:60]!r})"}
        r["tokens"] += sum(s["tokens"] for s in steps)
        return r
    task = p["cad_task"].replace("{value}", f"{value:.6g}")
    r = PACKS["cad"].solve(task, timeout=timeout)
    r["steps"] = steps + r["steps"]
    r["tokens"] += sum(s["tokens"] for s in steps)
    r["seconds"] = time.time() - start
    r["fusion"] = {"plan": p, "value_mm": value, "cad_task": task}
    r["reason"] = f"fusion (experimental): {p.get('pack', '?')} calculation by the coder, then cad"
    return r
