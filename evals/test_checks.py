"""Tests for plm.numeric.checks against the eval set.

    .venv/bin/python evals/test_checks.py

1. requested_unit() reads the right kind of unit out of every question
   (compared with the answer key's unit, which check() itself never sees).
2. The answer key, printed as a model would print it, raises no issues.
3. Known-bad outputs are caught.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import grade  # noqa: E402
import plm.packs  # noqa: E402,F401  (loads every pack, and with it its unit words)
from plm.numeric.answers import LITERAL_UNITS, ureg  # noqa: E402
from plm.numeric.checks import add_unit_words, agree, check, requested_unit  # noqa: E402


def same_kind(a, b):
    if a in LITERAL_UNITS or b in LITERAL_UNITS:
        return a == b
    return ureg.Quantity(1, a).dimensionality == ureg.Quantity(1, b).dimensionality


def main():
    problems = (grade.load_jsonl(ROOT / "evals/electrical/problems.jsonl")
                + grade.load_jsonl(ROOT / "evals/aerospace/problems.jsonl"))
    holdout = grade.load_jsonl(ROOT / "evals/electrical/holdout_levels.jsonl")
    fails = []

    for p in problems:
        got = requested_unit(p["question"])
        if got is None or not same_kind(got, p["unit"]):
            fails.append(f"{p['id']}: requested_unit -> {got!r}, key unit {p['unit']!r}")
        unit = "cells" if p["unit"] == "count" else p["unit"]
        issues = check(p["question"], f"ANSWER: {p['answer']:.6g} {unit}")
        if issues:
            fails.append(f"{p['id']}: false alarm on the answer key: {issues}")
    for h in holdout:
        if requested_unit(h["question"]) is None:
            fails.append(f"{h['id']}: requested_unit found nothing")

    by_id = {p["id"]: p for p in problems}
    bad = [
        ("ee-c02", "", "no ANSWER line"),
        ("ee-c02", "ANSWER: 3 V", "asked for A"),
        ("ee-c07", "ANSWER: 314 kH", "asked for ohm"),
        ("ee-c06", "ANSWER: -265 ohm", "must be positive"),
        ("ee-a13", "ANSWER: 80", "power factor"),
        ("ee-i11", "ANSWER: 7.6 cells", "whole number"),
        ("ee-i15", "ANSWER: 152.53 kWh", "asked for USD"),
        ("ee-c01", "ANSWER: 120 <unit>", "'<unit>'"),  # pint half-parses it; either message is a catch
        ("ae-c02", "ANSWER: 11772 kg", "asked for N"),
        ("ae-c10", "ANSWER: 700 kW", "asked for kN"),
        ("ae-i07", "ANSWER: 20239 km/s", "asked for km"),
        ("ae-a07", "ANSWER: -17.5 K", "must be positive"),
        ("ae-i14", "ANSWER: -1225 kg", "must be positive"),
    ]
    # Model-style aerospace answers that are fine.
    good = [("ae-a04", "ANSWER: 7.67 km/s"), ("ae-a04", "ANSWER: 7673 m/s"), ("ae-c05", "ANSWER: 1.225 kg/m³"),
            ("ae-a17", "ANSWER: 8.64 m/s²"), ("ae-c13", "ANSWER: 28.1 GJ"), ("ae-c01", "ANSWER: 0.75"),
            ("ae-a12", "ANSWER: 92.4 minutes"), ("ae-i06", "ANSWER: 19.9 MW")]
    for pid, output in good:
        if check(by_id[pid]["question"], output):
            fails.append(f"{pid}: {output!r} wrongly flagged: {check(by_id[pid]['question'], output)}")
    for pid, output, expect in bad:
        issues = check(by_id[pid]["question"], output)
        if not any(expect in i for i in issues):
            fails.append(f"{pid}: {output!r} should raise {expect!r}, got {issues}")
    # Signed answers are allowed when the question asks for a sign.
    if check(by_id["ee-a10"]["question"], "ANSWER: -2 V"):
        fails.append("ee-a10: negative voltage flagged although the question asks for the sign")

    agreements = [
        ("ee-c05", "ANSWER: 500 ohm", "ANSWER: 0.5 kΩ", True),
        ("ee-i04", "ANSWER: 416.1 uF", "ANSWER: 420 μF", True),   # within 2%
        ("ee-i04", "ANSWER: 416.1 uF", "ANSWER: 409 μF", True),
        ("ee-i04", "ANSWER: 416.1 uF", "ANSWER: 440 μF", False),
        ("ee-a10", "ANSWER: -2 V", "ANSWER: 2 V", False),
        ("ee-i15", "ANSWER: 152.53 USD", "ANSWER: $152.5", True),
        ("ee-c02", "ANSWER: 3 A", "no answer", False),
    ]
    for pid, a, b, expect in agreements:
        if agree(by_id[pid]["question"], a, b) != expect:
            fails.append(f"{pid}: agree({a!r}, {b!r}) should be {expect}")

    # The core alone knows only its own unit words; each pack's arrive when packs load.
    core_only = [("What is the energy, in joules?", "J"), ("What is the voltage, in volts?", None),
                 ("What is the thrust, in kilonewtons?", None)]
    script = (f"import sys; sys.path.insert(0, {str(ROOT)!r}); from plm.numeric.checks import requested_unit; "
              f"print([requested_unit(q) for q, _ in {core_only!r}])")
    out = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True).stdout.strip()
    if out != repr([want for _, want in core_only]):
        fails.append(f"core-only requested_unit -> {out!r}")
    try:
        add_unit_words({"volts": "kV"})
        fails.append("add_unit_words accepted a word that already means another unit")
    except ValueError:
        pass

    for f in fails:
        print("FAIL", f)
    total = 2 * len(problems) + len(holdout) + len(bad) + len(good) + 1 + len(agreements) + 2
    print(f"checks tests: {total - len(fails)}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
