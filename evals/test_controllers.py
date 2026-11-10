"""Offline tests for the pack controllers: Ollama is replaced by scripted replies.

    .venv/bin/python evals/test_controllers.py

Covers escalation, the trusted/checked fields, and the --thorough fallback,
without loading any model.
"""

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plm.general.controller as general  # noqa: E402
import plm.numeric.controller as numeric  # noqa: E402
import plm.numeric.decompose as decompose  # noqa: E402
import plm.pack as pack_module  # noqa: E402
import plm.packs as packs  # noqa: E402
import plm_software.controller as software  # noqa: E402
import plm_software.testgen as testgen  # noqa: E402
from plm.pack import Pack, pick  # noqa: E402
from plm.packs import PACKS, detect  # noqa: E402
from plm_aerospace import controller as aerospace  # noqa: E402
from plm_electrical import controller as electrical  # noqa: E402
from plm_physics import controller as physics  # noqa: E402
import plm_cad.controller as cad  # noqa: E402
import plm_sql.controller as sql  # noqa: E402
from plm.report import answer_body, caveat  # noqa: E402
from plm_sql.flags import named_tables, result_flags  # noqa: E402
from plm_sql.sandbox import run_query  # noqa: E402

FAILS = []


def expect(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name}: {detail}")


def fake_ollama(replies):
    """An ask() stand-in returning replies[model] in order, recording every call."""
    calls = []

    def ask(model, prompt, think, num_predict, timeout):
        calls.append(model)
        text = replies[model].pop(0)
        return {"response": text, "eval_tokens": len(text.split()), "prompt_tokens": 0, "load_s": 0,
                "wall_s": 0.0, "done_reason": "stop", "thinking_chars": 0, "mode": "fake"}
    return ask, calls


def program(value_expr, unit):
    return f'```python\nprint(f"ANSWER: {{{value_expr}:.4g}} {unit}")\n```'


def test_electrical():
    small, large = electrical.MODELS["small"], electrical.MODELS["large"]
    q = "A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?"

    numeric.ask, calls = fake_ollama({small: [program("220 * 0.1", "V")]})
    r = electrical.solve(q)
    expect("electrical ok", r["trusted"] and r["checked"] and calls == [small] and r["answer"]["value"] == 22, r)

    numeric.ask, calls = fake_ollama({small: [program("22", "kH")], large: [program("220 * 0.1", "V")]})
    r = electrical.solve(q)
    expect("electrical escalates on wrong unit", calls == [small, large] and r["trusted"] and len(r["steps"]) == 2, r)

    numeric.ask, calls = fake_ollama({small: [program("3", "")]})
    r = electrical.solve("Two resistors are in series. What is the total?")
    expect("electrical unchecked without a unit", not r["checked"] and not r["trusted"] and calls == [small]
           and "names no unit" in r["unchecked_reason"], r)

    numeric.ask, calls = fake_ollama({small: [program("-5", "ohm")], large: [program("-5", "ohm")]})
    r = electrical.solve("What is the resistance of the network, in ohms? It has 2 ohm and 3 ohm in series.")
    expect("electrical untrusted when every step fails", not r["trusted"] and r["checked"] and len(r["steps"]) == 2, r)


def test_units_strategy():
    """The unit-aware calculator through the shared numeric controller (not a pack default yet)."""
    plan = {"alert": {"num_predict": 256, "chain": [("small", "units"), ("large", "units")]}}
    models = {"small": "s", "large": "l"}
    q = "A 12 V battery drives 3 A through a heater. How much power does it use, in watts?"

    def run(replies):
        numeric.ask, calls = fake_ollama(replies)
        return numeric.solve(q, pack="test", classify=lambda t: ("alert", "test"), levels=plan, models=models), calls

    good = '```python\nANSWER = Q(12, "V") * Q(3, "A")\n```'
    r, calls = run({"s": [good]})
    expect("units: right dimensions -> trusted, converted to the asked unit", calls == ["s"] and r["trusted"]
           and r["answer"] == {"value": 36, "unit": "W"} and r["steps"][0]["strategy"] == "units", r)
    wrong = '```python\nANSWER = Q(12, "V") / Q(3, "A")\n```'   # ohms, not watts
    r, calls = run({"s": [wrong], "l": [good]})
    expect("units: wrong dimensions fail and escalate", calls == ["s", "l"] and r["trusted"]
           and "DimensionalityError" in " ".join(r["steps"][0]["issues"]), r)


