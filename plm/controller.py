"""Adaptive controller: pick an adrenaline level, run a specialist, check the answer, escalate.

The defaults are the best policy from evals/simulate_routing.py: calm and alert
problems go to the small model with the calculator, intensive ones to the large
model, and any answer that fails plm.checks moves to the next step. Agreement
checks (a second model's opinion) are not used: in the simulation they cost more
compute than they saved.

Model names can be overridden with PLM_SMALL_MODEL and PLM_LARGE_MODEL.
"""

import os
import time

from plm import calc
from plm.answers import ANSWER_FORMAT, parse_answer
from plm.checks import check
from plm.levels import classify
from plm.ollama import ask

MODELS = {
    "small": os.environ.get("PLM_SMALL_MODEL", "hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M"),
    "large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b"),
}

# Per level: token budget and the escalation chain of (model, strategy) steps.
# Budgets are >2.5x the longest calculator answer seen in the eval runs.
LEVELS = {
    "calm": {"num_predict": 384, "chain": [("small", "tool"), ("large", "tool")]},
    "alert": {"num_predict": 512, "chain": [("small", "tool"), ("large", "tool")]},
    "intensive": {"num_predict": 1024, "chain": [("large", "tool"), ("large", "bare")]},
}


def attempt(task, model, strategy, num_predict, timeout):
    fmt = calc.TOOL_FORMAT if strategy == "tool" else ANSWER_FORMAT
    start = time.time()
    r = ask(model, f"{task}\n\n{fmt}", False, num_predict, timeout)
    step = {"model": model, "strategy": strategy, "tokens": r["eval_tokens"],
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


def solve(task, level=None, timeout=300):
    """Answer one task. Returns the answer plus a record of every model call."""
    start = time.time()
    if level:
        reason = "set by caller"
    else:
        level, reason = classify(task)
    plan = LEVELS[level]

    steps = []
    for model_key, strategy in plan["chain"]:
        steps.append(attempt(task, MODELS[model_key], strategy, plan["num_predict"], timeout))
        if not steps[-1]["issues"]:
            break

    final = steps[-1]
    parsed = parse_answer(final["output"])
    return {
        "pack": "electrical",
        "task": task,
        "level": level,
        "reason": reason,
        "answer": {"value": parsed[0], "unit": parsed[1]} if parsed else None,
        "trusted": not final["issues"],
        "steps": steps,
        "tokens": sum(s["tokens"] for s in steps),
        "seconds": time.time() - start,
    }
