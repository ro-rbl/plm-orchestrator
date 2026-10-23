"""CAD pack: a part described in words becomes a CadQuery program, checked by building it.

The answer is the program, plus what the kernel measured. A program is trusted
when it builds exactly one valid solid whose overall size matches dimensions in
the task and which has every hole the task asks for by diameter, through or as
deep as asked (plm_cad.checks). Other features (pockets, slots, chamfers) aren't
checked, so a wrong pocket in a right-sized block still passes.

The policy fixed before the CAD sweep was the software pack's cascade (4B -> 8B
-> coder 14B, escalating on a failed check). CAD_RULE in evals/run_cad.py, also
fixed before the sweep, picks the cheapest policy within 1 problem of the best;
on the 36-part eval only one was:

    always coder 14B                          17/36 at 100% of always-coder compute
    cascade 8B -> coder                       16/36 at 134%
    cascade 4B -> 8B -> coder (pre-sweep)     15/36 at 112%
    always 4B                                 10/36 at 38%
    always 8B                                  7/36 at 63%

The small models mostly misuse CadQuery's API (19 of the 8B's 36 programs don't
build), and escalating costs more than asking the coder first. So every level
goes to the coder alone; a failed check is reported, not escalated. Budgets are
>2.5x the coder's longest answer at each level (94, 128, 261 tokens).

Model name can be overridden with PLM_CODER_MODEL.
"""

import os
import time

from plm.ollama import ask

from plm_cad import kernel
from plm_cad.checks import check
from plm_cad.levels import classify

MODELS = {"coder": os.environ.get("PLM_CODER_MODEL", "qwen2.5-coder:14b")}
LEVELS = {
    "calm": {"num_predict": 384, "chain": ["coder"]},
    "alert": {"num_predict": 512, "chain": ["coder"]},
    "intensive": {"num_predict": 768, "chain": ["coder"]},
}

PROMPT_VERSION = 1
CAD_FORMAT = (
    "Write one Python program in a ```python code block that builds this part with CadQuery, in "
    "millimeters. Start with `import cadquery as cq` and assign the finished part, a cq.Workplane "
    "holding one solid, to a variable named result. Do not export, show or print anything."
)


def attempt(task, model, num_predict, timeout):
    start = time.time()
    r = ask(model, f"{task}\n\n{CAD_FORMAT}", False, num_predict, timeout)
    code = kernel.extract_program(r["response"])
    measured, error = kernel.build(code) if code else (None, "no code block")
    return {"model": model, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
            "model_text": r["response"], "capped": r["done_reason"] == "length", "code": code,
            "measured": measured, "issues": check(task, measured, error), "seconds": time.time() - start}


def solve(task, level=None, timeout=300):
    """Model one part. Returns the program and its measurements plus a record of every model call."""
    start = time.time()
    if level:
        reason = "set by caller"
    else:
        level, reason = classify(task)
    plan = LEVELS[level]
    steps = []
    for model_key in plan["chain"]:
        steps.append(attempt(task, MODELS[model_key], plan["num_predict"], timeout))
        if not steps[-1]["issues"]:
            break
    final = steps[-1]
    return {
        "pack": "cad",
        "task": task,
        "level": level,
        "reason": reason,
        "answer": {"code": final["code"], "measured": final["measured"]} if final["code"] else None,
        "checked": True,
        "unchecked_reason": None,
        "trusted": not final["issues"],
        "steps": steps,
        "tokens": sum(s["tokens"] for s in steps),
        "seconds": time.time() - start,
    }