def test_aerospace():
    large = aerospace.MODELS["large"]
    q = "A rocket engine expels 250 kg/s of propellant at 2800 m/s. Ignoring pressure thrust, what is its thrust, in kilonewtons?"
    numeric.ask, calls = fake_ollama({large: [program("250 * 2800 / 1000", "kN")]})
    r = aerospace.solve(q)
    expect("aerospace: one call to the large model, calculator", calls == [large] and r["steps"][0]["strategy"] == "tool"
           and r["trusted"] and r["answer"]["value"] == 700 and r["pack"] == "aerospace", r)

    numeric.ask, calls = fake_ollama({large: [program("-33.38", "km/s")]})
    r = aerospace.solve("What total delta-v does the transfer take, in kilometers per second?", level="intensive")
    expect("aerospace: a failed check is reported, not escalated", calls == [large] and not r["trusted"]
           and any("positive" in i for i in r["steps"][0]["issues"]), r)


def test_physics():
    small, large = physics.MODELS["small"], physics.MODELS["large"]
    q = "A 1200 kg car accelerates at 2.5 m/s². What net force acts on it, in newtons?"
    numeric.ask, calls = fake_ollama({small: [program("1200 * 2.5", "N")]})
    r = physics.solve(q, level="calm")
    expect("physics: calm goes to the 4B with the calculator", calls == [small] and r["steps"][0]["strategy"] == "tool"
           and r["trusted"] and r["pack"] == "physics" and r["answer"]["value"] == 3000, r)

    numeric.ask, calls = fake_ollama({small: [program("1200 * 2.5", "kg")], large: [program("1200 * 2.5", "N")]})
    r = physics.solve(q, level="calm")
    expect("physics: a failed check escalates to the 8B with the calculator", calls == [small, large]
           and r["trusted"] and any("asked for N" in i for i in r["steps"][0]["issues"]), r)


def test_cad():
    coder = cad.MODELS["coder"]
    q = "Model a cube with 25 mm sides."
    good = "```python\nimport cadquery as cq\nresult = cq.Workplane('XY').box(25, 25, 25)\n```"
    cad.ask, calls = fake_ollama({coder: [good]})
    r = cad.solve(q)
    expect("cad: a part that builds to the asked size is trusted", calls == [coder] and r["trusted"] and r["pack"] == "cad"
           and r["answer"]["measured"]["bbox"] == [25.0, 25.0, 25.0] and round(r["answer"]["measured"]["volume"]) == 15625, r)

    wrong = "```python\nimport cadquery as cq\nresult = cq.Workplane('XY').box(25, 25, 50)\n```"
    cad.ask, calls = fake_ollama({coder: [wrong]})
    r = cad.solve(q)
    expect("cad: a wrong size is reported, not escalated", calls == [coder] and not r["trusted"]
           and "matches no dimension" in r["steps"][0]["issues"][0], r)

    real_levels = cad.LEVELS
    try:
        cad.LEVELS = {lv: dict(plan, repairs=1) for lv, plan in real_levels.items()}
        cad.ask, calls = fake_ollama({coder: [wrong, good]})
        r = cad.solve(q)
        expect("cad repair: a fixed part replaces the flagged one", calls == [coder, coder] and r["trusted"]
               and r["final_step"] == 2 and r["steps"][1]["repair"], r)
        cad.ask, calls = fake_ollama({coder: [wrong, wrong]})
        r = cad.solve(q)
        expect("cad repair: a still-flagged repair keeps the first answer", calls == [coder, coder]
               and not r["trusted"] and r["final_step"] == 1, r)
        cad.ask, calls = fake_ollama({coder: [good]})
        r = cad.solve(q)
        expect("cad repair: a passing part isn't retried", calls == [coder] and r["trusted"], r)
    finally:
        cad.LEVELS = real_levels


