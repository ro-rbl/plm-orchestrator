"""Run one local Ollama model over the software eval set, then grade it.

    .venv/bin/python evals/run_code.py evals/software/tasks.jsonl --model qwen2.5-coder:14b

Grading uses the hidden tests only. The visible examples (shown in the prompt)
are run and recorded separately, so the controller's examples-pass check can be
measured against an independent grade.

Writes results/software__<model>.jsonl, flushed per task; re-running resumes.
"""

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plm.ollama import ask  # noqa: E402
from plm.software.codegen import PROMPT_VERSION, build_prompt, extract_code  # noqa: E402
from plm.software.sandbox import run_tests  # noqa: E402


def load_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def verdict(row):
    if row.get("error"):
        return "request_error"
    if row["code"] is None:
        return "no_code"
    hidden = row["hidden"]
    if hidden["error"]:
        return "refused" if hidden["error"].startswith("refused") else "error"
    return "pass" if hidden["passed"] == hidden["total"] else "fail"


def summarize(rows):
    by_level = defaultdict(list)
    for r in rows:
        by_level[r["level"]].append(r)
        by_level["ALL"].append(r)
    kinds = ("pass", "fail", "error", "refused", "no_code", "request_error")
    print(f"{'level':<10} {'n':>3} " + " ".join(f"{k:>8}" for k in kinds) + f" {'acc':>5} {'avg tok':>8} {'capped':>7}")
    for lvl in ("calm", "alert", "intensive", "ALL"):
        rs = by_level[lvl]
        if rs:
            c = Counter(verdict(r) for r in rs)
            print(f"{lvl:<10} {len(rs):>3} " + " ".join(f"{c[k]:>8}" for k in kinds)
                  + f" {c['pass'] / len(rs):>5.0%} {sum(r['eval_tokens'] for r in rs) / len(rs):>8.0f}"
                  + f" {sum(r.get('done_reason') == 'length' for r in rs):>7}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("tasks")
    ap.add_argument("--model", required=True)
    ap.add_argument("--num-predict", type=int, default=1536)
    ap.add_argument("--timeout", type=int, default=600, help="seconds per request")
    ap.add_argument("--out")
    args = ap.parse_args()

    tasks = load_jsonl(args.tasks)
    safe_model = re.sub(r"[^A-Za-z0-9._-]+", "_", args.model)
    out = Path(args.out) if args.out else ROOT / "results" / f"software__{safe_model}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {r["id"] for r in load_jsonl(out)} if out.exists() else set()
    todo = [t for t in tasks if t["id"] not in done]
    print(f"{args.model}: {len(todo)} to run, {len(done)} already in {out}")

    with out.open("a") as f:
        for i, t in enumerate(todo, 1):
            row = {"id": t["id"], "level": t["level"], "model": args.model, "prompt_version": PROMPT_VERSION,
                   "num_predict": args.num_predict}
            try:
                row.update(ask(args.model, build_prompt(t), False, args.num_predict, args.timeout))
                row["code"] = extract_code(row["response"], t["entry"])
                if row["code"] is not None:
                    row["examples"] = run_tests(row["code"], t["examples"])
                    row["hidden"] = run_tests(row["code"], t["tests"])
            except Exception as e:  # keep going; one bad request must not lose the run
                row.update({"response": "", "code": None, "error": f"{type(e).__name__}: {e}", "eval_tokens": 0,
                            "prompt_tokens": 0, "load_s": 0, "wall_s": 0, "done_reason": "error"})
            f.write(json.dumps(row) + "\n")
            f.flush()
            v = verdict(row)
            detail = ""
            if row.get("hidden"):
                detail = f"{row['hidden']['passed']}/{row['hidden']['total']} hidden"
                if row["hidden"]["error"]:
                    detail += f"  [{row['hidden']['error'][:60]}]"
            print(f"[{i}/{len(todo)}] {t['id']} {v:<8} {row['eval_tokens']:>5} tok {row['wall_s']:>6.1f}s  {detail}"
                  + (f"  {row['error']}" if row.get("error") else ""), flush=True)

    summarize(load_jsonl(out))


if __name__ == "__main__":
    main()
