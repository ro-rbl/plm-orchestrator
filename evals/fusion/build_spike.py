"""Fusion spike: CAD + engineering problems, each set written before any model answered it.

    .venv/bin/python evals/fusion/build_spike.py      # writes spike.jsonl and round2.jsonl; fails if a reference doesn't build to its key

spike.jsonl (fu-*, 2026-11-07 morning) judged the first planner; round2.jsonl (fr-*, written after its results)
judges the metres variant (run_spike.py --variant m).

Each problem needs a calculation first (physics, electrical or aerospace) whose result is a dimension of the part
the CAD step then models. Keys: the dimension (mm) computed here, and the finished part's bbox and volume, measured
by building the reference CadQuery program in the CAD pack's kernel. Feasibility spike, not a verdict: 10 problems,
all written by Claude. Run with evals/fusion/run_spike.py.
"""

import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from plm_cad import kernel  # noqa: E402

PI = math.pi


def problems():
    out = []

    def add(pid, pack, task, dim, ref):
        out.append({"id": pid, "pack": pack, "task": task, "dim_mm": dim, "reference": ref})

    t = 6000 / (50e6 * 0.040) * 1000  # mm
    add("fu-01", "physics",
        "A steel plate 40 mm wide carries a 6000 N tensile load across its width, and the tensile stress may not exceed "
        "50 MPa. Find the minimum plate thickness, then model a plate 100 mm long and 40 mm wide with that thickness, "
        "with two 6 mm diameter through holes on the plate's long centerline, 60 mm apart and centered on the plate.",
        t, f"result = cq.Workplane('XY').box(100, 40, {t}).faces('>Z').workplane().pushPoints([(-30, 0), (30, 0)]).hole(6)")

    d = math.sqrt(4 * (10000 / 100e6) / PI) * 1000
    add("fu-02", "physics",
        "A round steel rod must carry a 10 kN tensile load with a stress of at most 100 MPa. Find the minimum rod "
        "diameter, then model a solid rod of that diameter and 80 mm long.",
        d, f"result = cq.Workplane('XY').circle({d / 2}).extrude(80)")

    a = 1.68e-8 * 0.2 / 1e-4 * 1e6  # mm^2
    t = a / 8
    add("fu-03", "electrical",
        "A copper busbar (resistivity 1.68e-8 ohm m) 200 mm long must have a resistance of 0.1 milliohm. It is 8 mm "
        "wide; find its thickness. Then model the busbar, 200 mm by 8 mm by that thickness, with a 5 mm diameter "
        "through hole 10 mm from each end, on the centerline.",
        t, f"result = cq.Workplane('XY').box(200, 8, {t}).faces('>Z').workplane().pushPoints([(-90, 0), (90, 0)]).hole(5)")

    h = 0.54 / 2700 * 1e9 / (60 * 50)
    add("fu-04", "physics",
        "A solid aluminium block (density 2700 kg/m^3) has a 60 mm by 50 mm base and must weigh 0.54 kg. Find its "
        "height, then model the block.",
        h, f"result = cq.Workplane('XY').box(60, 50, {h})")

    h = 2e6 / (PI * 50 ** 2)
    add("fu-05", "physics",
        "A cylindrical mold insert 100 mm in diameter must have a volume of exactly 2 liters. Find its height, then "
        "model it as a solid cylinder.",
        h, f"result = cq.Workplane('XY').circle(50).extrude({h})")

    d = (16 * 50 / (PI * 40e6)) ** (1 / 3) * 1000
    add("fu-06", "physics",
        "A solid circular shaft transmits a torque of 50 N m, and the shear stress may not exceed 40 MPa. Find the "
        "minimum shaft diameter, then model a solid shaft of that diameter and 120 mm long.",
        d, f"result = cq.Workplane('XY').circle({d / 2}).extrude(120)")

    t = 300 / 2 / 25
    add("fu-07", "electrical",
        "A copper bar must carry 300 A at a current density of 2 A/mm^2. It is 25 mm wide; find its thickness. Then "
        "model the bar, 150 mm long and 25 mm wide with that thickness, with an 8 mm diameter through hole at its center.",
        t, f"result = cq.Workplane('XY').box(150, 25, {t}).faces('>Z').workplane().hole(8)")

    s = math.sqrt(9000 / 100e3) * 1000
    add("fu-08", "physics",
        "A square foot pad spreads a 9000 N load on the ground, and the ground pressure may not exceed 100 kPa. Find "
        "the side length of the square, then model the pad as a square plate with that side, 10 mm thick, with a "
        "20 mm diameter through hole at its center.",
        s, f"result = cq.Workplane('XY').box({s}, {s}, 10).faces('>Z').workplane().hole(20)")

    L = 9.81 * 1.0 ** 2 / (4 * PI ** 2) * 1000
    add("fu-09", "physics",
        "A simple pendulum must have a period of 1.0 s where g = 9.81 m/s^2. Find its length, then model the pendulum "
        "rod as a solid cylinder 6 mm in diameter with that length.",
        L, f"result = cq.Workplane('XY').circle(3).extrude({L})")

    t = 1.0 / 7850 * 1e9 / (PI * 50 ** 2)
    add("fu-10", "physics",
        "A solid steel disc (density 7850 kg/m^3) 100 mm in diameter must weigh 1.0 kg. Find its thickness, then model "
        "the disc with that thickness and add a 20 mm diameter through hole at its center.",
        t, f"result = cq.Workplane('XY').circle(50).extrude({t}).faces('>Z').workplane().hole(20)")
    return out


