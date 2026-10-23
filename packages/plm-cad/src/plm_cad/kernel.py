"""Build a model-written CadQuery program and measure what it made.

The program runs in a separate `python -I` process (not -S: CadQuery lives in
site-packages), in an empty temp directory, with a time limit, after the same
kind of screen as the numeric calculator. The screen is a guard against
accidents, not a security sandbox.

The program must leave its part in `result`; models often call it `part` or
similar, so failing that, the last CadQuery object assigned is measured.
"""

import json
import re
import subprocess
import sys
import tempfile

CODE_RE = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.DOTALL | re.IGNORECASE)
ALLOWED_IMPORTS = {"cadquery", "math"}
BLOCKED = re.compile(r"__|\b(?:open|exec|eval|compile|input|globals|getattr|setattr|breakpoint|subprocess|os"
                     r"|sys|shutil|socket)\b\s*[.(]")
PRELUDE = "import cadquery as cq\nshow_object = debug = lambda *a, **k: None\n"
MEASURE = """
import json as _json
import cadquery as _cq
_found = globals().get("result")
if _found is None:
    _found = next((v for v in reversed(list(globals().values())) if isinstance(v, (_cq.Workplane, _cq.Shape))), None)
if _found is None:
    raise SystemExit("PLM_CAD: no result: assign the part to a variable named result")
_shape = _found.val() if isinstance(_found, _cq.Workplane) else _found
if isinstance(_shape, _cq.Workplane) or not isinstance(_shape, _cq.Shape):
    raise SystemExit("PLM_CAD: result holds no solid")
if len(_found.vals()) > 1 if isinstance(_found, _cq.Workplane) else False:
    _shape = _cq.Compound.makeCompound(_found.vals())
_bb = _shape.BoundingBox()
print("PLM_CAD " + _json.dumps({"valid": _shape.isValid(), "solids": len(_shape.Solids()),
                                "bbox": sorted([_bb.xlen, _bb.ylen, _bb.zlen]), "volume": _shape.Volume()}))
"""


def extract_program(text):
    blocks = CODE_RE.findall(text or "")
    return blocks[-1] if blocks else None


def screen(code):
    """A reason the program is refused, or None if it may run."""
    for line in code.splitlines():
        m = re.match(r"\s*(?:from\s+(\S+)\s+import|import\s+(.+))", line)
        if m:
            names = [m.group(1)] if m.group(1) else [n.split(" as ")[0].strip() for n in m.group(2).split(",")]
            bad = [n for n in names if n.split(".")[0] not in ALLOWED_IMPORTS]
            if bad:
                return f"import not allowed: {', '.join(bad)}"
    hit = BLOCKED.search(code)
    return f"blocked construct: {hit.group().strip()}" if hit else None


def build(code, timeout=60):
    """Run a part program. Returns (measurement dict or None, error or None)."""
    refused = screen(code)
    if refused:
        return None, refused
    with tempfile.TemporaryDirectory() as d:
        try:
            p = subprocess.run([sys.executable, "-I", "-c", PRELUDE + code + "\n" + MEASURE],
                               capture_output=True, text=True, timeout=timeout, cwd=d)
        except subprocess.TimeoutExpired:
            return None, f"timed out after {timeout} s"
    lines = [ln for ln in p.stdout.splitlines() if ln.startswith("PLM_CAD ")]
    if p.returncode or not lines:
        err = (p.stderr.strip().splitlines() or [f"exit {p.returncode}, no measurement"])[-1]
        return None, err.replace("PLM_CAD: ", "")[:300]
    return json.loads(lines[-1][len("PLM_CAD "):]), None
