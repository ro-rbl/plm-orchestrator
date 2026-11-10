"""General pack context window: memory and long-conversation recall of qwen3:8b at several num_ctx.

    .venv/bin/python evals/context/measure.py      # results/context_measure.jsonl, then the verdict

Written 2026-11-09 before any measurement. For each num_ctx in SIZES: unload qwen3:8b, send one ~CONV_TOKENS
conversation whose FIRST message holds a code word, ask for the code word in the last message, then read the loaded
size from /api/ps. Recall = the code word in the reply. The model is unloaded at the end (the user's assistant
reloads and re-pins its own copy on its next request).

CONTEXT_RULE (fixed before running): the general pack passes num_ctx only when the conversation needs more than
Ollama's 4096 (estimate: chars/3 + the reply budget), so short chats keep sharing the assistant's loaded copy.
The cap is the largest size in SIZES that (1) recalls the code word on the long conversation and (2) loads at most
3.0 GB above the 4096 size (24 GB Mac, already using swap). If no size above 4096 meets both, don't ship.
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODEL = "qwen3:8b"
URL = "http://localhost:11434"
SIZES = [4096, 8192, 16384, 32768, 40960]
CONV_TOKENS = 7000
WORD = "PELICAN-4471"
OUT = ROOT / "results/context_measure.jsonl"


def post(path, body, timeout=900):
    req = urllib.request.Request(URL + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def loaded_size():
    with urllib.request.urlopen(URL + "/api/ps", timeout=10) as r:
        for m in json.load(r)["models"]:
            if m["name"].startswith(MODEL):
                return m["size"] / 1e9, m.get("context_length")
    return None, None


def unload():
    post("/api/generate", {"model": MODEL, "keep_alive": 0})
    time.sleep(3)


def conversation():
    filler = ("The pump station logs pressure every minute; readings stayed between 3.1 and 3.4 bar, "
              "with no alarms, and the operator noted routine maintenance on valve seven. ")
    msgs = [{"role": "user", "content": f"Remember this code word for later: {WORD}. Reply OK."},
            {"role": "assistant", "content": "OK."}]
    while sum(len(m["content"]) for m in msgs) / 4 < CONV_TOKENS:  # ~4 chars per token
        msgs += [{"role": "user", "content": filler * 4 + " Summarize in one word."},
                 {"role": "assistant", "content": "Routine."}]
    msgs.append({"role": "user", "content": "What was the code word I asked you to remember? Answer with it only."})
    return msgs


def main():
    msgs = conversation()
    rows = []
    for ctx in SIZES:
        unload()
        t = time.time()
        r = post("/api/chat", {"model": MODEL, "messages": msgs, "stream": False, "think": False,
                               "options": {"temperature": 0, "num_predict": 32, "num_ctx": ctx}})
        size, loaded_ctx = loaded_size()
        reply = r["message"]["content"].strip()
        row = {"num_ctx": ctx, "loaded_ctx": loaded_ctx, "size_gb": round(size, 2) if size else None,
               "prompt_tokens": r.get("prompt_eval_count"), "seconds": round(time.time() - t, 1),
               "recall": WORD in reply, "reply": reply[:80]}
        rows.append(row)
        with OUT.open("a") as f:
            f.write(json.dumps(row) + "\n")
        print(row, flush=True)
    unload()
    base = next(r["size_gb"] for r in rows if r["num_ctx"] == 4096)
    ok = [r["num_ctx"] for r in rows if r["num_ctx"] > 4096 and r["recall"] and r["size_gb"] - base <= 3.0]
    print("CONTEXT_RULE ->", f"ship, cap num_ctx at {max(ok)}" if ok else "don't ship")


if __name__ == "__main__":
    sys.exit(main())
