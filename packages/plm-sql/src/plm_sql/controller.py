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

With the user's database (`plm --sql-db <file>`, or PLM_SQL_DB for the server; opened read-only, and
its schema is read from the file when the task gives none), the query also runs on the real data and
plm_sql.flags reads the result. When the coder's query is flagged, the 4B answers too, and its query
is used iff it raises no flag; otherwise the coder's is kept and reported with its flags. FLAGS_RULE
(evals/bench_sql_check.py), fixed before, adopted this on 2880 unseen Spider questions on 2026-10-29:
2230 vs 2212 for the coder alone (+7 to +30, paired 95%), at 105% compute. Without a database the
pack is as above.

Model names can be overridden with PLM_CODER_MODEL and PLM_SMALL_MODEL.
"""

import os
import sqlite3
import time
from pathlib import Path

from plm.ollama import ask

from plm_sql.flags import HUGE_ROWS, named_tables, result_flags
from plm_sql.levels import classify
from plm_sql.sandbox import run_query
from plm_sql.sqlgen import build_prompt, extract_sql, split_task

MODELS = {"coder": os.environ.get("PLM_CODER_MODEL", "qwen2.5-coder:14b"),
          "small": os.environ.get("PLM_SMALL_MODEL", "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M")}
SECOND_OPINION = "small"  # asked only when the coder's query is flagged on the user's database
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


def open_db(path):
    """(resolved path, schema SQL, table names) of a database file, read-only. Raises ValueError if it can't be read."""
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"no database file at {path}")
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            rows = con.execute("SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL "
                               "AND name NOT LIKE 'sqlite_%' ORDER BY rowid").fetchall()
        finally:
            con.close()
    except sqlite3.Error as e:
        raise ValueError(f"{path} isn't a readable SQLite database: {e}") from None
    if not rows:
        raise ValueError(f"{path} has no tables")
    return str(path), ";\n".join(r[1].strip() for r in rows) + ";", [r[0] for r in rows]


FLAG_TEXT = {"empty": "returns no rows on the database", "huge": f"returns more than {HUGE_ROWS} rows on the database",
             "nulls": "returns only NULLs on the database"}


def db_issues(task, query, db):
    """Flags for a query on the user's database, as issues, and its run there (or None)."""
    path, _, tables = db
    ran = run_query("", query, seconds=30, db_path=path) if query else None
    issues = []
    for f in result_flags(task["question"], query, ran, tables):
        if f == "error":
            issues.append(f"doesn't run on the database: {ran['error']}" if ran else "no SQL query in the reply")
        elif f == "tables":
            issues.append("uses none of the tables the question names (" + ", ".join(named_tables(task["question"], tables)) + ")")
        else:
            issues.append(FLAG_TEXT[f])
    return issues, ran


def attempt(task, text, model, num_predict, timeout, db=None):
    start = time.time()
    r = ask(model, build_prompt(text), False, num_predict, timeout)
    query = extract_sql(r["response"])
    issues, ran = check(task, query)
    on_db = None
    if db:  # the run on the real data replaces the run on the bare schema, as in the benchmark that judged it
        issues, ran_db = db_issues(task, query, db)
        on_db = ran_db and {k: ran_db[k] for k in ("columns", "n_rows", "error")}
    return {"model": model, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
            "model_text": r["response"], "capped": r["done_reason"] == "length", "code": query,
            "ran": ran and {k: ran[k] for k in ("columns", "n_rows", "error")}, "on_db": on_db, "issues": issues,
            "seconds": time.time() - start}


def solve(text, level=None, timeout=300, db=None):
    """Write one query. Returns it plus a record of every model call.

    db: a SQLite file to check the query on (read-only); defaults to PLM_SQL_DB. Its schema is put
    in front of the task when the task has no CREATE TABLE statements of its own.
    """
    start = time.time()
    db = db or os.environ.get("PLM_SQL_DB") or None
    db = open_db(db) if db else None
    asked = text
    if db and not split_task(text)["setup"]:
        text = f"{db[1]}\n\n{text.strip()}"
    task = split_task(text)
    if level:
        reason = "set by caller"
    else:
        level, reason = classify(text)
    plan = LEVELS[level]
    steps = []
    for model_key in plan["chain"]:
        steps.append(attempt(task, text, MODELS[model_key], plan["num_predict"], timeout, db))
        if not steps[-1]["issues"]:
            break
    final = steps[-1]
    if db and final["issues"]:
        # FLAGS_RULE's policy: a second opinion, used only if it raises no flag
        steps.append(attempt(task, text, MODELS[SECOND_OPINION], plan["num_predict"], timeout, db))
        if not steps[-1]["issues"]:
            final = steps[-1]
    if db:
        unchecked = None
    elif not task["setup"]:
        unchecked = "no CREATE TABLE statements given, so the query couldn't be run"
    elif final["code"] is not None and final["ran"] is None:
        unchecked = "the schema given doesn't load in SQLite, so the query couldn't be run"
    else:
        unchecked = None
    return {
        "pack": "sql",
        "task": asked,
        "level": level,
        "reason": reason,
        "answer": {"code": final["code"], "language": "sql"} if final["code"] else None,
        "checked": unchecked is None,
        "unchecked_reason": unchecked,
        "trusted": unchecked is None and not final["issues"],
        "final_step": steps.index(final) + 1,
        "database": db and db[0],
        "chosen_note": "the second opinion was flagged too, so the coder's query is kept" if db else None,
        "steps": steps,
        "tokens": sum(s["tokens"] for s in steps),
        "seconds": time.time() - start,
    }
