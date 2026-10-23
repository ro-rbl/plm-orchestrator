"""Which tasks the CAD pack claims.

A CAD task asks for a part to be made (model, design, create, build, make, draw)
and gives at least one size in millimeters or centimeters. Naming a CAD tool or
format (CadQuery, build123d, CAD, 3D model, STEP, STL) makes the claim certain:
then it ties the software pack's certain claim on "write a ... program", and CAD's
higher priority takes it, since the user wants a part, not a program. Questions
about CAD ("What does CAD stand for?") give no size and go to the general pack.
"""

import math
import re

MAKE = re.compile(r"\b(?:model|design|create|build|make|draw|write|generate|need)\b", re.IGNORECASE)
TOOL = re.compile(r"\b(?:cadquery|build123d|cad|3d model|solid model|step(?:-ready)?|stl)\b", re.IGNORECASE)
PART = re.compile(
    r"\b(?:part|block|cube|box|plate|cylinder|tube|pipe|rod|bar|disc|sphere|ball|cone|prism|bracket|flange"
    r"|shaft|spacer|standoff|washer|bushing|enclosure|channel|column|hemisphere|blank|gear|cup|housing|knob"
    r"|mount|clip|hinge|lid)\b", re.IGNORECASE)
SIZE = re.compile(r"\d\s*(?:mm|cm)\b|\bmm\b", re.IGNORECASE)


def claims(text):
    """inf when a CAD tool or format is named, else distinct part words, for a request to make a sized part."""
    if not (MAKE.search(text) and SIZE.search(text)):
        return 0
    if TOOL.search(text):
        return math.inf
    return len({m.lower() for m in PART.findall(text)})
