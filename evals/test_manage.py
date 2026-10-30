"""Offline tests for `plm packs` (plm/manage.py): Ollama, pip and entry points are faked.

    .venv/bin/python evals/test_manage.py

The live check (a fresh venv: install, list, doctor, remove) is in
docs/pack-packaging.md, step 5.
"""

import contextlib
import io
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plm.manage as manage  # noqa: E402
from plm import ollama  # noqa: E402
from plm.packs import PACKS  # noqa: E402

FAILS = []


def expect(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name}: {detail}")


def run(fn, *args):
    """fn's return value (or SystemExit code/message) and what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = fn(*args)
        except SystemExit as e:
            code = e.code
    return code, out.getvalue()


def ep(name, value, dist="plm-fake"):
    return types.SimpleNamespace(name=name, value=value, dist=types.SimpleNamespace(name=dist))


def test_source():
    packages = ROOT / "packages"
    expect("source: this checkout by default", manage._source("aerospace", None) == ["-e", str(packages / "plm-aerospace")],
           manage._source("aerospace", None))
    expect("source: a directory holding plm-<name>/", manage._source("software", str(packages))
           == ["-e", str(packages / "plm-software")])
    expect("source: the pack's own directory", manage._source("software", str(packages / "plm-software"))
           == ["-e", str(packages / "plm-software")])
    req = "plm-chemistry @ git+https://example.invalid/repo#subdirectory=packages/plm-chemistry"
    expect("source: a pip requirement passes through", manage._source("chemistry", req) == [req])
    code, _ = run(manage._source, "chemistry", None)
    expect("source: unknown pack with no source is an error", isinstance(code, str) and "--source" in code, code)
    code, _ = run(manage._source, "chemistry", str(ROOT / "evals"))
    expect("source: a directory without the pack is an error", isinstance(code, str) and "pyproject" in code, code)


def test_list_and_doctor():
    real = manage.discover, ollama.pulled, ollama.load
    loaded = []
    try:
        broken = ep("broken", "plm_broken.manifest:PACK", "plm-broken")
        manage.discover = lambda: iter([(ep("aerospace", "x", "plm-aerospace"), PACKS["aerospace"]),
                                        (broken, ImportError("No module named 'plm_broken'"))])
        ollama.pulled = lambda timeout=10: {"qwen3:8b"}
        ollama.load = lambda model, timeout=600: loaded.append(model)

        rows = manage.installed()
        expect("list: general is built in, broken pack reported", [r["name"] for r in rows]
               == ["general", "aerospace", "broken"] and rows[2]["error"] and rows[2]["dist"] == "plm-broken", rows)
        code, out = run(manage.cmd_list, types.SimpleNamespace(json=False))
        expect("list: prints load failure and model state", code == 0 and "FAILED TO LOAD" in out and "pulled" in out, out)

        code, out = run(manage.cmd_doctor, None)
        expect("doctor: a broken pack fails", code == 1 and "FAIL  broken" in out and "ok    aerospace" in out, out)
        expect("doctor: loads each model once", loaded.count("qwen3:8b") == 2, loaded)  # general + aerospace

        manage.discover = lambda: iter([(ep("aerospace", "x"), PACKS["aerospace"])])
        ollama.pulled = lambda timeout=10: set()
        code, out = run(manage.cmd_doctor, None)
        expect("doctor: a missing model fails", code == 1 and "not pulled" in out, out)

        def unreachable(timeout=10):
            raise OSError("connection refused")
        ollama.pulled = unreachable
        code, out = run(manage.cmd_list, types.SimpleNamespace(json=False))
        expect("list: Ollama down -> unknown, not missing", code == 0 and "unknown (Ollama unreachable)" in out
               and "MISSING" not in out, out)
    finally:
        manage.discover, ollama.pulled, ollama.load = real


def test_guards():
    code, _ = run(manage.cmd_remove, types.SimpleNamespace(name="general"))
    expect("remove: general can't be removed", isinstance(code, str) and "built into the core" in code, code)
    code, _ = run(manage.cmd_install, types.SimpleNamespace(name="general", source=None))
    expect("install: general is built in", isinstance(code, str) and "built into the core" in code, code)
    real = manage.discover
    try:
        manage.discover = lambda: iter([])
        code, _ = run(manage.cmd_remove, types.SimpleNamespace(name="aerospace"))
        expect("remove: a pack that isn't installed is an error", isinstance(code, str) and "no pack named" in code, code)
    finally:
        manage.discover = real
    expect("model names: untagged means :latest", ollama.full_name("ndd") == "ndd:latest"
           and ollama.full_name("hf.co/a/b-GGUF:Q4_K_M") == "hf.co/a/b-GGUF:Q4_K_M"
           and ollama.full_name("qwen3:8b") == "qwen3:8b")


def test_broken_pack_message():
    """With a broken pack installed, `plm <task>` and `plm serve` print one line naming `plm packs remove`."""
    import subprocess
    fake = ("import types, plm.pack as p\n"
            "p.discover = lambda: [(types.SimpleNamespace(name='broken', value='plm_broken.manifest:PACK'), "
            "ImportError('boom'))]\n"
            "import sys; sys.argv = ['plm'] + sys.argv[1:]\n"
            "from plm.__main__ import main; main()\n")
    for argv in (["What is 2 + 2?"], ["serve", "--port", "0"]):
        r = subprocess.run([sys.executable, "-c", fake, *argv], capture_output=True, text=True, timeout=60, cwd=ROOT)
        expect(f"broken pack: plm {argv[0]} prints one line", r.returncode == 1 and "Traceback" not in r.stderr
               and r.stderr.strip().count("\n") == 0 and "plm packs remove broken" in r.stderr, r.stderr)


def test_sql_db_errors():
    """A bad --sql-db or PLM_SQL_DB is a one-line error before any model is called."""
    import os
    import subprocess
    env = {k: v for k, v in os.environ.items() if k != "PLM_SQL_DB"}
    r = subprocess.run([sys.executable, "-m", "plm", "--sql-db", "/nonexistent/x.sqlite", "How many?"],
                       capture_output=True, text=True, timeout=60, cwd=ROOT, env=env)
    expect("--sql-db: a missing file is one line", r.returncode == 1 and "Traceback" not in r.stderr
           and "no database file" in r.stderr, r.stderr)
    r = subprocess.run([sys.executable, "-m", "plm", "serve", "--port", "0"], capture_output=True, text=True,
                       timeout=60, cwd=ROOT, env=env | {"PLM_SQL_DB": "/nonexistent/x.sqlite"})
    expect("serve: a missing PLM_SQL_DB stops startup", r.returncode == 1 and "isn't a file" in r.stderr, r.stderr)


def main():
    test_source()
    test_sql_db_errors()
    test_broken_pack_message()
    test_list_and_doctor()
    test_guards()
    for f in FAILS:
        print("FAIL", f)
    print("manage tests: all passed" if not FAILS else f"manage tests: {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
