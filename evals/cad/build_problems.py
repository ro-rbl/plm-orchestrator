"""Source of truth for the CAD eval set.

Each problem asks for one part in millimeters. Its key is the part's bounding box
(the three extents, sorted, so orientation is free) and its volume, computed here
from formulas, never typed. Each problem also carries a reference CadQuery program,
and --verify builds every reference with the real kernel and checks it against
the key, so a slip in a formula or a reference can't go unnoticed.

Written on 2026-10-22 before the CAD pack's claims, levels or policies existed.

    .venv/bin/python evals/cad/build_problems.py                      # write problems.jsonl and fresh.jsonl
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

# Grading tolerance on each bounding-box extent and the volume. Keys and correctly built parts agree to
# ~1e-6. It was 1% for the first sweep, which passed a 10 mm-deep blind hole asked as 12 mm deep in a
# 40 mm block (volume off 0.5%), so it is 0.1% from 2026-10-23, before the fresh parts were run.
REL_TOL = 0.001

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

# Fresh parts for judging a better key-free check, written on 2026-10-23 before that check was
# designed; the 36 above have been seen (their saved runs tune the check). -> fresh.jsonl
FRESH = [
    ("cad-f01", "alert", "A plate 90 mm by 50 mm and 6 mm thick with two 8 mm diameter through holes, 60 mm apart, centered on the plate.",
     (90, 50, 6), 90 * 50 * 6 - 2 * PI * 4 ** 2 * 6,
     "result = cq.Workplane('XY').box(90, 50, 6).faces('>Z').workplane().rarray(60, 1, 2, 1).hole(8)"),
    ("cad-f02", "alert", "A cylinder 50 mm in diameter and 20 mm tall with a 16 mm diameter through hole on its axis.",
     (50, 50, 20), PI * (25 ** 2 - 8 ** 2) * 20, "result = cq.Workplane('XY').circle(25).circle(8).extrude(20)"),
    ("cad-f03", "alert", "A block 60 mm by 30 mm and 30 mm tall with a blind hole 12 mm in diameter and 18 mm deep at the center of its top face.",
     (60, 30, 30), 60 * 30 * 30 - PI * 6 ** 2 * 18,
     "result = cq.Workplane('XY').box(60, 30, 30).faces('>Z').workplane().hole(12, 18)"),
    ("cad-f04", "alert", "A 40 mm cube with a 20 mm diameter hole straight through the centers of two opposite faces.",
     (40, 40, 40), 40 ** 3 - PI * 10 ** 2 * 40, "result = cq.Workplane('XY').box(40, 40, 40).faces('>Z').workplane().hole(20)"),
    ("cad-f05", "intensive", "A disc 120 mm in diameter and 8 mm thick with four 10 mm diameter through holes evenly spaced on a 90 mm diameter circle.",
     (120, 120, 8), PI * 60 ** 2 * 8 - 4 * PI * 5 ** 2 * 8,
     "result = cq.Workplane('XY').circle(60).extrude(8).faces('>Z').workplane().polarArray(45, 0, 360, 4).hole(10)"),
    ("cad-f06", "intensive", "A bar 80 mm long, 20 mm wide and 20 mm tall with three 6 mm diameter vertical through holes along its length, 25 mm apart and centered on the bar.",
     (80, 20, 20), 80 * 20 * 20 - 3 * PI * 3 ** 2 * 20,
     "result = cq.Workplane('XY').box(80, 20, 20).faces('>Z').workplane().rarray(25, 1, 3, 1).hole(6)"),
    ("cad-f07", "calm", "A tube 60 mm long with an outer diameter of 40 mm and an inner diameter of 30 mm.",
     (40, 40, 60), PI * (20 ** 2 - 15 ** 2) * 60, "result = cq.Workplane('XY').circle(20).circle(15).extrude(60)"),
    ("cad-f08", "alert", "A block 50 mm by 40 mm and 25 mm tall with its four vertical edges rounded to a 4 mm radius.",
     (50, 40, 25), 50 * 40 * 25 - 4 * (1 - PI / 4) * 4 ** 2 * 25,
     "result = cq.Workplane('XY').box(50, 40, 25).edges('|Z').fillet(4)"),
    ("cad-f09", "intensive", "An open-topped box 70 mm by 50 mm and 40 mm tall outside, with walls and floor 2.5 mm thick.",
     (70, 50, 40), 70 * 50 * 40 - 65 * 45 * 37.5, "result = cq.Workplane('XY').box(70, 50, 40).faces('>Z').shell(-2.5)"),
    ("cad-f10", "intensive", "A plate 100 mm by 100 mm and 10 mm thick with a 40 mm square through cutout at its center and four 8 mm diameter through holes, each centered 10 mm from the two nearest edges.",
     (100, 100, 10), 100 * 100 * 10 - 40 * 40 * 10 - 4 * PI * 4 ** 2 * 10,
     "result = (cq.Workplane('XY').box(100, 100, 10).faces('>Z').workplane().rect(40, 40).cutThruAll()"
     ".faces('>Z').workplane().rect(80, 80, forConstruction=True).vertices().hole(8))"),
    ("cad-f11", "intensive", "A stepped shaft with three coaxial sections: 40 mm in diameter and 30 mm long, then 25 mm in diameter and 50 mm long, then 15 mm in diameter and 20 mm long.",
     (40, 40, 100), PI * (20 ** 2 * 30 + 12.5 ** 2 * 50 + 7.5 ** 2 * 20),
     "result = (cq.Workplane('XY').circle(20).extrude(30).faces('>Z').workplane().circle(12.5).extrude(50)"
     ".faces('>Z').workplane().circle(7.5).extrude(20))"),
    ("cad-f12", "intensive", "A block 50 mm by 50 mm and 20 mm tall with a counterbored hole at the center of its top face: a 6 mm through hole with a counterbore 11 mm in diameter and 5 mm deep.",
     (50, 50, 20), 50 * 50 * 20 - PI * 3 ** 2 * 15 - PI * 5.5 ** 2 * 5,
     "result = cq.Workplane('XY').box(50, 50, 20).faces('>Z').workplane().cboreHole(6, 11, 5)"),
    ("cad-f13", "alert", "A cylinder 30 mm in diameter and 50 mm tall with a blind hole 10 mm in diameter and 20 mm deep in the center of one end.",
     (30, 30, 50), PI * 15 ** 2 * 50 - PI * 5 ** 2 * 20,
     "result = cq.Workplane('XY').circle(15).extrude(50).faces('>Z').workplane().hole(10, 20)"),
    ("cad-f14", "intensive", "An L-bracket: a base plate 80 mm by 50 mm and 6 mm thick, with an upright plate 50 mm wide and 6 mm thick standing flush on one 50 mm end of the base, 60 mm tall overall, and a 10 mm diameter through hole at the center of the base.",
     (80, 50, 60), 80 * 50 * 6 + 6 * 50 * 54 - PI * 5 ** 2 * 6,
     "result = (cq.Workplane('XY').box(80, 50, 6, centered=False).union(cq.Workplane('XY').box(6, 50, 60, centered=False))"
     ".cut(cq.Workplane('XY').center(40, 25).circle(5).extrude(6)))"),
    ("cad-f15", "intensive", "A regular hexagonal prism 30 mm across corners and 20 mm tall with a 10 mm diameter through hole on its axis.",
     (30, 30 * math.sqrt(3) / 2, 20), 3 * math.sqrt(3) / 8 * 30 ** 2 * 20 - PI * 5 ** 2 * 20,
     "result = cq.Workplane('XY').polygon(6, 30).circle(5).extrude(20)"),
]


# A second fresh set, written on 2026-10-23 after the first (cad-f*) had been used to judge a hole
# check, and before that check's v2. -> fresh2.jsonl
FRESH2 = [
    ("cad-g01", "calm", "A rectangular block 70 mm long, 45 mm wide and 15 mm tall.",
     (70, 45, 15), 70 * 45 * 15, "result = cq.Workplane('XY').box(70, 45, 15)"),
    ("cad-g02", "alert", "A plate 120 mm by 40 mm and 8 mm thick with a 12 mm diameter through hole at its center.",
     (120, 40, 8), 120 * 40 * 8 - PI * 6 ** 2 * 8, "result = cq.Workplane('XY').box(120, 40, 8).faces('>Z').workplane().hole(12)"),
    ("cad-g03", "alert", "A cylinder 36 mm in diameter and 45 mm tall with a blind hole 14 mm in diameter and 25 mm deep at the center of its top face.",
     (36, 36, 45), PI * 18 ** 2 * 45 - PI * 7 ** 2 * 25,
     "result = cq.Workplane('XY').circle(18).extrude(45).faces('>Z').workplane().hole(14, 25)"),
    ("cad-g04", "intensive", "An L-bracket: a base plate 70 mm by 40 mm and 5 mm thick, with an upright plate 40 mm wide and 5 mm thick standing flush on one 40 mm end of the base, 45 mm tall overall, and two 6 mm diameter through holes in the base, 30 mm apart, centered across its width, 40 mm from the upright's outer face.",
     (70, 40, 45), 70 * 40 * 5 + 5 * 40 * 40 - 2 * PI * 3 ** 2 * 5,
     "result = (cq.Workplane('XY').box(70, 40, 5, centered=False).union(cq.Workplane('XY').box(5, 40, 45, centered=False))"
     ".cut(cq.Workplane('XY').pushPoints([(40, 5), (40, 35)]).circle(3).extrude(5)))"),
    ("cad-g05", "intensive", "A stepped shaft with three coaxial sections: 30 mm in diameter and 20 mm long, then 22 mm in diameter and 40 mm long, then 16 mm in diameter and 25 mm long.",
     (30, 30, 85), PI * (15 ** 2 * 20 + 11 ** 2 * 40 + 8 ** 2 * 25),
     "result = (cq.Workplane('XY').circle(15).extrude(20).faces('>Z').workplane().circle(11).extrude(40)"
     ".faces('>Z').workplane().circle(8).extrude(25))"),
    ("cad-g06", "alert", "A tube 80 mm long with an outer diameter of 26 mm and an inner diameter of 20 mm.",
     (26, 26, 80), PI * (13 ** 2 - 10 ** 2) * 80, "result = cq.Workplane('XY').circle(13).circle(10).extrude(80)"),
    ("cad-g07", "intensive", "A flange: a disc 100 mm in diameter and 12 mm thick with a 40 mm central hole and eight 9 mm bolt holes evenly spaced on a 75 mm diameter bolt circle.",
     (100, 100, 12), PI * (50 ** 2 - 20 ** 2) * 12 - 8 * PI * 4.5 ** 2 * 12,
     "result = cq.Workplane('XY').circle(50).circle(20).extrude(12).faces('>Z').workplane().polarArray(37.5, 0, 360, 8).hole(9)"),
    ("cad-g08", "alert", "A block 60 mm by 60 mm and 25 mm tall with a rectangular pocket 40 mm by 20 mm and 8 mm deep centered in its top face.",
     (60, 60, 25), 60 * 60 * 25 - 40 * 20 * 8,
     "result = cq.Workplane('XY').box(60, 60, 25).faces('>Z').workplane().rect(40, 20).cutBlind(-8)"),
    ("cad-g09", "intensive", "A T-bracket: a base plate 90 mm by 40 mm and 6 mm thick with a rib 6 mm thick and 40 mm wide standing across the middle of its length, 50 mm tall overall, and a 8 mm diameter through hole in the base 25 mm from each end, centered across its width.",
     (90, 40, 50), 90 * 40 * 6 + 6 * 40 * 44 - 2 * PI * 4 ** 2 * 6,
     "result = (cq.Workplane('XY').box(90, 40, 6, centered=False).union(cq.Workplane('XY').box(6, 40, 50, centered=False).translate((42, 0, 0)))"
     ".cut(cq.Workplane('XY').pushPoints([(25, 20), (65, 20)]).circle(4).extrude(6)))"),
    ("cad-g10", "alert", "A 50 mm cube with its four vertical edges chamfered by 6 mm.",
     (50, 50, 50), 50 ** 3 - 4 * (6 * 6 / 2) * 50, "result = cq.Workplane('XY').box(50, 50, 50).edges('|Z').chamfer(6)"),
    ("cad-g11", "intensive", "A plate 80 mm by 80 mm and 6 mm thick with nine 5 mm diameter through holes in a centered 3 by 3 grid spaced 20 mm apart.",
     (80, 80, 6), 80 * 80 * 6 - 9 * PI * 2.5 ** 2 * 6,
     "result = cq.Workplane('XY').box(80, 80, 6).faces('>Z').workplane().rarray(20, 20, 3, 3).hole(5)"),
    ("cad-g12", "intensive", "A cylinder 40 mm in diameter and 30 mm tall with a counterbored hole on its axis: a 10 mm through hole with a counterbore 18 mm in diameter and 8 mm deep.",
     (40, 40, 30), PI * 20 ** 2 * 30 - PI * 5 ** 2 * 22 - PI * 9 ** 2 * 8,
     "result = cq.Workplane('XY').circle(20).extrude(30).faces('>Z').workplane().cboreHole(10, 18, 8)"),
    ("cad-g13", "calm", "A solid cone with a base 50 mm in diameter and a height of 30 mm.",
     (50, 50, 30), PI * 25 ** 2 * 30 / 3, "result = cq.Workplane('XY').add(cq.Solid.makeCone(25, 0, 30))"),
    ("cad-g14", "intensive", "An open-topped box 80 mm by 60 mm and 35 mm tall outside, with walls and floor 3 mm thick and a 10 mm diameter drain hole through the center of the floor.",
     (80, 60, 35), 80 * 60 * 35 - 74 * 54 * 32 - PI * 5 ** 2 * 3,
     "result = (cq.Workplane('XY').box(80, 60, 35).faces('>Z').shell(-3)"
     ".cut(cq.Workplane('XY').circle(5).extrude(3).translate((0, 0, -17.5))))"),
    ("cad-g15", "alert", "A square bar 25 mm by 25 mm and 100 mm long with a 10 mm diameter hole straight through its middle, perpendicular to its length.",
     (25, 25, 100), 25 * 25 * 100 - PI * 5 ** 2 * 25, "result = cq.Workplane('XY').box(25, 25, 100).faces('>X').workplane().hole(10)"),
]


# A third fresh set, written on 2026-10-23 before a repair retry existed, to judge it. -> fresh3.jsonl
FRESH3 = [
    ("cad-h01", "calm", "A square plate 60 mm by 60 mm and 3 mm thick.", (60, 60, 3), 60 * 60 * 3,
     "result = cq.Workplane('XY').box(60, 60, 3)"),
    ("cad-h02", "calm", "A solid cylinder 18 mm in diameter and 70 mm tall.", (18, 18, 70), PI * 9 ** 2 * 70,
     "result = cq.Workplane('XY').circle(9).extrude(70)"),
    ("cad-h03", "alert", "A plate 50 mm by 50 mm and 10 mm thick with a 16 mm diameter through hole at its center.",
     (50, 50, 10), 50 * 50 * 10 - PI * 8 ** 2 * 10, "result = cq.Workplane('XY').box(50, 50, 10).faces('>Z').workplane().hole(16)"),
    ("cad-h04", "alert", "A block 30 mm by 30 mm and 40 mm tall with a blind hole 8 mm in diameter and 15 mm deep at the center of its top face.",
     (30, 30, 40), 30 * 30 * 40 - PI * 4 ** 2 * 15, "result = cq.Workplane('XY').box(30, 30, 40).faces('>Z').workplane().hole(8, 15)"),
    ("cad-h05", "alert", "A tube 40 mm long with an outer diameter of 32 mm and an inner diameter of 24 mm.",
     (32, 32, 40), PI * (16 ** 2 - 12 ** 2) * 40, "result = cq.Workplane('XY').circle(16).circle(12).extrude(40)"),
    ("cad-h06", "alert", "A 24 mm cube with a 10 mm diameter hole straight through the centers of two opposite faces.",
     (24, 24, 24), 24 ** 3 - PI * 5 ** 2 * 24, "result = cq.Workplane('XY').box(24, 24, 24).faces('>Z').workplane().hole(10)"),
    ("cad-h07", "intensive", "A plate 80 mm by 50 mm and 4 mm thick with four 5 mm diameter through holes, each centered 8 mm from the two nearest edges.",
     (80, 50, 4), 80 * 50 * 4 - 4 * PI * 2.5 ** 2 * 4,
     "result = cq.Workplane('XY').box(80, 50, 4).faces('>Z').workplane().rect(64, 34, forConstruction=True).vertices().hole(5)"),
    ("cad-h08", "intensive", "A flange: a disc 70 mm in diameter and 8 mm thick with a 25 mm central hole and four 7 mm bolt holes evenly spaced on a 50 mm diameter bolt circle.",
     (70, 70, 8), PI * (35 ** 2 - 12.5 ** 2) * 8 - 4 * PI * 3.5 ** 2 * 8,
     "result = cq.Workplane('XY').circle(35).circle(12.5).extrude(8).faces('>Z').workplane().polarArray(25, 0, 360, 4).hole(7)"),
    ("cad-h09", "intensive", "A cylinder 50 mm in diameter and 25 mm tall with a 12 mm diameter through hole on its axis and four 6 mm diameter through holes evenly spaced on a 34 mm diameter circle.",
     (50, 50, 25), PI * 25 ** 2 * 25 - PI * 6 ** 2 * 25 - 4 * PI * 3 ** 2 * 25,
     "result = cq.Workplane('XY').circle(25).circle(6).extrude(25).faces('>Z').workplane().polarArray(17, 0, 360, 4).hole(6)"),
    ("cad-h10", "alert", "A block 70 mm by 40 mm and 20 mm tall with a rectangular pocket 50 mm by 20 mm and 6 mm deep centered in its top face.",
     (70, 40, 20), 70 * 40 * 20 - 50 * 20 * 6, "result = cq.Workplane('XY').box(70, 40, 20).faces('>Z').workplane().rect(50, 20).cutBlind(-6)"),
    ("cad-h11", "intensive", "A stepped shaft: a 24 mm diameter section 35 mm long followed on the same axis by a 16 mm diameter section 45 mm long, with a 6 mm diameter through hole along the whole axis.",
     (24, 24, 80), PI * (12 ** 2 - 3 ** 2) * 35 + PI * (8 ** 2 - 3 ** 2) * 45,
     "result = (cq.Workplane('XY').circle(12).extrude(35).faces('>Z').workplane().circle(8).extrude(45)"
     ".faces('>Z').workplane().hole(6))"),
    ("cad-h12", "intensive", "An open-topped box 50 mm by 50 mm and 30 mm tall outside, with walls and floor 2 mm thick.",
     (50, 50, 30), 50 * 50 * 30 - 46 * 46 * 28, "result = cq.Workplane('XY').box(50, 50, 30).faces('>Z').shell(-2)"),
    ("cad-h13", "intensive", "A block 50 mm by 30 mm and 25 mm tall with a counterbored hole at the center of its top face: a 5 mm through hole with a counterbore 9 mm in diameter and 4 mm deep.",
     (50, 30, 25), 50 * 30 * 25 - PI * 2.5 ** 2 * 21 - PI * 4.5 ** 2 * 4,
     "result = cq.Workplane('XY').box(50, 30, 25).faces('>Z').workplane().cboreHole(5, 9, 4)"),
    ("cad-h14", "intensive", "An L-bracket: a base plate 50 mm by 30 mm and 4 mm thick, with an upright plate 30 mm wide and 4 mm thick standing flush on one 30 mm end of the base, 40 mm tall overall, and a 6 mm diameter through hole at the center of the base.",
     (50, 30, 40), 50 * 30 * 4 + 4 * 30 * 36 - PI * 3 ** 2 * 4,
     "result = (cq.Workplane('XY').box(50, 30, 4, centered=False).union(cq.Workplane('XY').box(4, 30, 40, centered=False))"
     ".cut(cq.Workplane('XY').center(25, 15).circle(3).extrude(4)))"),
    ("cad-h15", "alert", "A block 45 mm by 45 mm and 15 mm tall with its four vertical edges chamfered by 4 mm.",
     (45, 45, 15), 45 * 45 * 15 - 4 * (4 * 4 / 2) * 15, "result = cq.Workplane('XY').box(45, 45, 15).edges('|Z').chamfer(4)"),
    ("cad-h16", "alert", "A plate 90 mm by 30 mm and 6 mm thick with a straight through slot centered in it, 40 mm long overall and 8 mm wide, with rounded ends.",
     (90, 30, 6), 90 * 30 * 6 - (32 * 8 + PI * 4 ** 2) * 6,
     "result = cq.Workplane('XY').box(90, 30, 6).faces('>Z').workplane().slot2D(40, 8).cutThruAll()"),
    ("cad-h17", "intensive", "A plate 100 mm by 40 mm and 5 mm thick with five 6 mm diameter through holes in a row along its center line, 18 mm apart, centered on the plate.",
     (100, 40, 5), 100 * 40 * 5 - 5 * PI * 3 ** 2 * 5,
     "result = cq.Workplane('XY').box(100, 40, 5).faces('>Z').workplane().rarray(18, 1, 5, 1).hole(6)"),
    ("cad-h18", "calm", "A disc 64 mm in diameter and 6 mm thick.", (64, 64, 6), PI * 32 ** 2 * 6,
     "result = cq.Workplane('XY').circle(32).extrude(6)"),
    ("cad-h19", "alert", "A cylinder 44 mm in diameter and 20 mm tall with a blind hole 20 mm in diameter and 12 mm deep at the center of its top face.",
     (44, 44, 20), PI * 22 ** 2 * 20 - PI * 10 ** 2 * 12,
     "result = cq.Workplane('XY').circle(22).extrude(20).faces('>Z').workplane().hole(20, 12)"),
    ("cad-h20", "intensive", "A square bar 16 mm by 16 mm and 120 mm long with two 6 mm diameter holes straight through it, perpendicular to its length, each 20 mm from one end.",
     (16, 16, 120), 16 * 16 * 120 - 2 * PI * 3 ** 2 * 16,
     "result = cq.Workplane('XY').box(16, 16, 120).faces('>X').workplane().pushPoints([(0, -40), (0, 40)]).hole(6)"),
]


MEASURE = """
import json as _json
_shape = result.val() if hasattr(result, "val") else result
_bb = _shape.BoundingBox()
print(_json.dumps({"valid": _shape.isValid(), "solids": len(_shape.Solids()),
                   "bbox": sorted([_bb.xlen, _bb.ylen, _bb.zlen]), "volume": _shape.Volume()}))
