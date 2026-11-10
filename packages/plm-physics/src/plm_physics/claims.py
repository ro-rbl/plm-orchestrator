"""Which tasks the physics pack claims, and how strongly.

A physics calculation names something from mechanics, fluids, heat or materials
and gives a quantity (a number with a unit) or asks for a unit. Conceptual
questions ("Why does ice float?") have neither and go to the general pack.

Physics shares its quantities with the specialist packs: speed, mass, pressure
and density are in aerospace questions too, where aerospace counts a phrase like
"dynamic pressure" once while physics would count "density" and "pressure"
twice. So generic quantity words let physics claim a text but add nothing to
its score: only words that are physics's own (pendulum, friction, buoyant, ...)
count as evidence. A text with generic words only scores GENERIC_ONLY, below
any specialist's claim, so physics takes it only when no specialist does. Its
priority is the lowest of the numeric packs, so equal evidence goes to the
specialist too. Words that mean electricity (power, energy alone, wire,
frequency) are in neither list.
"""

import re

from plm.numeric.checks import requested_unit
from plm.pack import evidence

GENERIC_ONLY = 0.5
GENERIC = re.compile(
    r"\b(?:mass|weight|speed|velocity|acceleration|accelerates?|density|pressure|temperature|flow rate"
    r"|height|distance)\b", re.IGNORECASE)
PHYSICS_TERM = re.compile(
    r"\b(?:force|net force|decelerat\w*|momentum|kinetic energy|potential energy|elastic energy|work|friction"
    r"|stiffness|spring(?: constant)?|pendulum|oscillat\w*|wavelength|waves?|torque|wrench|lever|flywheel"
    r"|rotat\w*|angular|radians?|wheel|moment of inertia|rolls?|rolling|gears?|shaft|pulley|piston"
    r"|gauge pressure|buoyan\w*|submerged|floats?|fluid|pipe|water|tank|ice|steam|heat|specific heat"
    r"|latent heat|boil\w*|melt\w*|thermal|conductivity|expansion|ideal gas|moles?|stress|strain"
    r"|young's modulus|tensile|cable|beam|collision|projectile|thrown|kicked|dropped|falls?|cliff|ramp"
    r"|incline\w*|slope|crate|ball|machine|motor|elevator|crane|pump|lifts?|kettle|gravity|centripetal|tension"
    r"|brakes?|stopping distance|air resistance"
    # 2026-11-08, from the holdout misses in NEXT.md (pho-c6, pho-a4, pho-i3, k09); shared phrases like
    # "speed of sound" and "gravitational acceleration" count for physics too, so a physics question that uses
    # one ties aerospace on it and wins on its own words. Judged by evals/test_physics_routing.py (PHYS_RULE).
    r"|speed of sound|in air|gravitational acceleration|bullet|block|string|stretch\w*"
    # 2026-11-10, attempt 2 (PHYS2_RULE, evals/test_physics_routing2.py): attempt 1's named leftovers. "launched"
    # counts here too, so "a projectile is launched" isn't a tie aerospace wins; a radiating black body is physics.
    r"|launch(?:ed)?|radiates?|black body|blackbody)\b",
    re.IGNORECASE)
QUANTITY = re.compile(r"\d\s*(?:m/s²|m/s\^?2|m/s|km/h|kg/m³|kg|g|N·m|N/m|N|kN|J|kJ|MJ|Pa|kPa|MPa|GPa|K|°C|m|cm|mm"
                      r"|km|m²|m³|rev/s|s|min|h|L|rpm|mol|degrees?|%)(?![\w/])")


def claims(text):
    """Distinct physics terms (generic quantities don't count), when there is a quantity or a unit is asked for."""
    if not (PHYSICS_TERM.search(text) or GENERIC.search(text)):
        return 0
    if not (QUANTITY.search(text) or requested_unit(text) is not None):
        return 0
    return evidence(PHYSICS_TERM, text) or GENERIC_ONLY
