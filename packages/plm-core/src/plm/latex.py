"""LaTeX quantities to plain text, so routing, levels and unit checks read them as they read plain text.

Textbooks and benchmarks (SciBench) write "$8.4 \\mathrm{~km}$" and "$\\mathrm{~m} / \\mathrm{s}^2$";
the claim rules and unit words expect "8.4 km" and "m/s^2". Only what the router and checks read
is converted: the model still gets the original text. Text with no "$" and no backslash is
returned unchanged, so no decision on plain text can move (LATEX_RULE in evals/test_detect.py).
"""

import re

SYMBOLS = {"\\mu": "µ", "\\Omega": "Ω", "\\omega": "omega", "\\theta": "theta", "\\rho": "rho", "\\times": "×",
           "\\cdot": "*", "\\circ": "°", "\\%": "%", "\\Delta": "Delta", "\\pi": "pi", "\\lambda": "lambda"}
WRAPPERS = re.compile(r"\\(?:mathrm|text|mathbf|textrm|operatorname|mbox)\s*\{([^{}]*)\}")


def plain(text):
    """The text with LaTeX markup turned into the plain spelling the router and checks read."""
    if "$" not in text and "\\" not in text:
        return text
    t = text
    for _ in range(3):  # nested wrappers: \mathrm{\mu C}
        t = WRAPPERS.sub(r"\1", t)
    t = re.sub(r"\^\s*\{?\s*\\circ\s*\}?", "°", t)       # 20^{\circ} -> 20°
    for k, v in SYMBOLS.items():
        t = t.replace(k, v)
    t = re.sub(r"\^\{([^{}]*)\}", r"^\1", t)               # s^{-1} -> s^-1
    t = re.sub(r"_\{([^{}]*)\}", r"_\1", t)
    t = t.replace("$", " ").replace("~", " ").replace("{", "").replace("}", "")
    t = re.sub(r"\\[,;:! ]", " ", t)                       # LaTeX spacing commands
    t = re.sub(r"\\([A-Za-z]+)", r"\1", t)                  # any other command: its name
    t = re.sub(r"\s*/\s*", "/", t)                         # m / s -> m/s
    t = re.sub(r"(\d)\s+°", r"\1°", t)                     # 20 ° C -> 20°C
    t = re.sub(r"°\s+([CFK])\b", r"°\1", t)
    t = re.sub(r"(µ)\s+([A-Za-z])", r"\1\2", t)            # µ C -> µC
    return re.sub(r"[ \t]+", " ", t).strip()


if __name__ == "__main__":  # self-test
    cases = {
        "$8.4 \\mathrm{~km}$ at $70 \\mathrm{~km} / \\mathrm{h}$": "8.4 km at 70 km/h",
        "$g=9.8 \\mathrm{~m} / \\mathrm{s}^2$": "g=9.8 m/s^2",
        "$20^{\\circ} \\mathrm{C}$": "20°C",
        "$q_1=3.0 \\mu \\mathrm{C}$": "q_1=3.0 µC",
        "$R = 220 \\Omega$": "R = 220 Ω",
        "plain 3 m/s text": "plain 3 m/s text",
    }
    bad = {k: (plain(k), v) for k, v in cases.items() if plain(k) != v}
    for k, (got, want) in bad.items():
        print(f"FAIL {k!r}: {got!r}, want {want!r}")
    print(f"latex self-test: {len(cases) - len(bad)}/{len(cases)} passed")
