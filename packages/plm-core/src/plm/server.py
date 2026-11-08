"""OpenAI-compatible server: the router as one model, `plm-router`.

    .venv/bin/python -m plm serve                 # picks a free port and prints it
    .venv/bin/python -m plm serve --port 8800     # or PLM_PORT=8800

Point any OpenAI-compatible client at http://127.0.0.1:<port>/v1 with any API key.

    GET  /health                 200 {"status": "ok", ...} if Ollama answers, else 503
    GET  /v1/models              plm-router, plm-router-thorough
    POST /v1/chat/completions    with or without "stream": true

Each request goes to the pack plm.packs.detect picks from the last user message, unless that message is a
follow-up to an earlier pack question (plm.followup): then it stays in that pack, with the question it changes.
Pack answers are released only after they're checked, so with "stream": true they
arrive as one chunk, with SSE comments keeping the connection alive meanwhile;
general answers stream token by token. The routing report is an extra top-level
"plm" field (on the last chunk when streaming), which clients that don't know it
ignore. Pack answers end with a caveat line when they failed a check or had
nothing to check against; general answers are never checked (see "plm").

Not supported: tool calling (tools are ignored), images, n > 1.

Only loopback addresses are served unless --allow-remote: there is no
authentication, and the software pack runs model-written code.
"""

import argparse
import json
import os
import signal
import socket
import sys
import threading
import time
import traceback
import urllib.error
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path

from plm import followup, ollama, packs
from plm.paths import log_dir
from plm.report import answer_text, final_step

LOG_DIR = log_dir()  # ./logs in a checkout, else the user's state folder (plm.paths)
MODEL_IDS = {"plm-router": {}, "plm-router-thorough": {"thorough": True}}
MAX_BODY = 10 * 1024 * 1024
KEEPALIVE_S = 10
STARTED = int(time.time())
_log_lock = threading.Lock()


class RequestError(Exception):
    def __init__(self, status, message, code=None):
        super().__init__(message)
        self.status, self.code = status, code


