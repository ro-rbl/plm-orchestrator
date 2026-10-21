"""Stronger code checks: a second model writes extra test cases from the task alone.

The test writer never sees the candidate code, so its tests are independent of
it. Its expected values can still be wrong, and a wrong test flags correct code;
evals/gen_tests.py measures how often that happens against reference solutions.
"""

import ast
import re

from plm.ollama import ask
from plm.software.codegen import CODE_RE

TESTGEN_PROMPT_VERSION = 1
N_TESTS = 8


def build_testgen_prompt(task):
    examples = "\n".join(f"    {e}" for e in task["examples"])
    shown = f"\n\nExamples (each expression must be True):\n{examples}" if task["examples"] else ""
    return (
        f"{task['prompt']}{shown}\n\n"
        f"Do not write the implementation. Instead, write {N_TESTS} more test cases for it as Python "
        "expressions that must evaluate to True, one per line, in a ```python code block. Each one must "
        f"call `{task['entry']}` and compare the result with the exact expected value, in the same style "
        "as the examples. Cover cases the examples miss, such as empty input, a single element, "
        "duplicates, negative numbers, unsorted input and boundary values, but only where they make sense "
        "for this task and its stated rules. Work out every expected value carefully from the task "
        "description: a wrong expected value is worse than a missing test."
    )


def parse_tests(text, entry, examples=()):
    """Valid, distinct test expressions that call `entry` and aren't copies of the examples."""
    blocks = CODE_RE.findall(text or "") or [text or ""]
    seen = {e.replace(" ", "") for e in examples}
    tests = []
    for line in "\n".join(blocks).splitlines():
        expr = re.sub(r"^\s*(?:assert\s+|>>>\s*)", "", line).split("  #")[0].strip()
        if not expr or expr.startswith("#") or not re.search(rf"\b{re.escape(entry)}\b", expr):
            continue
        try:
            ast.parse(expr, mode="eval")
        except SyntaxError:
            continue
        key = expr.replace(" ", "")
        if key not in seen:
            seen.add(key)
            tests.append(expr)
    return tests[:N_TESTS]


def is_broken_test(why, entry):
    """True if a test failed because the test itself is malformed, whatever the code does.

    A NameError for anything other than the entry point means the test uses a
    name it never defined (e.g. a misplaced parenthesis in a lambda), so it
    says nothing about the candidate and is ignored.
    """
    m = re.match(r"NameError: name '(\w+)' is not defined", why or "")
    return bool(m) and m.group(1) != entry


def failing_tests(result, entry):
    """Failures from run_tests() that count against the code (broken tests removed)."""
    return [(t, why) for t, why in result["failures"] if not is_broken_test(why, entry)]


def generate_tests(task, model, num_predict=1024, timeout=600):
    """Ask `model` for extra tests. Returns (tests, call record)."""
    r = ask(model, build_testgen_prompt(task), False, num_predict, timeout)
    tests = parse_tests(r["response"], task["entry"], task["examples"])
    return tests, {"model": model, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"], "seconds": r["wall_s"], "raw": r["response"],
                   "capped": r["done_reason"] == "length"}


if __name__ == "__main__":
    reply = """Here are tests:
```python
assert f([]) == []
f([1]) == [1]   # single
f([3, 1]) == [1, 3]
# a comment
f([2, 2] == [2, 2]
g(1) == 2
f([1]) == [1]
```"""
    got = parse_tests(reply, "f", examples=["f([3,1]) == [1,3]"])
    assert got == ["f([]) == []", "f([1]) == [1]"], got  # strips assert/comments; drops bad syntax, other names, dupes, examples
    assert parse_tests("no code", "f") == []
    assert is_broken_test("NameError: name 'c' is not defined", "LRUCache")
    assert not is_broken_test("NameError: name 'LRUCache' is not defined", "LRUCache")  # code didn't define it
    assert not is_broken_test("evaluated to False", "f")
    res = {"failures": [("t1", "NameError: name 'c' is not defined"), ("t2", "evaluated to False")]}
    assert failing_tests(res, "f") == [("t2", "evaluated to False")]
    print("testgen self-test: ok")
