"""Offline tests for the OpenAI-compatible server (plm/server.py).

    .venv/bin/python evals/test_server.py

A real server runs on a free loopback port and is called over HTTP; Ollama is
replaced by scripted replies, so no model is loaded.
"""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plm.general.controller as general  # noqa: E402
import plm.numeric.controller as numeric  # noqa: E402
import plm.ollama as ollama  # noqa: E402
import plm.server as server  # noqa: E402
import plm_software.controller as software  # noqa: E402
from plm_electrical import controller as electrical  # noqa: E402

FAILS = []
PROGRAM_22V = '```python\nprint(f"ANSWER: {220 * 0.1:.4g} V")\n```'
DOUBLE = "```python\ndef double(x):\n    return 2 * x\n```"


def expect(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name}: {str(detail)[:400]}")


def reply(text, prompt_tokens=7, delay=0.0):
    if delay:
        time.sleep(delay)
    return {"response": text, "eval_tokens": len(text.split()), "prompt_tokens": prompt_tokens, "load_s": 0,
            "wall_s": 0.0, "done_reason": "stop", "thinking_chars": 0, "mode": "fake"}


def fake_ask(by_model, delay=0.0):
    def ask(model, prompt, think, num_predict, timeout):
        return reply(by_model[model], delay=delay)
    return ask


def fake_chat(messages_seen):
    def chat(model, messages, num_predict, timeout, options=None):
        messages_seen.append((messages, options, num_predict))
        return reply("Canberra is the capital of Australia.")
    return chat


def fake_chat_stream(model, messages, num_predict, timeout, options=None):
    parts = ["Canberra ", "is ", "the ", "capital."]
    for p in parts:
        yield "delta", p
    yield "done", reply("".join(parts))


def install_fakes():
    """Replace every model call with scripted replies (for evals/compat_openai.py --fake).

    Returns a function that puts the real calls back.
    """
    import plm_software.testgen as testgen
    saved = (numeric.ask, software.ask, general.chat, general.chat_stream, ollama.version, testgen.ask)
    small, large = electrical.MODELS["small"], electrical.MODELS["large"]
    numeric.ask = fake_ask({small: PROGRAM_22V, large: PROGRAM_22V})
    software.ask = fake_ask({software.MODELS["small"]: DOUBLE})
    general.chat, general.chat_stream = fake_chat([]), fake_chat_stream
    ollama.version = lambda timeout=5: "0.0-fake"
    testgen.ask = lambda *a: reply("```python\ndouble(5) == 10\n```")

    def restore():
        numeric.ask, software.ask, general.chat, general.chat_stream, ollama.version, testgen.ask = saved
    return restore


