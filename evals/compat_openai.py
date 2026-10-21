"""Check the server against the official `openai` Python client.

    python evals/compat_openai.py --fake                                # in-process server, scripted model replies
    python evals/compat_openai.py --base-url http://127.0.0.1:PORT/v1   # a running `plm serve`, real models

`openai` is not a project dependency: run this with any Python that has `openai`
(and, for --fake, `pint`) installed. Live mode needs only `openai`.
"""

import argparse
import sys
import threading
from pathlib import Path

import openai

ROOT = Path(__file__).resolve().parent.parent
FAILS = []

ELECTRICAL = "A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?"
SOFTWARE = ("Write a function `double(x: int) -> int` that returns twice x.\n"
            "assert double(2) == 4\nassert double(-3) == -6")
GENERAL = "In one sentence: what is the capital of Australia?"


def expect(name, cond, detail=""):
    print(f"{'ok  ' if cond else 'FAIL'} {name}")
    if not cond:
        FAILS.append(f"{name}: {str(detail)[:300]}")


def check(client):
    ids = [m.id for m in client.models.list()]
    expect("models.list() returns both router ids", ids == ["plm-router", "plm-router-thorough"], ids)

    r = client.chat.completions.create(model="plm-router", messages=[{"role": "user", "content": ELECTRICAL}])
    plm = (r.model_extra or {}).get("plm", {})
    expect("electrical: answer 22 V", r.choices[0].message.content.startswith("22 V"), r.choices[0].message.content)
    expect("electrical: plm report readable from the SDK object", plm.get("pack") == "electrical" and plm.get("trusted"), plm)
    expect("electrical: usage adds up", r.usage.total_tokens == r.usage.prompt_tokens + r.usage.completion_tokens > 0,
           r.usage)

    r = client.chat.completions.create(model="plm-router", messages=[{"role": "user", "content": SOFTWARE}])
    plm = (r.model_extra or {}).get("plm", {})
    expect("software: code block that passed the examples", r.choices[0].message.content.startswith("```python")
           and plm.get("pack") == "software" and plm.get("trusted"), (r.choices[0].message.content, plm))

    chunks = list(client.chat.completions.create(
        model="plm-router", stream=True, stream_options={"include_usage": True},
        messages=[{"role": "system", "content": "Be brief."}, {"role": "user", "content": GENERAL}]))
    text = "".join(c.choices[0].delta.content or "" for c in chunks if c.choices)
    finals = [c for c in chunks if c.choices and c.choices[0].finish_reason]
    usage = [c.usage for c in chunks if not c.choices and c.usage]
    expect("general stream: text arrives in pieces", "Canberra" in text and len(chunks) >= 4, (text, len(chunks)))
    expect("general stream: one final chunk with finish_reason and plm", len(finals) == 1
           and (finals[0].model_extra or {}).get("plm", {}).get("pack") == "general", finals)
    expect("general stream: include_usage chunk", len(usage) == 1 and usage[0].total_tokens > 0, usage)

    chunks = list(client.chat.completions.create(model="plm-router", stream=True,
                                                 messages=[{"role": "user", "content": ELECTRICAL}]))
    text = "".join(c.choices[0].delta.content or "" for c in chunks if c.choices)
    expect("electrical stream: whole checked answer", text.startswith("22 V"), text)

    try:
        client.chat.completions.create(model="gpt-4o", messages=[{"role": "user", "content": "hi"}])
        expect("unknown model raises NotFoundError", False, "no error")
    except openai.NotFoundError as e:
        expect("unknown model raises NotFoundError", "plm-router" in str(e), e)
    try:
        client.chat.completions.create(model="plm-router", messages=[])
        expect("empty messages raises BadRequestError", False, "no error")
    except openai.BadRequestError:
        expect("empty messages raises BadRequestError", True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url")
    ap.add_argument("--fake", action="store_true", help="start an in-process server with scripted model replies")
    args = ap.parse_args()
    print(f"openai {openai.__version__}")
    restore = srv = None
    if args.fake:
        sys.path[:0] = [str(ROOT), str(ROOT / "evals")]
        import plm.server as server
        import test_server
        restore = test_server.install_fakes()
        srv = server.make_server("127.0.0.1", 0)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base_url = f"http://127.0.0.1:{srv.server_address[1]}/v1"
    elif args.base_url:
        base_url = args.base_url
    else:
        ap.error("pass --fake or --base-url")
    try:
        check(openai.OpenAI(base_url=base_url, api_key="unused", max_retries=0, timeout=900))
    finally:
        if srv:
            srv.shutdown()
            srv.server_close()
            restore()
    print(f"openai client compatibility: {'all passed' if not FAILS else f'{len(FAILS)} failed'}")
    for f in FAILS:
        print("FAIL", f)
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
