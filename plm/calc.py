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

CODE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
ALLOWED_IMPORTS = {"math", "cmath"}
BLOCKED = re.compile(r"__|\b(?:open|exec|eval|compile|input|globals|locals|getattr|setattr|breakpoint)\s*\(")


def extract_program(text):
    blocks = CODE_RE.findall(text or "")
    return blocks[-1] if blocks else None


def screen(code):
    """Return a reason the program is refused, or None if it may run."""
    for line in code.splitlines():
        m = re.match(r"\s*(?:from\s+(\S+)\s+import|import\s+(.+))", line)
        if m:
            names = [m.group(1)] if m.group(1) else [n.split(" as ")[0].strip() for n in m.group(2).split(",")]
            bad = [n for n in names if n.split(".")[0] not in ALLOWED_IMPORTS]
            if bad:
                return f"import not allowed: {', '.join(bad)}"
    hit = BLOCKED.search(code)
    return f"blocked construct: {hit.group().strip()}" if hit else None


def run_program(code, timeout=10):
    """Execute a screened program. Returns (stdout, error-or-None)."""
    refused = screen(code)
    if refused:
        return "", refused
    with tempfile.TemporaryDirectory() as tmp:
        try:
            p = subprocess.run([sys.executable, "-I", "-S", "-c", code], cwd=tmp, timeout=timeout,
                               capture_output=True, text=True)
        except subprocess.TimeoutExpired:
            return "", f"timed out after {timeout}s"
    if p.returncode != 0:
        last = (p.stderr.strip().splitlines() or ["?"])[-1]
        return p.stdout, f"exit {p.returncode}: {last[:200]}"
    return p.stdout, None


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
    print("calc self-test: ok")
