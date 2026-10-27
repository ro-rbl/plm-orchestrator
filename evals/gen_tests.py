"""Generate extra tests with a writer model, then measure them. Two phases:

    .venv/bin/python evals/gen_tests.py gen --writer qwen3:8b     # model calls; resumable
    .venv/bin/python evals/gen_tests.py check                      # no model calls

gen   writes results/software_tests__<writer>.jsonl (tests per task + call cost).
check scores every generated test against the task's reference solution (a test
      the reference fails is a wrong test), then runs every saved candidate
      solution from results/software__<model>.jsonl against the generated tests,
      writing results/software_gencheck__<writer>.jsonl for the routing simulation.
"""

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plm_software.sandbox import run_tests  # noqa: E402
from plm_software.testgen import TESTGEN_PROMPT_VERSION, failing_tests, generate_tests, is_broken_test  # noqa: E402
from plm.ollama import unreachable  # noqa: E402
from run_code import load_jsonl, verdict  # noqa: E402

RESULTS = ROOT / "results"
CANDIDATES = {
    "0.6B": "software__hf.co_bartowski_mlabonne_Qwen3-0.6B-abliterated-GGUF_Q4_K_M.jsonl",
    "4B": "software__hf.co_bartowski_mlabonne_Qwen3-4B-abliterated-GGUF_Q4_K_M.jsonl",
    "8B": "software__qwen3_8b.jsonl",
    "coder14B": "software__qwen2.5-coder_14b.jsonl",
}


def safe(model):
    return re.sub(r"[^A-Za-z0-9._-]+", "_", model)


def gen(writer, tasks):
    out = RESULTS / f"software_tests__{safe(writer)}.jsonl"
    done = {r["id"] for r in load_jsonl(out)} if out.exists() else set()
    todo = [t for t in tasks if t["id"] not in done]
    print(f"{writer}: {len(todo)} to run, {len(done)} already in {out}")
    with out.open("a") as f:
        for i, t in enumerate(todo, 1):
            row = {"id": t["id"], "level": t["level"], "writer": writer, "prompt_version": TESTGEN_PROMPT_VERSION}
            try:
                tests, call = generate_tests(t, writer)
                row.update({"tests": tests, **call})
            except Exception as e:  # keep going; one bad request must not lose the run
                if unreachable(e):  # stop without saving, so a resume retries this task and the rest
                    sys.exit(f"Ollama is unreachable ({type(e).__name__}: {e}); stopped, resume to retry")
                row.update({"tests": [], "error": f"{type(e).__name__}: {e}", "tokens": 0, "seconds": 0, "raw": ""})
            f.write(json.dumps(row) + "\n")
            f.flush()
            print(f"[{i}/{len(todo)}] {t['id']} {len(row['tests'])} tests {row['tokens']:>5} tok {row['seconds']:>6.1f}s"
                  + (f"  {row['error']}" if row.get("error") else ""), flush=True)


def check(tasks):
    by_id = {t["id"]: t for t in tasks}
    cands = {k: {r["id"]: r for r in load_jsonl(RESULTS / v)} for k, v in CANDIDATES.items()}
    for path in sorted(glob.glob(str(RESULTS / "software_tests__*.jsonl"))):
        writer_rows = load_jsonl(path)
        out = Path(path.replace("software_tests__", "software_gencheck__"))
        n_tests = n_valid = n_broken = tasks_with_wrong = 0
        stats = {k: {"wrong": 0, "caught_examples": 0, "caught_both": 0, "false_examples": 0, "false_both": 0} for k in cands}
        with out.open("w") as f:
            for w in writer_rows:
                t = by_id[w["id"]]
                ref = run_tests(t["reference"], w["tests"])
                broken = {test for test, why in ref["failures"] if is_broken_test(why, t["entry"])}
                wrong = {test for test, _ in failing_tests(ref, t["entry"])}  # well-formed, wrong expectation
                n_tests += len(w["tests"])
                n_valid += len(w["tests"]) - len(broken) - len(wrong)
                n_broken += len(broken)
                tasks_with_wrong += bool(wrong)
                row = {"id": w["id"], "writer": w["writer"], "tokens": w["tokens"], "n_tests": len(w["tests"]),
                       "broken_tests": sorted(broken), "wrong_tests": sorted(wrong), "candidates": {}}
                for k, rows in cands.items():
                    c = rows[w["id"]]
                    if c["code"] is None:
                        res = {"passed": 0, "total": len(w["tests"]), "error": "no code", "failures": []}
                    else:
                        res = run_tests(c["code"], w["tests"])
                    # Same rule the controller applies at runtime: broken tests don't count.
                    gen_fails = res["total"] if res["error"] else len(failing_tests(res, t["entry"]))
                    gen_ok = gen_fails == 0
                    ex = c.get("examples") or {}
                    ex_ok = c["code"] is not None and not ex.get("error") and ex.get("passed") == ex.get("total")
                    correct = verdict(c) == "pass"
                    row["candidates"][k] = {"gen_fails": gen_fails, "gen_total": res["total"], "gen_ok": gen_ok,
                                            "examples_ok": ex_ok, "correct": correct}
                    s = stats[k]
                    s["wrong"] += not correct
                    s["caught_examples"] += (not correct) and not ex_ok
                    s["caught_both"] += (not correct) and not (ex_ok and gen_ok)
                    s["false_examples"] += correct and not ex_ok
                    s["false_both"] += correct and not (ex_ok and gen_ok)
                f.write(json.dumps(row) + "\n")
        writer = writer_rows[0]["writer"]
        avg_tok = sum(w["tokens"] for w in writer_rows) / len(writer_rows)
        print(f"\n== writer {writer}: {n_tests} tests for {len(writer_rows)} tasks, {avg_tok:.0f} tok/task; "
              f"{n_valid}/{n_tests} ({n_valid / max(n_tests, 1):.0%}) valid against the reference, {n_broken} broken "
              f"(ignored at runtime), {n_tests - n_valid - n_broken} wrong; {tasks_with_wrong} tasks have a wrong test")
        print(f"   {'candidate':<10} {'wrong':>6} {'caught: examples':>17} {'+ gen tests':>12} "
              f"{'false alarms: examples':>23} {'+ gen tests':>12}")
        for k, s in stats.items():
            print(f"   {k:<10} {s['wrong']:>6} {s['caught_examples']:>17} {s['caught_both']:>12} "
                  f"{s['false_examples']:>23} {s['false_both']:>12}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("gen", "check"))
    ap.add_argument("--writer")
    args = ap.parse_args()
    tasks = load_jsonl(ROOT / "evals/software/tasks.jsonl")
    if args.phase == "gen":
        if not args.writer:
            ap.error("gen needs --writer")
        gen(args.writer, tasks)
    else:
        check(tasks)


if __name__ == "__main__":
    main()
