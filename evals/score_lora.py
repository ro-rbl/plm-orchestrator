"""Judge the aerospace 4B LoRA on the fresh judge set, and apply its adoption rule.

    .venv/bin/python evals/score_lora.py

Four models answer evals/aerospace/fresh_lora.jsonl with the calculator (tool strategy):
the shipped 4B (bartowski Q4_K_M), the control (the MLX 4-bit base, dequantized and
re-exported to Q8_0 like the tuned model, no adapter), the tuned 4B, and the 8B, which
the aerospace pack ships for every level. Levels come from the aerospace classifier, as
in production. Compute is model size x generated tokens, as in simulate_routing.py.

Rule, sets and training settings fixed on 2026-10-23 before training or any result.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import grade  # noqa: E402
import plm.packs  # noqa: E402,F401  (loads every pack, and with it its unit words)
from plm.numeric.checks import check  # noqa: E402
from plm_aerospace.levels import classify  # noqa: E402

PROBLEMS = ROOT / "evals/aerospace/fresh_lora.jsonl"
MODELS = {  # key -> (results file, size in billions of parameters)
    "4B": ("aerospace_fresh_lora__hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M__tool.jsonl", 4),
    "control": ("aerospace_fresh_lora__plm-qwen3-4b-control__tool.jsonl", 4),
    "tuned": ("aerospace_fresh_lora__plm-qwen3-4b-aero-lora__tool.jsonl", 4),
    "8B": ("aerospace_fresh_lora__qwen3_8b__tool.jsonl", 8),
}
LORA_RULE = ("calm and alert aerospace problems go to the tuned 4B + calculator (escalating to the 8B + calculator "
             "on a failed check; intensive to the 8B) iff, on the fresh set with the classifier's levels: (1) the "
             "tuned 4B beats the control on calm + alert problems by at least 2; (2) on alert problems it is within "
             "1 of the 8B + calculator; (3) that routed policy scores within 1 of always-8B + calculator, at lower compute")


def main():
    problems = grade.load_jsonl(PROBLEMS)
    rows = {}
    for k, (f, _) in MODELS.items():
        path = ROOT / "results" / f
        if not path.exists() or len(grade.load_jsonl(path)) < len(problems):
            sys.exit(f"no complete results for {k} ({f}); run evals/aerospace/lora_pipeline.sh")
        rows[k] = {r["id"]: r for r in grade.load_jsonl(path)}
    level = {p["id"]: classify(p["question"])[0] for p in problems}
    ok = {k: {p["id"]: grade.grade_one(p, rows[k][p["id"]]["response"])["verdict"] == "correct" for p in problems}
          for k in rows}
    cost = {k: {pid: MODELS[k][1] * r["eval_tokens"] for pid, r in rows[k].items()} for k in rows}

    def score(k, levels):
        return sum(ok[k][p["id"]] for p in problems if level[p["id"]] in levels)

    print(f"{'model':<8} {'calm':>5} {'alert':>6} {'intensive':>10} {'all':>5}   (levels from the classifier)")
    counts = {lv: sum(level[p["id"]] == lv for p in problems) for lv in ("calm", "alert", "intensive")}
    for k in rows:
        print(f"{k:<8} {score(k, {'calm'}):>2}/{counts['calm']:<2} {score(k, {'alert'}):>3}/{counts['alert']:<2} "
              f"{score(k, {'intensive'}):>6}/{counts['intensive']:<3} {score(k, {'calm', 'alert', 'intensive'}):>2}/{len(problems)}")

    routed = routed_cost = 0
    for p in problems:
        pid = p["id"]
        if level[pid] == "intensive":
            routed += ok["8B"][pid]
            routed_cost += cost["8B"][pid]
            continue
        routed_cost += cost["tuned"][pid]
        if check(p["question"], rows["tuned"][pid]["response"]):  # failed check: escalate
            routed_cost += cost["8B"][pid]
            routed += ok["8B"][pid]
        else:
            routed += ok["tuned"][pid]
    always_8b, always_8b_cost = score("8B", {"calm", "alert", "intensive"}), sum(cost["8B"].values())
    print(f"\nrouted (tuned 4B for calm + alert, escalating): {routed}/{len(problems)} at "
          f"{routed_cost / always_8b_cost:.0%} of always-8B compute; always 8B: {always_8b}/{len(problems)}")

    c1 = score("tuned", {"calm", "alert"}) - score("control", {"calm", "alert"})
    c2 = score("8B", {"alert"}) - score("tuned", {"alert"})
    c3 = always_8b - routed
    print(f"\nrule: {LORA_RULE}")
    print(f"(1) tuned - control on calm + alert: {c1:+d} (need >= 2)  (2) 8B - tuned on alert: {c2:+d} (need <= 1)"
          f"  (3) always-8B - routed: {c3:+d} (need <= 1), compute {routed_cost / always_8b_cost:.0%}")
    adopt = c1 >= 2 and c2 <= 1 and c3 <= 1 and routed_cost < always_8b_cost
    print("-> ADOPT: route calm and alert to the tuned 4B" if adopt else "-> NOT ADOPTED: keep everything on the 8B")


if __name__ == "__main__":
    main()
