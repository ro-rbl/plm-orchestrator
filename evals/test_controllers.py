"""Offline tests for the pack controllers: Ollama is replaced by scripted replies.

    .venv/bin/python evals/test_controllers.py

Covers escalation, the trusted/checked fields, and the --thorough fallback,
without loading any model.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plm.numeric.controller as numeric  # noqa: E402
import plm.software.controller as software  # noqa: E402
import plm.software.testgen as testgen  # noqa: E402
from plm.electrical import controller as electrical  # noqa: E402
from plm.packs import PACKS, detect  # noqa: E402

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


def test_software():
    small, large, coder = (software.MODELS[k] for k in ("small", "large", "coder"))
    task = ("Write a function `double(x: int) -> int` that returns twice x.\n"
            "assert double(2) == 4\nassert double(0) == 0")
    good = "```python\ndef double(x):\n    return 2 * x\n```"
    bad = "```python\ndef double(x):\n    return x + 2\n```"

    software.ask, calls = fake_ollama({small: [bad], large: [good]})
    r = software.solve(task)
    expect("software escalates on failed example", calls == [small, large] and r["trusted"] and r["checked"], r)

    software.ask, calls = fake_ollama({small: [good]})
    r = software.solve("Write a function `double(x: int) -> int` that returns twice x.")
    expect("software unchecked without examples", not r["checked"] and not r["trusted"] and calls == [small]
           and "only loading" in r["unchecked_reason"], r)

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


def test_registry():
    for name, pack in PACKS.items():
        expect(f"{name} provides the pack interface", all(hasattr(pack, a) for a in ("MODELS", "LEVELS", "solve")
                                                          ) and set(pack.LEVELS) == {"calm", "alert", "intensive"})
    expect("detect electrical", detect("What is the voltage across it, in volts?") == "electrical")
    expect("detect software", detect("Write a function `f(x)` that ...") == "software")


def main():
    real = numeric.ask, software.ask, testgen.ask
    try:
        test_electrical()
        test_software()
        test_registry()
    finally:
        numeric.ask, software.ask, testgen.ask = real
    for f in FAILS:
        print("FAIL", f)
    print(f"controller tests: {'all passed' if not FAILS else f'{len(FAILS)} failed'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
