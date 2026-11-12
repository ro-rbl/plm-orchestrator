"""SI_RULE (b): the packs' own problems with plm.numeric.si on and off (a regression guard; these sets are seen).

    .venv/bin/python evals/si_regression.py            # resumes; results/si_regression.jsonl
    .venv/bin/python evals/si_regression.py --report

For each problem in evals/{electrical,aerospace,physics}/problems.jsonl whose text si.normalize changes, the shipped
pack answers it with si off and on (unchanged problems get the same model call either way, so they can't differ and
aren't run). Graded by evals/grade.py. SI_RULE (b), fixed 2026-11-10 with evals/followup/run4.py: right answers with
si on minus off >= -2 in total and >= -2 in each pack.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import plm.ollama as ol  # noqa: E402
from grade import grade_one  # noqa: E402
from plm import packs  # noqa: E402
from plm.numeric import si  # noqa: E402

OUT = ROOT / "results/si_regression.jsonl"
PACKS = ("electrical", "aerospace", "physics")


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def problems():
    for pack in PACKS:
        for p in load(ROOT / f"evals/{pack}/problems.jsonl"):
            if si.normalize(p["question"]) != p["question"]:
                yield pack, p


def run():
    done = {(r["id"], r["si"]) for r in load(OUT)} if OUT.exists() else set()
    timeouts = 0
    with OUT.open("a") as f:
        for pack, p in problems():
            for on in (False, True):
                if (p["id"], on) in done:
                    continue
                si.ENABLED = on
                try:
                    r = packs.PACKS[pack].solve(p["question"])
                    timeouts = 0
                except TimeoutError as e:
                    timeouts += 1
                    print(f"{p['id']} timed out ({timeouts} in a row): {e}", flush=True)
                    if timeouts >= 3:
                        sys.exit("3 timeouts in a row; stopped, resume to retry")
                    continue
                except Exception as e:
                    if ol.unreachable(e):
                        sys.exit(f"Ollama unreachable ({e}); stopped, resume to retry")
                    r = {"answer": None, "tokens": 0}
                a = r["answer"]
                ok = bool(a) and grade_one(p, f"ANSWER: {a['value']} {a['unit']}")["verdict"] == "correct"
                f.write(json.dumps({"id": p["id"], "pack": pack, "si": on, "right": ok, "answer": a, "tokens": r["tokens"]}) + "\n")
                f.flush()
                print(f"{p['id']} si={'on ' if on else 'off'} {'right' if ok else 'WRONG'} {a}", flush=True)
    si.ENABLED = False


def report():
    rows = load(OUT) if OUT.exists() else []
    got = {(r["id"], r["si"]): r for r in rows}
    todo = list(problems())
    if not all((p["id"], on) in got for _, p in todo for on in (False, True)):
        return print(f"si regression incomplete: {len(got)}/{2 * len(todo)}")
    ok, total = True, 0
    for pack in PACKS:
        ids = [p["id"] for k, p in todo if k == pack]
        off, on = sum(got[i, False]["right"] for i in ids), sum(got[i, True]["right"] for i in ids)
        total += on - off
        ok &= on - off >= -2
        print(f"{pack}: {len(ids)} changed problems, off {off}, on {on} ({on - off:+d})")
    ok &= total >= -2
    print(f"total on - off: {total:+d}\nSI_RULE (b) -> {'pass' if ok else 'FAIL'}")


if __name__ == "__main__":
    if "--report" not in sys.argv:
        run()
    report()
