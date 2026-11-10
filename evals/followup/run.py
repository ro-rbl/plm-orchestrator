"""Follow-up answers: today's task wording (A) against a rewrite into one standalone question first (B).

    .venv/bin/python evals/followup/run.py --variant A      # resumes; results/followup_A.jsonl
    .venv/bin/python evals/followup/run.py --variant B
    .venv/bin/python evals/followup/run.py --report         # FOLLOWUP_ANSWER_RULE
    .venv/bin/python evals/followup/run.py --set 2 --variant A   # then B, then --set 2 --report (FOLLOWUP2_RULE)
    .venv/bin/python evals/followup/run.py --set 3 --variant A   # then B, then --set 3 --report (FOLLOWUP3_RULE: C vs A)

A: plm.followup.resolve's task ("Original question / Previous answer / Change(s) / Answer the original question
   again with the change applied.") goes to the pack, as shipped on 2026-11-08.
B: REWRITER (qwen3:8b) first rewrites the conversation's last message as one complete question; the pack solves
   that. One more model call per follow-up.
Graded on evals/followup/cases.jsonl (36 cases with keys, written before either variant ran): the pack's answer,
converted to the key's unit, within 2%. Live check that led here: "now for 200 ohm" came back 22 V (A).

FOLLOWUP_ANSWER_RULE, fixed 2026-11-08 before any answer: B replaces A iff a paired bootstrap 95% interval (2000
resamples, seed 20261108) of B's correct answers minus A's lies entirely above 0; tokens reported.

Set 2 (--set 2, evals/followup/cases2.jsonl: 100 new conversations from build2.py, keys computed in code; results in
results/followup2_{A,B}.jsonl). FOLLOWUP2_RULE, fixed 2026-11-09 before any model answered a set-2 case; set 1 (36,
already seen) doesn't count: accuracy first. Paired bootstrap 95% interval (2000 resamples, seed 20261109) of B's
correct answers minus A's, over all 100. If it lies entirely above 0, ship B (rewrite first); if entirely below 0,
keep A; if it contains 0, keep A (one model call fewer). Tokens (B's include the rewrite) and per-pack scores are
reported, never decide. Checked offline before any answer: every key grades right and 5% off grades wrong; routing
(shared by A and B) sends 89/100 to the labeled pack (projectile and orbit cases to aerospace; f2-063 photon
frequency and f2-095 load factor to general).

Set 3 (--set 3, evals/followup/cases3.jsonl: 90 new conversations from build3.py; results/followup3_{A,B}.jsonl).
Variant C, from the set-2 misses (10 of A's 25 asked a NEW quantity and got the original one): rewrite first (B)
only when the follow-up asks for a quantity of another kind than the original question (new_quantity below: both
expected units known and of different dimensionality); otherwise today's wording (A). Answers are deterministic
(temperature 0), so C is A's or B's row per case, no run of its own. FOLLOWUP3_RULE, fixed 2026-11-10 before any
model answered a set-3 case: ship C iff the paired bootstrap 95% interval (2000 resamples, seed 20261110) of C's
correct answers minus A's, over all 90, lies entirely above 0; otherwise keep A. B - A, tokens and per-kind scores
are reported, never decide.
"""

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from plm import packs  # noqa: E402
from plm.followup import resolve  # noqa: E402
from plm.numeric.checks import ureg  # noqa: E402
from plm.ollama import ask, unreachable  # noqa: E402

SETS = {"1": Path(__file__).parent / "cases.jsonl", "2": Path(__file__).parent / "cases2.jsonl",
        "3": Path(__file__).parent / "cases3.jsonl"}
CASES = SETS["1"]
REWRITER = "qwen3:8b"
REWRITE_PROMPT = """Below is a conversation. Rewrite the user's LAST message as one complete, self-contained question
that someone who never saw the conversation could answer: include every number, unit and condition from the
earlier question that still applies, with the change in the last message applied. If the last message asks for a
different unit, ask for that unit; otherwise ask for the same unit as before. Answer with the question only.

{transcript}"""
RULE3 = ("ship C (rewrite first only for a new kind of quantity) iff the paired bootstrap 95% interval (2000 "
         "resamples, seed 20261110) of C's correct answers minus A's over the 90 set-3 cases lies entirely above 0; "
         "otherwise keep A; B - A, tokens and per-kind scores reported, not decisive")
RULE2 = ("accuracy first: ship B (rewrite first) iff the paired bootstrap 95% interval (2000 resamples, seed 20261109) "
         "of B's correct answers minus A's over the 100 set-2 cases lies entirely above 0; otherwise keep A (entirely "
         "below 0: A is better; contains 0: A, one model call fewer); tokens and per-pack scores reported, not decisive")
RULE = ("B (rewrite first) replaces A (today's wording) iff a paired bootstrap 95% interval (2000 resamples, seed "
        "20261108) of B's correct answers minus A's lies entirely above 0; tokens reported")


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def out_path(variant):
    tag = {SETS["1"]: "", SETS["2"]: "2", SETS["3"]: "3"}[CASES]
    return ROOT / f"results/followup{tag}_{variant}.jsonl"


def new_quantity(messages):
    """True when the last message asks for a quantity of another kind than the first question (variant C)."""
    from plm.numeric.expected import expected_unit
    first = next(m["content"] for m in messages if m["role"] == "user")
    a, b = expected_unit(first)[0], expected_unit(messages[-1]["content"])[0]
    if not a or not b:
        return False
    try:
        return ureg.Quantity(1, a).dimensionality != ureg.Quantity(1, b).dimensionality
    except Exception:
        return False


