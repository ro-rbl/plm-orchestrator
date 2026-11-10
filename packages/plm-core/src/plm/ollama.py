"""Minimal Ollama client.

ask() is one single-prompt completion at temperature 0, which the packs and
evals use. chat() and chat_stream() take a whole conversation and the caller's
sampling options, for the general pack. All of them turn thinking off.
pulled(), pull() and load() are for `plm packs`.

The Ollama address comes from OLLAMA_HOST (default 127.0.0.1:11434).
"""

import json
import os
import time
import urllib.request


LISTENERS = []  # callables(event, model, record): "start" before each model call, "end" with its record after


def _notify(event, model, record=None):
    """Tell progress listeners (the full-screen interface) about a model call; a listener's error never
    breaks the call."""
    for fn in list(LISTENERS):
        try:
            fn(event, model, record)
        except Exception:
            pass


def unreachable(error):
    """True if a failed request means the Ollama server itself is down, not that one request went wrong.

    Eval runners save a failed request as an error row and move on; when the server is down, every
    remaining task would be saved that way, and resuming skips them (60 rows on 2026-10-25). They stop instead.
    """
    return isinstance(error, ConnectionError) or "Connection refused" in str(error)


def ollama_url():
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    return (host if host.startswith("http") else "http://" + host).rstrip("/")


def qwen3_no_think(model, think):
    # Qwen3 GGUFs pulled from Hugging Face ignore the API's think=false, and the
    # abliterated ones mostly ignore the "/no_think" soft switch too (prompt v2
    # sweep: 30/50 capped). Pre-filling an empty think block in raw mode is the
    # only switch that held on every model tested.
    # Qwen3 Instruct-2507 builds never think; they use their own template, whose
    # reply prompt has no think block. Neither the template (it still mentions
    # <think>, to strip old reasoning) nor Ollama's capabilities (it lists
    # "thinking") tell them apart from hybrid builds, so this goes by name.
    # Thinking-only builds (Thinking-2507) keep reasoning despite the prefill, so
    # they don't suit a cheap tier at all.
    name = model.lower()
    return not think and "qwen3" in name and "instruct" not in name


def ask(model, prompt, think, num_predict, timeout):
    options = {"temperature": 0, "num_predict": num_predict}
    if qwen3_no_think(model, think):
        endpoint = "/api/generate"
        body = {
            "model": model,
            "prompt": f"<|im_start|>user\n{prompt}<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n",
            "raw": True,
            "stream": False,
            "options": {**options, "stop": ["<|im_end|>"]},
        }
    else:
        endpoint = "/api/chat"
        body = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": think,
            "options": options,
        }
    req = urllib.request.Request(
        ollama_url() + endpoint, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    start = time.time()
    _notify("start", model)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        r = json.load(resp)
    msg = r.get("message") or {"content": r.get("response", ""), "thinking": r.get("thinking")}
    record = {
        "mode": "raw-prefill" if endpoint == "/api/generate" else "chat",
        "response": msg.get("content", ""),
        "thinking_chars": len(msg.get("thinking") or ""),
        "eval_tokens": r.get("eval_count", 0),
        "prompt_tokens": r.get("prompt_eval_count", 0),
        "load_s": r.get("load_duration", 0) / 1e9,
        "wall_s": time.time() - start,
        "done_reason": r.get("done_reason"),
    }
    _notify("end", model, record)
    return record


def version(timeout=5):
    """Ollama's version string; raises if Ollama is unreachable."""
    with urllib.request.urlopen(ollama_url() + "/api/version", timeout=timeout) as resp:
        return json.load(resp)["version"]


def _chatml(messages):
    """Qwen ChatML for raw mode, ending in an empty think block so the model answers directly."""
    turns = "".join(f"<|im_start|>{m['role']}\n{m['content']}<|im_end|>\n" for m in messages)
    return turns + "<|im_start|>assistant\n<think>\n\n</think>\n\n"


def _chat_request(model, messages, num_predict, options, stream):
    opts = {**(options or {}), "num_predict": num_predict}
    if qwen3_no_think(model, False):
        body = {"model": model, "prompt": _chatml(messages), "raw": True, "stream": stream,
                "options": {**opts, "stop": ["<|im_end|>"]}}
        endpoint = "/api/generate"
    else:
        body = {"model": model, "messages": messages, "stream": stream, "think": False, "options": opts}
        endpoint = "/api/chat"
    req = urllib.request.Request(ollama_url() + endpoint, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return endpoint, req


def _record(endpoint, final, content, start):
    """The same keys ask() returns, from Ollama's final message."""
    return {
        "mode": "raw-prefill" if endpoint == "/api/generate" else "chat",
        "response": content,
        "thinking_chars": 0,
        "eval_tokens": final.get("eval_count", 0),
        "prompt_tokens": final.get("prompt_eval_count", 0),
        "load_s": final.get("load_duration", 0) / 1e9,
        "wall_s": time.time() - start,
        "done_reason": final.get("done_reason"),
    }


def chat(model, messages, num_predict, timeout, options=None):
    """A whole conversation, thinking off. messages are {"role", "content"} dicts.

    options are Ollama sampling options (temperature, top_p, ...); unset ones
    use the model's own defaults.
    """
    endpoint, req = _chat_request(model, messages, num_predict, options, stream=False)
    start = time.time()
    _notify("start", model)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        r = json.load(resp)
    content = (r.get("message") or {}).get("content", r.get("response", ""))
    record = _record(endpoint, r, content, start)
    _notify("end", model, record)
    return record


def chat_stream(model, messages, num_predict, timeout, options=None):
    """Like chat(), but yields ("delta", text) as tokens arrive, then ("done", record)."""
    endpoint, req = _chat_request(model, messages, num_predict, options, stream=True)
    start = time.time()
    parts = []
    _notify("start", model)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        for line in resp:  # Ollama streams one JSON object per line
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("error"):
                raise RuntimeError(f"Ollama: {r['error']}")
            delta = (r.get("message") or {}).get("content", r.get("response", ""))
            if delta:
                parts.append(delta)
                yield "delta", delta
            if r.get("done"):
                record = _record(endpoint, r, "".join(parts), start)
                _notify("end", model, record)
                yield "done", record
                return
    raise RuntimeError("Ollama stream ended without a final message")


def full_name(model):
    """Model name as Ollama lists it: an untagged name means ':latest'."""
    return model if ":" in model.rsplit("/", 1)[-1] else model + ":latest"


def pulled(timeout=10):
    """Names of every model Ollama has pulled; raises if Ollama is unreachable."""
    with urllib.request.urlopen(ollama_url() + "/api/tags", timeout=timeout) as resp:
        return {m["name"] for m in json.load(resp)["models"]}


def _post(endpoint, body, timeout):
    req = urllib.request.Request(ollama_url() + endpoint, json.dumps(body).encode(), {"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def pull(model, timeout=3600):
    """Pull a model, yielding Ollama's progress messages; raises on an error message."""
    with _post("/api/pull", {"model": model}, timeout) as resp:
        for line in resp:
            msg = json.loads(line)
            if "error" in msg:
                raise RuntimeError(msg["error"])
            yield msg


def load(model, timeout=600):
    """Load a model into memory without generating; raises if it can't be loaded."""
    with _post("/api/generate", {"model": model}, timeout) as resp:
        r = json.load(resp)
    if r.get("done_reason") != "load":
        raise RuntimeError(f"unexpected reply: {r}")
