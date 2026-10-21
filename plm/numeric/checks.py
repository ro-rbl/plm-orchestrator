"""Answer checks the controller can run without knowing the right answer.

They use only the question text and what the model printed. A failed check is
a reason to escalate to a bigger model; a passed check proves nothing about
the number itself.

    check(question, output) -> list of issue strings ([] = nothing caught)
"""

import re

from plm.numeric.answers import LITERAL_UNITS, parse_answer, ureg

# Unit words that appear in questions ("..., in microfarads?") -> unit string.
# An explicit list rather than free parsing: pint would read "in a circuit" as years.
UNIT_WORDS = {
    "volts": "V", "millivolts": "mV", "kilovolts": "kV",
    "amperes": "A", "amps": "A", "milliamperes": "mA",
    "watts": "W", "milliwatts": "mW", "kilowatts": "kW",
    "var": "V*A", "volt-amperes": "V*A",
    "ohms": "ohm", "kilohms": "kohm", "ohm-meters": "ohm*m",
    "hertz": "Hz", "kilohertz": "kHz",
    "joules": "J", "watt-hours": "Wh", "kilowatt-hours": "kWh",
    "coulombs": "C",
    "seconds": "s", "milliseconds": "ms", "hours": "h",
    "farads": "F", "microfarads": "uF", "nanofarads": "nF", "farads per meter": "F/m",
    "henries": "H", "millihenries": "mH",
    "siemens": "S", "millisiemens": "mS",
    "decibels": "dB", "us dollars": "USD", "dollars": "USD",
}
_WORDS = "|".join(sorted(map(re.escape, UNIT_WORDS), key=len, reverse=True))
UNIT_PHRASE = re.compile(rf"\b(?:in|how many) ({_WORDS})\b", re.IGNORECASE)
COUNT_PHRASE = re.compile(r"whole number|how many (?:turns|cells|resistors|batteries)", re.IGNORECASE)

# Quantities that can't be zero or negative as an answer.
POSITIVE = {"ohm", "ohm*m", "F", "H", "S", "s", "Hz", "J", "W", "C", "V*A"}


def requested_unit(question):
    """The unit the question asks for, as a pint string or LITERAL_UNITS key; None if unclear."""
    if re.search(r"\(unitless\)", question, re.IGNORECASE):
        return ""
    if COUNT_PHRASE.search(question):
        return "count"
    hits = UNIT_PHRASE.findall(question)
    return UNIT_WORDS[hits[-1].lower()] if hits else None


def _base(unit):
    """Unprefixed unit with the same dimension, for the POSITIVE lookup."""
    for base in POSITIVE:
        if ureg.Quantity(1, unit).dimensionality == ureg.Quantity(1, base).dimensionality:
            return base
    return None


def check(question, output):
    parsed = parse_answer(output)
    if parsed is None:
        return ["no ANSWER line"]
    value, unit = parsed
    want = requested_unit(question)
    if want is None:
        return []  # nothing to check against

    issues = []
    if want in LITERAL_UNITS:
        if unit.lower() not in LITERAL_UNITS[want]:
            issues.append(f"asked for {want or 'a unitless number'}, got {unit!r}")
        if want == "count" and (value <= 0 or value != int(value)):
            issues.append(f"count must be a positive whole number, got {value}")
        if want == "" and re.search(r"power factor", question, re.IGNORECASE) and not 0 < value <= 1:
            issues.append(f"power factor must be in (0, 1], got {value}")
        return issues

    try:
        got = ureg.Quantity(value, unit)
        same_kind = got.dimensionality == ureg.Quantity(1, want).dimensionality
    except Exception:
        return [f"unreadable unit {unit!r}"]
    if not same_kind:
        return [f"asked for {want}, got {unit!r}"]
    signed_ok = re.search(r"\bsign\b|negative", question, re.IGNORECASE)
    if value <= 0 and not signed_ok and _base(want) in POSITIVE:
        issues.append(f"{want} answer must be positive, got {value}")
    return issues


def agree(question, output_a, output_b, rel_tol=0.02):
    """True if two outputs give the same answer (within rel_tol, after unit conversion).

    Catches what check() can't: a well-formed answer with the wrong number. The
    tolerance is looser than grading so 3- vs 4-significant-figure rounding agrees.
    """
    a, b = parse_answer(output_a), parse_answer(output_b)
    if a is None or b is None:
        return False
    want = requested_unit(question)
    try:
        if want in LITERAL_UNITS or not a[1] or not b[1]:
            va, vb = a[0], b[0]
        else:
            va = ureg.Quantity(a[0], a[1]).to(want).magnitude
            vb = ureg.Quantity(b[0], b[1]).to(want).magnitude
    except Exception:
        return False
    return abs(va - vb) <= rel_tol * max(abs(va), abs(vb), 1e-300)
