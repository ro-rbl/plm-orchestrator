"""Command line: paste a task, get an answer plus a report of what ran.

    .venv/bin/python -m plm "A 9 V supply feeds a divider of 10 kilohm over 4.7 kilohm. Output voltage in volts?"
    .venv/bin/python -m plm 'Write a function `is_leap(year: int) -> bool` ...'    # software pack
    .venv/bin/python -m plm < task.txt      # multi-line tasks, e.g. with assert/>>> example lines
    .venv/bin/python -m plm                 # interactive: one task per line
    .venv/bin/python -m plm --pack software --level intensive --show-work "..."
    .venv/bin/python -m plm --thorough "$(cat task.txt)"   # software: add model-written tests (~4x compute)
    .venv/bin/python -m plm --sql-db shop.sqlite "Which customers ordered twice?"   # sql pack, checked on the data
    .venv/bin/python -m plm serve           # OpenAI-compatible server, see plm/server.py
    .venv/bin/python -m plm packs list      # installed packs; also install / remove / doctor, see plm/manage.py

The pack is picked from the task text unless --pack is given. Every run is
appended to runs.jsonl in plm.paths.log_dir() (./logs in a checkout; override with PLM_LOG).
"""

import argparse
import json
import os
import sys
import urllib.error
from pathlib import Path

from plm.paths import log_dir
from plm.display import unmark
from plm.report import answer_text, final_step, short

LOG = Path(os.environ.get("PLM_LOG") or log_dir() / "runs.jsonl")


def how(step):
    if step.get("strategy"):
        return {"tool": "calculator", "units": "units calc", "bare": "direct"}[step["strategy"]]
    return "code" if "code" in step else "chat"


def report(result, show_work):
    print("\n" + unmark(answer_text(result)))  # no emoji, #, ** in a terminal that doesn't render Markdown
    print(f"\npack    {result['pack']}")
    print(f"level   {result['level']}  ({result['reason']})")
    chosen = final_step(result)
    for i, s in enumerate(result["steps"], 1):
        status = "ok" if not s["issues"] else "flagged: " + "; ".join(s["issues"])
        if s["issues"] and i < len(result["steps"]):
            status += " -> escalated"
        if s is chosen and i < len(result["steps"]):
            status += f"  [answer used: {result.get('chosen_note') or 'passed the examples and the most generated tests'}]"
        if not result["checked"] and not s["issues"]:
            status = "unchecked"
        print(f"step {i}  {short(s['model']):<22} {how(s):<10} {s['tokens']:>5} tok {s['seconds']:>6.1f} s   {status}")
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
    if result["pack"] == "general":
        print(f"note    {result['unchecked_reason']}")


def run_one(task, args, history=()):
    """Solve one task; `history` is the interactive session's earlier messages, for follow-ups (plm.followup)."""
    from plm.followup import phrase, resolve
    from plm.packs import PACKS, detect

    if not task.strip():
        # An empty prompt still gets a confident answer from the models, so never send one.
        sys.exit("plm: empty task (if piping a file, check that stdin actually reaches plm)")
    pack = args.pack if args.pack != "auto" else "sql" if args.sql_db else detect(task)
    if history and args.pack == "auto" and not args.sql_db:
        convo = [*history, {"role": "user", "content": task}]
        routed = resolve(convo)
        if routed["pack"] != "general" and (routed["context"] or "anchor" in routed):
            pack, task = routed["pack"], phrase(convo, routed)
            if routed["context"]:
                print(f"(follow-up: kept in {pack}, with the earlier question)")
    extra = {}
    if args.sql_db:
        if pack == "sql":
            extra["db"] = args.sql_db
        else:
            print(f"plm: --sql-db only applies to the sql pack; ignoring it for {pack}", file=sys.stderr)
    if args.thorough:
        if pack == "software":
            extra["thorough"] = True
        else:
            print("plm: --thorough only applies to the software pack; ignoring it", file=sys.stderr)
    if pack == "general":
        from plm.general.controller import styled
        extra["messages"] = styled([{"role": "user", "content": task}])
    try:
        result = PACKS[pack].solve(task, level=args.level, timeout=args.timeout, **extra)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        sys.exit(f"Ollama error {e.code}: {detail}\nModels in use: {PACKS[pack].models} "
                 "(set PLM_SMALL_MODEL / PLM_LARGE_MODEL / PLM_CODER_MODEL)")
    except urllib.error.URLError as e:
        sys.exit(f"Can't reach Ollama ({e.reason}). Is it running? Address comes from OLLAMA_HOST.")
    except ValueError as e:  # a --sql-db / PLM_SQL_DB file that can't be opened
        sys.exit(f"plm: {e}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(result) + "\n")
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        report(result, args.show_work)
    return result


def main():
    if sys.argv[1:2] == ["packs"]:
        # before importing plm.packs, which refuses to start with a broken pack installed
        from plm.manage import main as packs
        return packs(sys.argv[2:])
    try:  # a broken pack is a one-line message (it names `plm packs remove`), not a traceback
        if sys.argv[1:2] == ["serve"]:
            from plm.server import main as serve
        else:
            from plm.packs import PACKS
    except RuntimeError as e:
        sys.exit(f"plm: {e}")
    if sys.argv[1:2] == ["serve"]:
        return serve(sys.argv[2:])

    ap = argparse.ArgumentParser(prog="plm", description="Adaptive multi-model orchestrator "
                                 "('plm serve' for the server, 'plm packs' to manage packs)")
    ap.add_argument("task", nargs="*", help="the task; omit for interactive mode")
    ap.add_argument("--pack", choices=["auto", *PACKS], default="auto", help="domain pack (default: detect from the task)")
    ap.add_argument("--level", choices=["calm", "alert", "intensive"], help="force an adrenaline level instead of classifying")
    ap.add_argument("--thorough", action="store_true",
                    help="software: also check code against tests a second model writes (~4x compute)")
    ap.add_argument("--sql-db", metavar="FILE", help="sql: a SQLite database to read the schema from and check the query "
                    "on, read-only (implies --pack sql; the server reads PLM_SQL_DB)")
    ap.add_argument("--show-work", action="store_true", help="print each model's program or reasoning")
    ap.add_argument("--json", action="store_true", help="print the full result as JSON")
    ap.add_argument("--timeout", type=int, default=600, help="seconds per model call")
    ap.add_argument("--plain", action="store_true", help="with no task: line-by-line mode instead of the full screen")
    args = ap.parse_args()

    if args.task:
        run_one(" ".join(args.task), args)
    elif not sys.stdin.isatty():
        run_one(sys.stdin.read().strip(), args)
    elif not args.plain and args.pack == "auto" and not args.sql_db and not args.json:
        try:
            from plm import tui
        except ImportError:
            print('plm: the full-screen interface needs Textual: pip install "plm-core[tui]" '
                  "(plain line mode below; --plain to skip this note)\n")
        else:
            return tui.main()
        run_interactive(args)
    else:
        run_interactive(args)


def run_interactive(args):
    """Line-by-line mode: one task per line, with follow-ups."""
    print("plm: one task per line, empty line to quit; follow-ups like 'now for 200 ohm' use the earlier question")
    history = []
    while True:
        try:
            task = input("\ntask> ").strip()
        except EOFError:
            break
        if not task:
            break
        result = run_one(task, args, history)
        history += [{"role": "user", "content": task},
                    {"role": "assistant", "content": answer_text(result)}]


if __name__ == "__main__":
    main()
