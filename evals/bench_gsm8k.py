"""GSM8K (grade-school maths word problems) as a numeric cross-check: does the calculator help where no pack claims?

    .venv/bin/python evals/bench_gsm8k.py --model qwen3:8b --strategy bare   # results/bench_gsm8k__<model>[__tool].jsonl
    .venv/bin/python evals/bench_gsm8k.py --simulate                         # scores, 95% CIs, GSM_RULE

Data (not redistributed): openai/gsm8k "main" test split from Hugging Face, saved by the datasets-server
rows API as .benchmarks/numeric/gsm8k.jsonl (1319 problems; 2026-10-24). A fixed sample of 300 (SEED).

1247 of the 1319 route to the general pack (the 8B answering directly, unchecked), which is right:
they are everyday arithmetic, no pack's domain. So the question is whether the general pack should
hand plain numeric word problems to the shared calculator. Strategies: the 8B direct (what the general
pack does today), the 8B and 4B with the calculator. The answer is a number; graded exact (to 1e-6),
against the number after "####". Nothing ships from this run: GSM_RULE only names a candidate, which
would need its own routing rule and new cases. Fixed on 2026-10-24 before any model answered.
"""

import argparse
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plm.packs  # noqa: E402,F401
from plm.numeric import calc  # noqa: E402
from plm.numeric.answers import ANSWER_FORMAT, parse_answer  # noqa: E402
from plm.ollama import ask, unreachable  # noqa: E402
from plm.packs import detect  # noqa: E402

DATA = ROOT / ".benchmarks/numeric/gsm8k.jsonl"
RESULTS = ROOT / "results"
SEED, SAMPLE = 20261024, 300
MODELS = {"4B": "hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M", "8B": "qwen3:8b"}
RUNS = [("8B", "bare"), ("8B", "tool"), ("4B", "tool")]
GSM_RULE = ("if the 8B with the calculator beats the 8B direct (the general pack today) with a paired bootstrap 95% "
            "interval above 0, the candidate is: numeric word problems no pack claims go to the 8B with the calculator "
            "(to be built with its own routing rule and judged on new cases); otherwise the general pack stays as it is")


def problems():
    if not DATA.exists():
        sys.exit(f"{DATA} is missing: fetch it as this file's docstring says")
    rows = [json.loads(line) for line in open(DATA)]
    picked = sorted(random.Random(SEED).sample(range(len(rows)), SAMPLE))
    return [{"id": f"gsm-{i:04d}", "question": rows[i]["question"],
             "answer": float(rows[i]["answer"].rsplit("####", 1)[1].strip().replace(",", ""))} for i in picked]


def correct(output, answer):
    parsed = parse_answer(output)
    return parsed is not None and abs(parsed[0] - answer) <= 1e-6 * max(1, abs(answer))


def results_path(model, strategy):
    return RESULTS / f"bench_gsm8k__{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}{'' if strategy == 'bare' else '__' + strategy}.jsonl"


def run(model, strategy, timeout):
    ps = problems()
    out = results_path(model, strategy)
    done = {r["id"] for r in map(json.loads, open(out))} if out.exists() else set()
    todo = [p for p in ps if p["id"] not in done]
    print(f"{model} {strategy} on GSM8K: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, p in enumerate(todo, 1):
            row = {"id": p["id"], "model": model, "strategy": strategy}
            try:
                fmt = ANSWER_FORMAT if strategy == "bare" else calc.TOOL_FORMAT
                r = ask(model, f"{p['question']}\n\n{fmt}", False, 1024, timeout)
                output = r["response"]
                if strategy == "tool":
                    code = calc.extract_program(output)
                    output, row["program_error"] = calc.run_program(code) if code else ("", "no code block")
                row.update({"model_response": r["response"], "response": output, "eval_tokens": r["eval_tokens"],
                            "wall_s": r["wall_s"], "done_reason": r["done_reason"]})
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this task and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped, resume to retry")
                row.update({"response": "", "error": f"{type(e).__name__}: {e}", "eval_tokens": 0, "wall_s": 0,
                            "done_reason": "error"})
            row["correct"] = correct(row["response"], p["answer"])
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {p['id']} {'correct' if row['correct'] else 'wrong':<8} {row['eval_tokens']:>5} tok "
                  f"{row['wall_s']:>6.1f}s", flush=True)


def simulate(resamples=2000):
    ps = problems()
    R = {}
    for key, strategy in RUNS:
        p = results_path(MODELS[key], strategy)
        R[(key, strategy)] = {r["id"]: r for r in map(json.loads, open(p))} if p.exists() else {}
        if len(R[(key, strategy)]) < len(ps):
            sys.exit(f"no complete GSM8K results for {key} {strategy}; run results/run_bench_gsm8k.sh")
    n = len(ps)
    rng = random.Random(SEED)
    idx = [[rng.randrange(n) for _ in range(n)] for _ in range(resamples)]
    base = [R[("8B", "bare")][p["id"]]["correct"] for p in ps]
    print(f"GSM8K sample: {n} problems; routing of the full 1319: "
          + str(dict(__import__("collections").Counter(detect(json.loads(line)["question"]) for line in open(DATA)))))
    print(f"\n{'run':<14} {'score':>8} {'95% CI':>12} {'tokens/problem':>15} {'vs 8B direct, 95% CI':>22}")
    verdict = None
    for key, strategy in RUNS:
        res = [R[(key, strategy)][p["id"]]["correct"] for p in ps]
        boots = sorted(sum(res[i] for i in b) for b in idx)
        diffs = sorted(sum(res[i] - base[i] for i in b) for b in idx)
        lo, hi = boots[int(0.025 * resamples)], boots[int(0.975 * resamples)]
        dlo, dhi = diffs[int(0.025 * resamples)], diffs[int(0.975 * resamples)]
        tokens = sum(R[(key, strategy)][p["id"]]["eval_tokens"] for p in ps) / n
        name = f"{key} {strategy}"
        print(f"{name:<14} {sum(res):>4}/{n:<3} {lo / n:>5.0%}-{hi / n:<5.0%} {tokens:>15.0f} "
              f"{'' if (key, strategy) == ('8B', 'bare') else f'{dlo:+d} to {dhi:+d}':>22}")
        if (key, strategy) == ("8B", "tool"):
            verdict = dlo > 0
    print(f"\nrule: {GSM_RULE}")
    print("-> CANDIDATE: unclaimed numeric word problems to the 8B with the calculator" if verdict
          else "-> NO CHANGE: the general pack stays as it is")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--strategy", choices=["bare", "tool"], default="bare")
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()
    if args.simulate:
        return simulate()
    if not args.model:
        sys.exit("--model or --simulate")
    run(args.model, args.strategy, args.timeout)


if __name__ == "__main__":
    main()
