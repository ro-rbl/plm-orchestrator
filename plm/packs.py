"""Pack registry, used by the CLI and the server to find packs the same way.

Each pack is a `plm.pack.Pack` manifest; `detect` asks every pack for its claim
on a task and picks one with `plm.pack.pick`. The vocabulary below is still
shared here; it moves into each pack's own claims() next (docs/pack-packaging.md).
"""

import math
import re

from plm.aerospace import controller as aerospace
from plm.electrical import controller as electrical
from plm.general import controller as general
from plm.numeric.checks import requested_unit
from plm.pack import Pack, pick
from plm.software import controller as software

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


def software_claims(text):
    return math.inf if SOFTWARE_TASK.search(text) else 0


def electrical_claims(text):
    """Distinct electrical terms and unit symbols, when there are numbers or a unit is asked for."""
    if ((ELECTRICAL_TERM.search(text) or UNIT_SYMBOL.search(text))
            and (NUMBER.search(text) or requested_unit(text) is not None)):
        return _evidence(ELECTRICAL_TERM, text, UNIT_SYMBOL)
    return 0


def aerospace_claims(text):
    """Distinct aerospace terms, when there is a quantity or a unit is asked for.

    When electrical claims the same text too, e.g. "an aircraft with 300 kW of excess
    power" or "a satellite's 28 V bus", the domain with more distinct terms wins and
    ties go to electrical (its priority is higher).
    """
    if AEROSPACE_TERM.search(text) and (QUANTITY.search(text) or requested_unit(text) is not None):
        return _evidence(AEROSPACE_TERM, text)
    return 0


MANIFESTS = [
    Pack(name="electrical", version="0.1.0", claims=electrical_claims, priority=60, solve=electrical.solve,
         levels=electrical.LEVELS, models=electrical.MODELS, eval_set="evals/electrical/problems.jsonl"),
    Pack(name="aerospace", version="0.1.0", claims=aerospace_claims, priority=50, solve=aerospace.solve,
         levels=aerospace.LEVELS, models=aerospace.MODELS, eval_set="evals/aerospace/problems.jsonl"),
    Pack(name="software", version="0.1.0", claims=software_claims, priority=100, solve=software.solve,
         levels=software.LEVELS, models=software.MODELS, eval_set="evals/software/tasks.jsonl"),
    # Built in and always present: claims nothing, answers whatever no other pack claims.
    Pack(name="general", version="0.1.0", claims=lambda text: 0, priority=0, solve=general.solve,
         levels=general.LEVELS, models=general.MODELS, solve_stream=general.solve_stream),
]
PACKS = {p.name: p for p in MANIFESTS}


def detect(text):
    """Pick a pack from the task text: the strongest claim, else general."""
    return pick(PACKS.values(), text)
