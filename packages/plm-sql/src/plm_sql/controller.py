"""SQL pack: a question about tables becomes a SQLite query, checked by running it on the task's schema.

The task's CREATE TABLE statements (and any INSERTs) are loaded into a throwaway
read-only database (plm_sql.sandbox) and the query must run there: that catches
syntax errors, misspelt tables and columns, and non-SQLite dialect. It can't see a
query that runs but answers a different question; with no schema in the task
there is nothing to run, and the answer is reported unchecked.

Policies and rules were fixed before each run (evals/run_sql.py, evals/bench_sql.py). Our own
sets (45 eval tasks, then 48 harder fresh ones) settled on always 8B, with the coder tied (42/48).
The public benchmarks, written by others and larger, disagreed:

                          Spider (299 dev)      BIRD mini-dev (496)    compute vs always-coder
    always coder 14B      228 (76%, 72-81%)     254 (51%, 47-56%)      100%
    cascade 8B -> coder   209 (70%)             207 (42%)              70-80%
    always 8B             201 (67%, 62-73%)     172 (35%, 30-39%)      55-66%

BENCH_RULE capped extra compute at +10 points, so it kept always 8B; the coder beats it on both
benchmarks with paired 95% intervals well above 0 (+15 to +40, +62 to +105). On 2026-10-24 the user
chose accuracy over compute for SQL: every level goes to the coder alone, about 1.5-1.8x the 8B's
compute. A query that doesn't run is reported, not escalated (the check caught 38 of 242 of the
coder's wrong BIRD queries). Budgets are 2.9-3.7x the coder's longest answer at each level over
every set and benchmark (268, 321 and 210 tokens; none hit a cap).

Model name can be overridden with PLM_CODER_MODEL.
"""

import os
import time

from plm.ollama import ask

from plm_sql.levels import classify
from plm_sql.sandbox import run_query
from plm_sql.sqlgen import build_prompt, extract_sql, split_task

MODELS = {"coder": os.environ.get("PLM_CODER_MODEL", "qwen2.5-coder:14b")}
LEVELS = {
    "calm": {"num_predict": 768, "chain": ["coder"]},
    "alert": {"num_predict": 1024, "chain": ["coder"]},
    "intensive": {"num_predict": 768, "chain": ["coder"]},
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
