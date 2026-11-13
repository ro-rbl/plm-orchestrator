"""Follow-up set 5: always rewriting a follow-up first, against what ships (plm-core 0.1.4).

    .venv/bin/python evals/followup/run5.py --variant S     # then R; resumes; results/followup5_<V>.jsonl
    .venv/bin/python evals/followup/run5.py --report        # FOLLOWUP5_RULE

Both variants run the shipped pipeline (as evals/followup/run4.py's variant F: resolve + phrase, the pack, unit
prefixes handled in code), graded the same way (a general-pack reply leniently):
    S  shipped: a follow-up is rewritten into one question only when it asks for another kind of quantity
    R  S + plm.followup.ALWAYS_REWRITE: every message resolved as a follow-up is rewritten first
Why: always-rewrite (B) was +11 over the old wording on set 3 and +0 on set 2, before unit prefixes were fixed; the
shipped pipeline still misses follow-ups that ask for a new quantity (16/23 on set 4).

Graded on evals/followup/cases5.jsonl (80 conversations, build5.py, keys computed in code, written before any
answer). FOLLOWUP5_RULE, fixed 2026-11-13 before any model answered a set-5 case: ship ALWAYS_REWRITE iff the paired
bootstrap 95% interval (2000 resamples, seed 20261113) of R's right answers minus S's over all 80 lies entirely
above 0; otherwise keep S (one model call fewer on most follow-ups). Tokens and per-kind scores reported, not decisive.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import run4  # noqa: E402
from run import load  # noqa: E402

ROOT = run4.ROOT
run4.CASES = CASES = Path(__file__).parent / "cases5.jsonl"
run4.CACHE = ROOT / "results/followup5_cache.jsonl"
ALWAYS = {"S": False, "R": True}


def out_path(variant):
    return ROOT / f"results/followup5_{variant}.jsonl"


def run(variant):
    out = out_path(variant)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    timeouts = 0
    with out.open("a") as f:
        for c in load(CASES):
            if c["id"] in done:
                continue
            run4.fu.ALWAYS_REWRITE = ALWAYS[variant]
            try:
                row = {"id": c["id"], "variant": variant} | run4.run_one(c, "F")
                timeouts = 0
            except TimeoutError as e:  # not saved: a resume retries it
                timeouts += 1
                print(f"{c['id']} timed out ({timeouts} in a row): {e}", flush=True)
                if timeouts >= 3:
                    sys.exit("3 timeouts in a row; stopped, resume to retry")
                continue
            except Exception as e:
                if run4.ol.unreachable(e):
                    sys.exit(f"Ollama unreachable ({e}); stopped, resume to retry")
                row = {"id": c["id"], "variant": variant, "right": False, "tokens": 0, "error": f"{type(e).__name__}: {e}"}
            finally:
                run4.fu.ALWAYS_REWRITE = False
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"{variant} {c['id']} {'right' if row['right'] else 'WRONG'} {row.get('pack')} {str(row.get('answer'))[:60]}", flush=True)


def report():
    cases = load(CASES)
    ids = [c["id"] for c in cases]
    got = {v: {r["id"]: r for r in load(out_path(v))} if out_path(v).exists() else {} for v in ALWAYS}
    if not all(i in got[v] for v in ALWAYS for i in ids):
        return print("set 5 incomplete:", {v: len(got[v]) for v in ALWAYS})
    for v in ALWAYS:
        kinds = ", ".join(f"{k} {sum(got[v][c['id']]['right'] for c in cases if c['kind'] == k)}/"
                          f"{sum(c['kind'] == k for c in cases)}" for k in sorted({c["kind"] for c in cases}))
        print(f"{v}: {sum(got[v][i]['right'] for i in ids)}/{len(ids)} right, {sum(got[v][i]['tokens'] for i in ids)} tokens ({kinds})")
    diff = [got["R"][i]["right"] - got["S"][i]["right"] for i in ids]
    rng = random.Random(20261113)
    boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) for _ in range(2000))
    lo, hi = boot[50], boot[1949]
    print(f"R - S: {sum(diff):+d}, 95% {lo:+d} to {hi:+d}\nFOLLOWUP5_RULE -> {'SHIP ALWAYS_REWRITE' if lo > 0 else 'KEEP SHIPPED'}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=tuple(ALWAYS))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.variant:
        run(args.variant)
    report()


if __name__ == "__main__":
    main()