def test_sql():
    large = sql.MODELS["coder"]  # the one model the pack ships with
    schema = ("CREATE TABLE pets (id INTEGER PRIMARY KEY, name TEXT, kind TEXT);\n"
              "INSERT INTO pets VALUES (1, 'Rex', 'dog'), (2, 'Tom', 'cat');")
    task = f"{schema}\n\nWrite a SQL query: list the names of the dogs."
    good = "```sql\nSELECT name FROM pets WHERE kind = 'dog';\n```"
    bad = "```sql\nSELECT pet_name FROM pets WHERE kind = 'dog'\n```"
    sql.ask, calls = fake_ollama({large: [good]})
    r = sql.solve(task)
    expect("sql: a query that runs on the schema is trusted", calls == [large] and r["trusted"] and r["pack"] == "sql"
           and r["answer"]["code"] == "SELECT name FROM pets WHERE kind = 'dog'" and r["steps"][0]["ran"]["n_rows"] == 1, r)
    expect("sql: the answer renders as a sql block", answer_body(r).startswith("```sql\nSELECT name"), answer_body(r))
    sql.ask, calls = fake_ollama({large: [bad]})
    r = sql.solve(task)
    expect("sql: a query that doesn't run is reported, not escalated", calls == [large] and not r["trusted"] and r["checked"]
           and "no such column" in r["steps"][0]["issues"][0], r)
    sql.ask, calls = fake_ollama({large: ["I can't see the data."]})
    r = sql.solve(task)
    expect("sql: no query in the reply -> no answer, flagged", r["answer"] is None and not r["trusted"]
           and r["steps"][0]["issues"] == ["no SQL query in the reply"], r)
    sql.ask, calls = fake_ollama({large: [good]})
    r = sql.solve("Write a SQL query that lists the dogs from a table pets(id, name, kind).")
    expect("sql: no schema -> unchecked", calls == [large] and not r["checked"] and not r["trusted"]
           and "CREATE TABLE" in r["unchecked_reason"], r)
    sql.ask, calls = fake_ollama({large: ["```sql\nDELETE FROM pets\n```"]})
    r = sql.solve(task)
    expect("sql: a write is refused", "refused" in r["steps"][0]["issues"][0] and not r["trusted"], r)
    real_levels, real_models = sql.LEVELS, sql.MODELS
    try:  # a two-model chain escalates on a failed check (the mechanism the sweep's cascades measured)
        sql.MODELS = {"coder": large, "second": "coder-model"}
        sql.LEVELS = {lv: dict(plan, chain=["coder", "second"]) for lv, plan in real_levels.items()}
        sql.ask, calls = fake_ollama({large: [bad], "coder-model": [good]})
        r = sql.solve(task)
        expect("sql: in a chain, a query that doesn't run escalates", calls == [large, "coder-model"] and r["trusted"]
               and r["final_step"] == 2, r)
    finally:
        sql.LEVELS, sql.MODELS = real_levels, real_models
    two = run_query("CREATE TABLE t (a);", "SELECT * FROM t; ATTACH 'x' AS y")
    expect("sql: a second statement is refused", "one statement" in (two["error"] or ""), two)
    ext = run_query("CREATE TABLE t (a);", "SELECT load_extension('x')")
    expect("sql: extension loading is refused", "not authorized" in (ext["error"] or ""), ext)
    slow = run_query("CREATE TABLE t (a);", "WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r) SELECT COUNT(*) FROM r",
                     seconds=0.5)
    expect("sql: a runaway query is stopped", "longer than" in (slow["error"] or ""), slow)
    tables = ["singer", "concert", "singer_in_concert"]
    db = ("CREATE TABLE singer (id, name); CREATE TABLE concert (id, year); CREATE TABLE singer_in_concert (s, c);"
          "INSERT INTO singer VALUES (1, 'A'), (2, NULL); INSERT INTO concert VALUES (1, 2014);")
    q = "How many singers are there?"
    flagged = {query: result_flags(q, query, run_query(db, query), tables) for query in
               ["SELECT COUNT(*) FROM singer", "SELECT COUNT(*) FROM concert", "SELECT name FROM singer WHERE id = 9",
                "SELECT name FROM singer WHERE id = 2", "SELECT nme FROM singer", "SELECT 1"]}
    expect("sql flags: the right query raises none", flagged["SELECT COUNT(*) FROM singer"] == [], flagged)
    expect("sql flags: none of the question's tables", flagged["SELECT COUNT(*) FROM concert"] == ["tables"], flagged)
    expect("sql flags: no rows", flagged["SELECT name FROM singer WHERE id = 9"] == ["empty"], flagged)
    expect("sql flags: only NULLs", flagged["SELECT name FROM singer WHERE id = 2"] == ["nulls"], flagged)
    expect("sql flags: doesn't run", flagged["SELECT nme FROM singer"] == ["error"], flagged)
    expect("sql flags: no FROM at all still misses the question's table", flagged["SELECT 1"] == ["tables"], flagged)
    expect("sql flags: a plural folds to its table, a multiword table needs every word",
           named_tables("Which singers performed at a concert?", tables) == ["singer", "concert"]
           and named_tables("singer in concert", tables) == tables, named_tables("singer in concert", tables))
    big = run_query("CREATE TABLE t (n);" + "".join(f"INSERT INTO t VALUES ({i});" for i in range(101)), "SELECT n FROM t")
    expect("sql flags: more than 100 rows", result_flags("list every t", "SELECT n FROM t", big, ["t"]) == ["huge"], big["n_rows"])
    test_sql_database(large)
    expect("detect: a Python function on SQLite stays software",
           detect("Write a Python function `count(db: str) -> int` that runs a SQL query on a SQLite table.") == "software")
    expect("detect: a question about SQL with no query asked goes to general", detect("What is SQL injection?") == "general")


