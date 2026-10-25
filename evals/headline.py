"""The headline table: every public benchmark, each model alone, what the pack ships, and the hindsight bound.

    .venv/bin/python evals/headline.py            # prints the markdown table (docs/results.md holds a copy)

Reads only saved answers (results/bench_*), no model calls. "Ships" replays the pack's current
policy on those answers; "hindsight" counts a task right if any setup that ran got it right (the
best any router over these setups could do). Scores use each runner's own grade (see its docstring).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

R = ROOT / "results"
SMALL, LARGE, CODER = "hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M", "qwen3_8b", "qwen2.5-coder_14b"


def load(name):
    p = R / name
    return {r["id"]: r for r in map(json.loads, open(p))} if p.exists() else None


def sql(bench):
    runs = {k: load(f"bench_{bench}__{m}.jsonl") for k, m in (("4B", SMALL), ("8B", LARGE), ("coder", CODER))}
    bad = {i for r in runs.values() for i, x in r.items() if x["verdict"] == "gold_error"}
    ok = {k: {i: x["verdict"] == "correct" for i, x in r.items() if i not in bad} for k, r in runs.items()}
    return ok, ok["coder"], "coder alone"


def code():
    from bench_code import REFERENCE_FAILS
    ok = {}
    for k, m in (("4B", SMALL), ("8B", LARGE), ("coder", CODER)):
        ok[k] = {i: x["verdict"] == "pass" for b in ("humaneval", "mbpp")
                 for i, x in load(f"bench_{b}__{m}.jsonl").items() if i not in REFERENCE_FAILS}
    return ok, ok["coder"], "coder alone"


def physics():
    from bench_physics import problems
    from plm_physics.levels import classify
    runs = {"4B": load(f"bench_scibench__{SMALL}.jsonl"), "4B+calc": load(f"bench_scibench__{SMALL}__tool.jsonl"),
            "8B": load(f"bench_scibench__{LARGE}.jsonl"), "8B+calc": load(f"bench_scibench__{LARGE}__tool.jsonl")}
    ok = {k: {i: x["correct"] for i, x in r.items()} for k, r in runs.items()}
    shipped = {}
    for p in problems():
        chain = ["8B+calc", "8B"] if classify(p["question"])[0] == "intensive" else ["4B+calc", "8B+calc"]
        k = chain[0] if not runs[chain[0]][p["id"]]["issues"] else chain[1]
        shipped[p["id"]] = ok[k][p["id"]]
    return ok, shipped, "4B+calc -> 8B+calc (routed)"


def theoremqa():
    import bench_physics
    bench_physics.BENCH = "theoremqa"
    from plm_physics.levels import classify
    runs = {"4B": load(f"bench_theoremqa__{SMALL}.jsonl"), "4B+calc": load(f"bench_theoremqa__{SMALL}__tool.jsonl"),
            "8B": load(f"bench_theoremqa__{LARGE}.jsonl"), "8B+calc": load(f"bench_theoremqa__{LARGE}__tool.jsonl")}
    ok = {k: {i: x["correct"] for i, x in r.items()} for k, r in runs.items()}
    shipped = {}
    for p in bench_physics.problems():
        chain = ["8B+calc", "8B"] if classify(p["question"])[0] == "intensive" else ["4B+calc", "8B+calc"]
        k = chain[0] if not runs[chain[0]][p["id"]]["issues"] else chain[1]
        shipped[p["id"]] = ok[k][p["id"]]
    bench_physics.BENCH = "scibench"
    return ok, shipped, "4B+calc -> 8B+calc (routed)"


def cad():
    runs = {k: load(f"bench_cadprompt__{m}.jsonl") for k, m in (("4B", SMALL), ("8B", LARGE), ("coder", CODER))}
    ok = {k: {i: x["verdict"] == "correct" for i, x in r.items()} for k, r in runs.items()}
    return ok, ok["coder"], "coder alone"


def gsm8k():
    runs = {"8B": load(f"bench_gsm8k__{LARGE}.jsonl"), "8B+calc": load(f"bench_gsm8k__{LARGE}__tool.jsonl"),
            "4B+calc": load(f"bench_gsm8k__{SMALL}__tool.jsonl")}
    ok = {k: {i: x["correct"] for i, x in r.items()} for k, r in runs.items()}
    return ok, ok["8B"], "general pack: 8B direct"


def pct(d):
    return f"{sum(d.values())}/{len(d)} ({sum(d.values()) / len(d):.0%})"


def main():
    rows = [("SQL", "Spider dev (300 sampled)", *sql("spider")), ("SQL", "BIRD mini-dev", *sql("bird")),
            ("Software", "HumanEval+ and MBPP+", *code()), ("Physics", "SciBench physics", *physics()),
            ("Physics", "TheoremQA physics (confirmation)", *theoremqa()), ("CAD", "CADPrompt (195 parts)", *cad()),
            ("General", "GSM8K (300 sampled)", *gsm8k())]
    print("| Pack | Benchmark | " + " | ".join(["4B", "8B", "Coder 14B"]) + " | Ships | Hindsight |")
    print("|---|---|---|---|---|---|---|")
    for pack, bench, ok, shipped, policy in rows:
        def best(prefix):
            ks = [k for k in ok if k.split("+")[0] == prefix]
            return max((pct(ok[k]) + (" (+calc)" if "+" in k else "") for k in ks),
                       key=lambda s: int(s.split("/")[0])) if ks else "not run"
        hind = {i: any(ok[k][i] for k in ok) for i in shipped}
        print(f"| {pack} | {bench} | {best('4B')} | {best('8B')} | {best('coder')} | "
              f"{pct(shipped)}: {policy} | {pct(hind)} |")
    print("\nModel columns show each model's better strategy (direct or +calc) where both ran.")


if __name__ == "__main__":
    main()
