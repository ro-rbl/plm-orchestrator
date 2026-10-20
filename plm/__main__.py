"""Command line: paste a task, get an answer plus a report of what ran.

    .venv/bin/python -m plm "A 9 V supply feeds a divider of 10 kilohm over 4.7 kilohm. Output voltage in volts?"
    .venv/bin/python -m plm 'Write a function `is_leap(year: int) -> bool` ...'    # software pack
    .venv/bin/python -m plm < task.txt      # multi-line tasks, e.g. with assert/>>> example lines
    .venv/bin/python -m plm                 # interactive: one task per line
    .venv/bin/python -m plm --pack software --level intensive --show-work "..."

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

from plm import controller as electrical
from plm.software import controller as software

ROOT = Path(__file__).resolve().parent.parent
LOG = Path(os.environ.get("PLM_LOG", ROOT / "logs" / "runs.jsonl"))
PACKS = {"electrical": electrical, "software": software}
SOFTWARE_TASK = re.compile(r"\b(?:write|implement|create|code)\b.{0,40}\b(?:function|class|method|program)\b|\bdef \w+\s*\(",
                           re.IGNORECASE | re.DOTALL)


def detect_pack(text):
    return "software" if SOFTWARE_TASK.search(text) else "electrical"


def short(model):
    # hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M -> Qwen3-4B-abliterated
    if "/" not in model:
        return model
    return re.sub(r"^[^_]*_|-GGUF.*$", "", model.rsplit("/", 1)[-1])


def print_answer(result):
    ans, issues = result["answer"], "; ".join(result["steps"][-1]["issues"])
    if ans is None:
        print("\nNo answer. Last model output:\n" + result["steps"][-1]["model_text"].strip())
    elif result["pack"] == "software":
        print("\n```python\n" + ans["code"].strip() + "\n```")
        if not result["trusted"]:
            print(f"(unverified: {issues})")
    elif result["trusted"]:
        print(f"\n{ans['value']:.6g} {ans['unit']}".rstrip())
    else:
        print(f"\n{ans['value']:.6g} {ans['unit']}   (unverified: {issues})")


def report(result, show_work):
    print_answer(result)
    print(f"\npack    {result['pack']}")
    print(f"level   {result['level']}  ({result['reason']})")
    for i, s in enumerate(result["steps"], 1):
        how = {"tool": "calculator", "bare": "direct"}.get(s.get("strategy"), "code")
        status = "ok" if not s["issues"] else "flagged: " + "; ".join(s["issues"])
        if s["issues"] and i < len(result["steps"]):
            status += " -> escalated"
        print(f"step {i}  {short(s['model']):<22} {how:<10} {s['tokens']:>5} tok {s['seconds']:>6.1f} s   {status}")
        if show_work:
            work = s.get("program") or s.get("code") or s["model_text"]
            print("        " + work.strip().replace("\n", "\n        "))
    calls = len(result["steps"])
    print(f"total   {result['tokens']} tokens, {result['seconds']:.1f} s, {calls} model call{'s' if calls > 1 else ''}")


def run_one(task, args):
    if not task.strip():
        # An empty prompt still gets a confident answer from the models, so never send one.
        sys.exit("plm: empty task (if piping a file, check that stdin actually reaches plm)")
    pack = args.pack if args.pack != "auto" else detect_pack(task)
    try:
        result = PACKS[pack].solve(task, level=args.level, timeout=args.timeout)
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
    ap.add_argument("--level", choices=list(electrical.LEVELS), help="force an adrenaline level instead of classifying")
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
