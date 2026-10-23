"""Checks on a built part that need no answer key.

The kernel says whether the program made one valid solid. Beyond that, the
part's overall size should come from the task: every extent of its bounding box
should be a dimension the task states, half of one (a hemisphere's height), the
sum of two different ones (a stepped shaft is as long as its sections together),
or a hexagon's width across flats. Twice a stated size is deliberately not in the
list: that is the radius-for-diameter mistake (circle(20) for a 20 mm diameter).

With holes=True, holes are checked too, since a wrong hole leaves the outside size right: every
hole the task asks for by diameter ("four 6 mm through holes", "a blind hole 10 mm
in diameter and 12 mm deep", a tube's "inner diameter of 14 mm", a counterbore)
must be in the part as a concave cylinder of that diameter, as many times as
asked; a through hole must span the part along its axis (coaxial faces together,
so a counterbored through hole counts), and a blind hole must be as deep as asked.

The pack ships the size-only check (holes=False). The hole check was judged on fresh
parts (evals/score_cad_check.py) and not adopted: it caught 38 of 40 wrong parts to
size-only's 27, but it flagged a correct L-bracket, whose base-plate hole is "through"
the plate though not the whole part. Both checks also flag a correct three-section
shaft (its length is the sum of three stated sizes; only pairs are summed).
"""

import math
import re

DIMENSION = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)")
REL_TOL = 0.005
HOLE_TOL = 0.01
COUNTS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8, "twelve": 12}
NUM = r"(\d+(?:\.\d+)?)"
# (pattern, kind): kind "through", "blind" (with a depth group) or "any" (through decided by the wording)
HOLE_SPECS = [
    (re.compile(rf"\b(?:(\w+)\s+)?{NUM} mm (?:diameter )?((?:(?:through|vertical|bolt|corner|central|center|mounting)\s+)*)"
                rf"(?:holes?|bore)\b(\s+(?:straight\s+)?through)?", re.IGNORECASE), "any"),
    (re.compile(rf"\b(?:(\w+)\s+)?(?:blind )?(?:holes?|bore) {NUM} mm in diameter and {NUM} mm deep", re.IGNORECASE),
     "blind"),
    (re.compile(rf"\b(?:(\w+)\s+)?(?:holes?|bore) {NUM} mm in diameter(?! and \d)", re.IGNORECASE), "any"),
    (re.compile(rf"\binner diameter of {NUM} mm", re.IGNORECASE), "through"),
    (re.compile(rf"\bcounterbore {NUM} mm in diameter and {NUM} mm deep", re.IGNORECASE), "blind"),
]


def hole_specs(task):
    """[(diameter, count, kind, depth)] for the holes a task asks for by diameter."""
    specs = []
    for pat, kind in HOLE_SPECS:
        for m in pat.finditer(task):
            g = m.groups()
            if pat is HOLE_SPECS[0][0]:
                count, d, words, after = COUNTS.get((g[0] or "").lower(), 1), float(g[1]), g[2] or "", g[3]
                through = "through" in words.lower() or bool(after)
                specs.append((d, count, "through" if through else "any", None))
            elif kind == "blind" and len(g) == 3:
                specs.append((float(g[1]), COUNTS.get((g[0] or "").lower(), 1), "blind", float(g[2])))
            elif kind == "blind":
                specs.append((float(g[0]), 1, "blind", float(g[1])))
            elif kind == "through":
                specs.append((float(g[0]), 1, "through", None))
            else:
                specs.append((float(g[1]), COUNTS.get((g[0] or "").lower(), 1), "any", None))
    return specs


def hole_issues(task, holes):
    issues = []
    for d, count, kind, depth in hole_specs(task):
        same = [h for h in holes if math.isclose(h["diameter"], d, rel_tol=HOLE_TOL)]
        if kind == "through":
            same = [h for h in same if h["axis_through"]]
        elif kind == "blind":
            same = [h for h in same if math.isclose(h["depth"], depth, rel_tol=HOLE_TOL)]
        if len(same) < count:
            what = "through " if kind == "through" else f"{depth:g} mm deep " if kind == "blind" else ""
            issues.append(f"asked for {count} {what}hole{'s' if count > 1 else ''} of {d:g} mm, found {len(same)}")
    return issues


def task_sizes(task):
    nums = sorted({float(n) for n in DIMENSION.findall(task) if float(n) > 0})
    sums = {a + b for i, a in enumerate(nums) for b in nums[i + 1:]}
    halves = {n / 2 for n in nums}
    flats = {n * math.sqrt(3) / 2 for n in nums}
    return sorted(set(nums) | sums | halves | flats)


def check(task, measured, error, holes=False):
    """Issues with a built part ([] = nothing caught). holes=True adds the hole check (not adopted; see above)."""
    if error:
        return [error]
    issues = []
    if not measured["valid"]:
        issues.append("the kernel says the solid is invalid")
    if measured["solids"] != 1:
        issues.append(f"{measured['solids']} solids, expected one part")
    if measured["volume"] <= 0:
        issues.append("no volume")
    sizes = task_sizes(task)
    if sizes:
        for extent in measured["bbox"]:
            if not any(math.isclose(extent, s, rel_tol=REL_TOL) for s in sizes):
                issues.append(f"overall size {extent:.4g} mm matches no dimension in the task")
    return issues + (hole_issues(task, measured.get("holes", [])) if holes else [])
