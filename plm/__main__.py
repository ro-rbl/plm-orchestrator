"""Command line: paste a task, get an answer plus a report of what ran.

    .venv/bin/python -m plm "A 9 V supply feeds a divider of 10 kilohm over 4.7 kilohm. Output voltage in volts?"
    .venv/bin/python -m plm 'Write a function `is_leap(year: int) -> bool` ...'    # software pack
    .venv/bin/python -m plm < task.txt      # multi-line tasks, e.g. with assert/>>> example lines
    .venv/bin/python -m plm                 # interactive: one task per line
    .venv/bin/python -m plm --pack software --level intensive --show-work "..."
    .venv/bin/python -m plm --thorough "$(cat task.txt)"   # software: add model-written tests (~4x compute)

The pack is picked from the task text unless --pack is given. Every run is
appended to logs/runs.jsonl (override with PLM_LOG).
"""

import argparse
import json
import os
import re
import sys
import urllib.error
from pathlib import Path

from plm.packs import PACKS, detect

ROOT = Path(__file__).resolve().parent.parent
LOG = Path(os.environ.get("PLM_LOG", ROOT / "logs" / "runs.jsonl"))


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


def print_answer(result):
    ans, note = result["answer"], caveat(result)
    if ans is None:
        print("\nNo answer. Last model output:\n" + result["steps"][-1]["model_text"].strip())
    elif result["pack"] == "software":
        print("\n```python\n" + ans["code"].strip() + "\n```")
        if note:
            print(f"({note})")
    else:
        print(f"\n{ans['value']:.6g} {ans['unit']}".rstrip() + (f"   ({note})" if note else ""))


def report(result, show_work):
    print_answer(result)
    print(f"\npack    {result['pack']}")
    print(f"level   {result['level']}  ({result['reason']})")
    chosen = final_step(result)
    for i, s in enumerate(result["steps"], 1):
        how = {"tool": "calculator", "bare": "direct"}.get(s.get("strategy"), "code")
        status = "ok" if not s["issues"] else "flagged: " + "; ".join(s["issues"])
        if s["issues"] and i < len(result["steps"]):
            status += " -> escalated"
        if s is chosen and i < len(result["steps"]):
            status += "  [answer used: passed the examples and the most generated tests]"
        print(f"step {i}  {short(s['model']):<22} {how:<10} {s['tokens']:>5} tok {s['seconds']:>6.1f} s   {status}")
        if show_work:
            work = s.get("program") or s.get("code") or s["model_text"]
            print("        " + work.strip().replace("\n", "\n        "))
    writer = result.get("test_writer")
    if writer:
        print(f"tests   {short(writer['model']):<22} {'test writer':<10} {writer['tokens']:>5} tok {writer['seconds']:>6.1f} s"
              f"   {len(writer['tests'])} tests")
        if show_work:
            print("        " + "\n        ".join(writer["tests"]))
    calls = len(result["steps"]) + bool(writer)
    print(f"total   {result['tokens']} tokens, {result['seconds']:.1f} s, {calls} model call{'s' if calls > 1 else ''}")


def run_one(task, args):
    if not task.strip():
        # An empty prompt still gets a confident answer from the models, so never send one.
        sys.exit("plm: empty task (if piping a file, check that stdin actually reaches plm)")
    pack = args.pack if args.pack != "auto" else detect(task)
    extra = {}
    if args.thorough:
        if pack == "software":
            extra["thorough"] = True
        else:
            print("plm: --thorough only applies to the software pack; ignoring it", file=sys.stderr)
    try:
        result = PACKS[pack].solve(task, level=args.level, timeout=args.timeout, **extra)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        sys.exit(f"Ollama error {e.code}: {detail}\nModels in use: {PACKS[pack].MODELS} "
                 "(set PLM_SMALL_MODEL / PLM_LARGE_MODEL / PLM_CODER_MODEL)")
    except urllib.error.URLError as e:
        sys.exit(f"Can't reach Ollama ({e.reason}). Is it running? Address comes from OLLAMA_HOST.")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(result) + "\n")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        report(result, args.show_work)


def main():
    ap = argparse.ArgumentParser(prog="plm", description="Adaptive multi-model orchestrator")
    ap.add_argument("task", nargs="*", help="the task; omit for interactive mode")
    ap.add_argument("--pack", choices=["auto", *PACKS], default="auto", help="domain pack (default: detect from the task)")
    ap.add_argument("--level", choices=["calm", "alert", "intensive"], help="force an adrenaline level instead of classifying")
    ap.add_argument("--thorough", action="store_true",
                    help="software: also check code against tests a second model writes (~4x compute)")
    ap.add_argument("--show-work", action="store_true", help="print each model's program or reasoning")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per model call")
    args = ap.parse_args()

    if args.task:
        run_one(" ".join(args.task), args)
    elif not sys.stdin.isatty():
        run_one(sys.stdin.read().strip(), args)
    else:
        print("plm: one task per line, empty line to quit")
        while True:
            try:
                task = input("\ntask> ").strip()
            except EOFError:
                break
            if not task:
                break
            run_one(task, args)


if __name__ == "__main__":
    main()
