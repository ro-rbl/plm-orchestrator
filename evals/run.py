"""Run one local Ollama model over an eval set, then grade it.

    .venv/bin/python evals/run.py evals/electrical/problems.jsonl --model qwen3:8b
    .venv/bin/python evals/run.py evals/electrical/problems.jsonl --model qwen3:8b --strategy tool

Strategies:
    bare     the model answers directly (baseline)
    tool     the model writes a Python program; plm/numeric/calc.py runs it and its output is graded
    formula  same, but the model first states the formula and converts the givens to SI units
    units    the model computes with unit-carrying quantities; the harness converts the result
             to the unit the question asks for (plm/numeric/calc.py run_units_program)

Writes results/<set>__<model>.jsonl, one line per problem, flushed as it goes.
Re-running the same command resumes: problems already in the file are skipped.
The Ollama address comes from OLLAMA_HOST (default 127.0.0.1:11434).
"""

import argparse
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import grade  # noqa: E402
from plm.numeric import calc  # noqa: E402
from plm.numeric.checks import requested_unit  # noqa: E402
from plm.ollama import ask  # noqa: E402


# strategy -> (answer-format instructions, prompt version)
STRATEGIES = {
    "bare": (grade.ANSWER_FORMAT, grade.PROMPT_VERSION),
    "tool": (calc.TOOL_FORMAT, calc.TOOL_PROMPT_VERSION),
    "formula": (calc.FORMULA_FORMAT, calc.FORMULA_PROMPT_VERSION),
    "units": (calc.UNITS_FORMAT, calc.UNITS_PROMPT_VERSION),
}


def build_prompt(problem, strategy):
    return f"{problem['question']}\n\n{STRATEGIES[strategy][0]}"


def summarize(problems, rows):
    results = grade.report(problems, rows)
    verdicts = {r["id"]: r["verdict"] for r in results}
    by_level = defaultdict(list)
    for row in rows:
        by_level[row["level"]].append(row)
        by_level["ALL"].append(row)
    print(f"\n{'level':<10} {'avg tok':>8} {'avg s':>6} {'hit cap':>8}")
    for lvl in ("calm", "alert", "intensive", "ALL"):
        rs = by_level[lvl]
        if rs:
            capped = sum(r.get("done_reason") == "length" for r in rs)
            print(f"{lvl:<10} {sum(r['eval_tokens'] for r in rs) / len(rs):>8.0f} "
                  f"{sum(r['wall_s'] for r in rs) / len(rs):>6.1f} {capped:>8}")
    return verdicts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("problems")
    ap.add_argument("--model", required=True)
    ap.add_argument("--strategy", choices=list(STRATEGIES), default="bare")
    ap.add_argument("--think", action="store_true", help="allow Qwen3-style thinking")
    ap.add_argument("--num-predict", type=int, default=1024, help="max generated tokens per problem")
    ap.add_argument("--timeout", type=int, default=300, help="seconds per request")
    ap.add_argument("--out")
    args = ap.parse_args()

    problems = grade.load_jsonl(args.problems)
    set_name = Path(args.problems).parent.name
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", args.model)
    out = Path(args.out) if args.out else ROOT / "results" / f"{set_name}__{safe_model}{'__think' if args.think else ''}{'' if args.strategy == 'bare' else '__' + args.strategy}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)

    done = {r["id"] for r in grade.load_jsonl(out)} if out.exists() else set()
    todo = [p for p in problems if p["id"] not in done]
    print(f"{args.model}: {len(todo)} to run, {len(done)} already in {out}")

    with out.open("a") as f:
        for i, p in enumerate(todo, 1):
            row = {"id": p["id"], "level": p["level"], "model": args.model, "think": args.think,
                   "strategy": args.strategy,
                   "prompt_version": STRATEGIES[args.strategy][1],
                   "num_predict": args.num_predict}
            try:
                row.update(ask(args.model, build_prompt(p, args.strategy), args.think,
                               args.num_predict, args.timeout))
                if args.strategy != "bare":
                    # Grade what the program printed; keep the model's own text alongside.
                    row["model_response"] = row["response"]
                    code = calc.extract_program(row["response"])
                    t = time.time()
                    if not code:
                        row["response"], row["program_error"] = "", "no code block"
                    elif args.strategy == "units":
                        row["response"], row["program_error"] = calc.run_units_program(code, requested_unit(p["question"]))
                    else:
                        row["response"], row["program_error"] = calc.run_program(code)
                    row["program_s"] = time.time() - t
            except Exception as e:  # keep going; one bad request must not lose the run
                row.update({"response": "", "error": f"{type(e).__name__}: {e}", "eval_tokens": 0,
                            "prompt_tokens": 0, "load_s": 0, "wall_s": 0, "done_reason": "error"})
            f.write(json.dumps(row) + "\n")
            f.flush()
            verdict = grade.grade_one(p, row["response"])["verdict"]
            print(f"[{i}/{len(todo)}] {p['id']} {verdict:<11} {row['eval_tokens']:>5} tok {row['wall_s']:>6.1f}s"
                  + (f"  {row['error']}" if "error" in row else "")
                  + (f"  [{row['program_error']}]" if row.get("program_error") else ""), flush=True)

    rows = grade.load_jsonl(out)
    summarize(problems, rows)


if __name__ == "__main__":
    main()
