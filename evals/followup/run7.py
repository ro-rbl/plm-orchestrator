"""Follow-up set 7: longer conversations (two or three follow-ups), and keeping the first question as the anchor.

    .venv/bin/python evals/followup/run7.py --check         # offline: keys grade themselves; what S and A resolve
    .venv/bin/python evals/followup/run7.py --variant S     # then A, B; resumes; results/followup7_<V>.jsonl
    .venv/bin/python evals/followup/run7.py --report        # FOLLOWUP7_RULE

    S  the repo on 2026-11-13 (plm-core 0.1.5, not yet published): plm.followup.answer, i.e. FOLLOWUP6_RULE's L
       (evals/followup/run6.py: the large model with the whole conversation, the reworded task as fallback)
    A  S + plm.followup.ROOT_ANCHOR: an earlier message that was itself a follow-up never becomes the anchor, so
       the conversation keeps the question all its follow-ups change
    B  qwen3:8b alone as a plain chatbot (as run6.py's B)
Why: sets 1-6 have one follow-up per conversation. Seen live on 2026-11-13: after a lamp question and "now a 60 W
lamp" (right), "how much energy does it use in 3 hours, in watt-hours?" was solved alone and came back 300 Wh
(180), because resolve took "now a 60 W lamp" as the question being followed.

Graded on evals/followup/cases7.jsonl (83 conversations of 5 or 7 messages, build7.py, new anchors, keys computed in
code, written before any answer; only the last message is graded) exactly as set 6 was. Identical model calls are
cached (results/followup7_cache.jsonl).

FOLLOWUP7_RULE, fixed 2026-11-13 before any model answered a set-7 case. Paired bootstrap 95% intervals (2000
resamples, seed 20261115) of the difference in right answers over all 83. Ship ROOT_ANCHOR iff
    (a) the interval of A - S lies entirely above 0, and
    (b) the interval of A - B does not lie entirely below 0.
Otherwise keep S. Reported, never decide: tokens, per-kind scores, B - S, how each of S and A answered (whole /
fallback / shipped path), and, for the next hypothesis, how many of the answers the unit check rejected were right.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import run6  # noqa: E402
from run import load, right  # noqa: E402

run4, fu, ol = run6.run4, run6.fu, run6.ol
ROOT = run4.ROOT
run4.CASES = CASES = Path(__file__).parent / "cases7.jsonl"
run4.CACHE = ROOT / "results/followup7_cache.jsonl"
run6.SEED = 20261115
VARIANTS = ("S", "A", "B")


def out_path(variant):
    return ROOT / f"results/followup7_{variant}.jsonl"


def one(case, variant):
    if variant == "B":
        return run6.alone(case)
    fu.ROOT_ANCHOR = variant == "A"
    try:
        return run6.large(case)
    finally:
        fu.ROOT_ANCHOR = False


def run(variant):
    out = out_path(variant)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    timeouts = 0
    with out.open("a") as f:
        for c in load(CASES):
            if c["id"] in done:
                continue
            try:
                row = {"id": c["id"], "variant": variant} | one(c, variant)
                timeouts = 0
            except TimeoutError as e:  # not saved: a resume retries it
                timeouts += 1
                print(f"{c['id']} timed out ({timeouts} in a row): {e}", flush=True)
                if timeouts >= 3:
                    sys.exit("3 timeouts in a row; stopped, resume to retry")
                continue
            except Exception as e:
                if ol.unreachable(e):
                    sys.exit(f"Ollama unreachable ({e}); stopped, resume to retry")
                row = {"id": c["id"], "variant": variant, "right": False, "tokens": 0, "error": f"{type(e).__name__}: {e}"}
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"{variant} {c['id']} {'right' if row['right'] else 'WRONG'} {row.get('pack', '')} "
                  f"{row.get('path', '')} {str(row.get('answer'))[:60]}", flush=True)


def report():
    cases = load(CASES)
    ids = [c["id"] for c in cases]
    got = {v: {r["id"]: r for r in load(out_path(v))} if out_path(v).exists() else {} for v in VARIANTS}
    if not all(i in got[v] for v in VARIANTS for i in ids):
        return print("set 7 incomplete:", {v: len(got[v]) for v in VARIANTS})
    names = {"S": "S repo today (0.1.5)", "A": "A S + ROOT_ANCHOR", "B": f"B {run6.ALONE} alone"}
    for v in VARIANTS:
        kinds = ", ".join(f"{k} {sum(got[v][c['id']]['right'] for c in cases if c['kind'] == k)}/"
                          f"{sum(c['kind'] == k for c in cases)}" for k in sorted({c["kind"] for c in cases}))
        print(f"{names[v]:<24} {sum(got[v][i]['right'] for i in ids)}/{len(ids)} right, "
              f"{sum(got[v][i]['tokens'] for i in ids)} tokens ({kinds})")
    by_case = {c["id"]: c for c in cases}
    for v in "SA":
        paths = [got[v][i].get("path") for i in ids]
        rejected = [i for i in ids if got[v][i].get("path") == "fallback"]
        print(f"{v} answered by: " + ", ".join(f"{p} {paths.count(p)}" for p in ("whole", "fallback", "shipped"))
              + f"; of the {len(rejected)} rejected whole answers, "
              f"{sum(right(got[v][i].get('whole_answer'), by_case[i]) for i in rejected)} were right")
    a_s, a_b, b_s = (run6.interval(got[x], got[y], ids) for x, y in (("S", "A"), ("B", "A"), ("S", "B")))
    print(f"A - S: {a_s[0]:+d}, 95% {a_s[1]:+d} to {a_s[2]:+d}   (a) {'pass' if a_s[1] > 0 else 'FAIL'}")
    print(f"A - B: {a_b[0]:+d}, 95% {a_b[1]:+d} to {a_b[2]:+d}   (b) {'pass' if a_b[2] >= 0 else 'FAIL'}")
    print(f"B - S: {b_s[0]:+d}, 95% {b_s[1]:+d} to {b_s[2]:+d}   (reported only)")
    print(f"FOLLOWUP7_RULE -> {'SHIP ROOT_ANCHOR' if a_s[1] > 0 and a_b[2] >= 0 else 'KEEP S'}")


def check():
    """No model calls: every key grades right and 5% off grades wrong; what S and A resolve for each case."""
    cases = load(CASES)
    bad = [c["id"] for c in cases if not right({"value": c["answer"], "unit": c["unit"]}, c)
           or right({"value": c["answer"] * 1.05, "unit": c["unit"]}, c)]
    print(f"{len(cases)} cases; keys that fail their own grading: {bad or 'none'}")
    fu.ROUTE_FIX, run4.si.ENABLED = run4.FLAGS["F"]
    for v in "SA":
        fu.ROOT_ANCHOR = v == "A"
        packs, uses, first = {}, 0, 0
        for c in cases:
            msgs = c["messages"]
            routed = fu.resolve(msgs)
            packs[routed["pack"]] = packs.get(routed["pack"], 0) + 1
            first += routed.get("anchor") == msgs[0]["content"]
            uses += (routed["pack"] != "general" and "anchor" in routed
                     and bool(routed["context"] or fu.new_quantity(routed["anchor"], msgs[-1]["content"])))
        print(f"{v}: routed {packs}; anchor is the first question in {first} of {len(cases)}; "
              f"the large model gets the conversation in {uses}")
    fu.ROOT_ANCHOR = False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=VARIANTS)
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        return check()
    if args.variant:
        run(args.variant)
    report()


if __name__ == "__main__":
    main()
