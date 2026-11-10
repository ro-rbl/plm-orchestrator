"""Physics routing attempt 2, judged by PHYS2_RULE on 60 cases written before attempt 2 existed.

    .venv/bin/python evals/test_physics_routing2.py [-v]

evals/router/physics_cases2.jsonl (written 2026-11-10): 40 physics problems (projectiles, orbits, strings, sound,
fluids, rotation, heat, collisions) and 20 aerospace and electrical problems that must stay put. The baseline is
recorded in BASELINE from the router as it was when the cases were committed, before any change.

PHYS2_RULE, fixed 2026-11-10 before attempt 2: the change ships iff all of
    (a) physics cases right >= BASELINE physics + 3
    (b) other cases right >= BASELINE others - 1
    (c) every eval-set text still routes to its labeled pack (evals/test_detect.py, 279/279)
    (d) the holdout cases score at least 188/194
Exits 1 if any fails.

Attempt 2 is fixed here before it is written: the reverted attempt-1 diff
(docs/attempts/physics_routing_2026-11-08.diff) plus attempt 1's three named leftovers: "projectile"/"launched" ties
go to physics, "rev/s" counts as a quantity, and a light bulb "radiates"/"black body" is physics. Disclosure: the
baseline misses on these 60 cases were printed (-v) once before this was committed; the attempt is limited to what
attempt 1 already named so they can't steer it.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from plm.packs import detect  # noqa: E402
from test_detect import holdout_texts, known_texts  # noqa: E402

BASELINE = {"physics": 33, "others": 18}  # router before attempt 2 (eval texts 279/279, holdout 188/194)


def main():
    verbose = "-v" in sys.argv
    rows = [json.loads(line) for line in open(ROOT / "evals/router/physics_cases2.jsonl") if line.strip()]
    phys = [r for r in rows if r["pack"] == "physics"]
    others = [r for r in rows if r["pack"] != "physics"]
    p_ok = sum(detect(r["text"]) == r["pack"] for r in phys)
    o_ok = sum(detect(r["text"]) == r["pack"] for r in others)
    for r in rows if verbose else []:
        if detect(r["text"]) != r["pack"]:
            print(f"   miss {r['id']}: want {r['pack']}, got {detect(r['text'])}: {r['text'][:80]}")
    known = [(t, want) for _, t, want in known_texts()]
    k_ok = sum(detect(t) == want for t, want in known)
    hold = [(t, want) for _, t, want in holdout_texts()]
    h_ok = sum(detect(t) == want for t, want in hold)
    print(f"physics {p_ok}/{len(phys)}, others {o_ok}/{len(others)}, eval texts {k_ok}/{len(known)}, holdout {h_ok}/{len(hold)}")
    if BASELINE is None:
        print("no BASELINE yet")
        return 0
    a = p_ok >= BASELINE["physics"] + 3
    b = o_ok >= BASELINE["others"] - 1
    c = k_ok == len(known)
    d = h_ok >= 188
    print(f"PHYS2_RULE (a) {a} (b) {b} (c) {c} (d) {d}: {'SHIP' if a and b and c and d else 'DO NOT SHIP'}")
    return 0 if a and b and c and d else 1


if __name__ == "__main__":
    sys.exit(main())
