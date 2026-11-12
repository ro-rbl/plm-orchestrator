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
CONTEXT_SIZES = (8192, 16384, 32768, 40960)  # CONTEXT_RULE (evals/context/measure.py, 2026-11-09)
DEFAULT_CONTEXT = 4096  # Ollama's default; staying on it shares the copy the user's assistant keeps loaded
UNCHECKED = "no pack covers this task, so the answer wasn't checked"


# For people reading the reply in plm's own interface or command line (not sent for API clients of the server,
# who bring their own instructions). Local models otherwise decorate every answer with emoji, rules and headings.
STYLE = ("Answer plainly and briefly, in short paragraphs. Use a short list only when the answer really is a list, "
         "and headings only for a long answer. No emoji, no horizontal rules, no tables unless asked for one.")


def styled(messages):
    """messages with STYLE as (or added to the front of) the system message."""
    if messages and messages[0].get("role") == "system":
        return [{"role": "system", "content": STYLE + "\n\n" + messages[0]["content"]}, *messages[1:]]
    return [{"role": "system", "content": STYLE}, *messages]


def _messages(task, messages):
    return messages or [{"role": "user", "content": task}]


def context_options(messages, num_predict, options=None):
    """options with num_ctx raised only when the conversation won't fit Ollama's default 4096.

    Ollama silently drops the start of a longer conversation (measured: a code word in the first message was
    lost at 4096 and recalled at 8192 and up). Short chats keep the default, so the model isn't reloaded.
    A caller's own num_ctx wins.
    """
    need = sum(len(m.get("content") or "") for m in messages) // 3 + num_predict
    if need <= DEFAULT_CONTEXT or "num_ctx" in (options or {}):
        return options
    return {**(options or {}), "num_ctx": next((n for n in CONTEXT_SIZES if n >= need), CONTEXT_SIZES[-1])}


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
    msgs, budget = _messages(task, messages), max_tokens or NUM_PREDICT
    r = chat(model, msgs, budget, timeout, context_options(msgs, budget, options))
    return _result(task, level, _step(model, r), start)


def solve_stream(task, level=None, timeout=600, messages=None, options=None, max_tokens=None):
    """Like solve(), but yields ("delta", text) as the reply streams, then ("result", result)."""
    start = time.time()
    model = MODELS["large"]
    msgs, budget = _messages(task, messages), max_tokens or NUM_PREDICT
    for kind, value in chat_stream(model, msgs, budget, timeout, context_options(msgs, budget, options)):
        if kind == "delta":
            yield "delta", value
        else:
            yield "result", _result(task, level, _step(model, value), start)
