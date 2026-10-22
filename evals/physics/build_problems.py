"""Source of truth for the physics/mechanical eval set.

Answers are computed here, never hand-typed, and every constant a problem needs
is stated in the problem (lookups excepted). Written on 2026-10-22, before the
physics pack's level cues, routing claims or policies existed. Run this to
regenerate problems.jsonl:

    .venv/bin/python evals/physics/build_problems.py

Levels, as in the other numeric sets (plm/numeric/levels.py):
    calm      a lookup or a single formula with two inputs
    alert     a single formula with a few more inputs, or one conversion on top
    intensive an intermediate result must be computed and reused

Answers are magnitudes (speeds, not signed velocities): the shared checks treat a
non-positive speed, energy or force as a failed check unless the question asks for a sign.
"""

import json
import math
from pathlib import Path

PI = math.pi
G = 9.81
G0 = 9.80665
GT = "Taking g = 9.81 m/s²"

# (id, level, topic, question, answer, unit, rel_tol, solution)
PROBLEMS = [
    # ---------------- calm ----------------
    ("ph-c01", "calm", "kinematics", "A car travels 150 m in 6 s at constant speed. What is its speed, in meters per second?",
     150 / 6, "m/s", 0.01, "v = d / t"),
    ("ph-c02", "calm", "dynamics", "What net force accelerates a 1200 kg car at 2.5 m/s², in newtons?",
     1200 * 2.5, "N", 0.01, "F = m a"),
    ("ph-c03", "calm", "energy", "What is the kinetic energy of a 0.145 kg baseball moving at 40 m/s, in joules?",
     0.5 * 0.145 * 40 ** 2, "J", 0.01, "KE = m v^2 / 2"),
    ("ph-c04", "calm", "energy", "A motor does 18000 J of work in 30 s. What is its power output, in watts?",
     18000 / 30, "W", 0.01, "P = W / t"),
    ("ph-c05", "calm", "momentum", "What is the momentum of a 70 kg runner moving at 8 m/s, in kilogram meters per second?",
     70 * 8, "kg*m/s", 0.01, "p = m v"),
    ("ph-c06", "calm", "fluids", "A force of 500 N acts on a piston with an area of 0.02 square meters. What pressure does it exert, in pascals?",
     500 / 0.02, "Pa", 0.01, "p = F / A"),
    ("ph-c07", "calm", "materials", "A material has a density of 7800 kg/m³. What is the mass of 0.5 cubic meters of it, in kilograms?",
     7800 * 0.5, "kg", 0.01, "m = rho V"),
    ("ph-c08", "calm", "materials", "A steel rod carrying a load of 20 kN has a cross-sectional area of 0.0004 square meters. What is the stress in it, in megapascals?",
     20e3 / 0.0004 / 1e6, "MPa", 0.01, "sigma = F / A"),
    ("ph-c09", "calm", "oscillations", "A spring with a stiffness of 400 N/m is stretched by 0.05 m. What force does it exert, in newtons?",
     400 * 0.05, "N", 0.01, "F = k x"),
    ("ph-c10", "calm", "rotation", "A wrench applies 50 N at 0.3 m from a bolt, perpendicular to the handle. What torque does it apply, in newton-meters?",
     50 * 0.3, "N*m", 0.01, "T = F r"),
    ("ph-c11", "calm", "waves", "A wave has a frequency of 50 Hz and a wavelength of 6.8 m. What is its speed, in meters per second?",
     50 * 6.8, "m/s", 0.01, "v = f lambda"),
    ("ph-c12", "calm", "lookup", "What is the standard acceleration due to gravity at Earth's surface, in meters per second squared?",
     G0, "m/s^2", 0.01, "g0 = 9.80665 m/s^2"),
    ("ph-c13", "calm", "lookup", "What is the boiling point of water at standard atmospheric pressure, in kelvin?",
     373.15, "K", 0.01, "100 degC = 373.15 K"),
    ("ph-c14", "calm", "dynamics", f"What is the weight of a 15 kg box? {GT}. Give it in newtons.",
     15 * G, "N", 0.01, "W = m g"),
    ("ph-c15", "calm", "rotation", "A wheel turns at 30 radians per second. How many revolutions per minute is that?",
     30 * 60 / (2 * PI), "rpm", 0.01, "rpm = omega 60 / (2 pi)"),
    # ---------------- alert ----------------
    ("ph-a01", "alert", "kinematics", "A car accelerates uniformly from 10 m/s to 30 m/s in 8 s. How far does it travel in that time, in meters?",
     (10 + 30) / 2 * 8, "m", 0.01, "d = (u + v)/2 t"),
    ("ph-a02", "alert", "kinematics", f"A stone is dropped from rest and falls for 3 s. {GT} and ignoring air resistance, how far does it fall, in meters?",
     0.5 * G * 3 ** 2, "m", 0.01, "d = g t^2 / 2"),
    ("ph-a03", "alert", "dynamics", f"A 40 kg crate slides across a floor with a coefficient of kinetic friction of 0.3. {GT}, what is the friction force on it, in newtons?",
     0.3 * 40 * G, "N", 0.01, "f = mu m g"),
    ("ph-a04", "alert", "dynamics", f"A 10 kg block rests on a frictionless ramp inclined at 30 degrees. {GT}, what is the component of its weight along the ramp, in newtons?",
     10 * G * math.sin(math.radians(30)), "N", 0.01, "F = m g sin(theta)"),
    ("ph-a05", "alert", "energy", f"A 60 kg climber goes up 450 m. {GT}, how much potential energy is gained, in kilojoules?",
     60 * G * 450 / 1000, "kJ", 0.01, "PE = m g h"),
    ("ph-a06", "alert", "energy", f"A pump lifts 3000 kg of water through a height of 12 m in 2 minutes. {GT}, what is its useful power output, in kilowatts?",
     3000 * G * 12 / 120 / 1000, "kW", 0.01, "P = m g h / t, t = 120 s"),
    ("ph-a07", "alert", "circular-motion", "A 1500 kg car rounds a curve of radius 50 m at 20 m/s. What centripetal force does that take, in kilonewtons?",
     1500 * 20 ** 2 / 50 / 1000, "kN", 0.01, "F = m v^2 / r"),
    ("ph-a08", "alert", "oscillations", "A spring with a stiffness of 2000 N/m is compressed by 8 cm. How much elastic energy does it store, in joules?",
     0.5 * 2000 * 0.08 ** 2, "J", 0.01, "E = k x^2 / 2, x = 0.08 m"),
    ("ph-a09", "alert", "oscillations", f"What is the period of a simple pendulum 2 m long? {GT}. Give it in seconds.",
     2 * PI * math.sqrt(2 / G), "s", 0.01, "T = 2 pi sqrt(L / g)"),
    ("ph-a10", "alert", "oscillations", "A 0.5 kg mass hangs on a spring with a stiffness of 200 N/m and oscillates freely. What is its frequency, in hertz?",
     math.sqrt(200 / 0.5) / (2 * PI), "Hz", 0.01, "f = sqrt(k / m) / (2 pi)"),
    ("ph-a11", "alert", "fluids", f"What is the gauge pressure 25 m below the surface of fresh water with a density of 1000 kg/m³? {GT}. Give it in kilopascals.",
     1000 * G * 25 / 1000, "kPa", 0.01, "p = rho g h"),
    ("ph-a12", "alert", "fluids", f"A block with a volume of 0.002 cubic meters is fully submerged in seawater of density 1025 kg/m³. {GT}, what buoyant force acts on it, in newtons?",
     1025 * G * 0.002, "N", 0.01, "F = rho g V"),
    ("ph-a13", "alert", "fluids", "Water flows at 3 m/s through a pipe with an inner diameter of 0.1 m. What is the volume flow rate, in liters per second?",
     PI * 0.05 ** 2 * 3 * 1000, "L/s", 0.01, "Q = pi (d/2)^2 v"),
    ("ph-a14", "alert", "heat", "How much heat raises the temperature of 2 kg of water by 30 K, with a specific heat of 4186 J/(kg·K), in kilojoules?",
     2 * 4186 * 30 / 1000, "kJ", 0.01, "Q = m c dT"),
    ("ph-a15", "alert", "heat", "How much heat boils away 0.3 kg of water already at 100 °C, with a latent heat of vaporization of 2260 kJ/kg, in megajoules?",
     0.3 * 2260 / 1000, "MJ", 0.01, "Q = m L"),
    ("ph-a16", "alert", "gases", "What pressure do 2 moles of an ideal gas exert in a 0.05 cubic meter container at 300 K, with R = 8.314 J/(mol·K), in kilopascals?",
     2 * 8.314 * 300 / 0.05 / 1000, "kPa", 0.01, "p = n R T / V"),
    ("ph-a17", "alert", "heat", "A 20 m steel rail warms by 35 K. With a linear expansion coefficient of 12e-6 per kelvin, how much longer does it get, in millimeters?",
     20 * 12e-6 * 35 * 1000, "mm", 0.01, "dL = alpha L dT"),
    ("ph-a18", "alert", "materials", "A 2 m aluminium rod with a cross-section of 0.0001 square meters carries a tensile load of 7 kN. With a Young's modulus of 70 GPa, how much does it stretch, in millimeters?",
     7e3 * 2 / (1e-4 * 70e9) * 1000, "mm", 0.01, "dL = F L / (A E)"),
    ("ph-a19", "alert", "machines", "A shaft turning at 1500 revolutions per minute transmits a torque of 200 N·m. What power does it transmit, in kilowatts?",
     200 * 1500 * 2 * PI / 60 / 1000, "kW", 0.01, "P = T omega, omega = rpm 2 pi / 60"),
    ("ph-a20", "alert", "machines", "A machine with an efficiency of 80% takes in 5 kW. How much useful work does it do in 10 minutes, in megajoules?",
     0.8 * 5e3 * 600 / 1e6, "MJ", 0.01, "W = eta P t, t = 600 s"),
    # ---------------- intensive ----------------
    ("ph-i01", "intensive", "kinematics", f"A ball is kicked at 20 m/s at 35 degrees above level ground. {GT} and ignoring air resistance, how far away does it land, in meters?",
     20 ** 2 * math.sin(math.radians(70)) / G, "m", 0.01, "flight time 2 v sin(theta)/g, range = v cos(theta) t = v^2 sin(2 theta)/g"),
    ("ph-i02", "intensive", "kinematics", f"A stone is thrown horizontally at 12 m/s from the top of a cliff 45 m high. {GT} and ignoring air resistance, how far from the base of the cliff does it land, in meters?",
     12 * math.sqrt(2 * 45 / G), "m", 0.01, "t = sqrt(2 h / g), x = v t"),
    ("ph-i03", "intensive", "dynamics", f"A 2 kg block slides from rest down a 5 m long ramp inclined at 30 degrees, with a coefficient of kinetic friction of 0.2. {GT}, what is its speed at the bottom, in meters per second?",
     math.sqrt(2 * G * (math.sin(math.radians(30)) - 0.2 * math.cos(math.radians(30))) * 5), "m/s", 0.01,
     "a = g (sin - mu cos), v = sqrt(2 a L)"),
    ("ph-i04", "intensive", "momentum", "A 1200 kg car moving at 15 m/s hits a stationary 800 kg car and they move off together. How much kinetic energy is lost in the collision, in kilojoules?",
     (0.5 * 1200 * 15 ** 2 - 0.5 * 2000 * (1200 * 15 / 2000) ** 2) / 1000, "kJ", 0.01,
     "v = m1 u / (m1 + m2), loss = KE before - KE after"),
    ("ph-i05", "intensive", "dynamics", f"A car moving at 25 m/s brakes hard, with a coefficient of friction of 0.7 between tyres and road. {GT}, how far does it travel before stopping, in meters?",
     25 ** 2 / (2 * 0.7 * G), "m", 0.01, "a = mu g, d = v^2 / (2 a)"),
    ("ph-i06", "intensive", "circular-motion", f"A car rounds an unbanked curve of radius 80 m on a road with a coefficient of static friction of 0.6. {GT}, what is the highest speed it can take the curve at, in kilometers per hour?",
     math.sqrt(0.6 * G * 80) * 3.6, "km/h", 0.01, "mu m g = m v^2 / r, v = sqrt(mu g r), then m/s -> km/h"),
    ("ph-i07", "intensive", "rotation", "A flywheel shaped as a solid disc of mass 50 kg and radius 0.4 m spins at 3000 revolutions per minute. How much kinetic energy does it store, in kilojoules?",
     0.5 * (0.5 * 50 * 0.4 ** 2) * (3000 * 2 * PI / 60) ** 2 / 1000, "kJ", 0.01, "I = m r^2 / 2, omega = rpm 2 pi / 60, E = I omega^2 / 2"),
    ("ph-i08", "intensive", "rotation", f"A solid sphere rolls without slipping from rest down a slope, dropping 1.5 m in height. {GT}, what is its speed at the bottom, in meters per second?",
     math.sqrt(10 / 7 * G * 1.5), "m/s", 0.01, "m g h = (1/2) m v^2 + (1/2)(2/5) m v^2, v = sqrt(10 g h / 7)"),
    ("ph-i09", "intensive", "fluids", "Water flows through a horizontal pipe that narrows from a diameter of 0.2 m to 0.1 m. In the wide section the speed is 2 m/s and the pressure is 200 kPa. With a density of 1000 kg/m³, what is the pressure in the narrow section, in kilopascals?",
     (200e3 - 0.5 * 1000 * ((2 * (0.2 / 0.1) ** 2) ** 2 - 2 ** 2)) / 1000, "kPa", 0.01,
     "continuity v2 = v1 (d1/d2)^2 = 8 m/s, Bernoulli p2 = p1 - rho (v2^2 - v1^2) / 2"),
    ("ph-i10", "intensive", "fluids", f"Water drains from a large open tank through a hole 3 m below the surface. The hole has an area of 0.002 square meters. {GT} and ignoring losses, what is the outflow rate, in liters per second?",
     math.sqrt(2 * G * 3) * 0.002 * 1000, "L/s", 0.01, "v = sqrt(2 g h), Q = A v"),
    ("ph-i11", "intensive", "heat", "0.3 kg of water at 90 °C is mixed with 0.5 kg of water at 20 °C in an insulated container. With no heat lost, what is the final temperature, in degrees Celsius?",
     (0.3 * 90 + 0.5 * 20) / 0.8, "degC", 0.01, "heat lost = heat gained, T = (m1 T1 + m2 T2) / (m1 + m2)"),
    ("ph-i12", "intensive", "heat", "How much heat turns 0.2 kg of ice at 0 °C into water at 40 °C, with a latent heat of fusion of 334 kJ/kg and a specific heat of water of 4186 J/(kg·K), in kilojoules?",
     0.2 * 334 + 0.2 * 4186 * 40 / 1000, "kJ", 0.01, "melt m L, then warm m c dT, add"),
    ("ph-i13", "intensive", "gases", "A rigid 0.01 cubic meter cylinder holds air at 300 kPa and 300 K. It is heated at constant volume to 450 K. With R = 287 J/(kg·K) and cv = 718 J/(kg·K), how much heat does that take, in kilojoules?",
     300e3 * 0.01 / (287 * 300) * 718 * 150 / 1000, "kJ", 0.01, "m = p V / (R T), Q = m cv dT"),
    ("ph-i14", "intensive", "heat", "A brick wall 4 m by 2.5 m and 0.2 m thick has a thermal conductivity of 0.7 W/(m·K). With 20 °C inside and -5 °C outside, how much heat flows through it in one hour, in megajoules?",
     0.7 * 10 * 25 / 0.2 * 3600 / 1e6, "MJ", 0.01, "A = 10 m^2, P = k A dT / d = 875 W, Q = P t"),
    ("ph-i15", "intensive", "materials", "A 3 m steel cable with a diameter of 10 mm holds a 2000 kg load. With a Young's modulus of 200 GPa and g = 9.81 m/s², how much does it stretch, in millimeters?",
     2000 * G * 3 / (PI * 0.005 ** 2 * 200e9) * 1000, "mm", 0.01, "A = pi (d/2)^2, F = m g, dL = F L / (A E)"),
]


def main():
    ids = [p[0] for p in PROBLEMS]
    assert len(ids) == len(set(ids)), "duplicate problem id"
    out = Path(__file__).with_name("problems.jsonl")
    with out.open("w") as f:
        for pid, level, topic, question, answer, unit, tol, solution in PROBLEMS:
            f.write(json.dumps({
                "id": pid, "domain": "physics", "level": level, "topic": topic,
                "question": question, "answer": answer, "unit": unit,
                "rel_tol": tol, "solution": solution,
            }) + "\n")
    counts = {lvl: sum(p[1] == lvl for p in PROBLEMS) for lvl in ("calm", "alert", "intensive")}
    print(f"wrote {len(PROBLEMS)} problems to {out} {counts}")


if __name__ == "__main__":
    main()
