"""Calculator tool: the model writes a Python program, we run it, and its stdout is graded.

This is program-aided answering. It needs no native tool-calling support, so it
works with any model, including GGUFs whose templates lack tool definitions.

The program comes from a local model, so it is screened and then run isolated:
a separate `python -I -S` process, an empty temp directory, and a time limit.
The screen is a guard against accidents, not a security sandbox.
"""

import re
import subprocess
import sys
import tempfile

TOOL_PROMPT_VERSION = 1
TOOL_FORMAT = (
    "Do not do the arithmetic yourself. Write one Python program in a ```python code block "
    "that computes the answer, using only the math module. The program must print exactly one "
    "line: the final answer as a number followed by its unit, like this example:\n"
    'print(f"ANSWER: {force_kn:.4g} kN")\n'
    "Use the unit the question asks for. For unitless answers, print only the number."
)

# TOOL_FORMAT made small models skip straight to code with the wrong formula
# (0.6B: 24/50 bare -> 8/50 with the tool). This variant puts the reasoning back first.
FORMULA_PROMPT_VERSION = 1
FORMULA_FORMAT = (
    "First, in plain text, write the formula or formulas you will use, and list every given "
    "value converted to SI base units (for example 4.7 kilohm = 4700 ohm). Then write one Python "
    "program in a ```python code block that computes the answer from those values, using only "
    "the math module. Do not do the arithmetic yourself. The program must print exactly one "
    "line: the final answer as a number followed by its unit, like this example:\n"
    'print(f"ANSWER: {force_kn:.4g} kN")\n'
    "Use the unit the question asks for. For unitless answers, print only the number."
)

# Unit-aware calculator (ROADMAP 3b). The model writes every given value as Q(value, "unit") and
# assigns the result to ANSWER; the harness converts ANSWER to the unit the *question* asks for.
# A formula with the wrong dimensions then fails while computing or converting, instead of
# printing a wrong number with the right final unit, and unit conversions can't be forgotten.
# v1 (3-problem preflight, before the sweep): the 8B imported Q from a made-up "quantities"
# module every time and once looped listing units, so v2 shows a whole program with no import.
UNITS_PROMPT_VERSION = 2
UNITS_FORMAT = (
    "Do not do the arithmetic yourself. Write one Python program in a ```python code block that computes "
    "the answer with units. Q, sqrt, sin, cos, tan, log, exp and pi are already defined, so the program "
    "has no import lines. Write every given value with its unit as Q(value, \"unit\") and compute with "
    "these quantities; units convert automatically, and angles are given as Q(30, \"degree\"). Finish by "
    "assigning the result to ANSWER and do not print it: it is converted to the unit the question asks "
    "for. For a unitless answer, assign a plain number. A complete program looks like this:\n"
    "```python\n"
    "v = Q(250, \"m/s\")\n"
    "t = Q(3, \"min\")\n"
    "d = v * t\n"
    "ANSWER = d\n"
    "```"
)
UNITS_PRELUDE = """
import math as _math
import pint as _pint
_ureg = _pint.UnitRegistry()
Q = _ureg.Quantity
pi = _math.pi
def _plain(x, unit="dimensionless"):
    return x.to(unit).magnitude if isinstance(x, Q) else x
def sqrt(x): return x ** 0.5
def sin(x): return _math.sin(_plain(x, "radian"))
def cos(x): return _math.cos(_plain(x, "radian"))
def tan(x): return _math.tan(_plain(x, "radian"))
def log(x): return _math.log(_plain(x))
def exp(x): return _math.exp(_plain(x))
"""
LITERAL_WANTS = ("", "count", "USD", "dB")  # plm.numeric.answers.LITERAL_UNITS keys: plain numbers to pint

CODE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
ALLOWED_IMPORTS = {"math", "cmath"}
BLOCKED = re.compile(r"__|\b(?:open|exec|eval|compile|input|globals|locals|getattr|setattr|breakpoint)\s*\(")
# Unit programs share the process with the harness's pint setup, so its private names are off limits too.
BLOCKED_UNITS = re.compile(BLOCKED.pattern + r"|(?<![\w.])_\w|\._")


def extract_program(text):
    blocks = CODE_RE.findall(text or "")
    return blocks[-1] if blocks else None


def screen(code, blocked=BLOCKED):
    """Return a reason the program is refused, or None if it may run."""
    for line in code.splitlines():
        m = re.match(r"\s*(?:from\s+(\S+)\s+import|import\s+(.+))", line)
        if m:
            names = [m.group(1)] if m.group(1) else [n.split(" as ")[0].strip() for n in m.group(2).split(",")]
            bad = [n for n in names if n.split(".")[0] not in ALLOWED_IMPORTS]
            if bad:
                return f"import not allowed: {', '.join(bad)}"
    hit = blocked.search(code)
    return f"blocked construct: {hit.group().strip()}" if hit else None


