"""Software-pack controller: pick a level, have a specialist write the code, check it, escalate.

The check runs the code in the sandbox: it must load, define the requested
function or class, and pass every example given in the task. In the eval
sweep it caught 49 of 63 wrong answers with 1 false alarm, so every level uses
the same cheap-first cascade (4B -> 8B -> coder): 40/45 at 56% of the compute of
always using the coder (39/45). Routing by level on top of that made it worse
(39/45 at 83%), so the level only sets the token budget. See
evals/simulate_code_routing.py.

Model names can be overridden with PLM_SMALL_MODEL, PLM_LARGE_MODEL and PLM_CODER_MODEL.
"""

import os
import re
import time

from plm.ollama import ask
from plm.software.codegen import build_prompt, extract_code
from plm.software.levels import classify
from plm.software.sandbox import run_tests

MODELS = {
    "small": os.environ.get("PLM_SMALL_MODEL", "hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M"),
    "large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b"),
    "coder": os.environ.get("PLM_CODER_MODEL", "qwen2.5-coder:14b"),
}

# Per level: token budget and the escalation chain of model keys. Budgets are
# >2.5x the longest passing answer at that level in the eval sweep.
CASCADE = ["small", "large", "coder"]
LEVELS = {
    "calm": {"num_predict": 512, "chain": CASCADE},
    "alert": {"num_predict": 1024, "chain": CASCADE},
    "intensive": {"num_predict": 1536, "chain": CASCADE},
}

ENTRY_RE = re.compile(r"`(\w+)\s*\(|\bdef\s+(\w+)\s*\(|`?\bclass\s+`?(\w+)")
EXAMPLE_RE = re.compile(r"^\s*(?:assert\s+|>>>\s*)(.+?)\s*$", re.MULTILINE)


def parse_task(text):
    """Split pasted task text into a description, the entry name and example expressions."""
    m = ENTRY_RE.search(text)
    entry = next((g for g in m.groups() if g), None) if m else None
    examples = [e for e in EXAMPLE_RE.findall(text) if re.search(r"==|\bis\b|\bin\b|raises\(", e)]
    description = EXAMPLE_RE.sub("", text).strip()
    return {"prompt": description, "entry": entry, "examples": examples}


def attempt(task, model, num_predict, timeout):
    start = time.time()
    r = ask(model, build_prompt(task), False, num_predict, timeout)
    code = extract_code(r["response"], task["entry"] or "")
    step = {"model": model, "tokens": r["eval_tokens"], "model_text": r["response"], "code": code,
            "capped": r["done_reason"] == "length", "issues": []}
    if code is None:
        step["issues"].append("no code block")
    else:
        must_define = [f"callable({task['entry']})"] if task["entry"] else []
        result = run_tests(code, must_define + task["examples"])
        step["examples"] = result
        if result["error"]:
            step["issues"].append(result["error"])
        else:
            step["issues"] += [f"failed: {t}" + (f" ({why})" if why != "evaluated to False" else "")
                               for t, why in result["failures"]]
    step["seconds"] = time.time() - start
    return step


def solve(text, level=None, timeout=600):
    """Write code for one task. Returns the code plus a record of every model call."""
    start = time.time()
    task = parse_task(text)
    if level:
        reason = "set by caller"
    else:
        level, reason = classify(task["prompt"])
    plan = LEVELS[level]

    steps = []
    for model_key in plan["chain"]:
        steps.append(attempt(task, MODELS[model_key], plan["num_predict"], timeout))
        if not steps[-1]["issues"]:
            break

    final = steps[-1]
    checked = len(task["examples"])
    return {
        "pack": "software",
        "task": text,
        "level": level,
        "reason": reason + (f"; {checked} example{'s' if checked != 1 else ''} to check" if checked
                            else "; no examples given, so only loading is checked"),
        "answer": {"code": final["code"]} if final["code"] else None,
        "trusted": not final["issues"],
        "steps": steps,
        "tokens": sum(s["tokens"] for s in steps),
        "seconds": time.time() - start,
    }
