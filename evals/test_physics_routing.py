"""Physics routing, judged by PHYS_RULE on cases written before the change (evals/router/physics_cases.jsonl).

    .venv/bin/python evals/test_physics_routing.py [-v]

30 physics problems of the kinds the router missed (speed of sound, pendulums with "gravitational acceleration",
forces in newtons, collisions, power when lifting) and 15 aerospace and electrical problems that must stay put.
Before the change (2026-11-08): physics 24/30 (3 general, 2 aerospace, 1 electrical), others 15/15.

PHYS_RULE, fixed 2026-11-08 before any routing change: a change ships iff all of
    (a) at least 28 of the 30 physics cases go to physics
    (b) at least 14 of the 15 others go to their pack
    (c) every eval-set text still routes to its labeled pack (evals/test_detect.py, 279/279)
    (d) the holdout cases score at least 188/194 (their count before the change)
Exits 1 if any fails, so after it ships this is a regression test.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from plm.packs import detect  # noqa: E402
from test_detect import holdout_texts, known_texts  # noqa: E402


def main():
    verbose = "-v" in sys.argv
    rows = [json.loads(line) for line in open(ROOT / "evals/router/physics_cases.jsonl") if line.strip()]

    def count(items, label, need):
        miss = [(i, want, detect(t), t) for i, t, want in items if detect(t) != want]
        ok = len(items) - len(miss)
        print(f"{label}: {ok}/{len(items)} (need {need})")
        for i, want, got, t in miss if verbose else []:
            print(f"   miss {i}: want {want}, got {got}: {t[:90]}")
        return ok >= need

    a = count([(r["id"], r["text"], r["pack"]) for r in rows if r["pack"] == "physics"], "(a) physics cases", 28)
    b = count([(r["id"], r["text"], r["pack"]) for r in rows if r["pack"] != "physics"], "(b) aerospace/electrical cases", 14)
    c = count(known_texts(), "(c) eval-set texts", len(known_texts()))
    d = count(holdout_texts(), "(d) holdout cases", 188)
    passed = a and b and c and d
    print("PHYS_RULE:", "PASS" if passed else "FAIL")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
