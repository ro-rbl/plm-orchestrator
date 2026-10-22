"""Offline routing simulation: score routing policies from saved result files, no model calls.

Every model ran every problem, so any routing decision can be replayed from the
saved answers. A policy gives each level a cascade of steps:

    (model, verifier)   take model's answer unless plm.numeric.checks.check() flags it,
                        or verifier is set and its answer disagrees -> next step.
                        The last step's answer is always accepted.

Every call made is paid for. Levels come from the pack's classifier (what the real
controller sees) or, with --labels, the hand labels. Compute is approximated as
model params x generated tokens; it ignores prompt tokens and model load time.

    .venv/bin/python evals/simulate_routing.py [--pack electrical|aerospace] [--labels] [--checks]

--checks also prints, per strategy, how many wrong answers the checks catch.
Policies whose result files don't exist yet print "(not run yet)".
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import grade  # noqa: E402
import plm.packs  # noqa: E402,F401  (loads every pack, and with it its unit words)
from plm.numeric.checks import agree, check  # noqa: E402
from plm_aerospace.levels import classify as aerospace_classify  # noqa: E402
from plm_electrical.levels import classify as electrical_classify  # noqa: E402
from plm_physics.levels import classify as physics_classify  # noqa: E402

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
    # Unit-aware calculator (results/run_units.sh).
    "orig4B+units": "electrical__hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M__units.jsonl",
    "8B+units": "electrical__qwen3_8b__units.jsonl",
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
    # UNITS: fixed before the unit-aware calculator sweep ran (see UNITS_RULE).
    ("units: routed orig4B+units | 8B+units", tiers([("orig4B+units", None), ("8B+units", None)],
                                                    [("8B+units", None), ("8B", None)])),
    ("units: same, failed check -> plain calculator", tiers([("orig4B+units", None), ("orig4B+tool", None),
                                                             ("8B+tool", None)],
                                                            [("8B+units", None), ("8B+tool", None)])),
    ("units: always 8B+units", same([("8B+units", None)])),
]

# Aerospace: "4B" is the original Qwen3-4B, the default small tier (results/run_aerospace.sh).
# These policies were fixed before the aerospace sweep ran.
SMALL = "hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M"
F_AEROSPACE = {
    "4B": f"aerospace__{SMALL}.jsonl",
    "4B+tool": f"aerospace__{SMALL}__tool.jsonl",
    "8B": "aerospace__qwen3_8b.jsonl",
    "8B+tool": "aerospace__qwen3_8b__tool.jsonl",
    "4B+units": f"aerospace__{SMALL}__units.jsonl",
    "8B+units": "aerospace__qwen3_8b__units.jsonl",
}
POLICIES_AEROSPACE = [
    ("always 8B (bare)", same([("8B", None)])),
    ("always 8B+tool (shipped)", same([("8B+tool", None)])),
    ("always 4B (bare)", same([("4B", None)])),
    ("always 4B+tool", same([("4B+tool", None)])),
    ("routed: 4B+tool | 8B+tool", tiers([("4B+tool", None)], [("8B+tool", None)])),
    ("  + escalate on failed check (first default)", tiers([("4B+tool", None), ("8B+tool", None)],
                                                         [("8B+tool", None), ("8B", None)])),
    ("  + escalate on disagree w/ 4B bare", tiers([("4B+tool", "4B"), ("8B+tool", None)],
                                                  [("8B+tool", None), ("8B", None)])),
    # Added after the aerospace sweep was seen; hypotheses for fresh problems, not picks.
    ("post-hoc: calm 4B+tool, rest 8B+tool", {"calm": [("4B+tool", None)], "alert": [("8B+tool", None)],
                                              "intensive": [("8B+tool", None)]}),
    ("post-hoc: always 8B+tool, failed check -> 8B", same([("8B+tool", None), ("8B", None)])),
    # UNITS: fixed before the unit-aware calculator sweep ran (see UNITS_RULE).
    ("units: always 8B+units", same([("8B+units", None)])),
    ("units: 8B+units, failed check -> 8B+tool", same([("8B+units", None), ("8B+tool", None)])),
    ("units: routed 4B+units | 8B+units, escalating", tiers([("4B+units", None), ("8B+units", None)],
                                                            [("8B+units", None), ("8B+tool", None)])),
]

# Adoption rule for the unit-aware calculator, fixed before its sweep: a pack switches to a
# "units:" policy only if that policy is at least as accurate as the pack's shipped policy and
# costs at most 10 points more compute (shipped: electrical 48/50 at 35%, aerospace 39/50 at
# 41%). Secondary, reported either way: with --checks, the share of wrong answers the checks
# catch, units vs plain calculator for the same model.
UNITS_RULE = "units policy adopted iff accuracy >= shipped and compute <= shipped + 10 points"

# Physics: written with the pack, before its sweep (results/run_physics.sh) ran. The controller ships
# "escalate on failed check" until the sweep; PHYSICS_RULE then picks among these policies, applied
# below by pick_physics(), so the choice is mechanical. The rule is the one aerospace's switch followed
# in effect (routed 37/50 was 2 behind always-8B+tool 39/50, so the 8B shipped), written down first.
F_PHYSICS = {
    "4B": f"physics__{SMALL}.jsonl",
    "4B+tool": f"physics__{SMALL}__tool.jsonl",
    "8B": "physics__qwen3_8b.jsonl",
    "8B+tool": "physics__qwen3_8b__tool.jsonl",
}
POLICIES_PHYSICS = [
    ("always 8B (bare)", same([("8B", None)])),
    ("always 8B+tool", same([("8B+tool", None)])),
    ("always 4B (bare)", same([("4B", None)])),
    ("always 4B+tool", same([("4B+tool", None)])),
    ("routed: 4B+tool | 8B+tool", tiers([("4B+tool", None)], [("8B+tool", None)])),
    ("  + escalate on failed check (pre-sweep default)", tiers([("4B+tool", None), ("8B+tool", None)],
                                                             [("8B+tool", None), ("8B", None)])),
    ("  + escalate on disagree w/ 4B bare", tiers([("4B+tool", "4B"), ("8B+tool", None)],
                                                  [("8B+tool", None), ("8B", None)])),
]
PHYSICS_RULE = ("ship the cheapest policy above whose score is within 1 problem of the best one's "
                "(levels from the physics classifier; 1-2 problems on 50 are noise)")

PACKS = {
    "electrical": ("evals/electrical/problems.jsonl", electrical_classify, F, POLICIES),
    "aerospace": ("evals/aerospace/problems.jsonl", aerospace_classify, F_AEROSPACE, POLICIES_AEROSPACE),
    "physics": ("evals/physics/problems.jsonl", physics_classify, F_PHYSICS, POLICIES_PHYSICS),
}


def pick_physics(results):
    """PHYSICS_RULE over [(policy name, score, compute)]; None until every policy has results."""
    if len(results) < len(POLICIES_PHYSICS):
        return None
    best = max(score for _, score, _ in results)
    return min((r for r in results if r[1] >= best - 1), key=lambda r: r[2])


def main():
    pack = sys.argv[sys.argv.index("--pack") + 1] if "--pack" in sys.argv else "electrical"
    problems_path, classify, F, policies = PACKS[pack]
    probs = grade.load_jsonl(ROOT / problems_path)
    n = len(probs)
    R = {k: {r["id"]: r for r in grade.load_jsonl(RESULTS / v)} for k, v in F.items() if (RESULTS / v).exists()}
    F = {k: v for k, v in F.items() if k in R}
    if "8B" not in R:
        sys.exit(f"no saved 8B answers for {pack} yet (the compute baseline); run its sweep in results/")
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
    measured = []
    for name, pol in policies:
        needed = {m for steps in pol.values() for step in steps for m in step if m}
        if not needed <= R.keys():
            print(f"{name:<44} {'(not run yet)':>16}")
            continue
        score = spend = escalated = 0
        for p in probs:
            model, s, step = cascade(p, pol[levels[p["id"]]])
            score += ok[model][p["id"]]
            spend += s
            escalated += step > 0
        print(f"{name:<44} {score:>3}/{n} {spend / base:>8.0%} {escalated:>10}")
        measured.append((name.strip(), score, spend / base))

    # Hindsight bound: cheapest saved answer that was correct (8B bare if none were).
    spend = score = 0
    for p in probs:
        right = [k for k in F if ok[k][p["id"]]]
        k = min(right, key=lambda k: cost[k][p["id"]]) if right else "8B"
        score += ok[k][p["id"]]
        spend += cost[k][p["id"]]
    print(f"{'hindsight: cheapest correct answer':<44} {score:>3}/{n} {spend / base:>8.0%}")
    if pack == "physics" and "--labels" not in sys.argv:
        chosen = pick_physics(measured)
        print(f"\nrule: {PHYSICS_RULE}")
        print(f"-> {chosen[0]} ({chosen[1]}/{n} at {chosen[2]:.0%})" if chosen else "-> needs every policy's results")

    if "--checks" in sys.argv:
        print("\nhow many wrong answers the checks catch:")
        print(f"   {'strategy':<14} {'wrong':>6} {'caught':>7} {'false alarms':>13}")
        for k in F:
            flagged = {p["id"]: bool(check(p["question"], out[k][p["id"]])) for p in probs}
            wrong = [pid for pid in flagged if not ok[k][pid]]
            false = sum(flagged[pid] and ok[k][pid] for pid in flagged)
            print(f"   {k:<14} {len(wrong):>6} {sum(flagged[pid] for pid in wrong):>7} {false:>13}")


if __name__ == "__main__":
    main()