def _execute(flags, source, timeout):
    with tempfile.TemporaryDirectory() as tmp:
        try:
            p = subprocess.run([sys.executable, *flags, "-c", source], cwd=tmp, timeout=timeout,
                               capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            return "", f"timed out after {timeout}s"
    if p.returncode != 0:
        last = (p.stderr.strip().splitlines() or ["?"])[-1]
        return p.stdout, f"exit {p.returncode}: {last[:200]}"
    return p.stdout, None


def run_program(code, timeout=10):
    """Execute a screened program. Returns (stdout, error-or-None)."""
    refused = screen(code)
    if refused:
        return "", refused
    return _execute(["-I", "-S"], code, timeout)


def _foreign_import(line):
    m = re.match(r"\s*(?:from\s+(\S+)\s+import|import\s+(.+))", line)
    if not m:
        return False
    names = [m.group(1)] if m.group(1) else [n.split(" as ")[0].strip() for n in m.group(2).split(",")]
    return any(n.split(".")[0] not in ALLOWED_IMPORTS for n in names)


def _units_epilogue(want):
    """Convert the program's ANSWER to the asked unit and print the one ANSWER line the grader reads."""
    return f"""
_want = {want!r}
if "ANSWER" not in globals():
    raise SystemExit("the program never assigned ANSWER")
_a = ANSWER
if _want in ("", "count"):
    print(f"ANSWER: {{_plain(_a):.6g}}")
elif _want in ("USD", "dB"):
    print(f"ANSWER: {{_plain(_a):.6g}} {{_want}}")
elif _want is None:
    print(f"ANSWER: {{_a.magnitude:.6g}} {{_a.units:~}}" if isinstance(_a, Q) else f"ANSWER: {{_a:.6g}}")
elif isinstance(_a, Q):
    print(f"ANSWER: {{_a.to(_want).magnitude:.6g}} {{_want}}")
else:
    raise SystemExit(f"ANSWER is a plain number, but the question asks for {{_want}}")
"""


def run_units_program(code, want, timeout=10):
    """Execute a screened unit-aware program; want is plm.numeric.checks.requested_unit(question).

    Returns (stdout, error-or-None) like run_program. Runs with -I but without -S,
    so the installed pint is importable by the harness's prelude. Import lines for
    anything but math are dropped first: models add them out of habit (a made-up
    "quantities" module), and dropping a line can only remove capability.
    """
    code = "\n".join(line for line in code.splitlines() if not _foreign_import(line))
    refused = screen(code, BLOCKED_UNITS)
    if refused:
        return "", refused
    return _execute(["-I"], UNITS_PRELUDE + "\n" + code + "\n" + _units_epilogue(want), timeout)


if __name__ == "__main__":
    # Self-test: good program, refused import, crash, timeout, missing block.
    good = 'import math\nv = 170 / math.sqrt(2)\nprint(f"ANSWER: {v:.4g} V")'
    assert run_program(good) == ("ANSWER: 120.2 V\n", None), run_program(good)
    assert "not allowed" in run_program("import os\nprint(1)")[1]
    assert "not allowed" in run_program("from subprocess import run")[1]
    assert "blocked" in run_program("print(open('x').read())")[1]
    assert "blocked" in run_program("print(().__class__)")[1]
    assert run_program("print(1/0)")[1].startswith("exit 1: ZeroDivisionError")
    assert "timed out" in run_program("while True: pass", timeout=1)[1]
    assert extract_program("no code here") is None
    assert extract_program("text\n```python\nprint(1)\n```\nmore\n```py\nprint(2)\n```") == "print(2)\n"

    # Unit-aware programs.
    def units(code, want):
        return run_units_program(code, want)
    assert units('v = Q(170, "V")\nANSWER = v / sqrt(2)', "V") == ("ANSWER: 120.208 V\n", None), units('v=1', "V")
    assert units('ANSWER = Q(250, "m/s") / Q(0.6, "1/hour")', "km")[0] == "ANSWER: 1500 km\n"  # converts for you
    assert units('ANSWER = Q(255, "m/s") / Q(340, "m/s")', "")[0] == "ANSWER: 0.75\n"
    assert units('ANSWER = 1 / cos(Q(60, "degree"))', "")[0] == "ANSWER: 2\n"
    assert units('ANSWER = Q(5, "km")', None)[0] == "ANSWER: 5 km\n"
    assert units('ANSWER = Q(152.5, "dimensionless")', "USD")[0] == "ANSWER: 152.5 USD\n"
    assert "DimensionalityError" in units('ANSWER = Q(3, "m") / Q(2, "s")', "kg")[1]        # wrong final dimension
    assert "DimensionalityError" in units('x = Q(3, "m") + Q(2, "s")\nANSWER = x', "m")[1]   # wrong formula midway
    assert "DimensionalityError" in units('ANSWER = log(Q(4, "m"))', "")[1]
    assert "never assigned ANSWER" in units('x = Q(1, "m")', "m")[1]
    assert "plain number" in units('ANSWER = 42', "m/s")[1]
    assert "blocked" in units('ANSWER = _ureg', "m")[1] and "blocked" in units('ANSWER = Q._REGISTRY', "m")[1]
    assert units('import os\nANSWER = 1', "")[0] == "ANSWER: 1\n"  # foreign imports are dropped, not run
    assert units('from quantities import Q, m, s\nANSWER = Q(3, "km") / Q(2, "min")', "m/s")[0] == "ANSWER: 25 m/s\n"
    assert "NameError" in units('from quantities import km\nANSWER = 3 * km', "m")[1]  # needed a dropped name: fails
    assert "blocked" in units('import os\nANSWER = __import__("os")', "")[1]
    assert units('for _ in range(2):\n    pass\nm_dot = Q(2, "kg/s")\nANSWER = m_dot', "kg/s")[0] == "ANSWER: 2 kg/s\n"
    print("calc self-test: ok")
