"""CAD pack: level rules, from the features a part asks for.

    calm      one primitive solid
    alert     a primitive with one feature (a hole, pocket, slot, chamfer, fillet)
    intensive several features, a pattern, a shell, or solids joined

Written after the eval set and the holdout (evals/cad/holdout_levels.jsonl) were
written; the holdout is never used to tune them. Evaluate with:
    .venv/bin/python evals/eval_levels.py --pack cad
"""

import re

FEATURES = {
    "hole": r"\bholes?\b|\bbore\b",
    "counterbore": r"\bcounterbor\w*|\bcountersunk\b|\bcountersink\w*",
    "pocket": r"\bpockets?\b|\bcutouts?\b|\brecess\w*",
    "slot": r"\bslots?\b|\bkeyway\b|\bgroove\b",
    "chamfer": r"\bchamfer\w*",
    "fillet": r"\bfillet\w*|\brounded to\b",
    "cut-shape": r"\bhemisphere\b|\bhalf\b",
}
# Any of these alone makes a part intensive.
INTENSIVE = {
    "pattern": r"\b(?:two|three|four|five|six|eight|twelve)\b[^.]*\b(?:holes?|pockets?|slots?)\b|bolt circle"
               r"|\bgrid\b|evenly spaced|\bpattern\b",
    "shell": r"\bwalls?\b|\bhollow\b|open-topped|\bno lid\b|\bshell\b",
    "joined": r"\bbracket\b|\bflange\b|\bstepped\b|\bstanding\b|\bsitting on\b|\bfollowed\b|\brib\b"
              r"|\bchannel\b|\blip\b",
}


def classify(text):
    """Return (level, reason)."""
    big = sorted(n for n, p in INTENSIVE.items() if re.search(p, text, re.IGNORECASE))
    feats = sorted(n for n, p in FEATURES.items() if re.search(p, text, re.IGNORECASE))
    if big:
        return "intensive", f"{', '.join(big)}" + (f"; features: {', '.join(feats)}" if feats else "")
    if len(feats) >= 2:
        return "intensive", f"features: {', '.join(feats)}"
    if feats:
        return "alert", f"feature: {feats[0]}"
    return "calm", "one primitive"
