"""SQL pack: a question about tables becomes a SQLite query, checked by running it on the task's schema.

The task's CREATE TABLE statements (and any INSERTs) are loaded into a throwaway
read-only database (plm_sql.sandbox) and the query must run there: that catches
syntax errors, misspelt tables and columns, and non-SQLite dialect. It can't see a
query that runs but answers a different question; with no schema in the task
there is nothing to run, and the answer is reported unchecked.

Until the SQL sweep picks one (evals/run_sql.py, rule SQL_RULE, fixed before the
sweep), every level uses the software pack's cascade: 4B -> 8B -> coder 14B,
escalating when the query doesn't run.

Model names can be overridden with PLM_SMALL_MODEL, PLM_LARGE_MODEL and PLM_CODER_MODEL.
"""

import os
import time

from plm.ollama import ask

from plm_sql.levels import classify
from plm_sql.sandbox import run_query
from plm_sql.sqlgen import build_prompt, extract_sql, split_task

MODELS = {
    "small": os.environ.get("PLM_SMALL_MODEL", "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M"),
    "large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b"),
    "coder": os.environ.get("PLM_CODER_MODEL", "qwen2.5-coder:14b"),
}
# Pre-sweep: answers in the preflight were 30-76 tokens.
CASCADE = ["small", "large", "coder"]
LEVELS = {
    "calm": {"num_predict": 512, "chain": CASCADE},
    "alert": {"num_predict": 512, "chain": CASCADE},
    "intensive": {"num_predict": 768, "chain": CASCADE},
}


def check(task, query):
    """Issues with a query: none if it runs on the task's schema. (issues, run result or None)."""
    if query is None:
        return ["no SQL query in the reply"], None
    if not task["setup"]:
        return [], None
    ran = run_query(task["setup"], query)
    if ran["setup_error"]:
        return [], None
    return ([f"doesn't run on the schema: {ran['error']}"] if ran["error"] else []), ran


def attempt(task, text, model, num_predict, timeout):
    start = time.time()
    r = ask(model, build_prompt(text), False, num_predict, timeout)
    query = extract_sql(r["response"])
    issues, ran = check(task, query)
    return {"model": model, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
            "model_text": r["response"], "capped": r["done_reason"] == "length", "code": query,
            "ran": ran and {k: ran[k] for k in ("columns", "n_rows", "error")}, "issues": issues,
            "seconds": time.time() - start}


def solve(text, level=None, timeout=300):
    """Write one query. Returns it plus a record of every model call."""
    start = time.time()
    task = split_task(text)
    if level:
        reason = "set by caller"
    else:
        level, reason = classify(text)
    plan = LEVELS[level]
    steps = []
    for model_key in plan["chain"]:
        steps.append(attempt(task, text, MODELS[model_key], plan["num_predict"], timeout))
        if not steps[-1]["issues"]:
            break
    final = steps[-1]
    if not task["setup"]:
        unchecked = "no CREATE TABLE statements given, so the query couldn't be run"
    elif final["code"] is not None and final["ran"] is None:
        unchecked = "the schema given doesn't load in SQLite, so the query couldn't be run"
    else:
        unchecked = None
    return {
        "pack": "sql",
        "task": text,
        "level": level,
        "reason": reason,
        "answer": {"code": final["code"], "language": "sql"} if final["code"] else None,
        "checked": unchecked is None,
        "unchecked_reason": unchecked,
        "trusted": unchecked is None and not final["issues"],
        "final_step": len(steps),
        "steps": steps,
        "tokens": sum(s["tokens"] for s in steps),
        "seconds": time.time() - start,
    }
