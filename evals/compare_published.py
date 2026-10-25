"""Our shipped setups against published scores from other models, on the same public benchmarks.

    .venv/bin/python evals/compare_published.py      # re-runs saved BIRD queries (no model calls), prints tables

Published numbers are copied from their sources (retrieved 2026-10-24, kept in .benchmarks/leaderboards/):
    EvalPlus leaderboard   https://evalplus.github.io/results.json  (pass@1, greedy; HumanEval+ 164, MBPP+ 378)
    BIRD mini-dev          https://github.com/bird-bench/mini_dev README, "Baseline performance", EX on SQLite (500)
They are other people's runs with their own prompts, so the comparison is indicative, not exact.
To match the published grades: code uses our saved plus-test results (the same EvalPlus tests);
BIRD is regraded here with BIRD's own EX rule (the sets of result rows are equal), not our stricter one.
Spider has no comparable small-model leaderboard for its dev set with our setup, so it isn't compared.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import bench_sql  # noqa: E402
from bench_code import REFERENCE_FAILS  # noqa: E402
from plm_sql.sandbox import MAX_ROWS, run_query  # noqa: E402

R = ROOT / "results"
OURS = {"Qwen3-4B (Q4_K_M)": "hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M", "Qwen3-8B (Q4_K_M)": "qwen3_8b",
        "Qwen2.5-Coder-14B (Q4_K_M)": "qwen2.5-coder_14b"}
EVALPLUS = {  # model: (HumanEval+, MBPP+) pass@1 %
    "GPT-4o (Aug 2024)": (87.2, 72.2), "Qwen2.5-Coder-32B-Instruct": (87.2, 77.0), "GPT-4o mini (Jul 2024)": (83.5, 72.2),
    "DeepSeek-Coder-V2-Instruct (236B MoE)": (82.3, 75.1), "Claude 3.5 Sonnet (Jun 2024)": (81.7, 74.3),
    "CodeQwen1.5-7B-Chat": (78.7, 69.0), "Claude 3 Opus (Mar 2024)": (77.4, 73.3), "Llama-3-70B-Instruct": (72.0, 69.0),
    "GPT-3.5-Turbo (Nov 2023)": (70.7, 69.7), "Llama-3-8B-Instruct": (56.7, 54.8),
}
BIRD = {  # model: EX % on BIRD mini-dev, SQLite
    "GPT-4": 47.8, "GPT-4-32k": 47.0, "GPT-4-Turbo": 45.8, "Llama-3-70B-Instruct": 40.8, "GPT-3.5-Turbo": 38.0,
    "Phi-3-medium-128k-instruct": 30.6, "Llama-3-8B-Instruct": 24.4, "Mixtral-8x7B": 21.6,
}


def code_scores(model_file):
    out = []
    for bench in ("humaneval", "mbpp"):
        rows = [json.loads(line) for line in open(R / f"bench_{bench}__{model_file}.jsonl")]
        rows = [r for r in rows if r["id"] not in REFERENCE_FAILS]
        out.append(100 * sum(r["verdict"] == "pass" for r in rows) / len(rows))
    return out


def bird_ex(model_file):
    """BIRD's EX: the query's result rows, as a set, equal the gold query's."""
    tasks = {t["id"]: t for t in bench_sql.tasks("bird")}
    rows = {r["id"]: r for r in map(json.loads, open(R / f"bench_bird__{model_file}.jsonl"))}
    right = n = 0
    for tid, t in tasks.items():
        gold = run_query("", t["reference"], seconds=30, db_path=t["db"])
        if gold["error"] or gold["n_rows"] > MAX_ROWS:
            continue  # the gold query errors here (dropped, as in bench_sql), or is too big to compare in full
        n += 1
        q = rows[tid]["query"]
        if not q:
            continue
        got = run_query("", q, seconds=30, db_path=t["db"])
        if not got["error"] and got["n_rows"] <= MAX_ROWS:
            right += {tuple(r) for r in got["rows"]} == {tuple(r) for r in gold["rows"]}
    return 100 * right / n, n


def main():
    print("## Code: HumanEval+ and MBPP+ (EvalPlus plus tests, pass@1)\n")
    print("| Model | HumanEval+ | MBPP+ | Where |\n|---|---|---|---|")
    table = [(name, he, mb, "published (EvalPlus)") for name, (he, mb) in EVALPLUS.items()]
    for name, f in OURS.items():
        he, mb = code_scores(f)
        table.append((name, he, mb, "ours, local" + (" (the software pack ships this)" if "Coder" in name else "")))
    for name, he, mb, where in sorted(table, key=lambda r: -r[1]):
        print(f"| {name} | {he:.1f} | {mb:.1f} | {where} |")

    print("\n## SQL: BIRD mini-dev, SQLite, execution accuracy (BIRD's EX rule)\n")
    print("| Model | EX | Where |\n|---|---|---|")
    table = [(name, ex, "published (BIRD mini-dev README, baseline)") for name, ex in BIRD.items()]
    for name, f in OURS.items():
        ex, n = bird_ex(f)
        table.append((name, ex, f"ours, local, {n} questions" + (" (the SQL pack ships this)" if "Coder" in name else "")))
    for name, ex, where in sorted(table, key=lambda r: -r[1]):
        print(f"| {name} | {ex:.1f} | {where} |")


if __name__ == "__main__":
    main()
