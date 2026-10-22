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
import plm_software.controller as software  # noqa: E402
import plm_software.testgen as testgen  # noqa: E402
from plm_aerospace import controller as aerospace  # noqa: E402
from plm_electrical import controller as electrical  # noqa: E402
from plm.pack import Pack, pick  # noqa: E402
import plm.packs as packs  # noqa: E402
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
    expect("installed packs found by entry point", set(PACKS) == {"electrical", "aerospace", "software", "general"}
           and list(PACKS)[-1] == "general", list(PACKS))
    real_eps = packs.entry_points
    try:
        dup = types.SimpleNamespace(load=lambda: PACKS["electrical"], value="fake:PACK")
        packs.entry_points = lambda group: [dup, dup]
        packs._installed()
        expect("two packs with one name are an error", False)
    except RuntimeError:
        pass
    finally:
        packs.entry_points = real_eps


def main():
    real = numeric.ask, software.ask, testgen.ask, general.chat
    try:
        test_electrical()
        test_aerospace()
        test_units_strategy()
        test_software()
        test_general()
        test_registry()
    finally:
        numeric.ask, software.ask, testgen.ask, general.chat = real
    for f in FAILS:
        print("FAIL", f)
    print(f"controller tests: {'all passed' if not FAILS else f'{len(FAILS)} failed'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
