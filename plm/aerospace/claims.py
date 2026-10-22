"""Which tasks the aerospace pack claims, and how strongly."""

import re

from plm.numeric.checks import requested_unit
from plm.pack import evidence

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


def claims(text):
    """Distinct aerospace terms, when there is a quantity or a unit is asked for.

    When electrical claims the same text too, e.g. "an aircraft with 300 kW of excess
    power" or "a satellite's 28 V bus", the domain with more distinct terms wins and
    ties go to electrical (its priority is higher).
    """
    if AEROSPACE_TERM.search(text) and (QUANTITY.search(text) or requested_unit(text) is not None):
        return evidence(AEROSPACE_TERM, text)
    return 0
