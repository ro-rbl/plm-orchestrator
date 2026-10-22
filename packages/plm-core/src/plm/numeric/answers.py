"""The "ANSWER: <number> <unit>" contract: the prompt that asks for it and the parser that reads it.

Shared by the grader (evals/grade.py), the numeric controller (plm/numeric/controller.py) and
its answer checks (plm/numeric/checks.py), so all of them read model output the same way.
"""

import re

import pint

# v1 showed "ANSWER: <number> <unit>" and small models copied "<unit>" literally.
PROMPT_VERSION = 2
ANSWER_FORMAT = (
    "Solve the problem. Show brief working. Your last line must be the final answer "
    "as a number followed by its unit, written like this example:\n"
    "ANSWER: 3.3 kN\n"
    "Use the unit the question asks for. For unitless answers, give only the number."
)

ureg = pint.UnitRegistry()

# Units pint can't (or shouldn't) convert; matched by alias instead.
LITERAL_UNITS = {
    "": {"", "unitless", "dimensionless"},
    "dB": {"db", "decibel", "decibels"},
    "USD": {"usd", "$", "dollar", "dollars", "us dollars"},
    "count": {"", "count", "cell", "cells"},
}

ANSWER_RE = re.compile(r"ANSWER\s*:\s*(.+)", re.IGNORECASE)
SUPERSCRIPT_DIGITS = "⁰¹²³⁴⁵⁶⁷⁸⁹"
SUPERSCRIPT_SIGNS = "⁻⁺"
SUPERSCRIPTS = str.maketrans(SUPERSCRIPT_DIGITS + SUPERSCRIPT_SIGNS, "0123456789-+")
NUMBER_RE = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?", re.IGNORECASE)


def normalize(text):
    text = text.strip().replace("\u2212", "-").replace("\u2013", "-")
    # LaTeX and Markdown from the models: \text{V}, \, , 10^{-19}, **3 A**
    text = re.sub(r"\\(?:text|mathrm|mathit|rm)\s*\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\[,;:! ]", " ", text)
    text = text.replace("\\times", "×").replace("\\cdot", "*").replace("\\Omega", "ohm").replace("\\mu", "u")
    text = re.sub(r"\^\{([^}]*)\}", r"^\1", text)
    text = re.sub(f"10([{SUPERSCRIPT_SIGNS}]?[{SUPERSCRIPT_DIGITS}]+)",
                  lambda m: "10^" + m.group(1).translate(SUPERSCRIPTS), text)  # 10⁻¹⁹
    text = re.sub(r"\\[()\[\]]|[{}`]|\*\*", " ", text)
    text = text.replace("$", " $ ")
    # 1.6 × 10^-19  /  1.6x10^-19  /  1.6 * 10^-19  ->  1.6e-19
    text = re.sub(r"\s*(?:×|x|\*)\s*10\s*\^\s*\(?\s*([-+]?\d+)\s*\)?", r"e\1", text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)  # 14,722 -> 14722
    return text


def normalize_unit(unit):
    unit = unit.strip().rstrip(".;,").strip()
    unit = unit.replace("Ω", "ohm").replace("Ω", "ohm")
    unit = unit.replace("µ", "u").replace("μ", "u").replace("·", "*")
    unit = re.sub(r"\bohms\b", "ohm", unit, flags=re.IGNORECASE)
    unit = re.sub(r"\s*\(?\brms\b\)?", "", unit, flags=re.IGNORECASE).strip().strip("*").strip()
    unit = re.sub(r"(?<=[A-Za-z])-(?=[A-Za-z])", "*", unit)  # ohm-meter, kilowatt-hours
    if re.fullmatch(r"deg[CcFf]", unit):  # pint's Celsius and Fahrenheit, which the next rule would break
        return "deg" + unit[3].upper()
    if re.fullmatch(r"[A-Za-z]{4,}", unit):  # spelled-out words only; keep mS vs MS
        unit = unit.lower()
    return unit


def parse_answer(response):
    matches = ANSWER_RE.findall(response or "")
    if not matches:
        return None
    # "**ANSWER:** ANSWER: 56.9 W" -> keep what follows the last label on the line
    text = normalize(re.split(r"ANSWER\s*:", matches[-1], flags=re.IGNORECASE)[-1])
    num = NUMBER_RE.search(text)
    if not num:
        return None
    unit = text[: num.start()] + text[num.end():]  # "$152.53" puts the unit first
    return float(num.group()), normalize_unit(unit)
