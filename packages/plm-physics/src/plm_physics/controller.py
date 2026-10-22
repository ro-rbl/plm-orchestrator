"""Physics pack: tiers and level rules on top of the shared numeric controller.

The policy below was fixed before the physics sweep, in the electrical pack's
shape: calm and alert problems go to the small model with the calculator, and
escalate to the large model when an answer fails plm.numeric.checks; intensive
ones go to the large model with the calculator. evals/simulate_routing.py
--pack physics has the alternatives and the rule (PHYSICS_RULE) that picks
among them after the sweep.

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
    "calm": {"num_predict": 512, "chain": [("small", "tool"), ("large", "tool")]},
    "alert": {"num_predict": 768, "chain": [("small", "tool"), ("large", "tool")]},
    "intensive": {"num_predict": 1024, "chain": [("large", "tool"), ("large", "bare")]},
}


def solve(task, level=None, timeout=300):
    """Answer one physics task. Returns the answer plus a record of every model call."""
    return numeric.solve(task, pack="physics", classify=classify, levels=LEVELS, models=MODELS,
                         level=level, timeout=timeout)
