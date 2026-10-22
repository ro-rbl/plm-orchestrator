"""The physics pack's manifest: what the router needs to know about it."""

from plm.pack import Pack

from plm_physics import controller
from plm_physics.claims import claims

# Mechanics, fluids, heat and materials. Words other packs also declare (newtons,
# pascals, meters per second, ...) are repeated here so this pack works without them;
# a word two packs declare must mean the same unit.
UNIT_WORDS = {
    "newtons": "N", "kilonewtons": "kN", "newton-meters": "N*m", "newtons per meter": "N/m",
    "newton-seconds": "N*s", "kilogram meters per second": "kg*m/s",
    "meters per second": "m/s", "kilometers per hour": "km/h", "meters per second squared": "m/s^2",
    "radians per second": "rad/s", "revolutions per minute": "rpm", "hertz": "Hz",
    "centimeters": "cm", "millimeters": "mm", "cubic meters": "m^3", "liters": "L",
    "liters per second": "L/s", "cubic meters per second": "m^3/s",
    "grams": "g", "kilograms per cubic meter": "kg/m^3",
    "kilojoules": "kJ", "megajoules": "MJ",
    "pascals": "Pa", "kilopascals": "kPa", "megapascals": "MPa", "gigapascals": "GPa",
    "kelvin": "K", "degrees celsius": "degC",
}

PACK = Pack(name="physics", version="0.1.0", claims=claims, priority=40, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, unit_words=UNIT_WORDS,
            eval_set="evals/physics/problems.jsonl")
