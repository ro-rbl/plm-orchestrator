"""Fresh numeric answers for UNITS2_RULE: the physics pack's calculator step on SciBench subjects never run here.

    .venv/bin/python evals/units_fresh.py --model <ollama model>     # resumes; results/units_fresh__<model>.jsonl

Problems: SciBench's thermo, atkins, matter, chemmc and quan subjects (349; bench_physics.py used only fund and
class), asked as bench_physics.py asks ("... Give the answer in <unit>."). Each answer is saved with its output and
whether it's right (5%, SciBench's rule), so evals/score_units.py --round 2 can replay any check on it.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import bench_physics  # noqa: E402
from plm.numeric.controller import attempt  # noqa: E402
from plm.ollama import unreachable  # noqa: E402

FRESH = ("thermo", "atkins", "matter", "chemmc", "quan")


def problems():
    bench_physics.SOURCES = FRESH
    bench_physics.BENCH = "scibench"
    return bench_physics.problems()


def out_path(model):
    return ROOT / f"results/units_fresh__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.jsonl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    args = ap.parse_args()
    out = out_path(args.model)
    done = {json.loads(line)["id"] for line in open(out)} if out.exists() else set()
    timeouts = 0
    with out.open("a") as f:
        for p in problems():
            if p["id"] in done:
                continue
            try:
                step = attempt(p["question"], args.model, "tool", 1024, 600)
                timeouts = 0
            except TimeoutError as e:
                timeouts += 1
                print(f"{p['id']} timed out ({timeouts} in a row): {e}", flush=True)
                if timeouts >= 3:
                    sys.exit("3 timeouts in a row; stopped, resume to retry")
                continue
            except Exception as e:
                if unreachable(e):
                    sys.exit(f"Ollama unreachable ({e}); stopped, resume to retry")
                step = {"output": "", "tokens": 0, "issues": [f"{type(e).__name__}: {e}"]}
            row = {"id": p["id"], "model": args.model, "output": step["output"], "tokens": step["tokens"],
                   "issues": step["issues"], "correct": bench_physics.correct(step["output"], p["answer"])}
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"{p['id']} {'right' if row['correct'] else 'wrong'} {row['output'].strip()[:60]!r}", flush=True)


if __name__ == "__main__":
    main()
