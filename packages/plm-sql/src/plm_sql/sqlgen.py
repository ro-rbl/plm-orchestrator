"""Prompting for SQL tasks, splitting the schema out of a task, and pulling the query out of a reply."""

import re
import sqlite3

PROMPT_VERSION = 1
SQL_FORMAT = (
    "Reply with one ```sql code block containing a single SQLite query (SELECT, optionally with WITH). "
    "Return exactly the columns the question asks for, in the order it names them, and nothing else."
)

STATEMENT_START = re.compile(r"^\s*(?:create\s+(?:table|view|index|unique\s+index)|insert\s+into)\b", re.IGNORECASE)
SQL_RE = re.compile(r"```(?:sql|sqlite)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)
BARE_QUERY = re.compile(r"^\s*(?:select|with)\b.*", re.IGNORECASE | re.DOTALL)


def split_task(text):
    """{"setup": the CREATE/INSERT statements in the text, "question": the rest, "has_rows": any INSERT}."""
    setup, rest, buf = [], [], []
    for line in text.splitlines():
        if buf or STATEMENT_START.match(line):
            buf.append(line)
            if sqlite3.complete_statement("\n".join(buf)):
                setup.append("\n".join(buf))
                buf = []
        else:
            rest.append(line)
    rest += buf  # an unterminated statement is left in the question
    return {"setup": "\n".join(setup), "question": "\n".join(rest).strip(),
            "has_rows": any(s.lstrip().lower().startswith("insert") for s in setup)}


def build_prompt(text):
    return f"{text.strip()}\n\n{SQL_FORMAT}"


def extract_sql(text):
    """The last fenced block; else the reply itself if it is a bare query. Trailing semicolons dropped."""
    blocks = SQL_RE.findall(text or "")
    if blocks:
        query = blocks[-1]
    elif BARE_QUERY.match(text or ""):
        query = text
    else:
        return None
    return query.strip().rstrip(";").strip() or None
