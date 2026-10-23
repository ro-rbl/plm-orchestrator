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
# Holes: concave cylindrical faces, merged when the kernel splits one hole into several faces.
from OCP.BRepAdaptor import BRepAdaptor_Surface as _Surface
from OCP.BRepTools import BRepTools as _BRepTools
from OCP.GeomAbs import GeomAbs_Cylinder as _CYLINDER
from OCP.gp import gp_Pnt as _Pnt, gp_Vec as _Vec
from OCP.TopAbs import TopAbs_REVERSED as _REVERSED
_holes = {}
for _f in _shape.Faces():
    _a = _Surface(_f.wrapped)
    if _a.GetType() != _CYLINDER:
        continue
    _cyl = _a.Cylinder()
    _r, _ax = _cyl.Radius(), _cyl.Axis()
    _d, _o = _ax.Direction(), _ax.Location()
    _dv = _cq.Vector(_d.X(), _d.Y(), _d.Z())
    _ov = _cq.Vector(_o.X(), _o.Y(), _o.Z())
    # a point on the face and the solid's outward normal there, from the middle of its parameters
    _u0, _u1, _v0, _v1 = _BRepTools.UVBounds_s(_f.wrapped)
    _pt, _du, _dvv = _Pnt(), _Vec(), _Vec()
    _a.D1((_u0 + _u1) / 2, (_v0 + _v1) / 2, _pt, _du, _dvv)
    _n = _du.Crossed(_dvv)
    if _f.wrapped.Orientation() == _REVERSED:
        _n.Reverse()
    _pv = _cq.Vector(_pt.X(), _pt.Y(), _pt.Z())
    _radial = (_pv - _ov) - _dv * (_pv - _ov).dot(_dv)
    if _cq.Vector(_n.X(), _n.Y(), _n.Z()).dot(_radial) >= 0:
        continue  # an outside surface (normal points away from the axis), not a hole
    _ts = [(_v.toTuple()[0] - _ov.x) * _dv.x + (_v.toTuple()[1] - _ov.y) * _dv.y + (_v.toTuple()[2] - _ov.z) * _dv.z
           for _v in _f.Vertices()]
    if not _ts:
        continue
    # the axis line's point nearest the origin keys a hole, with its radius and direction
    _p0 = _ov - _dv * _ov.dot(_dv)
    _key = (round(_r, 3), tuple(round(abs(x), 3) for x in (_dv.x, _dv.y, _dv.z)), tuple(round(x, 2) for x in (_p0.x, _p0.y, _p0.z)))
    _lo, _hi = _holes.get(_key, (min(_ts), max(_ts)))
    _holes[_key] = (min(_lo, min(_ts)), max(_hi, max(_ts)))
_holes_out = []
for (_r, _dir, _p), (_lo, _hi) in _holes.items():
    _span = None  # the part's extent along the hole's axis, when the axis is along x, y or z
    for _i, _ext in enumerate((_bb.xlen, _bb.ylen, _bb.zlen)):
        if abs(_dir[_i] - 1) < 1e-3:
            _span = _ext
    # all hole faces on this axis together (a counterbored hole is two coaxial cylinders)
    _iv = sorted(v for k, v in _holes.items() if k[1:] == (_dir, _p))
    _clo, _chi = _iv[0]
    for _a0, _a1 in _iv[1:]:
        if _a0 <= _chi + 1e-6:
            _chi = max(_chi, _a1)
    _tol = 1e-3 * max(_span or 1, 1)
    _holes_out.append({"diameter": 2 * _r, "depth": _hi - _lo,
                       "through": _span is not None and abs((_hi - _lo) - _span) <= _tol,
                       "axis_through": _span is not None and abs((_chi - _clo) - _span) <= _tol})
print("PLM_CAD " + _json.dumps({"valid": _shape.isValid(), "solids": len(_shape.Solids()),
                                "bbox": sorted([_bb.xlen, _bb.ylen, _bb.zlen]), "volume": _shape.Volume(),
                                "holes": _holes_out}))
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
