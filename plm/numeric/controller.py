"""Shared controller for numeric packs: pick a level, run a specialist, check the answer, escalate.

A numeric pack supplies only its level classifier and its tiers (models, token
budgets, escalation chains); everything else here is the same for every pack
whose answers are a number with a unit.

An answer is trusted only if it passed the checks *and* there was something to
check: when the question names no unit (plm.numeric.checks.requested_unit is
None) the checks can't fail, so the answer is reported as unchecked instead.
"""

import time

from plm.numeric import calc
from plm.numeric.answers import ANSWER_FORMAT, parse_answer
from plm.numeric.checks import check, requested_unit
from plm.ollama import ask


def attempt(task, model, strategy, num_predict, timeout):
    fmt = calc.TOOL_FORMAT if strategy == "tool" else ANSWER_FORMAT
    start = time.time()
    r = ask(model, f"{task}\n\n{fmt}", False, num_predict, timeout)
    step = {"model": model, "strategy": strategy, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
            "model_text": r["response"], "capped": r["done_reason"] == "length"}
    if strategy == "tool":
        code = calc.extract_program(r["response"])
        output, program_error = calc.run_program(code) if code else ("", "no code block")
        step["program"] = code
    else:
        output, program_error = r["response"], None
    step["output"] = output
    step["issues"] = ([program_error] if program_error else []) + check(task, output)
    step["seconds"] = time.time() - start
    return step


def solve(task, *, pack, classify, levels, models, level=None, timeout=300):
    """Answer one task. Returns the answer plus a record of every model call."""
    start = time.time()
    if level:
        reason = "set by caller"
    else:
        level, reason = classify(task)
    plan = levels[level]

    steps = []
    for model_key, strategy in plan["chain"]:
        steps.append(attempt(task, models[model_key], strategy, plan["num_predict"], timeout))
        if not steps[-1]["issues"]:
            break

    final = steps[-1]
    parsed = parse_answer(final["output"])
    checked = requested_unit(task) is not None
    return {
        "pack": pack,
        "task": task,
        "level": level,
        "reason": reason,
        "answer": {"value": parsed[0], "unit": parsed[1]} if parsed else None,
        "checked": checked,
        "unchecked_reason": None if checked else "the question names no unit, so the answer couldn't be checked",
        "trusted": checked and not final["issues"],
        "steps": steps,
        "tokens": sum(s["tokens"] for s in steps),
        "seconds": time.time() - start,
    }
