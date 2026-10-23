"""Source of truth for the CAD eval set.

Each problem asks for one part in millimeters. Its key is the part's bounding box
(the three extents, sorted, so orientation is free) and its volume, computed here
from formulas, never typed. Each problem also carries a reference CadQuery program,
and --verify builds every reference with the real kernel and checks it against
the key, so a slip in a formula or a reference can't go unnoticed.

Written on 2026-10-22 before the CAD pack's claims, levels or policies existed.

    .venv/bin/python evals/cad/build_problems.py                      # write problems.jsonl
    .venv/bin/python evals/cad/build_problems.py --verify <python>    # build every reference with <python>,
                                                                      # which must have cadquery
Levels:
    calm      one primitive solid
    alert     a primitive with one feature (a hole, pocket, slot, chamfer, fillet)
    intensive several features, a pattern, or solids joined
"""

import json
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

PI = math.pi
HEX_AREA = 3 * math.sqrt(3) / 8 * 20 ** 2  # regular hexagon 20 mm across corners

# (id, level, task, bbox (any order), volume, reference program)
PROBLEMS = [
    # ---------------- calm ----------------
    ("cad-c01", "calm", "A rectangular block 50 mm long, 30 mm wide and 20 mm tall.",
     (50, 30, 20), 50 * 30 * 20, "result = cq.Workplane('XY').box(50, 30, 20)"),
    ("cad-c02", "calm", "A solid cylinder 40 mm in diameter and 25 mm tall.",
     (40, 40, 25), PI * 20 ** 2 * 25, "result = cq.Workplane('XY').circle(20).extrude(25)"),
    ("cad-c03", "calm", "A solid sphere 30 mm in diameter.",
     (30, 30, 30), 4 / 3 * PI * 15 ** 3, "result = cq.Workplane('XY').sphere(15)"),
    ("cad-c04", "calm", "A cube with 25 mm sides.",
     (25, 25, 25), 25 ** 3, "result = cq.Workplane('XY').box(25, 25, 25)"),
    ("cad-c05", "calm", "A tube 50 mm long with an outer diameter of 20 mm and an inner diameter of 14 mm.",
     (20, 20, 50), PI * (10 ** 2 - 7 ** 2) * 50, "result = cq.Workplane('XY').circle(10).circle(7).extrude(50)"),
    ("cad-c06", "calm", "A square plate 80 mm by 80 mm and 4 mm thick.",
     (80, 80, 4), 80 * 80 * 4, "result = cq.Workplane('XY').box(80, 80, 4)"),
    ("cad-c07", "calm", "A round rod 12 mm in diameter and 100 mm long.",
     (12, 12, 100), PI * 6 ** 2 * 100, "result = cq.Workplane('XY').circle(6).extrude(100)"),
    ("cad-c08", "calm", "A regular hexagonal prism 20 mm across corners and 10 mm tall.",
     (20, 20 * math.sqrt(3) / 2, 10), HEX_AREA * 10, "result = cq.Workplane('XY').polygon(6, 20).extrude(10)"),
    ("cad-c09", "calm", "A solid cone with a base 30 mm in diameter and a height of 40 mm.",
     (30, 30, 40), PI * 15 ** 2 * 40 / 3, "result = cq.Workplane('XY').add(cq.Solid.makeCone(15, 0, 40))"),
    ("cad-c10", "calm", "A rectangular bar 200 mm long with a 20 mm by 10 mm cross-section.",
     (200, 20, 10), 200 * 20 * 10, "result = cq.Workplane('XY').box(200, 20, 10)"),
    ("cad-c11", "calm", "A disc 100 mm in diameter and 5 mm thick.",
     (100, 100, 5), PI * 50 ** 2 * 5, "result = cq.Workplane('XY').circle(50).extrude(5)"),
    ("cad-c12", "calm", "A square column 10 mm by 10 mm and 100 mm tall.",
     (10, 10, 100), 10 * 10 * 100, "result = cq.Workplane('XY').box(10, 10, 100)"),
    # ---------------- alert ----------------
    ("cad-a01", "alert", "A plate 60 mm by 40 mm and 5 mm thick with a 10 mm diameter through hole at its center.",
     (60, 40, 5), 60 * 40 * 5 - PI * 5 ** 2 * 5,
     "result = cq.Workplane('XY').box(60, 40, 5).faces('>Z').workplane().hole(10)"),
    ("cad-a02", "alert", "A block 40 mm by 40 mm and 20 mm tall with a blind hole 10 mm in diameter and 12 mm deep at the center of its top face.",
     (40, 40, 20), 40 * 40 * 20 - PI * 5 ** 2 * 12,
     "result = cq.Workplane('XY').box(40, 40, 20).faces('>Z').workplane().hole(10, 12)"),
    ("cad-a03", "alert", "A cylinder 30 mm in diameter and 20 mm tall with a 10 mm diameter hole through its axis.",
     (30, 30, 20), PI * (15 ** 2 - 5 ** 2) * 20, "result = cq.Workplane('XY').circle(15).circle(5).extrude(20)"),
    ("cad-a04", "alert", "A block 50 mm by 50 mm and 30 mm tall with a rectangular pocket 30 mm by 30 mm and 10 mm deep centered in its top face.",
     (50, 50, 30), 50 * 50 * 30 - 30 * 30 * 10,
     "result = cq.Workplane('XY').box(50, 50, 30).faces('>Z').workplane().rect(30, 30).cutBlind(-10)"),
    ("cad-a05", "alert", "A plate 100 mm by 50 mm and 8 mm thick with a straight through slot centered in it, 30 mm long overall and 10 mm wide, with rounded ends.",
     (100, 50, 8), 100 * 50 * 8 - (20 * 10 + PI * 5 ** 2) * 8,
     "result = cq.Workplane('XY').box(100, 50, 8).faces('>Z').workplane().slot2D(30, 10).cutThruAll()"),
    ("cad-a06", "alert", "A 30 mm cube with a 12 mm diameter hole straight through the centers of two opposite faces.",
     (30, 30, 30), 30 ** 3 - PI * 6 ** 2 * 30, "result = cq.Workplane('XY').box(30, 30, 30).faces('>Z').workplane().hole(12)"),
    ("cad-a07", "alert", "A block 60 mm by 40 mm and 20 mm tall with its four vertical edges chamfered by 5 mm.",
     (60, 40, 20), 60 * 40 * 20 - 4 * (5 * 5 / 2) * 20,
     "result = cq.Workplane('XY').box(60, 40, 20).edges('|Z').chamfer(5)"),
    ("cad-a08", "alert", "A cylinder 40 mm in diameter and 30 mm tall with a blind hole 20 mm in diameter and 10 mm deep at the center of its top face.",
     (40, 40, 30), PI * 20 ** 2 * 30 - PI * 10 ** 2 * 10,
     "result = cq.Workplane('XY').circle(20).extrude(30).faces('>Z').workplane().hole(20, 10)"),
    ("cad-a09", "alert", "A plate 80 mm by 60 mm and 6 mm thick with a rectangular through cutout 30 mm by 20 mm at its center.",
     (80, 60, 6), 80 * 60 * 6 - 30 * 20 * 6,
     "result = cq.Workplane('XY').box(80, 60, 6).faces('>Z').workplane().rect(30, 20).cutThruAll()"),
    ("cad-a10", "alert", "A block 40 mm by 20 mm and 10 mm tall with its four vertical edges rounded to a 3 mm radius.",
     (40, 20, 10), 40 * 20 * 10 - 4 * (1 - PI / 4) * 3 ** 2 * 10,
     "result = cq.Workplane('XY').box(40, 20, 10).edges('|Z').fillet(3)"),
    ("cad-a11", "alert", "A solid hemisphere 40 mm in diameter.",
     (40, 40, 20), 2 / 3 * PI * 20 ** 3,
     "result = cq.Workplane('XY').sphere(20).cut(cq.Workplane('XY').box(50, 50, 25, centered=(True, True, False)).translate((0, 0, -25)))"),
    ("cad-a12", "alert", "A square bar 20 mm by 20 mm and 80 mm long with an 8 mm diameter hole straight through it at its middle, perpendicular to its length.",
     (20, 20, 80), 20 * 20 * 80 - PI * 4 ** 2 * 20,
     "result = cq.Workplane('XY').box(20, 20, 80).faces('>X').workplane().hole(8)"),
    # ---------------- intensive ----------------
    ("cad-i01", "intensive", "A plate 100 mm by 60 mm and 5 mm thick with four 6 mm diameter through holes, each centered 10 mm from the two nearest edges.",
     (100, 60, 5), 100 * 60 * 5 - 4 * PI * 3 ** 2 * 5,
     "result = cq.Workplane('XY').box(100, 60, 5).faces('>Z').workplane().rect(80, 40, forConstruction=True).vertices().hole(6)"),
    ("cad-i02", "intensive", "A flange: a disc 80 mm in diameter and 10 mm thick with a 30 mm central hole and six 8 mm bolt holes evenly spaced on a 60 mm diameter bolt circle.",
     (80, 80, 10), PI * (40 ** 2 - 15 ** 2) * 10 - 6 * PI * 4 ** 2 * 10,
     "result = cq.Workplane('XY').circle(40).circle(15).extrude(10).faces('>Z').workplane().polarArray(30, 0, 360, 6).hole(8)"),
    ("cad-i03", "intensive", "An L-bracket: a base plate 60 mm by 40 mm and 5 mm thick, with an upright plate 40 mm wide and 5 mm thick standing flush on one 40 mm end of the base, so the bracket is 50 mm tall overall.",
     (60, 40, 50), 60 * 40 * 5 + 5 * 40 * 45,
     "result = (cq.Workplane('XY').box(60, 40, 5, centered=False)"
     ".union(cq.Workplane('XY').box(5, 40, 50, centered=False)))"),
    ("cad-i04", "intensive", "A stepped shaft: a 30 mm diameter section 40 mm long followed on the same axis by a 20 mm diameter section 60 mm long.",
     (30, 30, 100), PI * 15 ** 2 * 40 + PI * 10 ** 2 * 60,
     "result = cq.Workplane('XY').circle(15).extrude(40).faces('>Z').workplane().circle(10).extrude(60)"),
    ("cad-i05", "intensive", "An open-topped box 60 mm by 40 mm and 30 mm tall outside, with walls and floor 3 mm thick.",
     (60, 40, 30), 60 * 40 * 30 - 54 * 34 * 27,
     "result = cq.Workplane('XY').box(60, 40, 30).faces('>Z').shell(-3)"),
    ("cad-i06", "intensive", "A plate 120 mm by 80 mm and 10 mm thick with six 10 mm diameter through holes in a centered grid of 3 by 2, spaced 30 mm apart in both directions.",
     (120, 80, 10), 120 * 80 * 10 - 6 * PI * 5 ** 2 * 10,
     "result = cq.Workplane('XY').box(120, 80, 10).faces('>Z').workplane().rarray(30, 30, 3, 2).hole(10)"),
    ("cad-i07", "intensive", "A block 40 mm by 40 mm and 20 mm tall with a counterbored hole at the center of its top face: an 8 mm through hole with a counterbore 14 mm in diameter and 6 mm deep.",
     (40, 40, 20), 40 * 40 * 20 - PI * 4 ** 2 * 14 - PI * 7 ** 2 * 6,
     "result = cq.Workplane('XY').box(40, 40, 20).faces('>Z').workplane().cboreHole(8, 14, 6)"),
    ("cad-i08", "intensive", "A pipe 100 mm long with an outer diameter of 30 mm and an inner diameter of 24 mm, with a flange 60 mm in diameter and 8 mm thick at one end; the bore runs through the flange.",
     (60, 60, 100), PI * (15 ** 2 - 12 ** 2) * 92 + PI * (30 ** 2 - 12 ** 2) * 8,
     "result = cq.Workplane('XY').circle(30).circle(12).extrude(8).faces('>Z').workplane().circle(15).circle(12).extrude(92)"),
    ("cad-i09", "intensive", "A block 80 mm by 40 mm and 20 mm tall with two square pockets 25 mm by 25 mm and 10 mm deep in its top face, centered 20 mm either side of the block's center along its length.",
     (80, 40, 20), 80 * 40 * 20 - 2 * 25 * 25 * 10,
     "result = cq.Workplane('XY').box(80, 40, 20).faces('>Z').workplane().pushPoints([(-20, 0), (20, 0)]).rect(25, 25).cutBlind(-10)"),
    ("cad-i10", "intensive", "A cylinder 60 mm in diameter and 40 mm tall with a regular hexagonal through hole 20 mm across corners on its axis.",
     (60, 60, 40), PI * 30 ** 2 * 40 - HEX_AREA * 40,
     "result = cq.Workplane('XY').circle(30).polygon(6, 20).extrude(40)"),
    ("cad-i11", "intensive", "A U-channel 100 mm long whose cross-section is 40 mm wide and 30 mm tall, with walls and base 4 mm thick.",
     (100, 40, 30), (40 * 30 - 32 * 26) * 100,
     "result = cq.Workplane('YZ').polyline([(-20, 0), (20, 0), (20, 30), (16, 30), (16, 4), (-16, 4), (-16, 30), (-20, 30)]).close().extrude(100)"),
    ("cad-i12", "intensive", "A square plate 70 mm by 70 mm and 6 mm thick with a 20 mm central hole, four 6 mm corner holes each centered 10 mm from the two nearest edges, and its four vertical edges chamfered by 5 mm.",
     (70, 70, 6), 70 * 70 * 6 - 4 * (5 * 5 / 2) * 6 - PI * 10 ** 2 * 6 - 4 * PI * 3 ** 2 * 6,
     "result = (cq.Workplane('XY').box(70, 70, 6).edges('|Z').chamfer(5).faces('>Z').workplane().hole(20)"
     ".faces('>Z').workplane().rect(50, 50, forConstruction=True).vertices().hole(6))"),
]

