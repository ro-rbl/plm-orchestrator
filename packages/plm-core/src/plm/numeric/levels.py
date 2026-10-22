"""Adrenaline level for a numeric task, from its text: rules only, no model.

    calm      a lookup or a single formula with two inputs
    alert     a single formula with a few more inputs, or one conversion on top
    intensive an intermediate result must be computed and reused

Each numeric pack supplies only its chain cues: families of phrases that signal
"compute X, then use X" in its domain. Counting the given values and turning
the counts into a level is the same for every pack.
"""

import re

NUMBER = re.compile(r"(?<![\w.])-?\d+(?:\.\d+)?(?:e-?\d+)?(?![\w.])|(?<=\s)\d+(?:\.\d+)?(?=[a-zA-Z%])")


def features(text, chain_cues):
    numbers = NUMBER.findall(text)
    cues = sorted(name for name, pat in chain_cues.items() if re.search(pat, text, re.IGNORECASE))
    return {"numbers": len(numbers), "chain": cues}


def classify(text, chain_cues):
    """Return (level, reason)."""
    f = features(text, chain_cues)
    if f["numbers"] == 0 and not f["chain"]:
        return "calm", "no given values: lookup"
    score = max(0, f["numbers"] - 2) + 2 * len(f["chain"])
    reason = f"{f['numbers']} given values" + (f", chain cues: {', '.join(f['chain'])}" if f["chain"] else "")
    if score == 0:
        return "calm", reason
    if score <= 2:
        return "alert", reason
    return "intensive", reason
