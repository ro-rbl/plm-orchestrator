"""Routing with a database set (PLM_SQL_DB) and no schema in the message, judged by SQLDB_RULE.

    .venv/bin/python evals/test_sqldb_routing.py [-v]

The server reads PLM_SQL_DB; before 2026-11-04 its routing read only the message, so a question like
"How many singers do we have?" (no CREATE TABLE, no "query") went to the general pack and the database
was never used. Cases (evals/router/, written before the SQL pack's database-aware claim existed):

    sqldb_spider.jsonl   120 Spider dev questions with their databases (written by people), labeled sql
    sqldb_cases.jsonl    20 casual data questions (dq*, sql) and 34 texts that share words with the
                         database's tables but aren't data questions (dn*: poems, advice, numeric problems,
                         code), each to be routed exactly as without a database
    every existing routing text (evals/test_detect.py), with each of the 20 databases set

Each database is built empty from evals/router/sqldb_schemas.json (routing reads names, not rows).

SQLDB_RULE, fixed on 2026-11-04 before the claim was written: it ships iff all of
    (a) at least 85% of the Spider questions (102/120) go to sql
    (b) at least 15 of the 20 casual questions go to sql
    (c) at least 30 of the 34 dn texts go where they go without a database
    (d) at least 99% of (existing routing text, database) pairs go where the text goes without a database
    (e) with no database set nothing changes (evals/dump_decisions.py diff before/after is empty; checked by hand)
Exits 1 if (a)-(d) fail, so after it ships this is a regression test.
"""

import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from plm.packs import detect  # noqa: E402
from test_detect import holdout_texts, known_texts, latex_texts  # noqa: E402

ROUTER = ROOT / "evals/router"


def rows(name):
    return [json.loads(line) for line in open(ROUTER / name) if line.strip()]


def build_dbs(folder):
    """db_id -> path of an empty SQLite file with that database's tables and columns."""
    out = {}
    for db, tables in json.load(open(ROUTER / "sqldb_schemas.json")).items():
        path = Path(folder) / f"{db}.sqlite"
        con = sqlite3.connect(path)
        for table, cols in tables.items():
            if table.startswith("sqlite_"):
                continue
            con.execute(f'CREATE TABLE "{table}" ({", ".join(chr(34) + c + chr(34) for c in cols)})')
        con.commit()
        con.close()
        out[db] = str(path)
    return out


def routed(text, db):
    """The pack `text` goes to with PLM_SQL_DB set to `db` (None: unset)."""
    old = os.environ.pop("PLM_SQL_DB", None)
    try:
        if db:
            os.environ["PLM_SQL_DB"] = db
        return detect(text)
    finally:
        os.environ.pop("PLM_SQL_DB", None)
        if old is not None:
            os.environ["PLM_SQL_DB"] = old


def main():
    verbose = "-v" in sys.argv
    with tempfile.TemporaryDirectory() as folder:
        dbs = build_dbs(folder)

        def to_sql(cases, label, need):
            miss = [c for c in cases if routed(c["text"], dbs[c["db"]]) != "sql"]
            ok = len(cases) - len(miss)
            print(f"{label}: {ok}/{len(cases)} to sql (need {need})")
            for c in miss if verbose else []:
                print(f"   miss {c['id']} [{c['db']}] -> {routed(c['text'], dbs[c['db']])}: {c['text'][:90]}")
            return ok >= need

        spider = rows("sqldb_spider.jsonl")
        cases = rows("sqldb_cases.jsonl")
        a = to_sql(spider, "(a) Spider dev questions", 102)
        b = to_sql([c for c in cases if c["id"].startswith("dq")], "(b) casual data questions", 15)

        dn = [c for c in cases if c["id"].startswith("dn")]
        moved = [(c, routed(c["text"], None), routed(c["text"], dbs[c["db"]])) for c in dn]
        moved = [m for m in moved if m[1] != m[2]]
        c_ok = len(dn) - len(moved) >= 30
        print(f"(c) not data questions: {len(dn) - len(moved)}/{len(dn)} routed as without a database (need 30)")
        for c, was, now in moved if verbose else []:
            print(f"   moved {c['id']} [{c['db']}] {was} -> {now}: {c['text'][:90]}")

        texts = [t for _, t, _ in known_texts() + holdout_texts() + latex_texts()]
        base = {t: routed(t, None) for t in texts}
        changed = [(db, t, base[t], routed(t, path)) for db, path in dbs.items() for t in texts]
        changed = [x for x in changed if x[2] != x[3]]
        pairs = len(texts) * len(dbs)
        d = len(changed) <= 0.01 * pairs
        print(f"(d) existing routing texts x {len(dbs)} databases: {len(changed)} of {pairs} pairs moved "
              f"(at most {int(0.01 * pairs)})")
        for db, t, was, now in changed[:40] if verbose else []:
            print(f"   moved [{db}] {was} -> {now}: {t[:90]}")

    passed = a and b and c_ok and d
    print("SQLDB_RULE (a)-(d):", "PASS" if passed else "FAIL", "| (e): diff evals/dump_decisions.py by hand")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
