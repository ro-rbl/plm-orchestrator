"""Physics pack: every level goes to the large model answering directly.

The policy fixed before the physics sweep had the electrical pack's shape (the
small model with the calculator for calm and alert, escalating on a failed
check). PHYSICS_RULE in evals/simulate_routing.py, also fixed before the sweep,
picks the cheapest policy within 1 problem of the best; on the 50-problem eval
only one was:

    always 8B, direct                       49/50 at 100% of always-8B compute
    always 4B, direct                       47/50 at 49%
    always 4B + calculator                  45/50 at 26%
    pre-sweep default (4B+calc, escalating) 44/50 at 36%
    always 8B + calculator                  43/50 at 44%

Unlike electrical and aerospace, the calculator costs accuracy here: every one
of the 8B's 7 calculator misses computed in base units and printed the asked,
prefixed unit without converting ("5e+04 MPa" for 50 MPa), which the unit
checks can't see (same dimension), so a failed check is reported, not escalated.
Budgets are >2.5x the longest direct answer at each level (252, 347, 589 tokens).

Model name can be overridden with PLM_LARGE_MODEL.
"""

import os

from plm.numeric import controller as numeric

from plm_physics.levels import classify

MODELS = {"large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b")}

# Per level: token budget and the (model, strategy) steps; a failed check is reported, not escalated.
LEVELS = {
    "calm": {"num_predict": 768, "chain": [("large", "bare")]},
    "alert": {"num_predict": 1024, "chain": [("large", "bare")]},
    "intensive": {"num_predict": 1536, "chain": [("large", "bare")]},
}


def solve(task, level=None, timeout=300):
    """Answer one physics task. Returns the answer plus a record of every model call."""
    return numeric.solve(task, pack="physics", classify=classify, levels=LEVELS, models=MODELS,
                         level=level, timeout=timeout)