def test_sql_database(large):
    """With the user's database: the schema comes from the file, and a flagged coder query gets a 4B second opinion."""
    import sqlite3
    import tempfile
    small = sql.MODELS["small"]
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "pets.sqlite"
        con = sqlite3.connect(path)
        con.executescript("CREATE TABLE pets (id INTEGER PRIMARY KEY, name TEXT, kind TEXT);"
                          "INSERT INTO pets VALUES (1, 'Rex', 'dog'), (2, 'Tom', 'cat');")
        con.commit()
        con.close()
        q = "List the names of the dog pets."
        good = "```sql\nSELECT name FROM pets WHERE kind = 'dog'\n```"
        empty = "```sql\nSELECT name FROM pets WHERE kind = 'Dog'\n```"
        prompts = []

        def recording(replies):
            ask, calls = fake_ollama(replies)

            def wrapped(model, prompt, *rest):
                prompts.append(prompt)
                return ask(model, prompt, *rest)
            return wrapped, calls

        sql.ask, calls = recording({large: [good]})
        r = sql.solve(q, db=str(path))
        expect("sql db: the schema is read from the file and a clean query is trusted, one call",
               calls == [large] and r["trusted"] and r["checked"] and "CREATE TABLE pets" in prompts[-1]
               and r["task"] == q and r["database"] == str(path.resolve()) and r["steps"][0]["on_db"]["n_rows"] == 1, r)
        sql.ask, calls = recording({large: [empty], small: [good]})
        r = sql.solve(q, db=str(path))
        expect("sql db: no rows -> the 4B's clean query is used", calls == [large, small] and r["trusted"]
               and r["answer"]["code"].endswith("'dog'") and r["final_step"] == 2
               and r["steps"][0]["issues"] == ["returns no rows on the database"], r)
        sql.ask, calls = recording({large: [empty], small: ["```sql\nSELECT nme FROM pets\n```"]})
        r = sql.solve(q, db=str(path))
        expect("sql db: both flagged -> the coder's query, reported with its flag", calls == [large, small]
               and not r["trusted"] and r["final_step"] == 1 and r["answer"]["code"].endswith("'Dog'")
               and caveat(r) == "unverified: returns no rows on the database", r)
        sql.ask, calls = recording({large: ["I need more detail."], small: [good]})
        r = sql.solve(q, db=str(path))
        expect("sql db: no query from the coder -> the 4B is asked", calls == [large, small] and r["trusted"], r)
        sql.ask, calls = recording({large: ["```sql\nSELECT COUNT(*) FROM pets WHERE kind = 'dog'\n```"]})
        r = sql.solve("How many pets are dogs?", db=str(path))
        expect("sql db: a count of one row is not flagged", calls == [large] and r["trusted"], r)
        try:
            sql.solve(q, db=str(Path(tmp) / "missing.sqlite"))
            expect("sql db: a missing file is an error", False)
        except ValueError as e:
            expect("sql db: a missing file is an error", "no database file" in str(e), e)
        (Path(tmp) / "junk.sqlite").write_text("not a database")
        try:
            sql.solve(q, db=str(Path(tmp) / "junk.sqlite"))
            expect("sql db: a non-database file is an error", False)
        except ValueError as e:
            expect("sql db: a non-database file is an error", "isn't a readable SQLite database" in str(e), e)
        con = sqlite3.connect(path)
        before = con.execute("SELECT COUNT(*) FROM pets").fetchone()[0]
        con.close()
        sql.ask, calls = recording({large: ["```sql\nDELETE FROM pets\n```"], small: ["```sql\nDROP TABLE pets\n```"]})
        r = sql.solve(q, db=str(path))
        con = sqlite3.connect(path)
        after = con.execute("SELECT COUNT(*) FROM pets").fetchone()[0]
        con.close()
        expect("sql db: writes are refused and the file is untouched", before == after == 2 and not r["trusted"], r)


