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

from plm.aerospace import controller as aerospace
from plm.electrical import controller as electrical
from plm.general import controller as general
from plm.numeric.checks import requested_unit
from plm.software import controller as software

PACKS = {"electrical": electrical, "aerospace": aerospace, "software": software, "general": general}

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
# Aerospace: flight and space vocabulary, plus a real quantity (a number with a
# unit) or a requested unit. Requiring a unit, not just a digit, keeps
# "What year did the Apollo 11 mission land?" in the general pack.
AEROSPACE_TERM = re.compile(
    r"\b(?:aircraft|airplanes?|aeroplanes?|planes?|airliners?|jets?|gliders?|drones?|helicopters?|rotors?"
    r"|propellers?|wings?|airfoils?|lift|drag|thrust|mach|stall|airspeed|knots?|altitude|atmosphere|rockets?"
    r"|propellant|specific impulse|delta-v|nozzles?|orbits?|orbital|satellites?|spacecraft|perigee|apogee"
    r"|hohmann|inclination|escape velocity|launch(?:ed)?|payload|stagnation|compressor|turbine|pitot"
    r"|reynolds|bank angle|rate of climb|lift-to-drag|wing loading|aspect ratio|load factor|breguet|drag polar"
    # gas dynamics and flight physics, which often name no vehicle (added from the eval set's misses)
    r"|isentropic\w*|speed of sound|dynamic pressure|mass flow|ratio of specific heats|gravitational acceleration)\b",
    re.IGNORECASE)
QUANTITY = re.compile(r"\d\s*(?:m/s|km/s|km/h|kg/s|kg/m³|kg|km|kN|MN|N|kPa|Pa|K|ft|knots?|s|t|tonnes?"
                      r"|degrees?|°|%)(?![\w/])")


def _evidence(term_re, text, symbols=None):
    """How many distinct domain terms (and unit symbols) the text uses."""
    n = len({m.lower() for m in term_re.findall(text)})
    return n + (len(symbols.findall(text)) if symbols else 0)


def detect(text):
    """Pick a pack from the task text: software, electrical, aerospace, or general."""
    if SOFTWARE_TASK.search(text):
        return "software"
    unit_asked = requested_unit(text) is not None
    is_electrical = bool((ELECTRICAL_TERM.search(text) or UNIT_SYMBOL.search(text))
                         and (NUMBER.search(text) or unit_asked))
    is_aerospace = bool(AEROSPACE_TERM.search(text) and (QUANTITY.search(text) or unit_asked))
    if is_electrical and is_aerospace:
        # e.g. "an aircraft with 300 kW of excess power" or "a satellite's 28 V bus":
        # the domain with more distinct terms wins, ties go to electrical.
        aero, elec = _evidence(AEROSPACE_TERM, text), _evidence(ELECTRICAL_TERM, text, UNIT_SYMBOL)
        return "aerospace" if aero > elec else "electrical"
    if is_electrical:
        return "electrical"
    if is_aerospace:
        return "aerospace"
    return "general"
