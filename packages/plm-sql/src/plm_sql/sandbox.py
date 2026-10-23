"""Run one model-written query on a throwaway SQLite database, in an isolated process.

The database is built in memory from setup SQL (the task's CREATE TABLE statements,
and any INSERTs it gives), then made read-only: `PRAGMA query_only`, plus an
authorizer that allows only reads, so ATTACH, PRAGMA and writes are refused. A
progress handler stops a query that runs too long. It runs in a separate
`python -I -S` process in an empty temp directory, like plm/numeric/calc.py; the
point is to keep a runaway or hostile query away from this process and its files.
"""

import json
import re
import subprocess
import sys
import tempfile

MAX_ROWS = 1000  # rows returned to the caller; the count is exact either way

HARNESS = r"""
import json, sqlite3, sys, time

p = json.loads(sys.stdin.read())

def out(**kw):
    print("\n" + json.dumps(kw))
    sys.exit(0)

if p.get("db_path"):  # an existing database file, opened read-only
    db = sqlite3.connect(f"file:{p['db_path']}?mode=ro", uri=True)
else:
    db = sqlite3.connect(":memory:")
    try:
        db.executescript(p["setup"])
    except sqlite3.Error as e:
        out(setup_error=f"{type(e).__name__}: {e}"[:300])
db.execute("PRAGMA query_only = ON")
READS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, getattr(sqlite3, "SQLITE_RECURSIVE", 33)}
db.set_authorizer(lambda action, *args: sqlite3.SQLITE_OK if action in READS else sqlite3.SQLITE_DENY)
start = time.time()
db.set_progress_handler(lambda: int(time.time() - start > p["seconds"]), 10000)
try:
    cur = db.execute(p["query"])
    columns = [d[0] for d in cur.description or []]
    rows = cur.fetchall()
except Exception as e:
    out(error=f"{type(e).__name__}: {e}"[:300])
out(columns=columns, rows=[list(r) for r in rows[:p["max_rows"]]], n_rows=len(rows))
"""

READ_ONLY = re.compile(r"^\s*(?:--[^\n]*\n\s*)*(?:select|with|values)\b", re.IGNORECASE)


def run_query(setup, query, seconds=5.0, db_path=None):
    """{"error": str|None, "columns": [...], "rows": [[...]], "n_rows": int}; setup errors are reported as such.

    With db_path, the query runs on that database file (opened read-only) instead of on `setup`.
    """
    result = {"error": None, "setup_error": None, "columns": [], "rows": [], "n_rows": 0}
    if not READ_ONLY.match(query or ""):
        return result | {"error": "refused: not a single read-only query (SELECT or WITH)"}
    payload = json.dumps({"setup": setup, "query": query, "seconds": seconds, "max_rows": MAX_ROWS,
                          "db_path": str(db_path) if db_path else None})
    with tempfile.TemporaryDirectory() as cwd:
        try:
            proc = subprocess.run([sys.executable, "-I", "-S", "-c", HARNESS], input=payload, capture_output=True,
                                  text=True, cwd=cwd, timeout=seconds + 10)
        except subprocess.TimeoutExpired:
            return result | {"error": "query process timed out"}
    last = proc.stdout.strip().rsplit("\n", 1)[-1] if proc.stdout.strip() else ""
    try:
        got = json.loads(last)
    except json.JSONDecodeError:
        return result | {"error": f"query process failed: {proc.stderr.strip()[-200:]}"}
    if got.get("error") == "OperationalError: interrupted":
        got["error"] = f"query ran longer than {seconds:g} s"
    return result | got