def round2():
    out = []

    def add(pid, pack, task, dim, ref):
        out.append({"id": pid, "pack": pack, "task": task, "dim_mm": dim, "reference": ref})

    side = math.sqrt(80000 / 20e6) * 1000
    add("fr-01", "physics",
        "A short square column carries an 80 kN compressive load, and the compressive stress may not exceed 20 MPa. "
        "Find the minimum side of the square section, then model the column with that square section and 150 mm tall.",
        side, f"result = cq.Workplane('XY').box({side}, {side}, 150)")

    t = 2.65e-8 * 0.5 / 50e-6 * 1e6 / 20
    add("fr-02", "electrical",
        "An aluminium busbar (resistivity 2.65e-8 ohm m) 500 mm long must have a resistance of 50 microohm. It is "
        "20 mm wide; find its thickness. Then model the busbar, 500 mm by 20 mm by that thickness, with a 10 mm "
        "diameter through hole 15 mm from each end, on the centerline.",
        t, f"result = cq.Workplane('XY').box(500, 20, {t}).faces('>Z').workplane().pushPoints([(-235, 0), (235, 0)]).hole(10)")

    h = 0.5 / 8500 * 1e9 / (PI * 20 ** 2)
    add("fr-03", "physics",
        "A solid brass cylinder (density 8500 kg/m^3) 40 mm in diameter must weigh 0.5 kg. Find its height, then "
        "model the cylinder.",
        h, f"result = cq.Workplane('XY').circle(20).extrude({h})")

    side = math.sqrt(14.7 / (0.5 * 1.225 * 20 ** 2 * 1.2)) * 1000
    add("fr-04", "aerospace",
        "A flat square plate faces a 20 m/s airflow (air density 1.225 kg/m^3, drag coefficient 1.2) and must produce "
        "14.7 N of drag. Find the side of the square, then model the plate with that side and 5 mm thick.",
        side, f"result = cq.Workplane('XY').box({side}, {side}, 5)")

    L = 0.36e-3 / (12e-6 * 100) * 1000
    add("fr-05", "physics",
        "A steel rod (thermal expansion coefficient 12e-6 per K) must lengthen by 0.36 mm when heated by 100 K. Find "
        "its length, then model the rod as a solid cylinder 10 mm in diameter with that length.",
        L, f"result = cq.Workplane('XY').circle(5).extrude({L})")

    L = 120 / 0.5 * 100 / 120  # cm^2 -> mm^2, / width
    add("fr-06", "electrical",
        "A heater plate must dissipate 120 W at a surface power density of 0.5 W/cm^2. It is 120 mm wide; find its "
        "length. Then model the plate, that long, 120 mm wide and 4 mm thick, with a 4 mm diameter through hole "
        "10 mm in from each side at each of the four corners.",
        L, f"result = cq.Workplane('XY').box({L}, 120, 4).faces('>Z').workplane()"
           f".pushPoints([({L / 2 - 10}, 50), ({L / 2 - 10}, -50), ({-L / 2 + 10}, 50), ({-L / 2 + 10}, -50)]).hole(4)")

    d = math.sqrt(4 * (20000 / 10e6) / PI) * 1000
    add("fr-07", "physics",
        "A hydraulic piston must produce 20 kN of force at an oil pressure of 10 MPa. Find the piston diameter, then "
        "model the piston as a solid cylinder of that diameter and 60 mm long.",
        d, f"result = cq.Workplane('XY').circle({d / 2}).extrude(60)")

    d = math.sqrt(4 * (6000 / 60e6) / PI) * 1000
    add("fr-08", "physics",
        "Two bolts share a 12 kN shear load equally, and the shear stress in each may not exceed 60 MPa. Find the "
        "minimum bolt diameter. Then model a bar 80 mm long, 30 mm wide and 10 mm thick with two through holes of "
        "that diameter on the long centerline, 50 mm apart and centered on the bar.",
        d, f"result = cq.Workplane('XY').box(80, 30, 10).faces('>Z').workplane().pushPoints([(-25, 0), (25, 0)]).hole({d})")

    c = 400 / (0.5 * 1.225 * 15 ** 2 * 1.0) / 6 * 1000
    add("fr-09", "aerospace",
        "A glider wing with a lift coefficient of 1.0 flies at 15 m/s in air of density 1.225 kg/m^3 and must lift "
        "400 N. Its span is 6 m; find its chord. Then model the wing as a flat plate 6000 mm long, as wide as that "
        "chord, and 20 mm thick.",
        c, f"result = cq.Workplane('XY').box(6000, {c}, 20)")

    w = 1.68e-8 * 1.0 / 0.4e-3 * 1e6 / 2
    add("fr-10", "electrical",
        "A copper ground strap (resistivity 1.68e-8 ohm m) 1 m long and 2 mm thick must have a resistance of "
        "0.4 milliohm. Find its width, then model the strap, 1000 mm long, that wide and 2 mm thick.",
        w, f"result = cq.Workplane('XY').box(1000, {w}, 2)")
    return out


def build(problems, name):
    rows = []
    for p in problems:
        measured, error = kernel.build(p["reference"])
        if error or not measured or not measured["valid"] or measured["solids"] != 1:
            sys.exit(f"{p['id']}: reference doesn't build: {error}")
        rows.append(p | {"bbox": measured["bbox"], "volume": measured["volume"], "rel_tol": 0.001})
        print(f"{p['id']} {p['pack']:<10} dim {p['dim_mm']:9.4f} mm  bbox {[round(x, 3) for x in measured['bbox']]}  "
              f"volume {measured['volume']:.1f}")
    (Path(__file__).parent / name).write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"wrote {len(rows)} problems to {name}")


def main():
    build(problems(), "spike.jsonl")
    build(round2(), "round2.jsonl")


if __name__ == "__main__":
    main()