def test_decompose():
    def program(value_expr, unit):  # these use math, which the shared helper never imports
        return f'```python\nimport math\nprint(f"ANSWER: {{{value_expr}:.6g}} {unit}")\n```'

    large = aerospace.MODELS["large"]
    q = "A rocket has an exhaust velocity of 3000 m/s and a mass ratio of 2.5. What is its delta-v, in kilometers per second?"
    plan = ("STEP: log of mass ratio | none | ln(2.5)\n"
            "STEP: delta-v | km/s | exhaust velocity * log of mass ratio / 1000")
    expect("plan parsed, none -> unitless", decompose.parse_plan(plan)
           == [("log of mass ratio", "", "ln(2.5)"), ("delta-v", "km/s", "exhaust velocity * log of mass ratio / 1000")])
    expect("plan tolerates numbering and bullets", len(decompose.parse_plan("- STEP 1: a | m | x\n2. STEP: b | s | y")) == 2)
    for out, unit, ok in [("ANSWER: 0.916", "", True), ("ANSWER: 3 km", "m", True), ("ANSWER: 3 s", "m", False),
                          ("ANSWER: 3", "m/s", False), ("ANSWER: 3 m", "furlongs-ish", True), ("nothing", "m", False),
                          ("ANSWER: 3 m", "", False)]:
        expect(f"step check {out!r} vs {unit!r}", (decompose.step_issue(out, unit) is None) == ok,
               decompose.step_issue(out, unit))

    prompts = []
    real_ask = decompose.ask
    try:
        def scripted(replies):
            def ask(model, prompt, think, num_predict, timeout):
                prompts.append(prompt)
                text = replies.pop(0)
                return {"response": text, "eval_tokens": 10, "prompt_tokens": 100, "wall_s": 0.0, "done_reason": "stop"}
            return ask

        decompose.ask = scripted([plan, program("math.log(2.5)", ""), program("3000 * 0.916291 / 1000", "km/s")])
        prompts.clear()
        r = numeric.attempt(q, large, "decompose", 1024, 60)
        expect("decompose: two steps, no fallback", r["fallback"] is None and len(r["calls"]) == 3
               and r["output"].startswith("ANSWER: 2.7488") and not r["issues"] and r["tokens"] == 30
               and r["prompt_tokens"] == 300, r)
        expect("decompose: step 2 sees step 1's value", "log of mass ratio = 0.916291" in prompts[2]
               and "Now compute step 2 only" in prompts[2], prompts[2])

        decompose.ask = scripted([plan, program("3000", "s"), program("3000 * math.log(2.5) / 1000", "km/s")])
        r = numeric.attempt(q, large, "decompose", 1024, 60)
        expect("decompose: wrong step dimension falls back to one program", r["fallback"]
               and "planned unitless" in r["fallback"] and r["calls"][-1]["kind"] == "fallback: tool"
               and r["output"].startswith("ANSWER: 2.7488") and not r["issues"], r)

        decompose.ask = scripted(["I'll just solve it.", program("3000 * math.log(2.5) / 1000", "km/s")])
        r = numeric.attempt(q, large, "decompose", 1024, 60)
        expect("decompose: no plan falls back", r["fallback"] == "no STEP lines in the plan" and len(r["calls"]) == 2, r)

        decompose.ask = scripted(["\n".join(f"STEP: s{k} | m | x" for k in range(7)), program("1", "km/s")])
        r = numeric.attempt(q, large, "decompose", 1024, 60)
        expect("decompose: too many steps falls back", "more than 6" in (r["fallback"] or ""), r)
    finally:
        decompose.ask = real_ask


