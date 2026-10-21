"""General pack: anything no other pack claims goes to the large model, unchecked.

There is no check for open-ended answers, so nothing is escalated and nothing is
routed down to a smaller model: without a check, a cheaper model's mistakes
would go unnoticed. The whole conversation is passed through (packs only see
the last user message), with the caller's sampling options.

Model name can be overridden with PLM_LARGE_MODEL.
"""

import os
import time

from plm.ollama import chat, chat_stream

MODELS = {"large": os.environ.get("PLM_LARGE_MODEL", "qwen3:8b")}
NUM_PREDICT = 2048  # default reply budget when the caller sets none
LEVELS = {lvl: {"num_predict": NUM_PREDICT, "chain": ["large"]} for lvl in ("calm", "alert", "intensive")}
UNCHECKED = "no pack covers this task, so the answer wasn't checked"


def _messages(task, messages):
    return messages or [{"role": "user", "content": task}]


def _result(task, level, step, start):
    return {
        "pack": "general",
        "task": task,
        "level": level or "alert",
        "reason": "no pack matched; sent to the large model",
        "answer": {"text": step["model_text"]},
        "checked": False,
        "unchecked_reason": UNCHECKED,
        "trusted": False,
        "steps": [step],
        "tokens": step["tokens"],
        "seconds": time.time() - start,
    }


def _step(model, r):
    return {"model": model, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
            "model_text": r["response"], "capped": r["done_reason"] == "length", "issues": [],
            "seconds": r["wall_s"]}


def solve(task, level=None, timeout=600, messages=None, options=None, max_tokens=None):
    """Answer with the large model. Returns the same result shape as every pack."""
    start = time.time()
    model = MODELS["large"]
    r = chat(model, _messages(task, messages), max_tokens or NUM_PREDICT, timeout, options)
    return _result(task, level, _step(model, r), start)


def solve_stream(task, level=None, timeout=600, messages=None, options=None, max_tokens=None):
    """Like solve(), but yields ("delta", text) as the reply streams, then ("result", result)."""
    start = time.time()
    model = MODELS["large"]
    for kind, value in chat_stream(model, _messages(task, messages), max_tokens or NUM_PREDICT, timeout, options):
        if kind == "delta":
            yield "delta", value
        else:
            yield "result", _result(task, level, _step(model, value), start)
