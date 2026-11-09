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


def judged():
    """40 problems for FUSE_RULE (evals/fusion/run_spike.py), written 2026-11-08 after rounds 1-2, before any answer."""
    out = []
    n = [0]

    def add(pack, task, dim, ref):
        n[0] += 1
        out.append({"id": f"fj-{n[0]:02d}", "pack": pack, "task": task, "dim_mm": dim, "reference": ref})

    def box(x, y, z, holes=(), d=0):
        r = f"cq.Workplane('XY').box({x}, {y}, {z})"
        if holes:
            r += f".faces('>Z').workplane().pushPoints({list(holes)}).hole({d})"
        return "result = " + r

    def cyl(d, h, hole=0):
        r = f"cq.Workplane('XY').circle({d / 2}).extrude({h})"
        if hole:
            r += f".faces('>Z').workplane().hole({hole})"
        return "result = " + r

    # cantilever bending: h = sqrt(6 F L / (b sigma))
    for F, L, b, sig in ((200, 300, 30, 60e6), (500, 250, 40, 100e6), (120, 400, 20, 80e6)):
        h = math.sqrt(6 * F * (L / 1000) / ((b / 1000) * sig)) * 1000
        add("physics", f"A rectangular cantilever beam {L} mm long and {b} mm wide carries a {F} N point load at its free "
            f"end, and the bending stress may not exceed {sig / 1e6:g} MPa. Find the minimum beam depth (height), then "
            f"model the beam as a solid block {L} mm long, {b} mm wide and that deep.", h, box(L, b, h))
    # floating cube: side = (m / (rho_w - rho)) ^ (1/3)
    for m, rho in ((2.0, 600), (5.0, 700), (1.2, 400)):
        a = (m / (1000 - rho)) ** (1 / 3) * 1000
        add("physics", f"A wooden cube (density {rho} kg/m^3) floating in fresh water (1000 kg/m^3) must just keep a "
            f"{m:g} kg load above the water when fully submerged. Find the cube's side length, then model the cube.",
            a, box(a, a, a))
    # round wire from voltage drop: A = rho L I / dV, d = sqrt(4A/pi)
    for L, I, dV, rho, mat in ((10, 5, 0.25, 1.68e-8, "copper"), (20, 10, 0.5, 2.65e-8, "aluminium"),
                               (5, 20, 0.1, 1.68e-8, "copper")):
        d = math.sqrt(4 * (rho * L * I / dV) / PI) * 1000
        add("electrical", f"A {mat} wire (resistivity {rho:g} ohm m) {L} m long carries {I} A, and the voltage drop "
            f"along it may not exceed {dV:g} V. Find the minimum wire diameter, then model a 300 mm long sample of the "
            f"wire as a solid cylinder of that diameter.", d, cyl(d, 300))
    # parallel-plate capacitor: A = C d / (eps0 epsr), square side
    for C, gap, er in ((1e-9, 0.1e-3, 4.0), (470e-12, 0.2e-3, 2.2), (2.2e-9, 0.05e-3, 10.0)):
        side = math.sqrt(C * gap / (8.854e-12 * er)) * 1000
        add("electrical", f"A parallel-plate capacitor with square plates must have a capacitance of {C * 1e12:g} pF, "
            f"with a dielectric of relative permittivity {er:g} and a gap of {gap * 1000:g} mm (vacuum permittivity "
            f"8.854e-12 F/m). Find the side of a plate, then model one plate as a square plate with that side, 1 mm "
            f"thick.", side, box(side, side, 1))
    # heat conduction: t = k A dT / Q
    for k, A_side, dT, Q in ((0.04, 500, 20, 4.0), (0.8, 300, 15, 54.0), (1.5, 200, 30, 360.0)):
        t = k * (A_side / 1000) ** 2 * dT / Q * 1000
        add("physics", f"A square insulating panel {A_side} mm by {A_side} mm (thermal conductivity {k:g} W/(m K)) has a "
            f"{dT} K temperature difference across it and may conduct at most {Q:g} W. Find its minimum thickness, "
            f"then model the panel.", t, box(A_side, A_side, t))
    # ideal gas tank: V = nRT/P, cylinder of given diameter
    for nmol, T, P, D in ((2.0, 300, 500e3, 100), (1.0, 293, 200e3, 120), (0.5, 350, 100e3, 80)):
        h = (nmol * 8.314 * T / P) * 1e9 / (PI * (D / 2) ** 2)
        add("physics", f"A cylindrical tank {D} mm in inside diameter must hold {nmol:g} mol of an ideal gas at {T} K "
            f"and {P / 1e3:g} kPa (R = 8.314 J/(mol K)). Find the inside height, then model the tank's gas space as a "
            f"solid cylinder {D} mm in diameter and that tall.", h, cyl(D, h))
    # drag on a cylinder end-on: A = D / (0.5 rho v^2 Cd), d = sqrt(4A/pi)
    for Dn, v, cd in ((5.0, 30, 0.8), (12.0, 25, 1.1), (2.0, 40, 0.9)):
        d = math.sqrt(4 * Dn / (0.5 * 1.225 * v ** 2 * cd) / PI) * 1000
        add("aerospace", f"A cylinder faces a {v} m/s airflow end-on (air density 1.225 kg/m^3, drag coefficient {cd:g}) "
            f"and must produce {Dn:g} N of drag. Find its diameter, then model the cylinder with that diameter and "
            f"100 mm long.", d, cyl(d, 100))
    # wing chord from lift and span
    for W, v, cl, span in ((600, 20, 1.2, 8), (250, 12, 0.9, 5), (1500, 30, 1.1, 10)):
        c = W / (0.5 * 1.225 * v ** 2 * cl) / span * 1000
        add("aerospace", f"A wing with a lift coefficient of {cl:g} flies at {v} m/s in air of density 1.225 kg/m^3 and "
            f"must lift {W} N. Its span is {span} m; find its chord. Then model a 500 mm long section of the wing as a "
            f"flat plate 500 mm long, as wide as that chord, and 15 mm thick.", c, box(500, c, 15))
    # tensile plate thickness with holes
    for F, w, sig, L in ((9000, 50, 60e6, 120), (4000, 25, 40e6, 90), (15000, 60, 125e6, 150)):
        t = F / (sig * w / 1000) * 1000
        add("physics", f"A plate {w} mm wide carries a {F} N tensile load across its width, and the stress may not "
            f"exceed {sig / 1e6:g} MPa. Find the minimum thickness, then model a plate {L} mm long and {w} mm wide with "
            f"that thickness and an 8 mm diameter through hole {L / 2 - 15:g} mm from its center at each end, on the "
            f"long centerline.", t, box(L, w, t, [(-(L / 2 - 15), 0), (L / 2 - 15, 0)], 8))
    # mass-sized disc with center hole
    for m, rho, D, mat in ((2.0, 7850, 120, "steel"), (0.3, 2700, 80, "aluminium"), (1.5, 8900, 90, "copper")):
        t = m / rho * 1e9 / (PI * (D / 2) ** 2)
        add("physics", f"A solid {mat} disc (density {rho} kg/m^3) {D} mm in diameter must weigh {m:g} kg. Find its "
            f"thickness, then model the disc with that thickness and add a 10 mm diameter through hole at its center.",
            t, cyl(D, t, 10))
    # torsion shaft
    for T, tau, L in ((120, 50e6, 150), (30, 25e6, 100), (400, 60e6, 200)):
        d = (16 * T / (PI * tau)) ** (1 / 3) * 1000
        add("physics", f"A solid circular shaft transmits {T} N m of torque, and the shear stress may not exceed "
            f"{tau / 1e6:g} MPa. Find the minimum diameter, then model a solid shaft of that diameter and {L} mm long.",
            d, cyl(d, L))
    # current density bar with center hole
    for I, J, w, L in ((500, 2.5, 40, 200), (150, 1.5, 20, 120), (800, 4.0, 50, 250)):
        t = I / J / w
        add("electrical", f"A copper bar must carry {I} A at a current density of {J:g} A/mm^2. It is {w} mm wide; find "
            f"its thickness. Then model the bar, {L} mm long and {w} mm wide with that thickness, with a 6 mm diameter "
            f"through hole at its center.", t, box(L, w, t, [(0, 0)], 6))
    # hydraulic piston
    for F, P, L in ((50000, 15e6, 80), (8000, 5e6, 50), (120000, 20e6, 100)):
        d = math.sqrt(4 * (F / P) / PI) * 1000
        add("physics", f"A hydraulic piston must produce {F / 1000:g} kN at an oil pressure of {P / 1e6:g} MPa. Find the "
            f"piston diameter, then model it as a solid cylinder of that diameter and {L} mm long.", d, cyl(d, L))
    # pendulum
    T, = (2.0,)
    L = 9.81 * T ** 2 / (4 * PI ** 2) * 1000
    add("physics", f"A simple pendulum must have a period of {T:g} s where g = 9.81 m/s^2. Find its length, then model "
        f"the pendulum rod as a solid cylinder 8 mm in diameter with that length.", L, cyl(8, L))
    return out


