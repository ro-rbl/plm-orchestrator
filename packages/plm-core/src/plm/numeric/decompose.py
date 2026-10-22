"""Decompose, then solve (ROADMAP 3b, an idea from SKY-001): plan the steps, compute each, check each.

One call plans the calculation as up to MAX_STEPS quantities, each with a unit and a
way to compute it from the givens and earlier steps; the last one is the answer.
Then one call per step writes a calculator program for that quantity alone, seeing
the values already computed. A step's result must parse, be finite and have the
dimension the plan gave it before the next step runs. The last step's output is the
answer and goes through the pack's usual checks.

If the plan can't be read or a step fails its check, the problem falls back to one
plain calculator program (the tool strategy), so a broken decomposition costs
tokens but never loses the answer the shipped strategy would give. Every call's
tokens count.

Written after the unit-aware calculator result: models made more mistakes when
one program had to carry more bookkeeping, so this splits the work across calls
instead. The adoption rule and cost bound were fixed before the sweep: see
evals/score_decompose.py (DECOMPOSE_RULE).
"""

import math
import re
import time

from plm.numeric import calc
from plm.numeric.answers import LITERAL_UNITS, parse_answer, ureg
from plm.ollama import ask

MAX_STEPS = 6
PLAN_PROMPT_VERSION = 1
PLAN_FORMAT = (
    "Do not compute anything yet. Plan the calculation as a short list of steps. Each step computes "
    "one quantity from the given values and the results of earlier steps; the last step computes the "
    f"quantity the question asks for, in the unit it asks for. Use at most {MAX_STEPS} steps. Write each "
    "step on its own line, exactly in this form, like these examples:\n"
    "STEP: total resistance | ohm | R1 + R2\n"
    "STEP: current | A | supply voltage / total resistance\n"
    "Write none as the unit of a unitless quantity. Write nothing else."
)
STEP_PROMPT_VERSION = 1
STEP_RE = re.compile(r"^[\W\d]*STEP\s*\d*\s*:\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def parse_plan(text):
    """[(name, unit, how), ...] from the planner's STEP lines; unit '' for unitless."""
    steps = []
    for name, unit, how in STEP_RE.findall(text or ""):
        unit = unit.strip().strip("`[]()")
        steps.append((name.strip(), "" if unit.lower() in ("none", "unitless", "dimensionless", "-") else unit, how))
    return steps


def step_prompt(task, plan, done, i):
    lines = [task, "", "The calculation is planned in these steps:"]
    lines += [f"{k}. {name} [{unit or 'unitless'}]: {how}" for k, (name, unit, how) in enumerate(plan, 1)]
    if done:
        lines += ["", "Already computed:"] + [f"{plan[k][0]} = {v:.6g} {u}".rstrip() for k, (v, u) in enumerate(done)]
    name, unit, how = plan[i]
    lines += ["", f"Now compute step {i + 1} only: {name}, in {unit or 'no unit (it is unitless)'}: {how}.",
              "Do not do the arithmetic yourself. Write one Python program in a ```python code block that "
              "computes this one quantity, using only the math module and the numbers above. The program must "
              "print exactly one line: the result as a number followed by its unit, like this example:",
              'print(f"ANSWER: {current_a:.6g} A")',
              f"Print it in {unit}." if unit else "It is unitless, so print only the number."]
    return "\n".join(lines)


def step_issue(output, unit):
    """Why a step's output can't be used, or None. The unit must have the planned dimension."""
    parsed = parse_answer(output)
    if parsed is None:
        return "no ANSWER line"
    value, got = parsed
    if not math.isfinite(value):
        return f"not a finite number: {value}"
    if not unit:
        return None if got.lower() in LITERAL_UNITS[""] else f"planned unitless, got {got!r}"
    try:
        want_dim = ureg.Quantity(1, unit).dimensionality
    except Exception:  # pint raises several types for names it doesn't know
        return None  # the plan's unit isn't one pint reads, so there's nothing to compare against
    try:
        got_dim = ureg.Quantity(1, got).dimensionality if got else ureg.Quantity(1).dimensionality
    except Exception:
        return f"unit {got!r} not understood"
    return None if got_dim == want_dim else f"planned {unit}, got {got or 'no unit'}"


def _call(model, prompt, num_predict, timeout, kind):
    r = ask(model, prompt, False, num_predict, timeout)
    return {"kind": kind, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"], "text": r["response"],
            "capped": r["done_reason"] == "length", "seconds": r["wall_s"], "done_reason": r["done_reason"]}


def _run(text):
    code = calc.extract_program(text)
    return calc.run_program(code) if code else ("", "no code block")


def solve(task, model, num_predict, timeout):
    """Plan, compute and check each step; fall back to one calculator program if any of that fails.

    Returns output (the final program's stdout), program_error, fallback (why, or None),
    plan, and every call with its tokens.
    """
    start = time.time()
    calls = [_call(model, f"{task}\n\n{PLAN_FORMAT}", num_predict, timeout, "plan")]
    plan = parse_plan(calls[0]["text"])
    fallback, output, error = None, "", None
    if not plan:
        fallback = "no STEP lines in the plan"
    elif len(plan) > MAX_STEPS:
        fallback = f"plan has {len(plan)} steps, more than {MAX_STEPS}"
    else:
        done = []
        for i, (name, unit, _) in enumerate(plan):
            call = _call(model, step_prompt(task, plan, done, i), num_predict, timeout, f"step {i + 1}")
            output, error = _run(call["text"])
            call["output"], call["program_error"] = output, error
            calls.append(call)
            issue = error or step_issue(output, unit)
            if issue:
                fallback = f"step {i + 1} ({name}): {issue}"
                break
            done.append(parse_answer(output))
    if fallback:
        call = _call(model, f"{task}\n\n{calc.TOOL_FORMAT}", num_predict, timeout, "fallback: tool")
        output, error = _run(call["text"])
        call["output"], call["program_error"] = output, error
        calls.append(call)
    return {"output": output, "program_error": error, "fallback": fallback, "plan": plan, "calls": calls,
            "tokens": sum(c["tokens"] for c in calls), "prompt_tokens": sum(c["prompt_tokens"] for c in calls),
            "seconds": time.time() - start, "done_reason": calls[-1]["done_reason"]}
