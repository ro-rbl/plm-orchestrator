"""Checking against the unit a question expects, not only the unit words it names (attempt 2, not yet in use).

plm.numeric.checks.check reads only unit words ("in volts"); a question asking "in m/s" or naming no unit
("What is its speed?") goes unchecked. expected_unit adds units asked as symbols and, with none named, a unit
of the kind of quantity asked for. check_expected checks an answer against it.

Attempt 1 (2026-11-08, docs/attempts/units_check_2026-11-08.diff) flagged 28 right answers for 72 caught, over
UNITS_RULE's limit: the old "must be positive" rule reached charges and energies that can be negative, and
"ratio"/"fraction of" questions were inferred as a speed or a length. Here a sign is checked only for quantities
that are never negative, and such questions get no inferred unit. Judged by evals/score_units.py --round 2
(UNITS2_RULE) on answers no check had seen; wired into the packs only if it passes.
"""

import re

from plm.latex import plain
from plm.numeric.answers import parse_answer
from plm.numeric.checks import LITERAL_UNITS, check, requested_unit, ureg

SYMBOL_PHRASE = re.compile(
    r"\b(?:in|how many) ((?:[kMGmµunp]?(?:m|g|s|N|J|W|V|A|Pa|Hz|F|H|C|Ω|ohm|L|K|eV|Wh|rad|mol))"
    r"(?:[·*/\^]?[a-zA-Zµ°Ω]*\^?[0-9²³]?){0,3}|km/h|rpm|°C)(?=\s*[?.,;:)]|\s*$)")
ASKED = re.compile(r"(?:^|[.?!]\s+)((?:what|find|calculate|compute|determine|estimate|how)\b[^.?!]*[?.!]?)\s*$",
                   re.IGNORECASE)
NO_UNIT = re.compile(r"\b(?:ratio|fraction|percent\w*|factor|times|relative|efficiency|coefficient|number of)\b",
                     re.IGNORECASE)
QUANTITY_UNIT = [(re.compile(rf"\b(?:{w})", re.IGNORECASE), u) for w, u in [
    (r"angular (?:velocity|speed)", "rad/s"), (r"acceleration|deceleration", "m/s^2"),
    (r"speed|velocity|how fast", "m/s"), (r"kinetic energy|potential energy|energy|work done|\bwork\b|heat", "J"),
    (r"power", "W"), (r"torque|moment\b", "N*m"), (r"momentum|impulse", "kg*m/s"),
    (r"force|tension|thrust|drag|lift|weight of|normal reaction", "N"), (r"pressure|stress", "Pa"),
    (r"voltage|potential difference|emf", "V"), (r"\bcurrent\b", "A"), (r"resistance|impedance|reactance", "ohm"),
    (r"capacitance", "F"), (r"inductance", "H"), (r"\bcharge\b", "C"), (r"frequency", "Hz"),
    (r"density", "kg/m^3"), (r"\bmass\b|how heavy", "kg"), (r"\bvolume\b", "m^3"), (r"\barea\b", "m^2"),
    (r"period|\btime\b|how long does|how long will|how long until|duration", "s"),
    (r"wavelength|distance|height|how high|how far|length|how long is|depth|radius|diameter|thickness|range|"
     r"displacement|altitude|deflection|extension|stretch", "m"),
]]
NEVER_NEGATIVE = ("ohm", "ohm*m", "F", "H", "s", "Hz", "kg", "m^2", "m^3", "kg/m^3", "K", "mol")


def symbol_unit(question):
    """A unit asked as a symbol ("in m/s", "in kN", "in km/h"), as a pint string, or None."""
    for m in reversed(list(SYMBOL_PHRASE.finditer(question))):
        token = m.group(1).replace("²", "^2").replace("³", "^3").replace("·", "*").replace("Ω", "ohm")
        try:
            q = ureg.Quantity(1, token)
        except Exception:
            continue
        if q.dimensionless and token not in ("rad", "rpm"):
            continue
        return token
    return None


def inferred_unit(question):
    """A unit of the kind of quantity the question's last sentence asks for, or None."""
    m = ASKED.search(question.strip())
    if not m or NO_UNIT.search(m.group(1)):
        return None
    hits = [(h.start(), u) for rx, u in QUANTITY_UNIT if (h := rx.search(m.group(1)))]
    return min(hits)[1] if hits else None


def expected_unit(question):
    """(unit, how): how is "named" (unit words: checks.requested_unit), "symbol", "inferred", or None."""
    question = plain(question)
    named = requested_unit(question)
    if named is not None:
        return named, "named"
    symbol = symbol_unit(question)
    if symbol is not None:
        return symbol, "symbol"
    guess = inferred_unit(question)
    return (guess, "inferred") if guess else (None, None)


def check_expected(question, output):
    """checks.check when the question names a unit in words (unchanged); else the expected unit's kind, and the
    sign only for quantities that are never negative."""
    unit, how = expected_unit(question)
    if how in (None, "named"):
        return check(question, output)
    parsed = parse_answer(output)
    if parsed is None:
        return ["no ANSWER line"]
    value, got = parsed
    if unit in LITERAL_UNITS:
        return []
    try:
        same = ureg.Quantity(value, got).dimensionality == ureg.Quantity(1, unit).dimensionality
    except Exception:
        return [f"unreadable unit {got!r}"]
    if not same:
        return [f"expected a {ureg.Quantity(1, unit).dimensionality} ({unit}), got {got!r}"]
    base = next((b for b in NEVER_NEGATIVE if ureg.Quantity(1, b).dimensionality == ureg.Quantity(1, unit).dimensionality), None)
    if base and value < 0:
        return [f"{unit} can't be negative, got {value}"]
    return []