MEASURE = """
import json as _json
_shape = result.val() if hasattr(result, "val") else result
_bb = _shape.BoundingBox()
print(_json.dumps({"valid": _shape.isValid(), "solids": len(_shape.Solids()),
                   "bbox": sorted([_bb.xlen, _bb.ylen, _bb.zlen]), "volume": _shape.Volume()}))
"""


def records():
    for pid, level, task, bbox, volume, ref in PROBLEMS:
        yield {"id": pid, "domain": "cad", "level": level, "task": task, "bbox": sorted(bbox), "volume": volume,
               "rel_tol": 0.01, "reference": ref}


def verify(python):
    """Build every reference with the kernel; it must be one valid solid matching the key."""
    bad = 0
    for r in records():
        with tempfile.TemporaryDirectory() as d:
            source = "import cadquery as cq\n" + r["reference"] + MEASURE
            p = subprocess.run([os.path.abspath(python), "-I", "-c", source],
                               capture_output=True, text=True, timeout=120, cwd=d)
        if p.returncode:
            print("FAIL", r["id"], p.stderr.strip().splitlines()[-1]); bad += 1; continue
        m = json.loads(p.stdout.strip().splitlines()[-1])
        ok = (m["valid"] and m["solids"] == 1 and math.isclose(m["volume"], r["volume"], rel_tol=1e-6)
              and all(math.isclose(a, b, rel_tol=1e-6) for a, b in zip(m["bbox"], r["bbox"])))
        if not ok:
            print("FAIL", r["id"], m, "key", r["bbox"], r["volume"]); bad += 1
    print(f"verify: {len(PROBLEMS) - bad}/{len(PROBLEMS)} references match their keys")
    return bad


def main():
    ids = [p[0] for p in PROBLEMS]
    assert len(ids) == len(set(ids)), "duplicate problem id"
    if "--verify" in sys.argv:
        sys.exit(1 if verify(sys.argv[sys.argv.index("--verify") + 1]) else 0)
    out = Path(__file__).with_name("problems.jsonl")
    with out.open("w") as f:
        for r in records():
            f.write(json.dumps(r) + "\n")
    counts = {lvl: sum(p[1] == lvl for p in PROBLEMS) for lvl in ("calm", "alert", "intensive")}
    print(f"wrote {len(PROBLEMS)} problems to {out} {counts}")


if __name__ == "__main__":
    main()
