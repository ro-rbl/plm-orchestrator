"""Pack registry, used by the CLI (and the server) to find packs the same way.

A pack is a module that provides:

    MODELS   tier name -> Ollama model name
    LEVELS   adrenaline level -> plan (calm, alert, intensive)
    solve(task, level=None, timeout=..., **options) -> dict with at least
             pack, task, level, reason, answer, checked, unchecked_reason,
             trusted, steps, tokens, seconds

`trusted` means the answer passed every check and there was something to check;
`checked` is False when the task gave the pack nothing to verify against.
"""

import re

from plm.electrical import controller as electrical
from plm.software import controller as software

PACKS = {"electrical": electrical, "software": software}

SOFTWARE_TASK = re.compile(r"\b(?:write|implement|create|code)\b.{0,40}\b(?:function|class|method|program)\b|\bdef \w+\s*\(",
                           re.IGNORECASE | re.DOTALL)


def detect(text):
    """Pick a pack from the task text. Verified on the 134 eval texts only."""
    return "software" if SOFTWARE_TASK.search(text) else "electrical"
