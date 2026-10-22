"""The electrical pack's manifest: what the router needs to know about it."""

from plm.pack import Pack

from plm_electrical import controller
from plm_electrical.claims import claims

UNIT_WORDS = {
    "volts": "V", "millivolts": "mV", "kilovolts": "kV",
    "amperes": "A", "amps": "A", "milliamperes": "mA",
    "milliwatts": "mW", "var": "V*A", "volt-amperes": "V*A",
    "ohms": "ohm", "kilohms": "kohm", "ohm-meters": "ohm*m",
    "hertz": "Hz", "kilohertz": "kHz",
    "watt-hours": "Wh", "kilowatt-hours": "kWh", "coulombs": "C",
    "farads": "F", "microfarads": "uF", "nanofarads": "nF", "farads per meter": "F/m",
    "henries": "H", "millihenries": "mH",
    "siemens": "S", "millisiemens": "mS",
    "decibels": "dB",
}

PACK = Pack(name="electrical", version="0.1.0", claims=claims, priority=60, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, unit_words=UNIT_WORDS,
            eval_set="evals/electrical/problems.jsonl")
