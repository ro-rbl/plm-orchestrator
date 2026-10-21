"""Run model-written code against test expressions in an isolated process.

Each test is a Python expression that must evaluate to True. The code runs in a
separate `python -I -S` process in an empty temp directory, with a time limit
per test and for the whole run. Imports are limited to a standard-library
allowlist. Like plm/numeric/calc.py, the screen guards against accidents; it is not a
security sandbox.
"""

import json
import re
import subprocess
import sys
import tempfile

ALLOWED_IMPORTS = {
    "math", "collections", "heapq", "itertools", "functools", "re", "string", "bisect",
    "typing", "dataclasses", "operator", "fractions", "decimal", "copy", "statistics", "enum",
}
# Unlike calc.py, dunders are allowed in general (classes need __init__); only the escape hatches are blocked.
# The builtins are matched only as bare names, so methods like re.compile( stay allowed.
BLOCKED = re.compile(
    r"(?<![.\w])(?:open|exec|eval|compile|input|breakpoint|globals|locals|vars|__import__)\s*\("
    r"|__(?:builtins|subclasses|globals|code|loader|spec|bases|mro)__"
)

HARNESS = r"""
import json, signal, sys

payload = json.loads(sys.stdin.read())

def raises(exc, fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except exc:
        return True
    except Exception:
        return False
    return False

def on_alarm(signum, frame):
    raise TimeoutError("test took too long")

signal.signal(signal.SIGALRM, on_alarm)
ns = {"raises": raises, "__name__": "solution"}
try:
    signal.setitimer(signal.ITIMER_REAL, payload["per_test"])
    exec(compile(payload["code"], "<solution>", "exec"), ns)
    signal.setitimer(signal.ITIMER_REAL, 0)
except BaseException as e:
    print("\n" + json.dumps({"loaded": False, "error": f"{type(e).__name__}: {e}"[:300], "results": []}))
    sys.exit(0)

results = []
for t in payload["tests"]:
    try:
        signal.setitimer(signal.ITIMER_REAL, payload["per_test"])
        ok = eval(t, ns) is True
        signal.setitimer(signal.ITIMER_REAL, 0)
        results.append([ok, None if ok else "evaluated to False"])
    except BaseException as e:
        signal.setitimer(signal.ITIMER_REAL, 0)
        results.append([False, f"{type(e).__name__}: {e}"[:200]])
print("\n" + json.dumps({"loaded": True, "error": None, "results": results}))
"""


def screen(code):
    """Return a reason the code is refused, or None if it may run."""
    for line in code.splitlines():
        m = re.match(r"\s*(?:from\s+(\S+)\s+import|import\s+(.+))", line)
        if m:
            names = [m.group(1)] if m.group(1) else [n.split(" as ")[0].strip() for n in m.group(2).split(",")]
            bad = [n for n in names if n.split(".")[0] not in ALLOWED_IMPORTS]
            if bad:
                return f"import not allowed: {', '.join(bad)}"
    hit = BLOCKED.search(code)
    return f"blocked construct: {hit.group().strip()}" if hit else None


def run_tests(code, tests, per_test=5, total=60):
    """Run `code`, then each test. Returns {loaded, error, passed, total, failures}."""
    result = {"loaded": False, "error": None, "passed": 0, "total": len(tests), "failures": []}
    refused = screen(code)
    if refused:
        result["error"] = f"refused: {refused}"
        return result
    payload = json.dumps({"code": code, "tests": tests, "per_test": per_test})
    with tempfile.TemporaryDirectory() as tmp:
        try:
            p = subprocess.run([sys.executable, "-I", "-S", "-c", HARNESS], input=payload, cwd=tmp,
                               timeout=total, capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            result["error"] = f"timed out after {total}s"
            return result
    try:
        out = json.loads(p.stdout.strip().splitlines()[-1])  # the code's own prints come first
    except (IndexError, json.JSONDecodeError):
        result["error"] = f"harness crashed: {(p.stderr.strip().splitlines() or ['?'])[-1][:200]}"
        return result
    result["loaded"], result["error"] = out["loaded"], out["error"]
    result["passed"] = sum(ok for ok, _ in out["results"])
    result["failures"] = [(t, why) for t, (ok, why) in zip(tests, out["results"]) if not ok]
    return result


if __name__ == "__main__":
    good = "def add(a, b):\n    return a + b\n"
    r = run_tests(good, ["add(1, 2) == 3", "add(-1, 1) == 0"])
    assert (r["passed"], r["total"], r["error"]) == (2, 2, None), r
    r = run_tests(good, ["add(1, 2) == 4", "add(1) == 1"])
    assert r["passed"] == 0 and "TypeError" in r["failures"][1][1], r
    r = run_tests("def f():\n    while True: pass\n", ["f() is None", "1 == 1"], per_test=1)
    assert r["passed"] == 1 and "TimeoutError" in r["failures"][0][1], r  # one hang fails one test
    assert run_tests("def f(:\n", ["f()"])["error"].startswith("SyntaxError"), run_tests("def f(:\n", ["f()"])
    assert "not allowed" in run_tests("import os\n", [])["error"]
    assert "blocked" in run_tests("x = open('f')\n", [])["error"]
    assert "blocked" in run_tests("x = ().__class__.__bases__\n", [])["error"]
    assert "blocked" in run_tests("x = compile('1', 'f', 'eval')\n", [])["error"]
    r = run_tests("import re\nP = re.compile(r'\\d+')\n", ["P.fullmatch('12') is not None"])
    assert r["passed"] == 1, r  # re.compile is a method call, not the compile builtin
    r = run_tests("import collections\nclass C:\n    def __init__(self):\n        self.d = collections.deque()\n", ["C().d is not None"])
    assert r["passed"] == 1, r  # classes with __init__ and allowed imports run
    r = run_tests("print('noise')\ndef g():\n    print('more')\n    return 1\n", ["g() == 1"])
    assert r["passed"] == 1, r  # the solution's own prints don't break result parsing
    assert run_tests("raise SystemExit(3)\n", ["1 == 1"])["error"].startswith("SystemExit")
    print("sandbox self-test: ok")
