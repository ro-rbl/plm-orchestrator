"""Follow-up set 4: two fixes for the set-3 misses, each judged against what ships today.

    .venv/bin/python evals/followup/run4.py --variant C     # then D, E, F; resumes; results/followup4_<V>.jsonl
    .venv/bin/python evals/followup/run4.py --report        # FOLLOWUP4_RULE and SI_RULE (a)
    .venv/bin/python evals/si_regression.py                 # SI_RULE (b)

Every variant runs the shipped pipeline (plm.followup.resolve + phrase, then the pack; the general pack gets the
whole conversation), with two experimental flags:
    C  today (variant C of FOLLOWUP3_RULE, shipped 2026-11-10)
    D  C + plm.followup.ROUTE_FIX: a message that asks for a quantity with a unit but would go to the general pack
       stays in the earlier question's pack and is rewritten into one question first
    E  D + plm.numeric.si.ENABLED: the model sees no unit prefixes ("1.5 kW" -> "1500 W"); converted back in code
    F  C + plm.numeric.si.ENABLED
Why: of C's 39 misses on set 3, 14 went to the general pack and 9 were off by a power of ten.

Graded on evals/followup/cases4.jsonl (83 conversations, build4.py, keys computed in code, written before any
answer): a pack's answer converted to the key's unit, within 2%. A general-pack reply is prose, so it counts as right
if ANY number in it (with the unit word after it when that converts, else taken as the key's unit) is within 2% of
the key: lenient on purpose, so D isn't credited for answers a reader could already find. Answers are deterministic
(temperature 0), so identical model calls are cached across variants (results/followup4_cache.jsonl).

Rules, fixed 2026-11-10 before any model answered a set-4 case (paired bootstrap, 2000 resamples, seed 20261111,
95% interval of the difference in right answers over all 83):
FOLLOWUP4_RULE: ship ROUTE_FIX iff the interval of D - C lies entirely above 0.
SI_RULE: ship plm.numeric.si iff (a) the interval of E - D (if ROUTE_FIX ships) or F - C (if it doesn't) lies
    entirely above 0, and (b) on the packs' own problem sets (evals/si_regression.py: electrical, aerospace and
    physics problems.jsonl, 150 problems, seen before, a regression guard only), right answers with si on minus off
    are >= -2 in total and >= -2 in each pack.
Tokens and per-kind scores are reported, never decide.
"""

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

import plm.followup as fu  # noqa: E402
import plm.ollama as ol  # noqa: E402
from plm import packs  # noqa: E402
from plm.numeric import si  # noqa: E402
from plm.numeric.checks import ureg  # noqa: E402
from run import load, right  # noqa: E402

CASES = Path(__file__).parent / "cases4.jsonl"
CACHE = ROOT / "results/followup4_cache.jsonl"
FLAGS = {"C": (False, False), "D": (True, False), "E": (True, True), "F": (False, True)}  # (ROUTE_FIX, si)
NUMBER = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)\s*([A-Za-zµΩ°/^*·0-9-]*)")
_cache = None


def cached(kind, key, fn):
    """fn()'s result, stored under (kind, key); model calls are deterministic, so variants share them."""
    global _cache
    if _cache is None:
        _cache = {r["k"]: r["v"] for r in load(CACHE)} if CACHE.exists() else {}
    k = kind + ":" + hashlib.sha256(json.dumps(key, sort_keys=True).encode()).hexdigest()
    if k not in _cache:
        _cache[k] = fn()
        with CACHE.open("a") as f:
            f.write(json.dumps({"k": k, "v": _cache[k]}) + "\n")
    return _cache[k]


def prose_right(text, case):
    for num, word in NUMBER.findall(text or ""):
        for unit in (word.rstrip(".,;:)"), case["unit"]):
            if right({"value": float(num), "unit": unit}, case):
                return True
    return False


