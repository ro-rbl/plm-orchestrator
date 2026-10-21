"""Turning a pack result into what a person or a client sees; shared by the CLI and the server."""

import re


def short(model):
    # hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M -> Qwen3-4B-abliterated
    if "/" not in model:
        return model
    return re.sub(r"^[^_]*_|-GGUF.*$", "", model.rsplit("/", 1)[-1])


def final_step(result):
    # Thorough mode can return an earlier answer than the last one tried.
    return result["steps"][result.get("final_step", len(result["steps"])) - 1]


def caveat(result):
    """Why the answer isn't trusted, or '' if it is."""
    issues = final_step(result)["issues"]
    if issues:
        return f"unverified: {'; '.join(issues)}"
    if not result.get("checked", True):
        return f"unchecked: {result['unchecked_reason']}"
    return ""


def answer_body(result):
    """The answer alone: a value with its unit, a code block, or the reply text."""
    ans = result["answer"]
    if ans is None:
        return "No answer. Last model output:\n" + result["steps"][-1]["model_text"].strip()
    if result["pack"] == "software":
        return "```python\n" + ans["code"].strip() + "\n```"
    if result["pack"] == "general":
        return ans["text"].strip()
    return f"{ans['value']:.6g} {ans['unit']}".rstrip()


def answer_text(result):
    """The answer plus, for pack answers, a caveat line when it failed a check or had nothing to check.

    General answers are never checked, so a caveat on each would be noise; the
    server's "plm" field and the CLI report still say so.
    """
    note = caveat(result) if result["pack"] != "general" else ""
    return answer_body(result) + (f"\n\n({note})" if note else "")
