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
                + grade.load_jsonl(ROOT / "evals/aerospace/problems.jsonl")
                + grade.load_jsonl(ROOT / "evals/physics/problems.jsonl"))
    holdout = (grade.load_jsonl(ROOT / "evals/electrical/holdout_levels.jsonl")
               + grade.load_jsonl(ROOT / "evals/physics/holdout_levels.jsonl"))
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
        ("ph-c02", "ANSWER: 3000 kg", "asked for N"),
        ("ph-a13", "ANSWER: 23.56 L", "asked for L/s"),
        ("ph-i11", "ANSWER: 46.25", "asked for degC"),
        ("ph-i05", "ANSWER: -45.5 m", "must be positive"),
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

    from plm.numeric.expected import expected_unit  # negative exponents and centi (2026-11-10)
    symbols = [("What is the wavenumber, in cm^-1?", ("cm^-1", "symbol")),
               ("Find the frequency in cm^-1.", ("cm^-1", "symbol")), ("in cm⁻¹?", ("cm^-1", "symbol")),
               ("rate constant in s^-1?", ("s^-1", "symbol")), ("speed in m/s?", ("m/s", "symbol")),
               ("How long is it in cm?", ("cm", "symbol"))]
    for q, want in symbols:
        if expected_unit(q) != want:
            fails.append(f"expected_unit({q!r}) = {expected_unit(q)}, want {want}")

    from plm.numeric import si  # unit prefixes handled in code (SI_RULE, 2026-11-12)
    si_cases = [
        ("A 1.5 kW kettle runs on 240 V. What current, in amperes?", "A 1500 W kettle runs on 240 V. What current, in amperes?"),
        ("A 2000 mAh battery, drawing 150 mA.", "A 2 Ah battery, drawing 0.15 A."),
        ("cross-section of 1 mm^2, modulus 200 GPa, stretch in millimeters?", "cross-section of 1e-06 m^2, modulus 2e+11 Pa, stretch in meters?"),
        ("R = 10 kilohm and C = 1 microfarad, in milliseconds?", "R = 10000 ohm and C = 1e-06 farad, in seconds?"),
        ("7.7 km/s, 100 km/h, a 9 g turn, 300 g, 50 kg/s, 1.225 kg/m^3, 3.3 kJ/kg, 100 kilometers per hour, 5 m, 12 V",
         "7.7 km/s, 100 km/h, a 9 g turn, 300 g, 50 kg/s, 1.225 kg/m^3, 3.3 kJ/kg, 100 kilometers per hour, 5 m, 12 V"),
        ("5 MW vs 5 mW, and in kN?", "5000000 W vs 0.005 W, and in N?"),
    ]
    for before, after in si_cases:
        if si.normalize(before) != after:
            fails.append(f"si.normalize({before!r}) = {si.normalize(before)!r}")
    q = "What current flows, in milliamperes?"
    if si.restore({"value": 0.15, "unit": "A"}, q, si.normalize(q)) != {"value": 150.0, "unit": "mA"}:
        fails.append("si.restore didn't convert A back to mA")
    if si.restore({"value": 3.0, "unit": "A"}, "in amperes?", "in amperes?") != {"value": 3.0, "unit": "A"}:
        fails.append("si.restore changed an answer to an unprefixed question")

    from plm.display import tidy, unmark  # replies tidied for reading (2026-11-12)
    raw = ("Intro **bold**.\n\n---\n\n### ✅ **1. Title** 🚀\n\n- **Cap**: \\( E = \\frac{1}{2} C V^{2} \\) → fast\n"
           "```python\nx = \"**kept** ✅ ---\"\n```\nDone ✓ 👍")
    display = [
        (tidy(raw), "Intro **bold**.\n\n### 1. Title\n\n- **Cap**: E = 1/2 C V^2 → fast\n"
                    "```python\nx = \"**kept** ✅ ---\"\n```\nDone ✓"),
        (unmark(raw), "Intro bold.\n\n1. Title\n\n- Cap: E = 1/2 C V^2 → fast\n"
                      "```python\nx = \"**kept** ✅ ---\"\n```\nDone ✓"),
        (tidy("Costs $5 to $10, 2 * 3 * 4."), "Costs $5 to $10, 2 * 3 * 4."),
        (unmark("22 V"), "22 V"),
    ]
    for got, want in display:
        if got != want:
            fails.append(f"display: {got!r} != {want!r}")

    for f in fails:
        print("FAIL", f)
    total = len(display) + len(si_cases) + 2 + 2 * len(problems) + len(holdout) + len(bad) + len(good) + 1 + len(agreements) + 2 + len(symbols)
    print(f"checks tests: {total - len(fails)}/{total} passed")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
