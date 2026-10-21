"""Grade model responses against a numeric eval set.

Every model is prompted to end its reply with one line:

    ANSWER: <number> <unit>

Usage:
    .venv/bin/python evals/grade.py evals/electrical/problems.jsonl responses.jsonl
    .venv/bin/python evals/grade.py evals/electrical/problems.jsonl --self-test

responses.jsonl has one {"id": ..., "response": "<full model text>"} per line.

Each item gets one verdict:
    correct     value within rel_tol after unit conversion
    wrong_value right kind of unit, wrong number
    unit_error  missing, unknown, or dimensionally wrong unit
    no_answer   no ANSWER line / no parsable number
"""

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plm.numeric.answers import (  # noqa: E402,F401
    ANSWER_FORMAT, LITERAL_UNITS, PROMPT_VERSION, normalize, normalize_unit, parse_answer, ureg,
)


def close(got, want, rel_tol):
    if rel_tol == 0:
        return abs(got - want) < 1e-9
    return abs(got - want) <= rel_tol * abs(want)


def grade_one(problem, response):
    parsed = parse_answer(response)
    if parsed is None:
        return {"verdict": "no_answer"}
    value, unit = parsed
    want_unit = problem["unit"]
    # value_ok: the bare number would be right in the requested unit. Separates
    # "can't do the math" from "can't follow the answer format".
    unit_error = {"verdict": "unit_error", "value": value, "unit": unit,
                  "value_ok": close(value, problem["answer"], problem["rel_tol"])}

    if want_unit in LITERAL_UNITS:
        if unit.lower() not in LITERAL_UNITS[want_unit]:
            return unit_error
        converted = value
    else:
        if not unit:
            return unit_error
        try:
            converted = ureg.Quantity(value, unit).to(want_unit).magnitude
        except Exception:  # pint raises many types on garbage like "<unit>"
            return unit_error

    verdict = "correct" if close(converted, problem["answer"], problem["rel_tol"]) else "wrong_value"
    return {"verdict": verdict, "value": value, "unit": unit, "converted": converted}


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def report(problems, responses):
    by_id = {r["id"]: r["response"] for r in responses}
    results = []
    for p in problems:
        r = grade_one(p, by_id.get(p["id"], ""))
        results.append({"id": p["id"], "level": p["level"], **r})

    levels = defaultdict(Counter)
    for r in results:
        for lvl in (r["level"], "ALL"):
            levels[lvl][r["verdict"]] += 1
            levels[lvl]["n"] += 1
            levels[lvl]["value_ok"] += r.get("value_ok", False)
    # "unit" = unit errors; "(num ok)" = how many of those had the right number anyway.
    print(f"{'level':<10} {'n':>3} {'correct':>8} {'wrong':>6} {'unit':>5} {'(num ok)':>9} {'none':>5}  acc")
    for lvl in ("calm", "alert", "intensive", "ALL"):
        c = levels[lvl]
        if c["n"]:
            print(f"{lvl:<10} {c['n']:>3} {c['correct']:>8} {c['wrong_value']:>6} {c['unit_error']:>5} "
                  f"{c['value_ok']:>9} {c['no_answer']:>5}  {c['correct'] / c['n']:.0%}")
    return results