def report3(cases, got):
    ids = [c["id"] for c in cases]
    if not all(i in got["A"] and i in got["B"] for i in ids):
        print("set 3 incomplete:", {v: len(got[v]) for v in "AB"})
        return
    pick = {c["id"]: ("B" if new_quantity(c["messages"]) else "A") for c in cases}
    C = {i: got[pick[i]][i] for i in ids}
    for name, rows in (("A", got["A"]), ("B", got["B"]), ("C", C)):
        print(f"{name}: {sum(rows[i]['right'] for i in ids)}/{len(ids)} right, {sum(rows[i]['tokens'] for i in ids)} tokens")
    for kind in sorted({c["kind"] for c in cases}):
        k = [c["id"] for c in cases if c["kind"] == kind]
        print(f"  {kind:8} ({len(k)}): A {sum(got['A'][i]['right'] for i in k)}, B {sum(got['B'][i]['right'] for i in k)}, "
              f"C {sum(C[i]['right'] for i in k)}; C rewrote {sum(pick[i] == 'B' for i in k)}")
    diff = [C[i]["right"] - got["A"][i]["right"] for i in ids]
    rng = random.Random(20261110)
    boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) for _ in range(2000))
    lo, hi = boot[50], boot[1949]
    bdiff = sum(got["B"][i]["right"] - got["A"][i]["right"] for i in ids)
    print(f"C - A: {sum(diff):+d}, paired bootstrap 95% {lo:+d} to {hi:+d}   (B - A: {bdiff:+d}, reported only)")
    print(f"rule: {RULE3}")
    print("-> SHIP C" if lo > 0 else "-> KEEP A")


def right(answer, case):
    if not answer:
        return False
    try:
        if case["unit"] == "":
            value = answer["value"] if not answer["unit"] else ureg.Quantity(answer["value"], answer["unit"]).to("").magnitude
        else:
            value = ureg.Quantity(answer["value"], answer["unit"] or case["unit"]).to(case["unit"]).magnitude
    except Exception:  # an answer in a unit that can't be converted is wrong
        return False
    return abs(value - case["answer"]) <= case["rel_tol"] * abs(case["answer"])


def run_one(case, variant):
    routed = resolve(case["messages"])
    tokens = 0
    task = routed["task"]
    if variant == "B":
        transcript = "\n".join(f"{m['role']}: {m['content']}" for m in case["messages"])
        r = ask(REWRITER, REWRITE_PROMPT.format(transcript=transcript), False, 512, 600)
        task, tokens = r["response"].strip(), r["eval_tokens"]
    result = packs.PACKS[routed["pack"]].solve(task)
    return {"pack": routed["pack"], "task": task, "answer": result["answer"], "trusted": result["trusted"],
            "tokens": tokens + result["tokens"], "right": right(result["answer"], case)}


def run(variant):
    cases = load(CASES)
    out = out_path(variant)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    timeouts = 0
    with out.open("a") as f:
        for c in cases:
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
                if unreachable(e):
                    sys.exit(f"Ollama unreachable ({e}); stopped, resume to retry")
                row = {"id": c["id"], "variant": variant, "right": False, "tokens": 0, "error": f"{type(e).__name__}: {e}"}
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"{variant} {c['id']} {'right' if row['right'] else 'WRONG'} {row.get('answer')}", flush=True)


def report():
    cases = load(CASES)
    got = {v: {r["id"]: r for r in load(out_path(v))} if out_path(v).exists() else {} for v in "AB"}
    if CASES == SETS["3"]:
        return report3(cases, got)
    ids = [c["id"] for c in cases]
    for v in "AB":
        rows = [got[v][i] for i in ids if i in got[v]]
        print(f"{v}: {sum(r['right'] for r in rows)}/{len(rows)} right, {sum(r['tokens'] for r in rows)} tokens")
    if all(i in got["A"] and i in got["B"] for i in ids):
        diff = [got["B"][i]["right"] - got["A"][i]["right"] for i in ids]
        rng = random.Random(20261108)
        boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) for _ in range(2000))
        if CASES == SETS["1"]:
            lo, hi = boot[50], boot[1949]
        else:  # set 2: its own seed, fixed with FOLLOWUP2_RULE
            rng = random.Random(20261109)
            boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) for _ in range(2000))
            lo, hi = boot[50], boot[1949]
            for pack in sorted({c["pack"] for c in cases}):
                pi = [c["id"] for c in cases if c["pack"] == pack]
                print(f"  {pack}: A {sum(got['A'][i]['right'] for i in pi)}/{len(pi)}, "
                      f"B {sum(got['B'][i]['right'] for i in pi)}/{len(pi)}")
        print(f"B - A: {sum(diff):+d}, paired bootstrap 95% {lo:+d} to {hi:+d}")
        print(f"rule: {RULE if CASES == SETS['1'] else RULE2}")
        print("-> ADOPT B (rewrite first)" if lo > 0 else "-> KEEP A")
        wrong = [i for i in ids if not got["A"][i]["right"]]
        print("A wrong on:", wrong)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("A", "B"))
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--set", choices=tuple(SETS), default="1")
    args = ap.parse_args()
    global CASES
    CASES = SETS[args.set]
    if args.report:
        return report()
    if not args.variant:
        sys.exit("--variant A|B, or --report")
    run(args.variant)
    report()


if __name__ == "__main__":
    main()
