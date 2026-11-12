"""Unprefixed units for the model, prefixes handled in code (shipped 2026-11-12, SI_RULE).

The calculator step gets prefixed values wrong by powers of ten: "1.5 kW on 240 V" came back 0.00625 A, "5 mm"
came back 0.0125 mm (follow-up set 3, 2026-11-10: 9 of 39 misses; the same bug as fusion round 1). normalize(task)
rewrites the text so the model never sees a prefix: "1.5 kW" -> "1500 W", "150 mA" -> "0.15 A", "in milliamperes"
-> "in amperes". restore(answer, task, normalized) converts the answer back to the unit the question asked for.

Only plain prefixed units are touched: a symbol or word from the lists below, alone or with ^2/^3 on a length.
Compound units ("km/h", "kJ/kg", "kg/m^3"), kilograms, bare grams ("a 9 g turn"), tonnes, minutes and hours are
left as written. Judged by SI_RULE (evals/followup/run4.py and evals/si_regression.py), fixed before any answer:
follow-up set 4 went from 66/83 to 74/83 (paired 95% +4 to +13), and the 66 own-set problems with a prefix from
51 to 58 right (electrical 23 -> 23, aerospace 14 -> 16, physics 14 -> 19). ENABLED = False turns it off.
"""

import re

from plm.numeric.answers import LITERAL_UNITS, ureg

ENABLED = True

PREFIX = {"k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12, "m": 1e-3, "µ": 1e-6, "μ": 1e-6, "u": 1e-6, "n": 1e-9,
          "p": 1e-12, "c": 1e-2}
WORD_PREFIX = {"kilo": 1e3, "mega": 1e6, "giga": 1e9, "tera": 1e12, "milli": 1e-3, "micro": 1e-6, "nano": 1e-9,
               "pico": 1e-12, "centi": 1e-2}
# base symbol -> the prefixes accepted before it
SYMBOLS = {
    "W": "kMGmµμu", "V": "kMmµμu", "A": "kmµμun", "J": "kMGmµμu", "N": "kMmµμu", "Pa": "kMGm", "Hz": "kMGT",
    "F": "mµμunp", "H": "mµμun", "C": "mµμunp", "Ω": "kMmµμu", "ohm": "kMm", "VA": "kM", "Ah": "m", "Wh": "m",
    "eV": "kMGm", "mol": "km", "s": "mµμunp", "g": "mµμu", "m": "kcmµμun",
}
WORDS = ("ohm", "farad", "henr", "amp", "ampere", "volt", "watt", "joule", "newton", "pascal", "hertz", "meter",
         "metre", "second", "coulomb", "mole", "gram")
_sym = "|".join(f"[{p}]{re.escape(b)}" for b, p in sorted(SYMBOLS.items(), key=lambda kv: -len(kv[0])))
_word = (r"(?:kilo|mega|giga|tera|milli|micro|nano|pico|centi)(?:" + "|".join(WORDS) + r")(?:s|es|y|ies)?"
         r"|kilohms?|megohms?")
UNIT = rf"(?P<sym>{_sym})(?P<exp>\^?[23]|²|³)?|(?P<word>{_word})"
AFTER = r"(?![\w/^·*²³-])(?! per\b)"
QUANTITY = re.compile(rf"(?<![\w.^/-])(?P<num>\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)(?P<gap>[  -]?)(?:{UNIT}){AFTER}")
ASKED = re.compile(rf"\b(?P<lead>(?i:in|how many)) (?:{UNIT}){AFTER}")


def _split(m):
    """(factor, base text) for a matched unit, or None to leave it alone."""
    if m.group("word"):
        word = m.group("word")
        low = word.lower()
        if low.startswith("kilogram"):
            return None
        if low.startswith(("kilohm", "megohm")):
            return (1e3 if low.startswith("kilo") else 1e6), "ohm" + ("s" if low.endswith("s") else "")
        for prefix, factor in WORD_PREFIX.items():
            if low.startswith(prefix):
                return factor, word[len(prefix):]
        return None
    sym, exp = m.group("sym"), m.group("exp") or ""
    prefix, base = sym[0], sym[1:]
    if base not in SYMBOLS or prefix not in SYMBOLS[base]:
        return None
    factor = PREFIX[prefix]
    if base == "g":  # mg, µg -> kg (grams aren't SI base; bare "g" is never matched)
        return factor * 1e-3, "kg"
    if exp:
        if base != "m":
            return None
        n = 2 if exp[-1] in "2²" else 3
        return factor ** n, f"m^{n}"
    return factor, base


def normalize(task):
    """task with prefixed quantities and asked units written unprefixed."""
    def quantity(m):
        split = _split(m)
        if split is None:
            return m.group(0)
        factor, base = split
        return f"{float(m.group('num')) * factor:.10g} {base}"

    def asked(m):
        split = _split(m)
        return m.group(0) if split is None else f"{m.group('lead')} {split[1]}"

    return ASKED.sub(asked, QUANTITY.sub(quantity, task))


def restore(answer, task, normalized):
    """answer ({"value", "unit"} or None) for the normalized task, converted to the unit task asks for."""
    from plm.numeric.expected import expected_unit
    if not answer or task == normalized:
        return answer
    want, asked = expected_unit(task)[0], expected_unit(normalized)[0]
    if not want or want in LITERAL_UNITS or want == asked:
        return answer
    try:
        value = ureg.Quantity(answer["value"], answer["unit"] or asked or want).to(want).magnitude
    except Exception:  # an answer in a unit that can't be converted stays as the model gave it
        return answer
    return {"value": float(f"{value:.6g}"), "unit": want}
