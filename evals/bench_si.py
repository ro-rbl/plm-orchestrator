"""Unit-prefix handling (plm.numeric.si, shipped 2026-11-12) on the public physics benchmarks: on against off.

    .venv/bin/python evals/bench_si.py            # resumes; results/bench_si.jsonl
    .venv/bin/python evals/bench_si.py --report

SI_RULE judged si on plm's own sets; this checks the public ones after the fact. For every SciBench, TheoremQA and
UGPhysics (first sample) problem whose text si.normalize changes (105 of 406; the rest get the same model call either
way), the shipped physics pack answers with si off and on, graded by each benchmark's own grader (value within its
tolerance). Fixed 2026-11-13 before running: report on - off per benchmark; if the total is below -3, turn si off for
the physics pack in the next release and say so in NEXT.md; otherwise leave it. Not a headline number: the headline
table's benchmark scores were measured per model and strategy, not through the pack.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import bench_physics  # noqa: E402
import physics_check  # noqa: E402
import plm.ollama as ol  # noqa: E402
from plm import packs  # noqa: E402
from plm.numeric import si  # noqa: E402

OUT = ROOT / "results/bench_si.jsonl"


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def problems():
    out = []
    for bench in ("scibench", "theoremqa"):
        bench_physics.BENCH = bench
        out += [(bench, p) for p in bench_physics.problems()]
    physics_check.SET = "first"
    out += [("ugphysics", p) for p in physics_check.problems()]
    return [(b, p) for b, p in out if si.normalize(p["question"]) != p["question"]]


def run():
    done = {(r["id"], r["si"]) for r in load(OUT)} if OUT.exists() else set()
    timeouts = 0
    with OUT.open("a") as f:
        for bench, p in problems():
            for on in (False, True):
                if (p["id"], on) in done:
                    continue
                si.ENABLED = on
                try:
                    r = packs.PACKS["physics"].solve(p["question"])
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
                    r = {"answer": None, "tokens": 0, "trusted": False}
                a = r["answer"]
                ok = bool(a) and bench_physics.correct(f"ANSWER: {a['value']} {a['unit']}", p["answer"])
                f.write(json.dumps({"id": p["id"], "bench": bench, "si": on, "right": ok, "answer": a,
                                    "trusted": r.get("trusted"), "tokens": r["tokens"]}) + "\n")
                f.flush()
                print(f"{p['id']} si={'on ' if on else 'off'} {'right' if ok else 'WRONG'} {a}", flush=True)
    si.ENABLED = True


def report():
    got = {(r["id"], r["si"]): r for r in (load(OUT) if OUT.exists() else [])}
    todo = problems()
    both = [(b, p) for b, p in todo if (p["id"], False) in got and (p["id"], True) in got]
    total = 0
    for bench in ("scibench", "theoremqa", "ugphysics"):
        ids = [p["id"] for b, p in both if b == bench]
        off, on = sum(got[i, False]["right"] for i in ids), sum(got[i, True]["right"] for i in ids)
        total += on - off
        print(f"{bench}: {len(ids)} of {sum(b == bench for b, _ in todo)} changed problems answered, off {off}, on {on} ({on - off:+d})")
    done = len(both) == len(todo)
    print(f"total on - off: {total:+d}{'' if done else '  (PARTIAL)'}")
    if done:
        print("-> " + ("turn si off for the physics pack" if total < -3 else "leave si on"))


if __name__ == "__main__":
    if "--report" not in sys.argv:
        run()
    report()
