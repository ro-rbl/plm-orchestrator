"""UNITS_RULE: the numeric check with units asked as symbols and units inferred from the quantity asked for
(plm.numeric.checks.expected_unit), replayed on every saved numeric answer against the check before it.

    .venv/bin/python evals/score_units.py [-v]

Sources (no model calls): the own electrical, aerospace and physics sets (results/<pack>__*.jsonl and
<pack>_<set>__*.jsonl, graded by evals/grade.py), and the physics benchmarks (SciBench, TheoremQA, UGPhysics,
graded by their saved "correct" field). The old check is checks.py as committed in OLD_COMMIT, loaded beside
the new one with the packs' unit words.

UNITS_RULE, fixed 2026-11-08 before this replay ran: expected_unit ships iff, over all these answers,
    (a) right answers it newly flags (false alarms) are at most 0.5% of the right answers, and
    (b) wrong answers it newly flags are at least twice the right answers it newly flags.
Routing must not change (requested_unit is untouched; evals/dump_decisions.py TEXT lines identical).
"""

import glob
import importlib.util
import json
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

import plm.packs  # noqa: E402,F401  (loads the packs' unit words into the new check)
from grade import grade_one  # noqa: E402
from plm.numeric import checks as new  # noqa: E402
from plm.packs import PACKS  # noqa: E402

OLD_COMMIT = "1b981d5"


def old_checks():
    src = subprocess.run(["git", "show", f"{OLD_COMMIT}:packages/plm-core/src/plm/numeric/checks.py"],
                         capture_output=True, text=True, cwd=ROOT, check=True).stdout
    path = Path(tempfile.mkdtemp()) / "old_checks.py"
    path.write_text(src)
    spec = importlib.util.spec_from_file_location("old_checks", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for p in PACKS.values():
        if p.unit_words:
            mod.add_unit_words(p.unit_words)
    return mod


def load(path):
    return [json.loads(line) for line in open(path) if line.strip()]


def answers():
    """(source, question, response, right) for every saved numeric answer."""
    for pack in ("electrical", "aerospace", "physics"):
        for qfile in sorted((ROOT / "evals" / pack).glob("*.jsonl")):
            probs = {p["id"]: p for p in load(qfile) if "answer" in p and "unit" in p}
            if not probs:
                continue
            prefix = pack if qfile.stem == "problems" else f"{pack}_{qfile.stem}"
            for f in sorted(glob.glob(str(ROOT / "results" / f"{prefix}__*.jsonl"))):
                for r in load(f):
                    if r["id"] in probs and r.get("response") is not None:
                        yield (prefix, probs[r["id"]]["question"], r["response"],
                               grade_one(probs[r["id"]], r["response"])["verdict"] == "correct")
    import bench_physics
    import physics_check
    for bench in ("scibench", "theoremqa"):
        bench_physics.BENCH = bench
        try:
            qs = {p["id"]: p["question"] for p in bench_physics.problems()}
        except SystemExit:
            print(f"(skipped {bench}: data missing)")
            continue
        for f in sorted(glob.glob(str(ROOT / "results" / f"bench_{bench}__*.jsonl"))):
            for r in load(f):
                if r["id"] in qs and "correct" in r and r.get("response") is not None:
                    yield bench, qs[r["id"]], r["response"], bool(r["correct"])
    for s in ("first", "confirm"):
        physics_check.SET = s
        try:
            qs = {p["id"]: p["question"] for p in physics_check.problems()}
        except SystemExit:
            print("(skipped UGPhysics: data missing)")
            break
        tag = "" if s == "first" else f"_{s}"
        for f in sorted(glob.glob(str(ROOT / "results" / f"physcheck_ugphysics{tag}__*.jsonl"))):
            for r in load(f):
                if r["id"] in qs and "correct" in r and r.get("response") is not None:
                    yield "ugphysics", qs[r["id"]], r["response"], bool(r["correct"])


def main():
    verbose = "-v" in sys.argv
    old = old_checks()
    n = Counter()
    examples = {"false": [], "caught": []}
    for source, q, resp, right in answers():
        o, w = bool(old.check(q, resp)), bool(new.check(q, resp))
        n["answers"] += 1
        n["right"] += right
        n["newly_checked"] += old.requested_unit(q) is None and new.expected_unit(q)[0] is not None
        if w and not o:
            key = "new_false" if right else "new_caught"
            n[key] += 1
            n[f"{key}:{source}"] += 1
            examples["false" if right else "caught"].append((source, q[-90:], resp.strip()[-60:], new.check(q, resp)))
        if o and not w:
            n["unflagged_right" if right else "unflagged_wrong"] += 1
    print(f"answers {n['answers']} (right {n['right']}); questions newly checked {n['newly_checked']} answers")
    print(f"newly flagged: wrong answers caught {n['new_caught']}, right answers falsely flagged {n['new_false']}")
    print(f"no longer flagged: right {n['unflagged_right']}, wrong {n['unflagged_wrong']}")
    print("by source:", {k.split(":")[1]: v for k, v in n.items() if k.startswith("new_caught:")},
          "false:", {k.split(":")[1]: v for k, v in n.items() if k.startswith("new_false:")})
    for kind in ("false", "caught") if verbose else ():
        for e in examples[kind][:12]:
            print(f"   {kind}: [{e[0]}] ...{e[1]!r} -> {e[2]!r} {e[3]}")
    a = n["new_false"] <= 0.005 * n["right"]
    b = n["new_caught"] >= 2 * n["new_false"]
    print(f"rule: (a) false alarms {n['new_false']} <= {0.005 * n['right']:.1f}: {a}; "
          f"(b) caught {n['new_caught']} >= 2 x {n['new_false']}: {b}")
    print("UNITS_RULE:", "SHIP" if a and b else "DON'T SHIP")


if __name__ == "__main__":
    main()
