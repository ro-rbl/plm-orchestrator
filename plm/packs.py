"""Pack registry, used by the CLI and the server to find packs the same way.

A pack is a module that provides:

    MODELS   tier name -> Ollama model name
    LEVELS   adrenaline level -> plan (calm, alert, intensive)
    solve(task, level=None, timeout=..., **options) -> dict with at least
             pack, task, level, reason, answer, checked, unchecked_reason,
             trusted, steps, tokens, seconds

`trusted` means the answer passed every check and there was something to check;
`checked` is False when the task gave the pack nothing to verify against.
"""

import re

from plm.electrical import controller as electrical
from plm.general import controller as general
from plm.numeric.checks import requested_unit
from plm.software import controller as software

PACKS = {"electrical": electrical, "software": software, "general": general}

SOFTWARE_TASK = re.compile(r"\b(?:write|implement|create|code)\b.{0,40}\b(?:function|class|method|program)\b|\bdef \w+\s*\(",
                           re.IGNORECASE | re.DOTALL)
# An electrical calculation names something electrical (a term, or a unit symbol
# after a number) and gives numbers or asks for a unit. Conceptual questions
# ("Explain Ohm's law") have neither and go to the general pack.
ELECTRICAL_TERM = re.compile(
    r"\b(?:volts?|voltage|amps?|amperes?|amperage|current|ohms?|resist(?:or|ors|ance)|capacit(?:or|ors|ance)"
    r"|inductors?|inductance|watts?|kilowatts?|kWh|transformers?|circuits?|hertz|batter(?:y|ies)|LEDs?"
    r"|op-amps?|amplifiers?|impedance|reactance|three-phase|RMS|farads?|henr(?:y|ies)|siemens|coulombs?"
    r"|power factor|electricity|diodes?)\b",
    re.IGNORECASE)
UNIT_SYMBOL = re.compile(r"\d\s*(?:k|m|M|u|µ|μ|n)?(?:V|A|W|Ω|Hz|F|H|VA|var|Ah|Wh)\b")  # case-sensitive on purpose
NUMBER = re.compile(r"\d")


def detect(text):
    """Pick a pack from the task text: software, electrical, or general."""
    if SOFTWARE_TASK.search(text):
        return "software"
    electrical_term = ELECTRICAL_TERM.search(text) or UNIT_SYMBOL.search(text)
    if electrical_term and (NUMBER.search(text) or requested_unit(text) is not None):
        return "electrical"
    return "general"
