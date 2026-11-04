"""Which tasks the SQL pack claims: a schema to query, or a request for a query against a table.

Certain (inf) on either, so SQL wins over the numeric packs, whose term counts a
schema's column names can trip. Software's certain claim on "write a ... function"
ties it, and software's higher priority keeps a Python function that happens to use
SQLite. Questions about SQL that ask for no query ("What is SQL injection?",
"INNER vs LEFT JOIN") claim nothing and go to the general pack.

With a database set (PLM_SQL_DB, as the server reads it), a question with no schema
in it can still be about that data: "How many singers do we have?" The pack then
claims a data question (one starting what, which, how many, list, show ...; none that
asks for prose or advice: write, explain, why, how do I ...) that names a table of the
database, two of its columns, or one column that isn't a generic word like "name" or
"year". Names match word by word, plurals either way ("Pets" ~ "pet", "movies" ~ "movie").
The claim is the number of names used minus a half, so a numeric problem whose own
pack counts as many terms ("A stadium speaker draws 8 A at 230 V") stays with that pack.
Designed on Spider train questions and databases; judged once on held-out cases by
evals/test_sqldb_routing.py (SQLDB_RULE, 2026-11-04): 115/120 Spider dev questions and
18/20 casual ones to sql; 30/34 look-alikes and 9855/9860 other routing texts unmoved.
"""

import math
import os
import re
import sqlite3
from functools import lru_cache

SCHEMA = re.compile(r"\bcreate\s+table\b", re.IGNORECASE)
QUERY = re.compile(r"\b(?:quer(?:y|ies)|select\s+statement)\b|\bselect\b.{1,80}?\bfrom\b", re.IGNORECASE | re.DOTALL)
TABLE = re.compile(r"\bsql(?:ite)?\b|\btables?\b|\b\w+\(\s*\w+(?:\s*,\s*\w+)+\s*\)", re.IGNORECASE)

WORD = re.compile(r"[A-Za-z]+")
PART = re.compile(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+")  # "AirportName" -> Airport, Name; "MPG" -> MPG
DATA = re.compile(r"^\s*(?:please\s+)?(?:what|which|who|whose|whom|when|where|how\s+(?:many|much|old|long)|list|show|find|"
                  r"give|return|count|tell\s+me|sort|order|rank|top|for\s+each|select|get|display|compute|calculate|"
                  r"number\s+of|average|total|names?\s+of)\b", re.IGNORECASE)
PROSE = re.compile(r"\b(?:write|explain|why|recommend|suggest|plan|draft|summari[sz]e|translate|describe|compose|"
                   r"how\s+(?:do|can|should|would|could)\s+(?:i|you|we)|what\s+(?:makes|should|does|do)\b|"
                   r"what\s+(?:is|are)\s+(?:a|an|the\s+(?:best|history|rules?|difference))\b)", re.IGNORECASE)


GENERIC = {"id", "name", "year", "date", "age", "type", "level", "code", "day", "time", "number", "title", "price",
           "amount", "weight", "height", "period", "rank", "result", "status", "note", "details", "description", "location",
           "city", "country", "state", "address", "first", "last", "count", "total", "average", "size", "color", "sex",
           "gender", "place", "position", "area", "value", "rating", "score", "share"}


def forms(word):
    """The word and each singular it could be: "movies" -> movies, movie, movy; "wines" -> wines, wine, win."""
    w = word.lower()
    out = {w}
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        out.add(w[:-1])
        if w.endswith("es"):
            out.add(w[:-2])
        if w.endswith("ies"):
            out.add(w[:-3] + "y")
    return out


def parts(name):
    return tuple(p.lower() for w in WORD.findall(name) for p in PART.findall(w))


@lru_cache(maxsize=8)
def schema_names(path, mtime):
    """(table names, other column names) of the database, each name as its lowercase parts (mtime only keys the cache)."""
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        tables, columns = set(), set()
        for (table,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"):
            tables.add(parts(table))
            quoted = table.replace('"', '""')
            columns.update(parts(r[1]) for r in con.execute(f'PRAGMA table_info("{quoted}")'))
        return frozenset(n for n in tables if n), frozenset(n for n in columns - tables if n)
    finally:
        con.close()


def db_claim(text, path):
    """How many of the database's names a data question uses (0 when it isn't one, or names none)."""
    if not DATA.search(text) or PROSE.search(text):
        return 0
    try:
        names = schema_names(path, os.path.getmtime(path))
    except (OSError, sqlite3.Error):  # unreadable or not SQLite: the server checked it exists, nothing more
        return 0
    words = set().union(*(forms(w) for w in WORD.findall(text)))
    hit = [[n for n in group if all(forms(p) & words for p in n)] for group in names]
    tables, columns = len(hit[0]), len(hit[1])
    distinctive = any(len(n) > 1 or n[0] not in GENERIC for n in hit[1])
    # half a point down, so a pack whose own terms count as many wins the tie (SQL's priority would)
    return tables + columns - 0.5 if tables or columns >= 2 or distinctive else 0


def claims(text):
    if SCHEMA.search(text) or (QUERY.search(text) and TABLE.search(text)):
        return math.inf
    db = os.environ.get("PLM_SQL_DB")
    return db_claim(text, os.path.expanduser(db)) if db else 0
