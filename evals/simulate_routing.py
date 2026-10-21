"""Offline routing simulation: score routing policies from saved result files, no model calls.

Every model ran every problem, so any routing decision can be replayed from the
saved answers. A policy gives each level a cascade of steps:

    (model, verifier)   take model's answer unless plm.numeric.checks.check() flags it,
                        or verifier is set and its answer disagrees -> next step.
                        The last step's answer is always accepted.

Every call made is paid for. Levels come from the pack's classifier (what the real
controller sees) or, with --labels, the hand labels. Compute is approximated as
model params x generated tokens; it ignores prompt tokens and model load time.

    .venv/bin/python evals/simulate_routing.py [--pack electrical|aerospace] [--labels]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import grade  # noqa: E402
from plm.numeric.checks import agree, check  # noqa: E402
from plm.aerospace.levels import classify as aerospace_classify  # noqa: E402
from plm.electrical.levels import classify as electrical_classify  # noqa: E402

RESULTS = ROOT / "results"
F = {
    "0.6B": "electrical__hf.co_bartowski_mlabonne_Qwen3-0.6B-abliterated-GGUF_Q4_K_M.jsonl",
    "4B": "electrical__hf.co_bartowski_mlabonne_Qwen3-4B-abliterated-GGUF_Q4_K_M.jsonl",
    "4B+tool": "electrical__hf.co_bartowski_mlabonne_Qwen3-4B-abliterated-GGUF_Q4_K_M__tool.jsonl",
    "8B": "electrical__qwen3_8b.jsonl",
    "8B+tool": "electrical__qwen3_8b__tool.jsonl",
    "4B+formula": "electrical__hf.co_bartowski_mlabonne_Qwen3-4B-abliterated-GGUF_Q4_K_M__formula.jsonl",
    "8B+formula": "electrical__qwen3_8b__formula.jsonl",
    # The fair 4B comparators (results/run_4b_compare.sh).
    "orig4B": "electrical__hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M.jsonl",
    "orig4B+tool": "electrical__hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M__tool.jsonl",
    "inst4B+tool": "electrical__qwen3_4b-instruct-2507-q4_K_M__tool.jsonl",
}
PARAMS = {"0.6B": 0.6, "4B": 4, "8B": 8, "orig4B": 4, "inst4B": 4}


def same(steps):
    return {"calm": steps, "alert": steps, "intensive": steps}


def tiers(low, high):
    return {"calm": low, "alert": low, "intensive": high}


POLICIES = [
    ("always 8B (bare)", same([("8B", None)])),
    ("always 8B+tool", same([("8B+tool", None)])),
    ("always 4B+tool", same([("4B+tool", None)])),
    ("routed: 4B+tool | 8B+tool", tiers([("4B+tool", None)], [("8B+tool", None)])),
    ("  + escalate on failed check", tiers([("4B+tool", None), ("8B+tool", None)],
                                           [("8B+tool", None), ("8B", None)])),
    ("  + escalate on disagree w/ 0.6B", tiers([("4B+tool", "0.6B"), ("8B+tool", None)], [("8B+tool", None)])),
    ("  + escalate on disagree w/ 4B bare", tiers([("4B+tool", "4B"), ("8B+tool", None)], [("8B+tool", None)])),
    ("  + same, intensive verified by 4B+tool", tiers([("4B+tool", "4B"), ("8B+tool", None)],
                                                      [("8B+tool", "4B+tool"), ("8B", None)])),
    ("unrouted cascade: 4B+tool vs 4B -> 8B+tool", same([("4B+tool", "4B"), ("8B+tool", None)])),
    ("unrouted cascade from 0.6B", same([("0.6B", None), ("4B+tool", "4B"), ("8B+tool", None)])),
    # Added after the formula-first sweep results were seen.
    ("always 8B+formula", same([("8B+formula", None)])),
    ("routed: 4B+tool | 8B+formula", tiers([("4B+tool", None)], [("8B+formula", None)])),
    ("routed: 4B+formula | 8B+formula", tiers([("4B+formula", None)], [("8B+formula", None)])),
    ("routed: 4B+tool vs 4B+formula -> 8B+formula", tiers([("4B+tool", "4B+formula"), ("8B+formula", None)],
                                                          [("8B+formula", None)])),
    # Added after the 4B comparison sweep: the default policy's shape with each candidate small model
    # (orig4B = original Qwen3-4B, inst4B = Qwen3-4B-Instruct-2507; "4B" above is the abliterated build).
    ("routed: orig4B+tool | 8B+tool", tiers([("orig4B+tool", None), ("8B+tool", None)],
                                            [("8B+tool", None), ("8B", None)])),
    ("routed: inst4B+tool | 8B+tool", tiers([("inst4B+tool", None), ("8B+tool", None)],
                                            [("8B+tool", None), ("8B", None)])),
    ("always orig4B+tool", same([("orig4B+tool", None)])),
    ("always orig4B (bare)", same([("orig4B", None)])),
]

# Aerospace: "4B" is the original Qwen3-4B, the default small tier (results/run_aerospace.sh).
# These policies were fixed before the aerospace sweep ran.
SMALL = "hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M"
F_AEROSPACE = {
    "4B": f"aerospace__{SMALL}.jsonl",
    "4B+tool": f"aerospace__{SMALL}__tool.jsonl",
    "8B": "aerospace__qwen3_8b.jsonl",
    "8B+tool": "aerospace__qwen3_8b__tool.jsonl",
}
POLICIES_AEROSPACE = [
    ("always 8B (bare)", same([("8B", None)])),
    ("always 8B+tool", same([("8B+tool", None)])),
    ("always 4B (bare)", same([("4B", None)])),
    ("always 4B+tool", same([("4B+tool", None)])),
    ("routed: 4B+tool | 8B+tool", tiers([("4B+tool", None)], [("8B+tool", None)])),
    ("  + escalate on failed check (the default)", tiers([("4B+tool", None), ("8B+tool", None)],
                                                         [("8B+tool", None), ("8B", None)])),
    ("  + escalate on disagree w/ 4B bare", tiers([("4B+tool", "4B"), ("8B+tool", None)],
                                                  [("8B+tool", None), ("8B", None)])),
]

PACKS = {
    "electrical": ("evals/electrical/problems.jsonl", electrical_classify, F, POLICIES),
    "aerospace": ("evals/aerospace/problems.jsonl", aerospace_classify, F_AEROSPACE, POLICIES_AEROSPACE),
}


def main():
    pack = sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else "electrical"
    problems_path, classify, F, policies = PACKS[pack]
    probs = grade.load_jsonl(ROOT / problems_path)
    n = len(probs)
    R = {k: {r["id"]: r for r in grade.load_jsonl(RESULTS / v)} for k, v in F.items()}
    ok = {k: {p["id"]: grade.grade_one(p, R[k][p["id"]]["response"])["verdict"] == "correct" for p in probs} for k in F}
    cost = {k: {p["id"]: PARAMS[k.split("+")[0]] * R[k][p["id"]]["eval_tokens"] for p in probs} for k in F}
    out = {k: {p["id"]: R[k][p["id"]]["response"] for p in probs} for k in F}
    if "--labels" in sys.argv:
        src, levels = "hand labels", {p["id"]: p["level"] for p in probs}
    else:
        src, levels = f"plm.{pack}.levels classifier", {p["id"]: classify(p["question"])[0] for p in probs}
    base = sum(cost["8B"].values())

    def cascade(p, steps):
        pid, q = p["id"], p["question"]
        spend = 0
        for i, (model, verifier) in enumerate(steps):
            spend += cost[model][pid]
            if i == len(steps) - 1:
                return model, spend, i
            if check(q, out[model][pid]):
                continue
            if verifier:
                spend += cost[verifier][pid]
                if not agree(q, out[model][pid], out[verifier][pid]):
                    continue
            return model, spend, i
        raise AssertionError("unreachable")

    print(f"levels from: {src}\n")
    print(f"{'policy (calm+alert | intensive)':<44} {'score':>6} {'compute':>8} {'escalated':>10}")
    for name, pol in policies:
        score = spend = escalated = 0
        for p in probs:
            model, s, step = cascade(p, pol[levels[p["id"]]])
            score += ok[model][p["id"]]
            spend += s
            escalated += step > 0
        print(f"{name:<44} {score:>3}/{n} {spend / base:>8.0%} {escalated:>10}")

    # Hindsight bound: cheapest saved answer that was correct (8B bare if none were).
    spend = score = 0
    for p in probs:
        right = [k for k in F if ok[k][p["id"]]]
        k = min(right, key=lambda k: cost[k][p["id"]]) if right else "8B"
        score += ok[k][p["id"]]
        spend += cost[k][p["id"]]
    print(f"{'hindsight: cheapest correct answer':<44} {score:>3}/{n} {spend / base:>8.0%}")


if __name__ == "__main__":
    main()
