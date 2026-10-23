"""Checks on a built part that need no answer key.

The kernel says whether the program made one valid solid. Beyond that, the
part's overall size should come from the task: every extent of its bounding box
should be a dimension the task states, half of one (a hemisphere's height), the
sum of two different ones (a stepped shaft is as long as its sections together),
or a hexagon's width across flats. Twice a stated size is deliberately not in the
list: that is the radius-for-diameter mistake (circle(20) for a 20 mm diameter).
"""

import math
import re

DIMENSION = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)")
REL_TOL = 0.005


def task_sizes(task):
    nums = sorted({float(n) for n in DIMENSION.findall(task) if float(n) > 0})
    sums = {a + b for i, a in enumerate(nums) for b in nums[i + 1:]}
    halves = {n / 2 for n in nums}
    flats = {n * math.sqrt(3) / 2 for n in nums}
    return sorted(set(nums) | sums | halves | flats)


def check(task, measured, error):
    """Issues with a built part ([] = nothing caught)."""
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
    return issues