def run_one(case, variant):
    fu.ROUTE_FIX, si.ENABLED = FLAGS[variant]
    msgs = case["messages"]
    routed = fu.resolve(msgs)
    pack = routed["pack"]
    if pack == "general":
        r = cached("general", msgs, lambda: (lambda x: {"text": x["answer"]["text"], "tokens": x["tokens"]})(
            packs.PACKS["general"].solve(msgs[-1]["content"], messages=msgs)))
        return {"pack": pack, "task": msgs[-1]["content"], "answer": {"text": r["text"][-300:]}, "tokens": r["tokens"],
                "right": prose_right(r["text"], case)}
    rewrite_tokens = []
    real = ol.ask

    def ask(model, prompt, think, num_predict, timeout):  # phrase()'s rewriter call, cached
        r = cached("rewrite", [model, prompt], lambda: (lambda x: {"response": x["response"], "eval_tokens": x["eval_tokens"]})(
            real(model, prompt, think, num_predict, timeout)))
        rewrite_tokens.append(r["eval_tokens"])
        return r
    ol.ask = ask
    try:
        task = fu.phrase(msgs, routed)
    finally:
        ol.ask = real
    seen = si.normalize(task) if si.ENABLED else task  # same text to the model = same call
    r = cached("solve", [pack, seen, task if seen != task else ""], lambda: (lambda x: {
        "answer": x["answer"], "trusted": x["trusted"], "tokens": x["tokens"]})(packs.PACKS[pack].solve(task)))
    return {"pack": pack, "task": task, "answer": r["answer"], "trusted": r["trusted"],
            "tokens": sum(rewrite_tokens) + r["tokens"], "right": right(r["answer"], case)}


def out_path(variant):
    return ROOT / f"results/followup4_{variant}.jsonl"


def run(variant):
    out = out_path(variant)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    timeouts = 0
    with out.open("a") as f:
        for c in load(CASES):
            if c["id"] in done:
                continue
            try:
                row = {"id": c["id"], "variant": variant} | run_one(c, variant)
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
            print(f"{variant} {c['id']} {'right' if row['right'] else 'WRONG'} {row.get('pack')} {str(row.get('answer'))[:60]}", flush=True)


def interval(a, b, ids):
    diff = [b[i]["right"] - a[i]["right"] for i in ids]
    rng = random.Random(20261111)
    boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) for _ in range(2000))
    return sum(diff), boot[50], boot[1949]


def report():
    cases = load(CASES)
    ids = [c["id"] for c in cases]
    got = {v: {r["id"]: r for r in load(out_path(v))} if out_path(v).exists() else {} for v in FLAGS}
    full = [v for v in FLAGS if all(i in got[v] for i in ids)]
    for v in full:
        kinds = ", ".join(f"{k} {sum(got[v][c['id']]['right'] for c in cases if c['kind'] == k)}/"
                          f"{sum(c['kind'] == k for c in cases)}" for k in sorted({c["kind"] for c in cases}))
        print(f"{v}: {sum(got[v][i]['right'] for i in ids)}/{len(ids)} right, {sum(got[v][i]['tokens'] for i in ids)} tokens "
              f"({kinds}; to general {sum(got[v][i].get('pack') == 'general' for i in ids)})")
    if not {"C", "D"} <= set(full):
        return print("incomplete:", {v: len(got[v]) for v in FLAGS})
    d, lo, hi = interval(got["C"], got["D"], ids)
    route = lo > 0
    print(f"D - C: {d:+d}, 95% {lo:+d} to {hi:+d}\nFOLLOWUP4_RULE -> {'SHIP ROUTE_FIX' if route else 'KEEP TODAY (no ROUTE_FIX)'}")
    base, with_si = ("D", "E") if route else ("C", "F")
    if with_si not in full:
        return print(f"SI_RULE (a): {with_si} incomplete")
    d, lo, hi = interval(got[base], got[with_si], ids)
    print(f"{with_si} - {base}: {d:+d}, 95% {lo:+d} to {hi:+d}\nSI_RULE (a) -> {'pass' if lo > 0 else 'FAIL'}"
          "   ((b): evals/si_regression.py)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=tuple(FLAGS))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.variant:
        run(args.variant)
    report()


if __name__ == "__main__":
    main()
