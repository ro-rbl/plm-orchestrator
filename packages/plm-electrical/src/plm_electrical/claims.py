"""Which tasks the electrical pack claims, and how strongly."""

import re

from plm.numeric.checks import requested_unit
from plm.pack import evidence

# An electrical calculation names something electrical (a term, or a unit symbol
# after a number) and gives numbers or asks for a unit. Conceptual questions
# ("Explain Ohm's law") have neither and go to the general pack.
ELECTRICAL_TERM = re.compile(
    # "air resistance" (and wind, rolling, "600 N of resistance") is mechanics, not a resistor
    r"\b(?:volts?|voltage|amps?|amperes?|amperage|current|ohms?"
    r"|(?<!air )(?<!wind )(?<!rolling )(?<!N of )(?<!newtons of )resist(?:or|ors|ance)"
    r"|capacit(?:or|ors|ance)"
    r"|inductors?|inductance|watts?|kilowatts?|kWh|transformers?|circuits?|hertz|batter(?:y|ies)|LEDs?"
    r"|op-amps?|amplifiers?|impedance|reactance|three-phase|RMS|farads?|henr(?:y|ies)|siemens|coulombs?"
    r"|power factor|electricity|diodes?)\b",
    re.IGNORECASE)
UNIT_SYMBOL = re.compile(r"\d\s*(?:k|m|M|u|µ|μ|n)?(?:V|A|W|Ω|Hz|F|H|VA|var|Ah|Wh)\b")  # case-sensitive on purpose
NUMBER = re.compile(r"\d")


def claims(text):
    """Distinct electrical terms and unit symbols, when there are numbers or a unit is asked for."""
    if ((ELECTRICAL_TERM.search(text) or UNIT_SYMBOL.search(text))
            and (NUMBER.search(text) or requested_unit(text) is not None)):
        return evidence(ELECTRICAL_TERM, text, UNIT_SYMBOL)
    return 0
