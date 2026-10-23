"""CAD pack: a part described in words becomes a CadQuery program, checked by building it.

The answer is the program, plus what the kernel measured. A program is trusted
when it builds exactly one valid solid whose overall size matches dimensions in
the task (plm_cad.checks); a check that fails moves the task to the next model.
The policy was fixed before the CAD sweep, in the software pack's shape (both
answer with code): a cheap-first cascade 4B -> 8B -> coder 14B for every level.
evals/run_cad.py --simulate has the alternatives and the rule (CAD_RULE) that
picks among them after the sweep.

Model names can be overridden with PLM_SMALL_MODEL, PLM_LARGE_MODEL and PLM_CODER_MODEL.
"""

import os
import time

from plm.ollama import ask

from plm_cad import kernel
from plm_cad.checks import check
from plm_cad.levels import classify

MODELS = {
    "small": os.environ.get("PLM_SMALL_MODEL", "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M"),
    "large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b"),
    "coder": os.environ.get("PLM_CODER_MODEL", "qwen2.5-coder:14b"),
}
CASCADE = ["small", "large", "coder"]
LEVELS = {
    "calm": {"num_predict": 768, "chain": CASCADE},
    "alert": {"num_predict": 1024, "chain": CASCADE},
    "intensive": {"num_predict": 1536, "chain": CASCADE},
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
