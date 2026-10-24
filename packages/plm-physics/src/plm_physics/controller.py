"""Physics pack: the 4B with the calculator for calm and alert problems, escalating to the 8B.

On the 50-problem eval set, PHYSICS_RULE (evals/simulate_routing.py, fixed before that
sweep) shipped always 8B answering directly: 49/50, while the calculator lost points
there by printing base-unit values under prefixed units ("5e+04 MPa" for 50 MPa).

SciBench's physics problems (evals/bench_physics.py: Halliday and classical mechanics,
144, written by others; PHYS_RULE, accuracy first, fixed before the runs) reversed that:

    4B+calc | 8B+calc, escalating (now)     69/144 (48%) at 48% of always-8B-direct compute
    always 8B + calculator                  68/144 at 45%
    always 4B + calculator                  63/144 at 24%
    always 8B, direct (shipped before)      52/144 (36%) at 100%

The routed policy beats always-8B-direct by +4 to +30 problems (paired 95%), at half the
compute: it is the electrical pack's shape. The check caught 19 of 76-94 wrong answers
per strategy. Budgets cover the longest calculator answers seen; 5-6 of 144 hit 1024.

Model names can be overridden with PLM_SMALL_MODEL and PLM_LARGE_MODEL.
"""

import os

from plm.numeric import controller as numeric

from plm_physics.levels import classify

MODELS = {
    "small": os.environ.get("PLM_SMALL_MODEL", "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M"),
    "large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b"),
}

# Per level: token budget and the escalation chain of (model, strategy) steps.
LEVELS = {
    "calm": {"num_predict": 1024, "chain": [("small", "tool"), ("large", "tool")]},
    "alert": {"num_predict": 1024, "chain": [("small", "tool"), ("large", "tool")]},
    "intensive": {"num_predict": 1536, "chain": [("large", "tool"), ("large", "bare")]},
}


def solve(task, level=None, timeout=300):
    """Answer one physics task. Returns the answer plus a record of every model call."""
    return numeric.solve(task, pack="physics", classify=classify, levels=LEVELS, models=MODELS,
                         level=level, timeout=timeout)
