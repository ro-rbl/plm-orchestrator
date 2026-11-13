"""Set 5 answered by single local models as plain chatbots, for comparison with plm (no rule, nothing ships on it).

    .venv/bin/python evals/followup/baselines5.py --model qwen3:8b            # resumes; results/followup5_base__*.jsonl
    .venv/bin/python evals/followup/baselines5.py --model qwen3:8b --think
    .venv/bin/python evals/followup/baselines5.py --report

Each model gets the whole conversation as one prompt and the numeric packs' answer format ("ANSWER: 3.3 kN" as the
last line): no router, no calculator, no checks, no rewrite. Graded like plm's answers (the ANSWER line converted to
the key's unit, within 2%); a reply with no ANSWER line is graded leniently, as a general-pack reply is in run4.py.
Fixed 2026-11-13 before any model answered a set-5 case. Thinking runs get 4096 tokens, the others 1024.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import run4  # noqa: E402
import run5  # noqa: E402
from plm.numeric.answers import ANSWER_FORMAT, parse_answer  # noqa: E402
from plm.ollama import ask, unreachable  # noqa: E402
from run import load, right  # noqa: E402

ROOT = run4.ROOT
PROMPT = "Below is a conversation. Answer the user's last message.\n\n{transcript}\n\n" + ANSWER_FORMAT


def out_path(model, think):
    return ROOT / f"results/followup5_base__{re.sub(r'[^A-Za-z0-9.]+', '_', model)}{'__think' if think else ''}.jsonl"


def run(model, think):
    out = out_path(model, think)
    done = {r["id"] for r in load(out)} if out.exists() else set()
    timeouts = 0
    with out.open("a") as f:
        for c in load(run5.CASES):
            if c["id"] in done:
                continue
            transcript = "\n".join(f"{m['role']}: {m['content']}" for m in c["messages"])
            try:
                r = ask(model, PROMPT.format(transcript=transcript), think, 4096 if think else 1024, 900)
                timeouts = 0
            except TimeoutError as e:
                timeouts += 1
                print(f"{c['id']} timed out ({timeouts} in a row): {e}", flush=True)
                if timeouts >= 3:
                    sys.exit("3 timeouts in a row; stopped, resume to retry")
                continue
            except Exception as e:
                if unreachable(e):
                    sys.exit(f"Ollama unreachable ({e}); stopped, resume to retry")
                raise
            parsed = parse_answer(r["response"])
            ok = right({"value": parsed[0], "unit": parsed[1]}, c) if parsed else run4.prose_right(r["response"], c)
            f.write(json.dumps({"id": c["id"], "right": ok, "tokens": r["eval_tokens"], "seconds": round(r["wall_s"], 1),
                                "answer": list(parsed) if parsed else None, "capped": r["done_reason"] == "length",
                                "response": r["response"][-400:]}) + "\n")
            f.flush()
            print(f"{model}{' think' if think else ''} {c['id']} {'right' if ok else 'WRONG'} {parsed}", flush=True)


def report():
    cases = load(run5.CASES)
    kinds = sorted({c["kind"] for c in cases})

    def line(name, rows):
        n = len(rows)
        per = ", ".join(f"{k} {sum(rows[c['id']]['right'] for c in cases if c['kind'] == k and c['id'] in rows)}/"
                        f"{sum(c['kind'] == k and c['id'] in rows for c in cases)}" for k in kinds)
        note = "" if n == len(cases) else f"  (PARTIAL: {n} of {len(cases)} answered)"
        print(f"{name:<34} {sum(r['right'] for r in rows.values())}/{n} right, {sum(r['tokens'] for r in rows.values())} tokens ({per}){note}")

    for v, name in (("S", "plm 0.1.4 (shipped)"), ("R", "plm, always rewrite")):
        if run5.out_path(v).exists():
            line(name, {r["id"]: r for r in load(run5.out_path(v))})
    for f in sorted(ROOT.glob("results/followup5_base__*.jsonl")):
        line(f.stem.replace("followup5_base__", "alone: "), {r["id"]: r for r in load(f)})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--think", action="store_true")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.model:
        run(args.model, args.think)
    report()


if __name__ == "__main__":
    main()
