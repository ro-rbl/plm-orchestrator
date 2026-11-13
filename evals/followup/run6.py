"""Follow-up set 6: follow-ups through the pack's large model with the whole conversation, against what ships
(plm-core 0.1.4) and against qwen3:8b alone.

    .venv/bin/python evals/followup/run6.py --check         # offline: keys grade themselves, routing, who gets L
    .venv/bin/python evals/followup/run6.py --variant S     # then L, B; resumes; results/followup6_<V>.jsonl
    .venv/bin/python evals/followup/run6.py --report        # FOLLOWUP6_RULE

    S  shipped: plm.followup.resolve + phrase, then the pack (as evals/followup/run5.py's S), unit prefixes in code
    L  plm.followup.whole: when the shipped path would use the conversation for a numeric pack (a resolved follow-up,
       or a message asking a new kind of quantity of the earlier question), that pack's large model gets the whole
       conversation and the calculator format in one call. If that call's answer has an issue (no program, a program
       error, a failed unit check), the shipped path answers instead and both are counted in tokens. Every other
       message (to the general pack, or a question routed on its own) is S's row.
    B  qwen3:8b alone as a plain chatbot: the whole conversation in one prompt and the packs' ANSWER format; no
       router, calculator, checks or rewrite (the prompt of evals/followup/baselines5.py).
Why: on set 5 plm got 69/80 and the 8B alone 76/80 (paired +7, 95% +1 to +13, computed after the fact).

Graded on evals/followup/cases6.jsonl (92 conversations, build6.py, new anchors, keys computed in code, written
before any answer) as sets 4 and 5 were: an ANSWER converted to the key's unit, within 2%; a general-pack reply, or
a B reply with no ANSWER line, leniently (any number in it). Identical model calls are cached
(results/followup6_cache.jsonl).

FOLLOWUP6_RULE, fixed 2026-11-13 before any model answered a set-6 case. Paired bootstrap 95% intervals (2000
resamples, seed 20261114) of the difference in right answers over all 92. Ship L iff
    (a) the interval of L - S lies entirely above 0, and
    (b) the interval of L - B does not lie entirely below 0.
Otherwise keep what ships. Tokens, per-kind scores, B - S and how often L fell back are reported, never decide.
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import run4  # noqa: E402
from plm.numeric.answers import ANSWER_FORMAT, parse_answer  # noqa: E402
from run import load, right  # noqa: E402

ROOT = run4.ROOT
fu, ol = run4.fu, run4.ol
run4.CASES = CASES = Path(__file__).parent / "cases6.jsonl"
run4.CACHE = ROOT / "results/followup6_cache.jsonl"
VARIANTS = ("S", "L", "B")
ALONE = "qwen3:8b"
ALONE_PROMPT = "Below is a conversation. Answer the user's last message.\n\n{transcript}\n\n" + ANSWER_FORMAT
SEED = 20261114


def out_path(variant):
    return ROOT / f"results/followup6_{variant}.jsonl"


def shipped(case):
    return run4.run_one(case, "F")  # F = the shipped flags: no ROUTE_FIX, si on


def large(case):
    msgs = case["messages"]
    fu.ROUTE_FIX, run4.si.ENABLED = run4.FLAGS["F"]
    routed = fu.resolve(msgs)
    if routed["pack"] == "general":
        return shipped(case) | {"path": "shipped"}
    real, calls = ol.ask, []

    def ask(model, prompt, think, num_predict, timeout):  # whole()'s one model call, cached
        r = run4.cached("whole", [model, prompt, num_predict], lambda: (lambda x: {
            k: x[k] for k in ("response", "eval_tokens", "prompt_tokens", "done_reason")})(
            real(model, prompt, think, num_predict, timeout)))
        calls.append(r)
        return r
    ol.ask = ask
    try:
        w = fu.whole(msgs, routed)
    finally:
        ol.ask = real
    if w is None:
        return shipped(case) | {"path": "shipped"}
    if w["steps"][-1]["issues"]:
        s = shipped(case)
        return s | {"path": "fallback", "tokens": s["tokens"] + w["tokens"], "issues": w["steps"][-1]["issues"],
                    "whole_answer": w["answer"]}
    return {"pack": w["pack"], "task": w["task"], "answer": w["answer"], "trusted": w["trusted"], "tokens": w["tokens"],
            "right": right(w["answer"], case), "path": "whole"}


def alone(case):
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in case["messages"])
    r = ol.ask(ALONE, ALONE_PROMPT.format(transcript=transcript), False, 1024, 900)
    parsed = parse_answer(r["response"])
    ok = right({"value": parsed[0], "unit": parsed[1]}, case) if parsed else run4.prose_right(r["response"], case)
    return {"right": ok, "tokens": r["eval_tokens"], "seconds": round(r["wall_s"], 1),
            "answer": list(parsed) if parsed else None, "capped": r["done_reason"] == "length",
            "response": r["response"][-400:]}


RUN = {"S": shipped, "L": large, "B": alone}


def run(variant):
    out = out_path(variant)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    timeouts = 0
    with out.open("a") as f:
        for c in load(CASES):
            if c["id"] in done:
                continue
            try:
                row = {"id": c["id"], "variant": variant} | RUN[variant](c)
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


def interval(a, b, ids):
    diff = [b[i]["right"] - a[i]["right"] for i in ids]
    rng = random.Random(SEED)
    boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) for _ in range(2000))
    return sum(diff), boot[50], boot[1949]


def report():
    cases = load(CASES)
    ids = [c["id"] for c in cases]
    got = {v: {r["id"]: r for r in load(out_path(v))} if out_path(v).exists() else {} for v in VARIANTS}
    if not all(i in got[v] for v in VARIANTS for i in ids):
        return print("set 6 incomplete:", {v: len(got[v]) for v in VARIANTS})
    names = {"S": "S plm 0.1.4 (shipped)", "L": "L large model, whole conversation", "B": f"B {ALONE} alone"}
    for v in VARIANTS:
        kinds = ", ".join(f"{k} {sum(got[v][c['id']]['right'] for c in cases if c['kind'] == k)}/"
                          f"{sum(c['kind'] == k for c in cases)}" for k in sorted({c["kind"] for c in cases}))
        print(f"{names[v]:<34} {sum(got[v][i]['right'] for i in ids)}/{len(ids)} right, "
              f"{sum(got[v][i]['tokens'] for i in ids)} tokens ({kinds})")
    paths = [got["L"][i].get("path") for i in ids]
    print("L answered by: " + ", ".join(f"{p} {paths.count(p)}" for p in ("whole", "fallback", "shipped")))
    ls, lb, bs = (interval(got[a], got[b], ids) for a, b in (("S", "L"), ("B", "L"), ("S", "B")))
    print(f"L - S: {ls[0]:+d}, 95% {ls[1]:+d} to {ls[2]:+d}   (a) {'pass' if ls[1] > 0 else 'FAIL'}")
    print(f"L - B: {lb[0]:+d}, 95% {lb[1]:+d} to {lb[2]:+d}   (b) {'pass' if lb[2] >= 0 else 'FAIL'}")
    print(f"B - S: {bs[0]:+d}, 95% {bs[1]:+d} to {bs[2]:+d}   (reported only)")
    print(f"FOLLOWUP6_RULE -> {'SHIP L (plm.followup.whole)' if ls[1] > 0 and lb[2] >= 0 else 'KEEP SHIPPED'}")


def check():
    """No model calls: every key grades right and 5% off grades wrong; where routing sends each case; who gets L."""
    cases = load(CASES)
    bad = [c["id"] for c in cases if not right({"value": c["answer"], "unit": c["unit"]}, c)
           or right({"value": c["answer"] * 1.05, "unit": c["unit"]}, c)]
    print(f"{len(cases)} cases; keys that fail their own grading: {bad or 'none'}")
    fu.ROUTE_FIX, run4.si.ENABLED = run4.FLAGS["F"]
    packs, uses = {}, 0
    for c in cases:
        routed = fu.resolve(c["messages"])
        packs[routed["pack"]] = packs.get(routed["pack"], 0) + 1
        numeric = routed["pack"] != "general" and "anchor" in routed
        uses += numeric and bool(routed["context"] or fu.new_quantity(routed["anchor"], c["messages"][-1]["content"]))
        if routed["pack"] != c["pack"]:
            print(f"  {c['id']} ({c['kind']}) labeled {c['pack']} -> {routed['pack']}: {c['messages'][-1]['content'][:60]}")
    print(f"routed: {packs}; L's large-model path applies to {uses} of {len(cases)}")


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
