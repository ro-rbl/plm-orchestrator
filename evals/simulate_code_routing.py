"""Offline routing simulation for the software pack, from saved results; no model calls.

A step's answer is accepted unless the controller's check fails: no code, code
that doesn't load, or code that fails a visible example from the prompt. The
grade uses the hidden tests, which the check never sees. Every call made is paid
for; compute is approximated as model params x generated tokens.

Policies were fixed before the sweep results existed, so none was picked after
the fact.

    .venv/bin/python evals/simulate_code_routing.py [--labels]
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plm.software.levels import classify  # noqa: E402
from run_code import load_jsonl, verdict  # noqa: E402

RESULTS = ROOT / "results"
F = {
    "0.6B": "software__hf.co_bartowski_mlabonne_Qwen3-0.6B-abliterated-GGUF_Q4_K_M.jsonl",
    "4B": "software__hf.co_bartowski_mlabonne_Qwen3-4B-abliterated-GGUF_Q4_K_M.jsonl",
    "8B": "software__qwen3_8b.jsonl",
    "coder14B": "software__qwen2.5-coder_14b.jsonl",
    # The fair 4B comparators (results/run_4b_compare.sh); "4B" above is the abliterated build.
    "orig4B": "software__hf.co_bartowski_Qwen_Qwen3-4B-GGUF_Q4_K_M.jsonl",
    "inst4B": "software__qwen3_4b-instruct-2507-q4_K_M.jsonl",
}
PARAMS = {"0.6B": 0.6, "4B": 4, "8B": 8, "coder14B": 14, "orig4B": 4, "inst4B": 4}
GENCHECK = {  # test writer -> output of `evals/gen_tests.py check`
    "4B": "software_gencheck__hf.co_bartowski_mlabonne_Qwen3-4B-abliterated-GGUF_Q4_K_M.jsonl",
    "8B": "software_gencheck__qwen3_8b.jsonl",
    "coder14B": "software_gencheck__qwen2.5-coder_14b.jsonl",
}


def same(chain):
    return {"calm": chain, "alert": chain, "intensive": chain}


POLICIES = [
    ("always 0.6B", same(["0.6B"])),
    ("always 4B", same(["4B"])),
    ("always 8B", same(["8B"])),
    ("always coder14B", same(["coder14B"])),
    ("routed: 4B | 8B | coder14B", {"calm": ["4B"], "alert": ["8B"], "intensive": ["coder14B"]}),
    ("  + escalate on failed examples", {"calm": ["4B", "8B", "coder14B"], "alert": ["8B", "coder14B"],
                                         "intensive": ["coder14B", "8B"]}),
    ("routed cheap: 0.6B | 4B | 8B, escalating", {"calm": ["0.6B", "4B", "8B", "coder14B"],
                                                 "alert": ["4B", "8B", "coder14B"], "intensive": ["8B", "coder14B"]}),
    ("unrouted cascade: 4B -> 8B -> coder14B", same(["4B", "8B", "coder14B"])),
    ("unrouted cascade from 0.6B", same(["0.6B", "4B", "8B", "coder14B"])),
    # Added after the 4B comparison sweep: the default cascade with each candidate first step.
    ("unrouted cascade: orig4B -> 8B -> coder14B", same(["orig4B", "8B", "coder14B"])),
    ("unrouted cascade: inst4B -> 8B -> coder14B", same(["inst4B", "8B", "coder14B"])),
    ("always orig4B", same(["orig4B"])),
    ("always inst4B", same(["inst4B"])),
]


def check_fails(row):
    ex = row.get("examples")
    return row["code"] is None or not ex or bool(ex["error"]) or ex["passed"] < ex["total"]


def main():
    tasks = load_jsonl(ROOT / "evals/software/tasks.jsonl")
    R = {k: {r["id"]: r for r in load_jsonl(RESULTS / v)} for k, v in F.items()}
    ok = {k: {t["id"]: verdict(R[k][t["id"]]) == "pass" for t in tasks} for k in F}
    cost = {k: {t["id"]: PARAMS[k] * R[k][t["id"]]["eval_tokens"] for t in tasks} for k in F}
    flagged = {k: {t["id"]: check_fails(R[k][t["id"]]) for t in tasks} for k in F}
    if "--labels" in sys.argv:
        src, levels = "hand labels", {t["id"]: t["level"] for t in tasks}
    else:
        src, levels = "plm.software.levels classifier", {t["id"]: classify(t["prompt"])[0] for t in tasks}
    base = sum(cost["coder14B"].values())
    n = len(tasks)

    print("how well the examples check predicts the hidden-test grade:")
    print(f"{'model':<10} {'wrong':>6} {'caught':>7} {'false alarm':>12}")
    for k in F:
        wrong = sum(not ok[k][t["id"]] for t in tasks)
        caught = sum(not ok[k][t["id"]] and flagged[k][t["id"]] for t in tasks)
        false = sum(ok[k][t["id"]] and flagged[k][t["id"]] for t in tasks)
        print(f"{k:<10} {wrong:>6} {caught:>7} {false:>12}")

    print(f"\nlevels from: {src}")
    print(f"{'policy (calm | alert | intensive)':<44} {'score':>6} {'compute':>8} {'escalated':>10}")
    for name, pol in POLICIES:
        score = spend = escalated = 0
        for t in tasks:
            chain = pol[levels[t["id"]]]
            for i, k in enumerate(chain):
                spend += cost[k][t["id"]]
                if i == len(chain) - 1 or not flagged[k][t["id"]]:
                    break
            score += ok[k][t["id"]]
            escalated += i > 0
        print(f"{name:<44} {score:>3}/{n} {spend / base:>8.0%} {escalated:>10}")

    spend = score = 0
    for t in tasks:
        right = [k for k in F if ok[k][t["id"]]]
        k = min(right, key=lambda k: cost[k][t["id"]]) if right else "coder14B"
        score += ok[k][t["id"]]
        spend += cost[k][t["id"]]
    print(f"{'hindsight: cheapest correct answer':<44} {score:>3}/{n} {spend / base:>8.0%}")

    # Stronger check: examples + tests from a writer model (evals/gen_tests.py). The
    # writer's call is charged once per task. "best-of" changes only the case where
    # no step passes: take the answer that passed the examples and the most generated
    # tests instead of the last one.
    chain = ["4B", "8B", "coder14B"]
    for writer, fname in GENCHECK.items():
        path = RESULTS / fname
        if not path.exists():
            continue
        gen = {r["id"]: r for r in load_jsonl(path)}
        for fallback in ("last", "best-of"):
            score = spend = escalated = 0
            for t in tasks:
                g = gen[t["id"]]
                spend += PARAMS[writer] * g["tokens"]
                tried = []
                for i, k in enumerate(chain):
                    spend += cost[k][t["id"]]
                    c = g["candidates"][k]
                    tried.append((c["examples_ok"], -c["gen_fails"], i, k))
                    if c["examples_ok"] and c["gen_ok"]:
                        break
                pick = k if fallback == "last" or (c["examples_ok"] and c["gen_ok"]) else max(tried)[3]
                score += ok[pick][t["id"]]
                escalated += len(tried) > 1
            name = f"cascade + {writer}-written tests, {fallback}"
            print(f"{name:<44} {score:>3}/{n} {spend / base:>8.0%} {escalated:>10}")
    print("\ncompute is relative to always coder14B")


if __name__ == "__main__":
    main()