def test_software():
    small, large, coder = (software.MODELS[k] for k in ("small", "large", "coder"))
    task = ("Write a function `double(x: int) -> int` that returns twice x.\n"
            "assert double(2) == 4\nassert double(0) == 0")
    good = "```python\ndef double(x):\n    return 2 * x\n```"
    bad = "```python\ndef double(x):\n    return x + 2\n```"

    software.ask, calls = fake_ollama({coder: [good]})
    r = software.solve(task)
    expect("software: the coder answers alone and is checked", calls == [coder] and r["trusted"] and r["checked"], r)
    software.ask, calls = fake_ollama({coder: [bad]})
    r = software.solve(task)
    expect("software: a failed example is reported, not escalated", calls == [coder] and not r["trusted"], r)

    software.ask, calls = fake_ollama({coder: [good]})
    r = software.solve("Write a function `double(x: int) -> int` that returns twice x.")
    expect("software unchecked without examples", not r["checked"] and not r["trusted"] and calls == [coder]
           and "only loading" in r["unchecked_reason"], r)

    real_levels = software.LEVELS
    try:  # the cascade mechanics, as the benchmarks measured them
        software.LEVELS = {lv: dict(plan, chain=["small", "large", "coder"]) for lv, plan in real_levels.items()}
        software.ask, calls = fake_ollama({small: [bad], large: [good]})
        r = software.solve(task)
        expect("software escalates on failed example", calls == [small, large] and r["trusted"] and r["checked"], r)

        # --thorough: generated tests include a wrong one that every candidate fails; the tie goes
        # to the later model, as in evals/simulate_code_routing.py.
        tests = "```python\ndouble(5) == 10\ndouble(-1) == -2\ndouble(3) == 7\n```"
        software.ask, calls = fake_ollama({small: [good], large: [good], coder: [good]})
        testgen.ask, writer_calls = fake_ollama({large: [tests]})
        r = software.solve(task, thorough=True)
        expect("thorough runs the whole cascade on a wrong generated test", calls == [small, large, coder], calls)
        expect("thorough writes tests once", writer_calls == [large], writer_calls)
        expect("thorough tie goes to the later model", r["final_step"] == 3 and not r["trusted"] and r["checked"], r)
        expect("thorough counts the writer's tokens", r["tokens"] == sum(s["tokens"] for s in r["steps"]) + r["test_writer"]["tokens"], r)

        software.ask, calls = fake_ollama({small: [bad], large: [good]})
        testgen.ask, writer_calls = fake_ollama({large: ["```python\ndouble(5) == 10\n```"]})
        r = software.solve(task, thorough=True)
        expect("thorough skips test writing until code passes the examples", calls == [small, large]
               and writer_calls == [large] and r["trusted"], (calls, writer_calls, r["trusted"]))
    finally:
        software.LEVELS = real_levels


