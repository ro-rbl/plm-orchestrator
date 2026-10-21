"""Aerospace pack: tiers and level rules on top of the shared numeric controller.

The policy has the electrical pack's shape, fixed before the aerospace sweep:
calm and alert problems go to the small model with the calculator, intensive
ones to the large model, and any answer that fails plm.numeric.checks moves to
the next step. evals/simulate_routing.py --pack aerospace measures it.

Model names can be overridden with PLM_SMALL_MODEL and PLM_LARGE_MODEL.
"""

import os

from plm.aerospace.levels import classify
from plm.numeric import controller as numeric

MODELS = {
    "small": os.environ.get("PLM_SMALL_MODEL", "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M"),
    "large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b"),
}

# Per level: token budget and the escalation chain of (model, strategy) steps.
LEVELS = {
    "calm": {"num_predict": 512, "chain": [("small", "tool"), ("large", "tool")]},
    "alert": {"num_predict": 768, "chain": [("small", "tool"), ("large", "tool")]},
    "intensive": {"num_predict": 1024, "chain": [("large", "tool"), ("large", "bare")]},
}


def solve(task, level=None, timeout=300):
    """Answer one aerospace task. Returns the answer plus a record of every model call."""
    return numeric.solve(task, pack="aerospace", classify=classify, levels=LEVELS, models=MODELS,
                         level=level, timeout=timeout)