def is_loopback(host):
    if host == "localhost":
        return True
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def text_of(content):
    """Message content as text: a string, or the text parts of a list of content parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""


def parse_request(body):
    """Validate a chat-completions body; returns what the router needs from it."""
    try:
        req = json.loads(body or b"null")
    except json.JSONDecodeError as e:
        raise RequestError(400, f"request body is not valid JSON: {e}")
    if not isinstance(req, dict):
        raise RequestError(400, "request body must be a JSON object")
    model = req.get("model") or "plm-router"
    if model not in MODEL_IDS:
        raise RequestError(404, f"unknown model {model!r}; available: {', '.join(MODEL_IDS)}", "model_not_found")
    if not isinstance(req.get("messages"), list) or not req["messages"]:
        raise RequestError(400, "'messages' must be a non-empty list")
    messages = []
    for m in req["messages"]:
        if not isinstance(m, dict):
            raise RequestError(400, "each message must be a JSON object")
        role = {"developer": "system"}.get(m.get("role"), m.get("role"))
        if role in ("system", "user", "assistant"):  # tool results are dropped: tools aren't supported
            messages.append({"role": role, "content": text_of(m.get("content"))})
    users = [m["content"] for m in messages if m["role"] == "user" and m["content"].strip()]
    if not users:
        raise RequestError(400, "no user message with text content")
    max_tokens = req.get("max_completion_tokens") or req.get("max_tokens")
    if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens < 1):
        raise RequestError(400, "max_tokens must be a positive integer")
    options = {k: req[k] for k in ("temperature", "top_p") if isinstance(req.get(k), (int, float))}
    if isinstance(req.get("seed"), int):
        options["seed"] = req["seed"]
    return {
        "model": model,
        "messages": messages,
        "task": users[-1].strip(),
        "stream": bool(req.get("stream")),
        "include_usage": bool((req.get("stream_options") or {}).get("include_usage")),
        "options": options,
        "max_tokens": max_tokens,
    }


def solve(req, pack):
    if pack == "general":
        return packs.PACKS["general"].solve(req["task"], messages=req["messages"], options=req["options"],
                                            max_tokens=req["max_tokens"])
    extra = MODEL_IDS[req["model"]] if pack == "software" else {}
    return packs.PACKS[pack].solve(req["task"], **extra)


def usage(result):
    calls = result["steps"] + ([result["test_writer"]] if result.get("test_writer") else [])
    prompt = sum(c.get("prompt_tokens", 0) for c in calls)
    return {"prompt_tokens": prompt, "completion_tokens": result["tokens"], "total_tokens": prompt + result["tokens"]}


def finish_reason(result):
    return "length" if final_step(result).get("capped") else "stop"


def plm_report(result):
    """The routing report: which pack and models ran, what was checked, what it cost."""
    keep = ("model", "strategy", "tokens", "prompt_tokens", "seconds", "issues", "capped")
    report = {k: result.get(k) for k in ("pack", "level", "reason", "trusted", "checked", "unchecked_reason",
                                         "tokens", "seconds")}
    report["steps"] = [{k: s[k] for k in keep if k in s} for s in result["steps"]]
    if result.get("final_step"):
        report["final_step"] = result["final_step"]
    if result.get("test_writer"):
        report["test_writer"] = {k: result["test_writer"][k] for k in ("model", "tokens", "seconds", "tests")}
    return report


def log_request(req, pack, result, stream):
    target = os.environ.get("PLM_SERVER_LOG", str(LOG_DIR / "server.jsonl"))
    if target == "off":
        return
    entry = {"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": req["model"], "stream": stream, "pack": pack,
             "level": result["level"], "trusted": result["trusted"], "checked": result["checked"],
             "tokens": result["tokens"], "seconds": round(result["seconds"], 2),
             "calls": [{"model": s["model"], "tokens": s["tokens"]} for s in result["steps"]],
             "context": req.get("context", False), "task": req["task"][:500]}
    Path(target).parent.mkdir(parents=True, exist_ok=True)
    with _log_lock, open(target, "a") as f:
        f.write(json.dumps(entry) + "\n")


def upstream_error(e):
    """Map an exception from a model call to (status, OpenAI-style error body)."""
    if isinstance(e, urllib.error.HTTPError):
        detail = e.read().decode(errors="replace")[:300]
        return 502, {"message": f"Ollama error {e.code}: {detail}", "type": "upstream_error", "code": "ollama_error"}
    if isinstance(e, (urllib.error.URLError, ConnectionError, TimeoutError, socket.timeout)):
        reason = getattr(e, "reason", e)
        return 502, {"message": f"can't reach Ollama at {ollama.ollama_url()}: {reason}", "type": "upstream_error",
                     "code": "ollama_unreachable"}
    traceback.print_exc()
    return 500, {"message": f"{type(e).__name__}: {e}", "type": "server_error", "code": None}


class Handler(BaseHTTPRequestHandler):
    server_version = "plm"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"plm serve: {self.address_string()} {fmt % args}\n")

    def _json(self, status, obj):
        data = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _error(self, status, message, code=None, kind="invalid_request_error"):
        self._json(status, {"error": {"message": message, "type": kind, "code": code}})

    def _path(self):
        return self.path.split("?", 1)[0].rstrip("/") or "/"

    def do_GET(self):
        path = self._path()
        if path == "/health":
            try:
                self._json(200, {"status": "ok", "ollama": ollama.version(), "packs": list(packs.PACKS)})
            except Exception as e:
                self._json(503, {"status": "unavailable", "error": f"can't reach Ollama at {ollama.ollama_url()}: {e}"})
        elif path == "/v1/models":
            self._json(200, {"object": "list", "data": [
                {"id": m, "object": "model", "created": STARTED, "owned_by": "plm"} for m in MODEL_IDS]})
        else:
            self._error(404, f"no route for GET {path}", "not_found")

    def do_POST(self):
        path = self._path()
        if path != "/v1/chat/completions":
            return self._error(404, f"no route for POST {path}", "not_found")
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._error(400, "invalid Content-Length")
        if length > MAX_BODY:
            return self._error(413, "request body too large")
        try:
            req = parse_request(self.rfile.read(length))
        except RequestError as e:
            return self._error(e.status, str(e), e.code)
        routed = followup.resolve(req["messages"])  # a follow-up keeps its conversation's pack and question
        pack, req["context"] = routed["pack"], routed["context"]
        if routed["context"] and pack != "general":  # general already gets the whole conversation
            req["task"] = routed["task"]
        cid, created = "chatcmpl-" + uuid.uuid4().hex, int(time.time())
        if req["stream"]:
            self._stream(req, pack, cid, created)
        else:
            self._complete(req, pack, cid, created)

    def _complete(self, req, pack, cid, created):
        try:
            result = solve(req, pack)
        except Exception as e:
            status, err = upstream_error(e)
            return self._json(status, {"error": err})
        self._json(200, {
            "id": cid, "object": "chat.completion", "created": created, "model": req["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": answer_text(result)},
                         "finish_reason": finish_reason(result)}],
            "usage": usage(result),
            "plm": plm_report(result),
        })
        log_request(req, pack, result, stream=False)

    def _stream(self, req, pack, cid, created):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.close_connection = True  # the stream ends when the connection closes
        lock, done = threading.Lock(), threading.Event()

        def write(raw):
            with lock:
                self.wfile.write(raw)
                self.wfile.flush()

        def send(obj):
            write(f"data: {json.dumps(obj)}\n\n".encode())

        def chunk(delta, finish=None):
            return {"id": cid, "object": "chat.completion.chunk", "created": created, "model": req["model"],
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}

        def keepalive():  # SSE comments; clients ignore them, but they keep proxies and timeouts happy
            while not done.wait(KEEPALIVE_S):
                try:
                    write(b": routing\n\n")
                except OSError:
                    return

        threading.Thread(target=keepalive, daemon=True).start()
        gen = None
        try:
            send(chunk({"role": "assistant", "content": ""}))
            if pack == "general":
                gen = packs.PACKS["general"].solve_stream(req["task"], messages=req["messages"],
                                                          options=req["options"], max_tokens=req["max_tokens"])
                for kind, value in gen:
                    if kind == "delta":
                        send(chunk({"content": value}))
                    else:
                        result = value
            else:
                result = solve(req, pack)
                send(chunk({"content": answer_text(result)}))
            final = chunk({}, finish_reason(result))
            final["plm"] = plm_report(result)
            send(final)
            if req["include_usage"]:
                send({"id": cid, "object": "chat.completion.chunk", "created": created, "model": req["model"],
                      "choices": [], "usage": usage(result)})
            write(b"data: [DONE]\n\n")
            log_request(req, pack, result, stream=True)
        except (BrokenPipeError, ConnectionResetError):
            sys.stderr.write("plm serve: client disconnected mid-stream\n")
        except Exception as e:
            _, err = upstream_error(e)
            try:
                send({"error": err})
                write(b"data: [DONE]\n\n")
            except OSError:
                pass
        finally:
            done.set()
            if gen is not None:
                gen.close()  # closes the Ollama connection, which stops generation


class Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, handler):
        if ":" in address[0]:
            self.address_family = socket.AF_INET6
        super().__init__(address, handler)


def make_server(host="127.0.0.1", port=0):
    return Server((host, port), Handler)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="plm serve", description="OpenAI-compatible server for the plm router")
    ap.add_argument("--host", default=os.environ.get("PLM_HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PLM_PORT", "0")), help="0 picks a free port")
    ap.add_argument("--allow-remote", action="store_true",
                    help="listen on a non-loopback address (no auth; the software pack runs model-written code)")
    args = ap.parse_args(argv)
    if not is_loopback(args.host) and not args.allow_remote:
        sys.exit(f"plm serve: refusing to listen on {args.host}: there is no authentication and the software pack "
                 "runs model-written code. Use --allow-remote if you really mean it.")

    sql_db = os.environ.get("PLM_SQL_DB")
    if sql_db and not Path(sql_db).expanduser().is_file():
        sys.exit(f"plm serve: PLM_SQL_DB is {sql_db!r}, which isn't a file")

    server = make_server(args.host, args.port)
    port = server.server_address[1]
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    pid_file, port_file = LOG_DIR / "plm-serve.pid", LOG_DIR / "plm-serve.port"
    pid_file.write_text(f"{os.getpid()}\n")
    port_file.write_text(f"{port}\n")
    signal.signal(signal.SIGTERM, lambda *_: threading.Thread(target=server.shutdown, daemon=True).start())
    host = f"[{args.host}]" if ":" in args.host else args.host
    print(f"plm serve: listening on http://{host}:{port}/v1 (models: {', '.join(MODEL_IDS)}; pid {os.getpid()})",
          flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if pid_file.exists() and pid_file.read_text().strip() == str(os.getpid()):
            pid_file.unlink()
            port_file.unlink(missing_ok=True)
        print("plm serve: stopped", flush=True)


if __name__ == "__main__":
    main()
