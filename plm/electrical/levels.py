"""Electrical pack: chain cues for the shared numeric level rules (plm/numeric/levels.py).

The cues are written from the level definitions there, not fitted per question.
Evaluate them with:  .venv/bin/python evals/eval_levels.py --pack electrical
"""

from plm.numeric import levels as numeric_levels

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
    return numeric_levels.features(text, CHAIN_CUES)


def classify(text):
    """Return (level, reason)."""
    return numeric_levels.classify(text, CHAIN_CUES)