def self_test(problems):
    """Grade the answer key, then deliberately broken answers, and check the verdicts."""
    def fmt(p, value=None, unit=None):
        v = p["answer"] if value is None else value
        u = p["unit"] if unit is None else unit
        if u == "count":
            u = "cells"
        return f"working...\nANSWER: {v:.6g} {u}"

    failures = []
    for p in problems:
        cases = [(fmt(p), "correct"), (fmt(p, value=p["answer"] * 2 + 1), "wrong_value"), ("no answer here", "no_answer")]
        if p["unit"] not in LITERAL_UNITS:
            cases.append((fmt(p, unit="kg"), "unit_error"))
            cases.append((fmt(p, unit=""), "unit_error"))
        for response, expected in cases:
            got = grade_one(p, response)["verdict"]
            if got != expected:
                failures.append((p["id"], expected, got, response.splitlines()[-1]))

    # Formats real models produce.
    formats = [
        ("ee-c11", "ANSWER: 1.602 × 10^-19 C", "correct"),
        ("ee-c12", "ANSWER: 1.68e-8 Ω·m", "correct"),
        ("ee-c05", "ANSWER: 0.5 kΩ", "correct"),
        ("ee-a16", "ANSWER: 6 µF", "correct"),
        ("ee-a12", "ANSWER: 13.33 hours", "correct"),
        ("ee-c01", "ANSWER: 120.2 V RMS", "correct"),
        ("ee-a10", "ANSWER: −2.0 V", "correct"),
        ("ee-i06", "ANSWER: 14,722 W", "correct"),
        ("ee-i06", "ANSWER: 14.72 kW", "correct"),
        ("ee-i15", "ANSWER: $152.53", "correct"),
        ("ee-i11", "ANSWER: 8", "correct"),
        ("ee-a13", "ANSWER: 0.8", "correct"),
        ("ee-a13", "ANSWER: 80 %", "unit_error"),
        ("ee-a20", "ANSWER: 4 s", "wrong_value"),
        ("ee-a10", "ANSWER: 2.0 V", "wrong_value"),
        # Seen in real runs:
        ("ee-c02", "ANSWER: 3  A**", "correct"),
        ("ee-c04", "ANSWER: 650**", "unit_error"),
        ("ee-c08", "ANSWER: 0.125 \\, \\text{J}", "correct"),
        ("ee-c11", "ANSWER: 1.602176634 \\times 10^{-19} C", "correct"),
        ("ee-c14", "ANSWER: 4.5 kilowatt-hours", "correct"),
        ("ee-c12", "ANSWER: 1.72e-8 ohm-meter", "correct"),
        ("ee-c03", "ANSWER: 250 Watts", "correct"),
        ("ee-c05", "ANSWER: 0.5kΩ", "correct"),
        ("ee-a16", "ANSWER: 6 microfarad", "correct"),
        ("ee-a20", "ANSWER: 4 milliseconds", "correct"),
        ("ee-i13", "ANSWER: 10 unitless", "correct"),
        ("ee-i15", "ANSWER: 152.53 $", "correct"),
        ("ee-c01", "ANSWER: 120 <unit>", "unit_error"),
        ("ee-c06", "ANSWER: <number> <unit>", "no_answer"),
        ("ee-i07", "**ANSWER:** ANSWER: 56.9 W", "correct"),
        ("ee-c11", "ANSWER: 1.602176634 × 10⁻¹⁹ C", "correct"),
        ("ee-c11", "ANSWER: 1.602 × 10¹⁹ C", "wrong_value"),
        ("ee-a06", "ANSWER: 1.12 mΩ", "wrong_value"),
    ]
    by_id = {p["id"]: p for p in problems}
    for pid, response, expected in formats:
        got = grade_one(by_id[pid], response)["verdict"]
        if got != expected:
            failures.append((pid, expected, got, response))

    total = sum(3 + 2 * (p["unit"] not in LITERAL_UNITS) for p in problems) + len(formats)
    for f in failures:
        print("FAIL", f)
    print(f"self-test: {total - len(failures)}/{total} checks passed")
    return not failures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("problems")
    ap.add_argument("responses", nargs="?")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--out", help="write per-item results as JSONL")
    args = ap.parse_args()

    problems = load_jsonl(args.problems)
    if args.self_test:
        sys.exit(0 if self_test(problems) else 1)
    if not args.responses:
        ap.error("responses file required unless --self-test")
    results = report(problems, load_jsonl(args.responses))
    if args.out:
        with open(args.out, "w") as f:
            for r in results:
                f.write(json.dumps(r) + "\n")


if __name__ == "__main__":
    main()
