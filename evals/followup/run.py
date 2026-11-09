"""Follow-up answers: today's task wording (A) against a rewrite into one standalone question first (B).

    .venv/bin/python evals/followup/run.py --variant A      # resumes; results/followup_A.jsonl
    .venv/bin/python evals/followup/run.py --variant B
    .venv/bin/python evals/followup/run.py --report         # FOLLOWUP_ANSWER_RULE

A: plm.followup.resolve's task ("Original question / Previous answer / Change(s) / Answer the original question
   again with the change applied.") goes to the pack, as shipped on 2026-11-08.
B: REWRITER (qwen3:8b) first rewrites the conversation's last message as one complete question; the pack solves
   that. One more model call per follow-up.
Graded on evals/followup/cases.jsonl (36 cases with keys, written before either variant ran): the pack's answer,
converted to the key's unit, within 2%. Live check that led here: "now for 200 ohm" came back 22 V (A).

FOLLOWUP_ANSWER_RULE, fixed 2026-11-08 before any answer: B replaces A iff a paired bootstrap 95% interval (2000
resamples, seed 20261108) of B's correct answers minus A's lies entirely above 0; tokens reported.
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

CASES = Path(__file__).parent / "cases.jsonl"
REWRITER = "qwen3:8b"
REWRITE_PROMPT = """Below is a conversation. Rewrite the user's LAST message as one complete, self-contained question
that someone who never saw the conversation could answer: include every number, unit and condition from the
earlier question that still applies, with the change in the last message applied. If the last message asks for a
different unit, ask for that unit; otherwise ask for the same unit as before. Answer with the question only.

{transcript}"""
RULE = ("B (rewrite first) replaces A (today's wording) iff a paired bootstrap 95% interval (2000 resamples, seed "
        "20261108) of B's correct answers minus A's lies entirely above 0; tokens reported")


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def out_path(variant):
    return ROOT / f"results/followup_{variant}.jsonl"


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
    ids = [c["id"] for c in cases]
    for v in "AB":
        rows = [got[v][i] for i in ids if i in got[v]]
        print(f"{v}: {sum(r['right'] for r in rows)}/{len(rows)} right, {sum(r['tokens'] for r in rows)} tokens")
    if all(i in got["A"] and i in got["B"] for i in ids):
        diff = [got["B"][i]["right"] - got["A"][i]["right"] for i in ids]
        rng = random.Random(20261108)
        boot = sorted(sum(diff[rng.randrange(len(diff))] for _ in diff) for _ in range(2000))
        lo, hi = boot[50], boot[1949]
        print(f"B - A: {sum(diff):+d}, paired bootstrap 95% {lo:+d} to {hi:+d}")
        print(f"rule: {RULE}")
        print("-> ADOPT B (rewrite first)" if lo > 0 else "-> KEEP A")
        wrong = [i for i in ids if not got["A"][i]["right"]]
        print("A wrong on:", wrong)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=("A", "B"))
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report()
    if not args.variant:
        sys.exit("--variant A|B, or --report")
    run(args.variant)
    report()


if __name__ == "__main__":
    main()
