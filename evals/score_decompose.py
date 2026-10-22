"""Score the decompose-then-solve sweep (results/run_decompose.sh) and apply its adoption rule.

    .venv/bin/python evals/score_decompose.py

The rule, the cost bound and the sets were fixed on 2026-10-22, before any decompose
result existed. Primary set: evals/aerospace/fresh_intensive.jsonl, written before the
strategy and never used to design it. Secondary: the eval set's 15 intensive problems,
where the shipped 8B + calculator gets 7/15; they have been seen, so they only guard
against a loss, they can't justify a switch on their own.

Cost stated up front: compute is generated tokens (one model, the 8B, throughout, as in
evals/simulate_routing.py); a plan plus a call per step was expected to cost about
3-4x one calculator program. Prompt tokens are reported too, since every step resends
the question and the plan.
"""

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import grade  # noqa: E402
import plm.packs  # noqa: E402,F401  (loads every pack, and with it its unit words)
from plm.numeric.checks import check  # noqa: E402
from plm_aerospace.levels import classify  # noqa: E402

DECOMPOSE_RULE = ("aerospace's intensive level switches to decompose iff, on the fresh set, decompose solves at "
                  "least 3 more of 15 than 8B + calculator; on the eval set's 15 intensive problems it solves at "
                  "least as many as 8B + calculator (7); and on the fresh set it costs at most 4x the calculator's "
                  "generated tokens")
MIN_GAIN, MAX_COST_RATIO = 3, 4.0

RESULTS = ROOT / "results"
SETS = {  # set -> (problems, {strategy: results file}); only intensive problems are scored
    "fresh": ("evals/aerospace/fresh_intensive.jsonl",
              {"tool": "aerospace_fresh_intensive__qwen3_8b__tool.jsonl",
               "decompose": "aerospace_fresh_intensive__qwen3_8b__decompose.jsonl"}),
    "eval": ("evals/aerospace/problems.jsonl",
             {"tool": "aerospace__qwen3_8b__tool.jsonl", "decompose": "aerospace__qwen3_8b__decompose.jsonl"}),
}


def score(problems, path):
    if not path.exists():
        sys.exit(f"no {path.relative_to(ROOT)} yet; run results/run_decompose.sh")
    rows ={r["id"]: r for r in grade.load_jsonl(path)}
    missing = [p["id"] for p in problems if p["id"] not in rows]
    if missing:
        sys.exit(f"{path.name}: no result for {', '.join(missing)}; run results/run_decompose.sh")
    out = {"correct": 0, "tokens": 0, "prompt_tokens": 0, "wrong": 0, "wrong_flagged": 0, "fallbacks": Counter(),
           "verdicts": {}}
    for p in problems:
        r = rows[p["id"]]
        verdict = grade.grade_one(p, r["response"])["verdict"]
        out["verdicts"][p["id"]] = verdict
        out["correct"] += verdict == "correct"
        out["tokens"] += r["eval_tokens"]
        out["prompt_tokens"] += r["prompt_tokens"]
        if verdict != "correct":
            out["wrong"] += 1
            out["wrong_flagged"] += bool(r.get("program_error") or check(p["question"], r["response"]))
        if r.get("fallback"):
            out["fallbacks"][r["fallback"].split(":")[0]] += 1
    return out


def main():
    scores = {}
    for name, (problems_path, files) in SETS.items():
        problems = [p for p in grade.load_jsonl(ROOT / problems_path) if p["level"] == "intensive"]
        n = len(problems)
        print(f"\n{name} set: {n} intensive problems ({problems_path})")
        print(f"{'strategy':<10} {'correct':>8} {'gen tok/problem':>16} {'prompt tok/problem':>19} {'wrong flagged':>14}")
        for strategy, f in files.items():
            s = scores[name, strategy] = score(problems, RESULTS / f)
            print(f"{strategy:<10} {s['correct']:>5}/{n} {s['tokens'] / n:>16.0f} {s['prompt_tokens'] / n:>19.0f} "
                  f"{s['wrong_flagged']:>9}/{s['wrong']}")
        d = scores[name, "decompose"]
        if d["fallbacks"]:
            print("decompose fell back to one program:", dict(d["fallbacks"]))
        both = [(pid, scores[name, "tool"]["verdicts"][pid], v) for pid, v in d["verdicts"].items()
                if v != scores[name, "tool"]["verdicts"][pid]]
        for pid, t, v in both:
            print(f"  {pid}: tool {t}, decompose {v}")
        if name == "fresh":  # what production would see: only what the classifier calls intensive gets decompose
            seen = [p["id"] for p in problems if classify(p["question"])[0] == "intensive"]
            print(f"classifier calls {len(seen)}/{n} intensive; on those: tool "
                  f"{sum(scores[name, 'tool']['verdicts'][i] == 'correct' for i in seen)}, decompose "
                  f"{sum(d['verdicts'][i] == 'correct' for i in seen)}")

    gain = scores["fresh", "decompose"]["correct"] - scores["fresh", "tool"]["correct"]
    held = scores["eval", "decompose"]["correct"] >= scores["eval", "tool"]["correct"]
    ratio = scores["fresh", "decompose"]["tokens"] / scores["fresh", "tool"]["tokens"]
    print(f"\nrule: {DECOMPOSE_RULE}")
    print(f"fresh gain {gain:+d} (need >= {MIN_GAIN}); eval set held: {held}; cost {ratio:.1f}x (limit {MAX_COST_RATIO}x)")
    adopt = gain >= MIN_GAIN and held and ratio <= MAX_COST_RATIO
    print("ADOPT: switch aerospace intensive to decompose" if adopt else "NOT ADOPTED")


if __name__ == "__main__":
    main()
