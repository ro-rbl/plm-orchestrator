"""Build the routing cases for a server started with PLM_SQL_DB (a database, no schema in the message).

    .venv/bin/python evals/router/build_sqldb_cases.py     # needs Spider in .benchmarks/ (see evals/bench_sql.py)

Writes, next to this file:
    sqldb_schemas.json   the 20 Spider dev databases' table and column names (no rows: routing reads names only)
    sqldb_spider.jsonl   SPIDER_N Spider dev questions sampled with SEED, each with its database, labeled "sql":
                         real questions written by people, with no schema in them, as a user with a database asks

The hand-written cases are in sqldb_cases.jsonl. Spider (Yu et al., EMNLP 2018) is CC BY-SA 4.0;
these files keep its questions and schema names unchanged. All three were written on 2026-11-04,
before the SQL pack's database-aware claim existed (evals/test_sqldb_routing.py, SQLDB_RULE).
"""

import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPIDER = HERE.parent.parent / ".benchmarks/spider/spider_data"
SEED, SPIDER_N = 20261104, 120


def main():
    dev = json.load(open(SPIDER / "dev.json"))
    dbs = sorted({d["db_id"] for d in dev})
    tables = {t["db_id"]: t for t in json.load(open(SPIDER / "tables.json"))}
    schemas = {}
    for db in dbs:
        t = tables[db]
        cols = {name: [] for name in t["table_names_original"]}
        for ti, col in t["column_names_original"]:
            if ti >= 0:
                cols[t["table_names_original"][ti]].append(col)
        schemas[db] = cols
    (HERE / "sqldb_schemas.json").write_text(json.dumps(schemas, indent=1) + "\n")
    pick = sorted(random.Random(SEED).sample(range(len(dev)), SPIDER_N))
    with open(HERE / "sqldb_spider.jsonl", "w") as f:
        for i in pick:
            f.write(json.dumps({"id": f"spider-dev-{i:04d}", "db": dev[i]["db_id"], "pack": "sql",
                                "text": dev[i]["question"]}) + "\n")
    print(f"wrote {len(schemas)} schemas and {SPIDER_N} Spider questions")


if __name__ == "__main__":
    main()
