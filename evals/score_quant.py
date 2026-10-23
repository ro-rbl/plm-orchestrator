"""Judge a Q8_0 small tier against the shipped Q4_K_M one, and apply the rule fixed before any Q8_0 answer.

    .venv/bin/python evals/score_quant.py

The hypothesis comes from the LoRA run (results/lora.log): its control, the 4B re-exported
at Q8_0, beat the shipped Q4_K_M 4B 26 to 22 on ae-l-*. That control came from MLX 4-bit
weights, so it doesn't isolate the quantization; this test does: both 4Bs are bartowski's
GGUFs of Qwen/Qwen3-4B, differing only in quant (Q4_K_M 2.5 GB, Q8_0 4.3 GB).

Problems: the electrical, aerospace and physics eval sets (150; the hypothesis wasn't formed
on them) plus evals/<pack>/fresh_quant.jsonl (36, written before the Q8_0 4B answered
anything). The shipped Q4_K_M answers on the eval sets are the saved ones: 8 of them re-run
on 2026-10-23 came back token-identical (temperature 0). Levels come from each pack's
classifier; compute is model size x generated tokens, relative to the always-8B (bare)
baseline, as in simulate_routing.py. Run: results/run_quant.sh.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import grade  # noqa: E402
import plm.packs  # noqa: E402,F401  (loads every pack, and with it its unit words)
from plm.numeric.checks import check  # noqa: E402
from plm_aerospace.levels import classify as aerospace_classify  # noqa: E402
from plm_electrical.levels import classify as electrical_classify  # noqa: E402
from plm_physics.levels import classify as physics_classify  # noqa: E402

PACKS = {"electrical": electrical_classify, "aerospace": aerospace_classify, "physics": physics_classify}
SETS = ("problems", "fresh_quant")
MODELS = {  # key -> (results-file model name, suffix, size in billions of parameters)
    "Q4+tool": ("hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M", "__tool", 4),
    "Q8+tool": ("hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q8_0", "__tool", 4),
    "8B+tool": ("qwen3_8b", "__tool", 8),
    "8B": ("qwen3_8b", "", 8),
}
LOW, HIGH = ("calm", "alert"), ("intensive",)
# Each pack's shipped policy, as a cascade per level (escalate on a failed check; the last step is kept).
SHIPPED = {
    "electrical": {**{lv: ["Q4+tool", "8B+tool"] for lv in LOW}, "intensive": ["8B+tool", "8B"]},
    "aerospace": {lv: ["8B+tool"] for lv in LOW + HIGH},
    "physics": {lv: ["8B"] for lv in LOW + HIGH},
}
CANDIDATE = {**{lv: ["Q8+tool", "8B+tool"] for lv in LOW}, "intensive": ["8B+tool", "8B"]}
QUANT_RULE = (
    "(1) the Q8_0 4B is better iff, with the calculator, on the 186 problems (three eval sets and the fresh set) "
    "it wins more of the problems the two 4Bs disagree on than chance allows (one-sided sign test, p < 0.05), and "
    "on no pack (eval + fresh) does it score more than 2 below the Q4_K_M 4B; "
    "(2) only then, per pack, the routed policy with the Q8_0 4B (calm + alert: Q8_0 4B + calculator, escalating "
    "to the 8B + calculator on a failed check; intensive: 8B + calculator, then 8B) replaces the shipped policy iff, "
    "on that pack's eval and fresh problems together, it scores at least the shipped score minus 1 at lower "
    "compute; for electrical, whose shipped policy already routes to the Q4_K_M 4B, at least the shipped score at "
    "no more than 10 points more compute")


def sign_test(wins, losses):
    """One-sided exact binomial p of at least `wins` successes in wins + losses fair coin flips."""
    n = wins + losses
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n if n else 1.0


def load(pack, set_name, key):
    model, suffix, _ = MODELS[key]
    stem = pack if set_name == "problems" else f"{pack}_{set_name}"
    path = ROOT / "results" / f"{stem}__{model}{suffix}.jsonl"
    return {r["id"]: r for r in grade.load_jsonl(path)} if path.exists() else {}


def main():
    probs, rows, missing = {}, {}, []
    for pack in PACKS:
        probs[pack] = [p for s in SETS for p in grade.load_jsonl(ROOT / f"evals/{pack}/{s}.jsonl")]
        for key in MODELS:
            rows[pack, key] = {}
            for s in SETS:
                got = load(pack, s, key)
                want = {p["id"] for p in grade.load_jsonl(ROOT / f"evals/{pack}/{s}.jsonl")}
                if not want <= got.keys():
                    missing.append(f"{pack} {s} {key} ({len(want & got.keys())}/{len(want)})")
                rows[pack, key].update(got)
    if missing:
        sys.exit("no complete results yet for: " + ", ".join(missing) + "; run results/run_quant.sh")

    ok, cost, level = {}, {}, {}
    for pack, classify in PACKS.items():
        for p in probs[pack]:
            level[p["id"]] = classify(p["question"])[0]
            for key in MODELS:
                r = rows[pack, key][p["id"]]
                ok[key, p["id"]] = grade.grade_one(p, r["response"])["verdict"] == "correct"
                cost[key, p["id"]] = MODELS[key][2] * r["eval_tokens"]

    # (1) Q8_0 vs Q4_K_M, with the calculator, problem by problem.
    print(f"{'pack':<11} {'set':<12} {'n':>3} {'Q4_K_M':>7} {'Q8_0':>5}   with the calculator")
    wins = losses = 0
    worst = 0
    for pack in PACKS:
        for s in SETS:
            ids = [p["id"] for p in grade.load_jsonl(ROOT / f"evals/{pack}/{s}.jsonl")]
            q4, q8 = sum(ok["Q4+tool", i] for i in ids), sum(ok["Q8+tool", i] for i in ids)
            print(f"{pack:<11} {s:<12} {len(ids):>3} {q4:>7} {q8:>5}")
        ids = [p["id"] for p in probs[pack]]
        worst = min(worst, sum(ok["Q8+tool", i] for i in ids) - sum(ok["Q4+tool", i] for i in ids))
        wins += sum(ok["Q8+tool", i] and not ok["Q4+tool", i] for i in ids)
        losses += sum(ok["Q4+tool", i] and not ok["Q8+tool", i] for i in ids)
    p_value = sign_test(wins, losses)
    better = p_value < 0.05 and worst >= -2
    print(f"\ndisagreements: Q8_0 right only {wins}, Q4_K_M right only {losses}; one-sided sign test p = {p_value:.3f}; "
          f"worst pack Q8_0 - Q4_K_M: {worst:+d}")

    # (2) per pack: the routed policy with the Q8_0 4B vs the shipped policy.
    def run(pack, policy):
        score = spend = 0
        for p in probs[pack]:
            chain = policy[level[p["id"]]]
            for i, key in enumerate(chain):
                spend += cost[key, p["id"]]
                if i == len(chain) - 1 or not check(p["question"], rows[pack, key][p["id"]]["response"]):
                    break
            score += ok[key, p["id"]]
        return score, spend / sum(cost["8B", p["id"]] for p in probs[pack])

    print(f"\n{'pack':<11} {'n':>3} {'shipped':>14} {'Q8_0 routed':>16}   (compute vs always-8B bare)")
    adopted = []
    for pack in PACKS:
        (s_score, s_cost), (c_score, c_cost) = run(pack, SHIPPED[pack]), run(pack, CANDIDATE)
        if pack == "electrical":
            passes = c_score >= s_score and c_cost <= s_cost + 0.10
        else:
            passes = c_score >= s_score - 1 and c_cost < s_cost
        print(f"{pack:<11} {len(probs[pack]):>3} {s_score:>4} at {s_cost:>4.0%}   {c_score:>6} at {c_cost:>4.0%}"
              f"   {'passes' if passes else 'fails'} part (2)")
        if better and passes:
            adopted.append(pack)

    print(f"\nrule: {QUANT_RULE}")
    print(f"(1) Q8_0 better: {'yes' if better else 'no'}")
    if adopted:
        print(f"-> ADOPT: the Q8_0 4B routed for {', '.join(adopted)}")
    else:
        print("-> NOT ADOPTED: keep the shipped policies" + ("" if better else " (part 1 failed)"))


if __name__ == "__main__":
    main()