def call(port, method, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=data, method=method,
                                 headers={"Content-Type": "application/json", "Authorization": "Bearer anything"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def sse_events(body):
    """(data events, comment count) from an SSE body."""
    events, comments = [], 0
    for block in body.decode().split("\n\n"):
        for line in block.splitlines():
            if line.startswith(":"):
                comments += 1
            elif line.startswith("data: "):
                payload = line[len("data: "):]
                events.append(payload if payload == "[DONE]" else json.loads(payload))
    return events, comments


def chat_body(text, **kw):
    return {"model": "plm-router", "messages": [{"role": "user", "content": text}], **kw}


def run(port, log_path):
    small, large = electrical.MODELS["small"], electrical.MODELS["large"]
    numeric.ask = fake_ask({small: PROGRAM_22V, large: PROGRAM_22V})
    software.ask = fake_ask({software.MODELS["small"]: DOUBLE})
    seen = []
    general.chat = fake_chat(seen)
    general.chat_stream = fake_chat_stream
    ollama.version = lambda timeout=5: "0.0-fake"

    status, _, body = call(port, "GET", "/v1/models")
    ids = [m["id"] for m in json.loads(body)["data"]]
    expect("models lists both ids", status == 200 and ids == ["plm-router", "plm-router-thorough"], body)

    status, _, body = call(port, "GET", "/health")
    expect("health ok when Ollama answers", status == 200 and json.loads(body)["status"] == "ok"
           and json.loads(body)["ollama"] == "0.0-fake", body)

    def down(timeout=5):
        raise urllib.error.URLError("connection refused")
    ollama.version = down
    status, _, body = call(port, "GET", "/health")
    expect("health 503 when Ollama is down", status == 503 and json.loads(body)["status"] == "unavailable", body)

    q = "A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?"
    status, headers, body = call(port, "POST", "/v1/chat/completions", chat_body(q))
    r = json.loads(body)
    expect("electrical completion shape", status == 200 and r["object"] == "chat.completion"
           and r["choices"][0]["message"] == {"role": "assistant", "content": "22 V"}
           and r["choices"][0]["finish_reason"] == "stop" and r["model"] == "plm-router", body)
    expect("electrical report", r["plm"]["pack"] == "electrical" and r["plm"]["trusted"] is True
           and r["plm"]["steps"][0]["model"] == small, r.get("plm"))
    expect("usage adds up", r["usage"]["total_tokens"] == r["usage"]["prompt_tokens"] + r["usage"]["completion_tokens"]
           and r["usage"]["prompt_tokens"] == 7, r["usage"])

    status, _, body = call(port, "POST", "/v1/chat/completions",
                           chat_body("A 220 ohm resistor carries 0.1 A. What is the voltage across it?"))
    content = json.loads(body)["choices"][0]["message"]["content"]
    expect("unchecked electrical answer says so", content.startswith("22 V") and "(unchecked:" in content, content)

    task = [{"type": "text", "text": "Write a function `double(x: int) -> int` that returns twice x."},
            {"type": "text", "text": "assert double(2) == 4"}]
    status, _, body = call(port, "POST", "/v1/chat/completions",
                           {"model": "plm-router", "messages": [{"role": "system", "content": "be brief"},
                                                                {"role": "user", "content": task}]})
    r = json.loads(body)
    expect("software via content parts", status == 200 and r["plm"]["pack"] == "software" and r["plm"]["trusted"]
           and r["choices"][0]["message"]["content"].startswith("```python\ndef double"), body)

    history = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello!"},
               {"role": "developer", "content": "Answer in one sentence."},
               {"role": "user", "content": "What's the capital of Australia?"}]
    status, _, body = call(port, "POST", "/v1/chat/completions",
                           {"model": "plm-router", "messages": history, "temperature": 0.2, "max_tokens": 64})
    r = json.loads(body)
    expect("general completion", status == 200 and r["plm"]["pack"] == "general" and r["plm"]["checked"] is False
           and r["choices"][0]["message"]["content"] == "Canberra is the capital of Australia.", body)
    msgs, opts, budget = seen[-1]
    expect("general gets the whole conversation", [m["role"] for m in msgs] == ["user", "assistant", "system", "user"]
           and opts == {"temperature": 0.2} and budget == 64, seen[-1])

    status, headers, body = call(port, "POST", "/v1/chat/completions",
                                 chat_body("What's the capital of Australia?", stream=True,
                                           stream_options={"include_usage": True}))
    events, _ = sse_events(body)
    text = "".join(e["choices"][0]["delta"].get("content", "") for e in events
                   if isinstance(e, dict) and e.get("choices"))
    expect("general streams token by token", status == 200 and headers["Content-Type"] == "text/event-stream"
           and text == "Canberra is the capital." and len(events) >= 7 and events[-1] == "[DONE]", events)
    finals = [e for e in events if isinstance(e, dict) and e.get("choices") and e["choices"][0]["finish_reason"]]
    expect("stream's last chunk carries finish_reason and plm", len(finals) == 1 and "plm" in finals[0]
           and finals[0]["plm"]["pack"] == "general", finals)
    expect("include_usage adds a usage chunk", any(isinstance(e, dict) and e.get("choices") == [] and "usage" in e
                                                   for e in events), events)

    numeric.ask = fake_ask({small: PROGRAM_22V}, delay=0.35)
    server.KEEPALIVE_S = 0.1
    status, _, body = call(port, "POST", "/v1/chat/completions", chat_body(q, stream=True))
    events, comments = sse_events(body)
    contents = [e["choices"][0]["delta"]["content"] for e in events
                if isinstance(e, dict) and e.get("choices") and e["choices"][0]["delta"].get("content")]
    expect("pack answers stream as one chunk", contents == ["22 V"] and events[-1] == "[DONE]", events)
    expect("keepalive comments while routing", comments >= 1, comments)
    server.KEEPALIVE_S = 10
    numeric.ask = fake_ask({small: PROGRAM_22V})

    testgen_calls = []
    import plm_software.testgen as testgen
    testgen.ask = lambda model, prompt, think, n, timeout: (testgen_calls.append(model) or
                                                           reply("```python\ndouble(5) == 10\n```"))
    status, _, body = call(port, "POST", "/v1/chat/completions",
                           {"model": "plm-router-thorough",
                            "messages": [{"role": "user", "content": "Write a function `double(x: int) -> int`.\n"
                                                                     "assert double(2) == 4"}]})
    r = json.loads(body)
    expect("thorough model id turns on generated tests", status == 200 and "test_writer" in r["plm"]
           and testgen_calls == [software.MODELS["large"]], body)

    for name, raw, want in [("invalid JSON", b"{nope", 400), ("not an object", b"[1, 2]", 400),
                            ("no messages", json.dumps({"model": "plm-router"}).encode(), 400),
                            ("no user text", json.dumps({"messages": [{"role": "system", "content": "x"}]}).encode(), 400),
                            ("bad max_tokens", json.dumps(chat_body("hi", max_tokens=0)).encode(), 400),
                            ("unknown model", json.dumps({**chat_body("hi"), "model": "gpt-4o"}).encode(), 404)]:
        status, _, body = call(port, "POST", "/v1/chat/completions", raw=raw)
        expect(f"{name} -> {want}", status == want and "error" in json.loads(body), (status, body))
    status, _, body = call(port, "GET", "/v1/nope")
    expect("unknown path -> 404", status == 404, status)

    def refused(*a, **k):
        raise urllib.error.URLError("connection refused")
    numeric.ask = refused
    status, _, body = call(port, "POST", "/v1/chat/completions", chat_body(q))
    expect("Ollama down during a request -> 502", status == 502 and
           json.loads(body)["error"]["code"] == "ollama_unreachable", (status, body))
    status, _, body = call(port, "POST", "/v1/chat/completions", chat_body(q, stream=True))
    events, _ = sse_events(body)
    expect("Ollama down mid-stream -> error event", any(isinstance(e, dict) and "error" in e for e in events)
           and events[-1] == "[DONE]", events)

    logged = [json.loads(line) for line in open(log_path)]
    expect("requests are logged with their pack", [e["pack"] for e in logged][:3] == ["electrical", "electrical", "software"]
           and all("task" in e for e in logged), [e.get("pack") for e in logged])

    for host, want in [("127.0.0.1", True), ("localhost", True), ("::1", True), ("0.0.0.0", False),
                       ("192.168.1.5", False), ("example.com", False)]:
        expect(f"is_loopback({host})", server.is_loopback(host) is want)


def main():
    real = (numeric.ask, software.ask, general.chat, general.chat_stream, ollama.version)
    import plm_software.testgen as testgen
    real_testgen = testgen.ask
    with tempfile.TemporaryDirectory() as tmp:
        log_path = os.path.join(tmp, "server.jsonl")
        os.environ["PLM_SERVER_LOG"] = log_path
        srv = server.make_server("127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            run(srv.server_address[1], log_path)
        finally:
            srv.shutdown()
            srv.server_close()
            numeric.ask, software.ask, general.chat, general.chat_stream, ollama.version = real
            testgen.ask = real_testgen
    for f in FAILS:
        print("FAIL", f)
    print(f"server tests: {'all passed' if not FAILS else f'{len(FAILS)} failed'}")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
