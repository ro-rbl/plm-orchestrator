"""Aerospace pack: level rules and tiers; the rest is plm.numeric."""

from plm.aerospace import controller
from plm.aerospace.claims import claims
from plm.pack import Pack

# Mechanics, flight and orbits. A physics pack will want many of these too; the
# same word may come from two packs as long as it means the same unit.
UNIT_WORDS = {
    "newtons": "N", "kilonewtons": "kN", "meganewtons": "MN", "newton-seconds": "N*s",
    "feet": "ft",
    "meters per second": "m/s", "kilometers per second": "km/s", "kilometers per hour": "km/h", "knots": "kn",
    "meters per second squared": "m/s^2",
    "tonnes": "t", "kilograms per second": "kg/s", "kilograms per cubic meter": "kg/m^3",
    "pascals": "Pa", "kilopascals": "kPa", "megapascals": "MPa",
    "kelvin": "K", "joules per kilogram": "J/kg", "kilojoules per kilogram": "kJ/kg",
}

PACK = Pack(name="aerospace", version="0.1.0", claims=claims, priority=50, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, unit_words=UNIT_WORDS,
            eval_set="evals/aerospace/problems.jsonl")
