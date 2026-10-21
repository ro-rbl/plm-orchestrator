"""Aerospace pack: every level goes to the large model with the calculator.

The policy fixed before the aerospace sweep had the electrical pack's shape
(small model for calm and alert, escalate on a failed check). On the 50-problem
eval it lost to the large model alone on both counts:

    always 8B + calculator                 39/50 at 41% of always-8B compute
    routed 4B+calc | 8B+calc, escalating   37/50 at 46%

The original Qwen3-4B, which matches the 8B on electrical, is weaker here (75%
vs 90% on alert problems), and the unit checks catch only 2-3 of the wrong
answers, so escalating on them adds compute without adding correct answers.
The saving over the 8B answering directly comes from the calculator, not from
routing. The level still sets the token budget (>3x the longest answer seen).
evals/simulate_routing.py --pack aerospace has every policy measured, including
two added afterwards and marked post-hoc.

Model name can be overridden with PLM_LARGE_MODEL.
"""

import os

from plm.aerospace.levels import classify
from plm.numeric import controller as numeric

MODELS = {"large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b")}

# Per level: token budget and the (model, strategy) steps; a failed check is reported, not escalated.
LEVELS = {
    "calm": {"num_predict": 512, "chain": [("large", "tool")]},
    "alert": {"num_predict": 768, "chain": [("large", "tool")]},
    "intensive": {"num_predict": 1024, "chain": [("large", "tool")]},
}


def solve(task, level=None, timeout=300):
    """Answer one aerospace task. Returns the answer plus a record of every model call."""
    return numeric.solve(task, pack="aerospace", classify=classify, levels=LEVELS, models=MODELS,
                         level=level, timeout=timeout)
