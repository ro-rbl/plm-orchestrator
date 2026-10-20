"""Minimal Ollama client: one non-streaming completion per call.

The Ollama address comes from OLLAMA_HOST (default 127.0.0.1:11434).
"""

import json
import os
import time
import urllib.request


def ollama_url():
    host = os.environ.get("OLLAMA_HOST", "127.0.0.1:11434")
    return (host if host.startswith("http") else "http://" + host).rstrip("/")


def qwen3_no_think(model, think):
    # Qwen3 GGUFs pulled from Hugging Face ignore the API's think=false, and the
    # abliterated ones mostly ignore the "/no_think" soft switch too (prompt v2
    # sweep: 30/50 capped). Pre-filling an empty think block in raw mode is the
    # only switch that held on every model tested.
    return not think and "qwen3" in model.lower()


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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        r = json.load(resp)
    msg = r.get("message") or {"content": r.get("response", ""), "thinking": r.get("thinking")}
    return {
        "mode": "raw-prefill" if endpoint == "/api/generate" else "chat",
        "response": msg.get("content", ""),
        "thinking_chars": len(msg.get("thinking") or ""),
        "eval_tokens": r.get("eval_count", 0),
        "prompt_tokens": r.get("prompt_eval_count", 0),
        "load_s": r.get("load_duration", 0) / 1e9,
        "wall_s": time.time() - start,
        "done_reason": r.get("done_reason"),
    }
