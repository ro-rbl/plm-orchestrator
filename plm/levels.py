"""Adrenaline level from task text: rules only, no model.

    calm      a lookup or a single formula with two inputs
    alert     a single formula with a few more inputs, or one conversion on top
    intensive an intermediate result must be computed and reused

The rules are written from those definitions, not fitted per question.
Evaluate them with:  .venv/bin/python evals/eval_levels.py
"""

import re

NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:e-?\d+)?(?![\w.])|(?<=\s)\d+(?:\.\d+)?(?=[a-zA-Z%])")

# Each family is a sign that the answer needs a chain: compute X, then use X.
CHAIN_CUES = {
    "losses": r"efficien|internal resistance|\blost\b|\bloss|voltage drop|voltage at the",
    "sizing": r"\bmaximum\b|\bminimum\b|needed to|required to|\braise\b|must run",
    "topology": r"\bbridge\b|\bnode\b|\bdelta\b|\bwye\b|in series with a parallel|connected in parallel\b.*\bto the\b|"
                r"through the \d|same circuit|\bthen\b|stage",
    "ac-chain": r"power factor.*(capacit|reactive)|series RLC|series RC.*across|three-phase.*(real|total) power|line current",
    "accumulate": r"\bcost\b|per day|a day|all day|surplus|deficit|\bfalls to\b",
}


def features(text):
    numbers = NUMBER.findall(text)
    cues = sorted(name for name, pat in CHAIN_CUES.items() if re.search(pat, text, re.IGNORECASE))
    return {"numbers": len(numbers), "chain": cues}


def classify(text):
    """Return (level, reason)."""
    f = features(text)
    if f["numbers"] == 0 and not f["chain"]:
        return "calm", "no given values: lookup"
    score = max(0, f["numbers"] - 2) + 2 * len(f["chain"])
    reason = f"{f['numbers']} given values" + (f", chain cues: {', '.join(f['chain'])}" if f["chain"] else "")
    if score == 0:
        return "calm", reason
    if score <= 2:
        return "alert", reason
    return "intensive", reason
