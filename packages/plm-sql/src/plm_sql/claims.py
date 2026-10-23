"""Which tasks the SQL pack claims: a schema to query, or a request for a query against a table.

Certain (inf) on either, so SQL wins over the numeric packs, whose term counts a
schema's column names can trip. Software's certain claim on "write a ... function"
ties it, and software's higher priority keeps a Python function that happens to use
SQLite. Questions about SQL that ask for no query ("What is SQL injection?",
"INNER vs LEFT JOIN") claim nothing and go to the general pack.
"""

import math
import re

SCHEMA = re.compile(r"\bcreate\s+table\b", re.IGNORECASE)
QUERY = re.compile(r"\b(?:quer(?:y|ies)|select\s+statement)\b|\bselect\b.{1,80}?\bfrom\b", re.IGNORECASE | re.DOTALL)
TABLE = re.compile(r"\bsql(?:ite)?\b|\btables?\b|\b\w+\(\s*\w+(?:\s*,\s*\w+)+\s*\)", re.IGNORECASE)


def claims(text):
    return math.inf if SCHEMA.search(text) or (QUERY.search(text) and TABLE.search(text)) else 0
