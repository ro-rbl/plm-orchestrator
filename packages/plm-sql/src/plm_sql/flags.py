"""Signs that a query which runs is still probably wrong, read from its result on a real database.

The schema-only check (plm_sql.controller.check) catches a query that doesn't run; on empty
tables it can't see one that runs and answers something else. With the user's database (opened
read-only), the result itself says more:

    error    the query doesn't run (or there is no query)
    empty    it returns no rows
    huge     it returns more than HUGE_ROWS rows
    nulls    every value it returns is NULL
    tables   the question names a table (every word of its name, plurals folded) and the query
             uses none of the tables the question names

Fixed on 2026-10-27 from the saved Spider (300) and BIRD mini-dev (496) answers, before any model
answered the sets that judge them (evals/bench_sql_check.py, FLAGS_RULE).
"""

import re

HUGE_ROWS = 100
WORD = re.compile(r"[A-Za-z]+")


def stem(word):
    """Lowercase, with a plural ending folded: "singers" -> "singer", "countries" -> "country"."""
    w = word.lower()
    for suffix in ("ies", "es", "s"):
        if w.endswith(suffix) and len(w) > len(suffix) + 2:
            return w[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return w


def named_tables(question, tables):
    """The tables whose every name part (split on non-letters) appears in the question."""
    words = {stem(w) for w in WORD.findall(question)}
    return [t for t in tables if WORD.findall(t) and all(stem(p) in words for p in WORD.findall(t))]


def used_tables(query, tables):
    return [t for t in tables if re.search(rf"(?<![\w.]){re.escape(t)}(?![\w])", query, re.IGNORECASE)]


def result_flags(question, query, ran, tables):
    """Flags for one query: `ran` is plm_sql.sandbox.run_query's result on the real database (or None
    when there was no query), `tables` the database's table names. An empty list means nothing looks wrong."""
    if query is None or ran is None or ran["error"]:
        return ["error"]
    flags = []
    if ran["n_rows"] == 0:
        flags.append("empty")
    if ran["n_rows"] > HUGE_ROWS:
        flags.append("huge")
    if ran["n_rows"] and all(v is None for row in ran["rows"] for v in row):
        flags.append("nulls")
    named = named_tables(question, tables)
    if named and not set(named) & set(used_tables(query, tables)):
        flags.append("tables")
    return flags