def round3():
    """40 problems for FUSE3_RULE (coder-computed calculation step), written 2026-11-08 night before any answer."""
    out = []
    n = [0]

    def add(pack, task, dim, ref):
        n[0] += 1
        out.append({"id": f"f3-{n[0]:02d}", "pack": pack, "task": task, "dim_mm": dim, "reference": ref})

    def box(x, y, z, holes=(), d=0):
        r = f"cq.Workplane('XY').box({x}, {y}, {z})"
        if holes:
            r += f".faces('>Z').workplane().pushPoints({list(holes)}).hole({d})"
        return "result = " + r

    def cyl(d, h, hole=0):
        r = f"cq.Workplane('XY').circle({d / 2}).extrude({h})"
        if hole:
            r += f".faces('>Z').workplane().hole({hole})"
        return "result = " + r

    def tube(od, idia, h):
        return f"result = cq.Workplane('XY').circle({od / 2}).circle({idia / 2}).extrude({h})"

    # Hooke: L = delta E A / F, rod of given diameter
    for dl, F, d, E in ((0.5, 10000, 10, 200e9), (0.3, 5000, 8, 70e9), (1.0, 20000, 12, 110e9)):
        A = math.pi * (d / 2000) ** 2
        L = dl / 1000 * E * A / F * 1000
        add("physics", f"A rod {d} mm in diameter (Young's modulus {E / 1e9:g} GPa) stretches by {dl:g} mm under a "
            f"{F / 1000:g} kN tensile load. Find its length, then model the rod as a solid cylinder of that "
            f"diameter and length.", L, cyl(d, L))
    # stopping distance: d = v^2 / (2a), a test track plate that long
    for v, a in ((20, 8), (15, 5), (30, 6)):
        dist = v ** 2 / (2 * a) * 1000 / 100  # 1:100 scale model
        add("physics", f"A car braking from {v} m/s decelerates at {a} m/s^2. Find its stopping distance, then model "
            f"a 1:100 scale test strip as a plate that long (the scaled length), 50 mm wide and 3 mm thick.",
            dist, box(dist, 50, 3))
    # heater wire length: R = V^2 / P, L = R A / rho
    for V, P, d, rho in ((230, 1000, 0.5, 1.1e-6), (120, 600, 0.4, 1.1e-6), (24, 50, 0.3, 4.9e-7)):
        R = V ** 2 / P
        L = R * math.pi * (d / 2000) ** 2 / rho * 1000
        add("electrical", f"A heater runs at {P} W from a {V} V supply and is made of wire {d:g} mm in diameter with "
            f"resistivity {rho:g} ohm m. Find the wire length, then model a straight 2 mm diameter rod with that "
            f"length as a stand-in for the wire.", L, cyl(2, L))
    # fin area: Q = h A dT, square fin
    for Q, h, dT in ((20, 25, 40), (50, 10, 60), (5, 15, 25)):
        side = math.sqrt(Q / (h * dT)) * 1000
        add("physics", f"A square cooling fin must shed {Q} W by convection with a heat transfer coefficient of {h} "
            f"W/(m^2 K) and a {dT} K temperature difference (count one face only). Find the side of the square, then "
            f"model the fin as a square plate with that side, 2 mm thick.", side, box(side, side, 2))
    # pipe bore from flow: A = Q / v, tube 5 mm wall
    for Qf, v in ((0.002, 1.5), (0.0005, 1.0), (0.01, 2.5)):
        d = math.sqrt(4 * Qf / v / math.pi) * 1000
        add("physics", f"Water must flow at {Qf * 1000:g} L/s through a pipe at a mean speed of {v:g} m/s. Find the "
            f"pipe's inside diameter, then model 200 mm of the pipe as a tube with that inside diameter and a 5 mm "
            f"wall.", d, tube(d + 10, d, 200))
    # thin-walled vessel: t = p D / (2 sigma), tube
    for p_, D, sig in ((2e6, 200, 100e6), (5e6, 120, 150e6), (1e6, 400, 80e6)):
        t = p_ * D / (2 * sig)
        add("physics", f"A thin-walled cylindrical pressure vessel with a {D} mm inside diameter holds {p_ / 1e6:g} MPa, "
            f"and the hoop stress may not exceed {sig / 1e6:g} MPa. Find the minimum wall thickness, then model a "
            f"100 mm long section of the vessel as a tube with that inside diameter and wall thickness.",
            t, tube(D + 2 * t, D, 100))
    # centripetal: r = v^2 / a, disc of that diameter... at 1:10
    for v, a in ((10, 50), (6, 30), (15, 100)):
        r = v ** 2 / a * 1000 / 10
        add("physics", f"An object moves in a circle at {v} m/s with a centripetal acceleration of {a} m/s^2. Find the "
            f"radius, then model a 1:10 scale turntable as a disc 8 mm thick with that scaled radius.",
            r, cyl(2 * r, 8))
    # nozzle exit: A = mdot / (rho v), disc of that diameter with 6 mm center hole
    for mdot, rho, v in ((2.0, 0.5, 2000), (0.5, 0.8, 1500), (5.0, 0.3, 2500)):
        d = math.sqrt(4 * mdot / (rho * v) / math.pi) * 1000
        add("aerospace", f"A rocket nozzle exhausts {mdot:g} kg/s of gas of density {rho:g} kg/m^3 at {v} m/s. Find the "
            f"exit diameter, then model a cover plate as a disc of that diameter, 4 mm thick, with a 6 mm hole at "
            f"its center.", d, cyl(d, 4, 6))
    # wing span from aspect ratio: b = sqrt(AR S), plate span x mean chord x 10, at 1:20
    for AR, S in ((8, 12.5), (6, 6.0), (10, 16.9)):
        b = math.sqrt(AR * S) * 1000 / 20
        c = S / math.sqrt(AR * S) * 1000 / 20
        add("aerospace", f"A wing has an area of {S:g} m^2 and an aspect ratio of {AR}. Find its span, then model a 1:20 "
            f"scale model of the wing as a flat plate as long as the scaled span, as wide as the scaled mean chord "
            f"(area / span, scaled), and 10 mm thick.", b, box(b, c, 10))
    # nichrome resistor length: L = R A / rho with R = V / I
    for V, I, d in ((12, 2, 0.5), (5, 0.5, 0.25), (24, 3, 0.8)):
        L = (V / I) * math.pi * (d / 2000) ** 2 / 1.1e-6 * 1000
        add("electrical", f"A resistor made of nichrome wire (resistivity 1.1e-6 ohm m), {d:g} mm in diameter, must "
            f"draw {I:g} A from {V} V. Find the wire length, then model a straight rod of that length, 3 mm in "
            f"diameter, as a stand-in.", L, cyl(3, L))
    # capacitor spacer: gap = eps0 er A / C
    for C, side, er in ((100e-12, 50, 4.0), (1e-9, 100, 3.0), (47e-12, 30, 2.5)):
        gap = 8.854e-12 * er * (side / 1000) ** 2 / C * 1000
        add("electrical", f"A parallel-plate capacitor has square plates {side} mm on a side and a dielectric of "
            f"relative permittivity {er:g}, and must have a capacitance of {C * 1e12:g} pF (vacuum permittivity "
            f"8.854e-12 F/m). Find the plate gap, then model the dielectric spacer as a square plate {side} mm on a "
            f"side with that thickness.", gap, box(side, side, gap))
    # projectile range at 45 deg: R = v^2 / g, rail at 1:100
    for v in (20, 35, 12):
        R = v ** 2 / 9.81 * 1000 / 100
        add("physics", f"A ball is launched at {v} m/s at 45 degrees over level ground (g = 9.81 m/s^2). Find its range, "
            f"then model a 1:100 scale rail as a bar as long as the scaled range, 10 mm wide and 10 mm tall.",
            R, box(R, 10, 10))
    # float: cylinder submerged depth h = m / (rho_w A)
    for m, D in ((3.0, 150), (0.8, 80), (10.0, 300)):
        h = m / (1000 * math.pi * (D / 2000) ** 2) * 1000
        add("physics", f"A cylindrical float {D} mm in diameter carries {m:g} kg in fresh water (1000 kg/m^3), ignoring "
            f"its own weight. Find how deep it sinks, then model the submerged part as a solid cylinder of that "
            f"diameter and depth.", h, cyl(D, h))
    # one more: Ohm bus bar width
    L = 1.68e-8 * 0.5 / 0.2e-3 * 1e6 / 3
    add("electrical", "A copper strip (resistivity 1.68e-8 ohm m) 500 mm long and 3 mm thick must have a resistance of "
        "0.2 milliohm. Find its width, then model the strip, 500 mm long, that wide and 3 mm thick.", L, box(500, L, 3))
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
    build(judged(), "judged.jsonl")
    build(round3(), "round3.jsonl")


if __name__ == "__main__":
    main()
