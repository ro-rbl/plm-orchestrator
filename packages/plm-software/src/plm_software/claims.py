"""Which tasks the software pack claims: a request to write code, or a def signature."""

import math
import re

SOFTWARE_TASK = re.compile(r"\b(?:write|implement|create|code)\b.{0,40}\b(?:function|class|method|program)\b|\bdef \w+\s*\(",
                           re.IGNORECASE | re.DOTALL)


def claims(text):
    """Certain whenever the text asks for code, so software wins over every numeric pack."""
    return math.inf if SOFTWARE_TASK.search(text) else 0