"""


def records(problems=PROBLEMS):
    for pid, level, task, bbox, volume, ref in problems:
        yield {"id": pid, "domain": "cad", "level": level, "task": task, "bbox": sorted(bbox), "volume": volume,
               "rel_tol": REL_TOL, "reference": ref}


def verify(python, problems=PROBLEMS):
    """Build every reference with the kernel; it must be one valid solid matching the key."""
    bad = 0
    for r in records(problems):
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
    print(f"verify: {len(problems) - bad}/{len(problems)} references match their keys")
    return bad


def main():
    ids = [p[0] for p in PROBLEMS + FRESH + FRESH2 + FRESH3]
    assert len(ids) == len(set(ids)), "duplicate problem id"
    if "--verify" in sys.argv:
        python = sys.argv[sys.argv.index("--verify") + 1]
        sys.exit(1 if sum(verify(python, ps) for ps in (PROBLEMS, FRESH, FRESH2, FRESH3)) else 0)
    for problems, name in ((PROBLEMS, "problems.jsonl"), (FRESH, "fresh.jsonl"), (FRESH2, "fresh2.jsonl"), (FRESH3, "fresh3.jsonl")):
        out = Path(__file__).with_name(name)
        with out.open("w") as f:
            for r in records(problems):
                f.write(json.dumps(r) + "\n")
        counts = {lvl: sum(p[1] == lvl for p in problems) for lvl in ("calm", "alert", "intensive")}
        print(f"wrote {len(problems)} problems to {out} {counts}")


if __name__ == "__main__":
    main()