def test_general():
    seen = []

    def chat(model, messages, num_predict, timeout, options=None):
        seen.append((model, messages, num_predict, options))
        return {"response": "Canberra.", "eval_tokens": 2, "prompt_tokens": 9, "load_s": 0, "wall_s": 0.0,
                "done_reason": "stop", "thinking_chars": 0, "mode": "fake"}

    general.chat = chat
    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"},
               {"role": "user", "content": "Capital of Australia?"}]
    r = general.solve("Capital of Australia?", messages=history, options={"temperature": 0.3}, max_tokens=50)
    expect("general passes the whole conversation", seen[-1] == (general.MODELS["large"], history, 50, {"temperature": 0.3}),
           seen[-1])
    expect("general is never trusted", r["answer"] == {"text": "Canberra."} and not r["checked"] and not r["trusted"]
           and r["unchecked_reason"] == general.UNCHECKED, r)
    general.solve("Plain question")
    expect("general defaults", seen[-1][1] == [{"role": "user", "content": "Plain question"}]
           and seen[-1][2] == general.NUM_PREDICT and seen[-1][3] is None, seen[-1])
    long = [{"role": "user", "content": "x" * 9000}]  # ~3000 tokens + 2048 reply > 4096
    general.solve("x", messages=long)
    expect("general raises num_ctx for a long conversation", seen[-1][3] == {"num_ctx": 8192}, seen[-1][3])
    general.solve("x", messages=[{"role": "user", "content": "x" * 300000}], options={"temperature": 0.3})
    expect("general caps num_ctx and keeps options", seen[-1][3] == {"temperature": 0.3, "num_ctx": 40960}, seen[-1][3])
    general.solve("x", messages=long, options={"num_ctx": 4096})
    expect("caller's num_ctx wins", seen[-1][3] == {"num_ctx": 4096}, seen[-1][3])


def test_registry():
    for name, pack in PACKS.items():
        expect(f"{name} manifest is named for its key", pack.name == name, pack.name)
        expect(f"{name} provides the pack interface", callable(pack.solve) and callable(pack.claims)
               and set(pack.levels) == {"calm", "alert", "intensive"} and pack.models, pack)
    expect("general claims nothing", PACKS["general"].claims("What's the capital of Australia?") == 0)
    expect("only general streams", [n for n, p in PACKS.items() if p.solve_stream] == ["general"])
    # ties between equal claims go to the higher priority; no claim falls back to general
    a = Pack("a", "0", claims=lambda t: 2, priority=1, solve=None, levels={}, models={})
    b = Pack("b", "0", claims=lambda t: 2, priority=2, solve=None, levels={}, models={})
    c = Pack("c", "0", claims=lambda t: 3, priority=0, solve=None, levels={}, models={})
    none = Pack("none", "0", claims=lambda t: 0, priority=9, solve=None, levels={}, models={})
    expect("pick: tie goes to priority", pick([a, b], "x") == "b")
    expect("pick: higher claim beats priority", pick([a, b, c], "x") == "c")
    expect("pick: no claim -> general", pick([none], "x") == "general" and pick([], "x") == "general")
    expect("detect electrical", detect("What is the voltage across it, in volts?") == "electrical")
    expect("detect software", detect("Write a function `f(x)` that ...") == "software")
    expect("detect general", detect("What's the capital of Australia?") == "general")
    expect("installed packs found by entry point", set(PACKS) == {"electrical", "aerospace", "physics", "software", "cad", "sql", "general"}
           and list(PACKS)[-1] == "general", list(PACKS))
    real_eps = pack_module.entry_points
    try:
        dup = types.SimpleNamespace(load=lambda: PACKS["electrical"], value="fake:PACK")
        pack_module.entry_points = lambda group: [dup, dup]
        packs._installed()
        expect("two packs with one name are an error", False)
    except RuntimeError:
        pass
    finally:
        pack_module.entry_points = real_eps


def main():
    real = numeric.ask, software.ask, testgen.ask, general.chat, cad.ask, sql.ask
    try:
        test_electrical()
        test_aerospace()
        test_units_strategy()
        test_decompose()
        test_physics()
        test_cad()
        test_sql()
        test_software()
        test_general()
        test_registry()
    finally:
        numeric.ask, software.ask, testgen.ask, general.chat, cad.ask, sql.ask = real
    for f in FAILS:
        print("FAIL", f)
    print(f"controller tests: {'all passed' if not FAILS else f'{len(FAILS)} failed'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
