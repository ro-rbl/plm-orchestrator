"""Adrenaline level for a coding task, from its description: rules only, no model.

    calm      one transformation: a loop, a comprehension, a builtin
    alert     one standard algorithm, or input-validation rules to get exactly right
    intensive designing a data structure, search, optimization/DP, or writing a parser

The cue families are written from those definitions, not fitted per task.
Evaluate them with:  .venv/bin/python evals/eval_levels.py --pack software
"""

import re

INTENSIVE_CUES = {
    "design": r"write a class\b",
    "search": r"shortest|\bpaths?\b|graph|backtrack|queens|ladder|island|sudoku",
    "optimize": r"\b(?:minimum|maximum|fewest|largest number|longest|lexicographically smallest)\b",
    "dp": r"dynamic programming|subsequence|knapsack|levenshtein|edit distance",
    "parser": r"\bparses?\b|\bevaluates?\b|precedence|(?:without|do not use) (?:using )?(?:eval|the \w+ module)",
}
ALERT_CUES = {
    "rules": r"\bvalid\b|raise \w*error|leading zeros|at most once|in that order|unbalanced|balanced",
    "algorithm": r"binary search|o\(log n\)|o\(n\)|linear time|merge|frequen|anagram|nested|matrix|rotate"
                 r"|roman|encode|cipher|prefix|triangle|bracket|interval|range strings",
}


def classify(text):
    """Return (level, reason)."""
    hits = lambda cues: sorted(n for n, p in cues.items() if re.search(p, text, re.IGNORECASE))  # noqa: E731
    intensive, alert = hits(INTENSIVE_CUES), hits(ALERT_CUES)
    if intensive:
        return "intensive", "cues: " + ", ".join(intensive)
    if alert:
        return "alert", "cues: " + ", ".join(alert)
    return "calm", "no algorithm cues"
