"""Prompting for code tasks and pulling the code back out of the reply."""

import re

from plm_software.sandbox import ALLOWED_IMPORTS

# v1 said "including any imports" and listed typing; small models then wrote
# "from typing import int", which crashes (13 of the 0.6B and 4B errors).
PROMPT_VERSION = 2
CODE_FORMAT = (
    "Reply with one ```python code block containing the complete implementation. Import a module "
    "only if your code uses it; built-in types such as int, str, list and dict need no import. "
    "You may only import these standard-library modules: "
    + ", ".join(sorted(ALLOWED_IMPORTS))
    + ". Do not include tests, example usage or input()."
)

CODE_RE = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL | re.IGNORECASE)


def build_prompt(task):
    if not task["examples"]:
        return f"{task['prompt']}\n\n{CODE_FORMAT}"
    examples = "\n".join(f"    {e}" for e in task["examples"])
    return f"{task['prompt']}\n\nExamples (each expression must be True):\n{examples}\n\n{CODE_FORMAT}"


def extract_code(text, entry):
    """The last fenced block that defines `entry`; else the last block; else unfenced code."""
    defines = re.compile(rf"^\s*(?:def|class)\s+{re.escape(entry)}\b", re.MULTILINE)
    blocks = CODE_RE.findall(text or "")
    for block in reversed(blocks):
        if defines.search(block):
            return block
    if blocks:
        return blocks[-1]
    return text if defines.search(text or "") else None
