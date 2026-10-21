"""Source of truth for the aerospace eval set.

Answers are computed here, never hand-typed, and every constant a problem needs
is stated in the problem (lookups excepted), so the key doesn't depend on which
value of GM or R a model happens to remember. Run this to regenerate
problems.jsonl:

    .venv/bin/python evals/aerospace/build_problems.py

Levels, as in the electrical set (plm/numeric/levels.py):
    calm      a lookup or a single formula with two inputs
    alert     a single formula with a few more inputs, or one conversion on top
    intensive an intermediate result must be computed and reused
"""

import json
import math
from pathlib import Path

PI = math.pi
G0 = 9.80665
GM = 3.986e14          # Earth, m^3/s^2
RE = 6371e3            # Earth radius, m


def circ(r):
    return math.sqrt(GM / r)


def hohmann(r1, r2):
    a = (r1 + r2) / 2
    vp, va = math.sqrt(GM * (2 / r1 - 1 / a)), math.sqrt(GM * (2 / r2 - 1 / a))
    return (vp - circ(r1)) + (circ(r2) - va)


EARTH = "Use GM = 3.986e14 m³/s² and an Earth radius of 6371 km."

# (id, level, topic, question, answer, unit, rel_tol, solution)
PROBLEMS = [
    # ---------------- calm ----------------
    ("ae-c01", "calm", "aerodynamics", "An aircraft flies at 255 m/s where the speed of sound is 340 m/s. What is its Mach number (unitless)?",
     255 / 340, "", 0.01, "M = v / a"),
    ("ae-c02", "calm", "flight-mechanics", "What is the weight of a 1200 kg aircraft at a gravitational acceleration of 9.81 m/s², in newtons?",
     1200 * 9.81, "N", 0.01, "W = m g"),
    ("ae-c03", "calm", "units", "An aircraft flies at 250 knots, where 1 knot is 0.5144 m/s. What is its airspeed in meters per second?",
     250 * 0.5144, "m/s", 0.01, "v = 250 * 0.5144"),
    ("ae-c04", "calm", "propulsion", "A rocket engine has a specific impulse of 300 s. What is its effective exhaust velocity in meters per second, taking g0 = 9.80665 m/s²?",
     300 * G0, "m/s", 0.01, "ve = Isp g0"),
    ("ae-c05", "calm", "atmosphere", "What is the air density at sea level in the International Standard Atmosphere, in kilograms per cubic meter?",
     1.225, "kg/m^3", 0.01, "ISA sea-level density"),
    ("ae-c06", "calm", "constants", "What is standard gravitational acceleration g0, in meters per second squared?",
     G0, "m/s^2", 0.005, "Defined value 9.80665"),
    ("ae-c07", "calm", "atmosphere", "What is the speed of sound at sea level in the International Standard Atmosphere, in meters per second?",
     math.sqrt(1.4 * 287.05 * 288.15), "m/s", 0.01, "ISA sea level: a = sqrt(gamma R T) = 340.3 m/s"),
    ("ae-c08", "calm", "flight-mechanics", "An aircraft weighing 50000 N has a wing area of 25 square meters. What is its wing loading, in pascals?",
     50000 / 25, "Pa", 0.01, "W / S (N/m^2 = Pa)"),
    ("ae-c09", "calm", "aerodynamics", "A wing has a span of 30 m and an area of 90 square meters. What is its aspect ratio (unitless)?",
     30 ** 2 / 90, "", 0.01, "AR = b^2 / S"),
    ("ae-c10", "calm", "propulsion", "A rocket engine expels 250 kg/s of propellant at an exhaust velocity of 2800 m/s. Ignoring pressure thrust, what is its thrust in kilonewtons?",
     250 * 2800 / 1000, "kN", 0.01, "F = mdot ve"),
    ("ae-c11", "calm", "orbits", "What is the escape velocity from Earth's surface, in kilometers per second?",
     math.sqrt(2 * GM / RE) / 1000, "km/s", 0.01, "v = sqrt(2 GM / R) = 11.19 km/s"),
    ("ae-c12", "calm", "flight-mechanics", "An aircraft weighing 60 kN has 300 kW of excess power. What is its rate of climb, in meters per second?",
     300e3 / 60e3, "m/s", 0.01, "ROC = P_excess / W"),
    ("ae-c13", "calm", "orbits", "A 1000 kg satellite moves at 7500 m/s. What is its kinetic energy, in joules?",
     0.5 * 1000 * 7500 ** 2, "J", 0.01, "E = m v^2 / 2"),
    ("ae-c14", "calm", "flight-mechanics", "What is the load factor of an aircraft in a level, coordinated turn at a 60 degree bank angle (unitless)?",
     1 / math.cos(math.radians(60)), "", 0.01, "n = 1 / cos(bank)"),
    ("ae-c15", "calm", "aerodynamics", "Air with a density of 1.225 kg/m³ flows at 50 m/s. What is its dynamic pressure, in pascals?",
     0.5 * 1.225 * 50 ** 2, "Pa", 0.01, "q = rho v^2 / 2"),

    # ---------------- alert ----------------
    ("ae-a01", "alert", "aerodynamics", "A light aircraft with a wing area of 16.2 square meters flies at 60 m/s in air with a density of 1.225 kg/m³, at a lift coefficient of 0.5. What lift does the wing produce, in newtons?",
     0.5 * 1.225 * 60 ** 2 * 16.2 * 0.5, "N", 0.01, "L = q S CL"),
    ("ae-a02", "alert", "aerodynamics", "An airliner with a wing area of 120 square meters flies at 230 m/s where the air density is 0.4135 kg/m³. Its drag coefficient is 0.03. What is its drag, in kilonewtons?",
     0.5 * 0.4135 * 230 ** 2 * 120 * 0.03 / 1000, "kN", 0.01, "D = q S CD"),
    ("ae-a03", "alert", "flight-mechanics", "An aircraft weighing 10000 N has a wing area of 15 square meters and a maximum lift coefficient of 1.6. At sea level, where the air density is 1.225 kg/m³, what is its stall speed in meters per second?",
     math.sqrt(2 * 10000 / (1.225 * 15 * 1.6)), "m/s", 0.01, "v = sqrt(2 W / (rho S CLmax))"),
    ("ae-a04", "alert", "orbits", f"What is the speed of a satellite in a circular orbit 400 km above Earth's surface, in kilometers per second? {EARTH}",
     circ(RE + 400e3) / 1000, "km/s", 0.01, "v = sqrt(GM / (R + h))"),
    ("ae-a05", "alert", "orbits", "What is the escape velocity from the surface of Mars, in kilometers per second? Use GM = 4.283e13 m³/s² and a radius of 3389.5 km.",
     math.sqrt(2 * 4.283e13 / 3389.5e3) / 1000, "km/s", 0.01, "v = sqrt(2 GM / R)"),
    ("ae-a06", "alert", "propulsion", "A rocket with a specific impulse of 310 s has a liftoff mass of 500 tonnes and a burnout mass of 150 tonnes. Taking g0 = 9.80665 m/s², what is its ideal delta-v, in meters per second?",
     310 * G0 * math.log(500 / 150), "m/s", 0.01, "dv = Isp g0 ln(m0 / mf)"),
    ("ae-a07", "alert", "atmosphere", "In the International Standard Atmosphere the temperature is 288.15 K at sea level and falls by 6.5 K per kilometer in the troposphere. What is the temperature at 5 km altitude, in kelvin?",
     288.15 - 6.5 * 5, "K", 0.005, "T = 288.15 - 6.5 h"),
    ("ae-a08", "alert", "propulsion", "Air with a density of 1.2 kg/m³ flows at 100 m/s through a duct with a cross-section of 0.5 square meters. What is the mass flow rate, in kilograms per second?",
     1.2 * 100 * 0.5, "kg/s", 0.01, "mdot = rho v A"),
    ("ae-a09", "alert", "aerodynamics", "A wing with a chord of 1.5 m flies at 50 m/s in air with a density of 1.225 kg/m³ and a dynamic viscosity of 1.789e-5 Pa·s. What is the Reynolds number based on chord (unitless)?",
     1.225 * 50 * 1.5 / 1.789e-5, "", 0.01, "Re = rho v c / mu"),
    ("ae-a10", "alert", "flight-mechanics", "A glider with a lift-to-drag ratio of 15 glides in still air from an altitude of 2000 m. How far does it travel over the ground, in kilometers?",
     15 * 2000 / 1000, "km", 0.01, "d = (L/D) h"),
    ("ae-a11", "alert", "flight-mechanics", "An aircraft makes a level turn at 100 m/s with a bank angle of 30 degrees. Taking g = 9.81 m/s², what is the turn radius, in meters?",
     100 ** 2 / (9.81 * math.tan(math.radians(30))), "m", 0.01, "R = v^2 / (g tan(bank))"),
    ("ae-a12", "alert", "orbits", f"What is the period of a circular orbit 400 km above Earth's surface, in minutes? {EARTH}",
     2 * PI * math.sqrt((RE + 400e3) ** 3 / GM) / 60, "min", 0.01, "T = 2 pi sqrt(r^3 / GM)"),
    ("ae-a13", "alert", "propulsion", "Air at 288 K is compressed isentropically by a pressure ratio of 10. With a ratio of specific heats of 1.4, what is its temperature after compression, in kelvin?",
     288 * 10 ** (0.4 / 1.4), "K", 0.01, "T2 = T1 (p2/p1)^((gamma-1)/gamma)"),
    ("ae-a14", "alert", "atmosphere", "An aircraft flies at an equivalent airspeed of 100 m/s at an altitude where the air density is 0.6125 kg/m³. With a sea-level density of 1.225 kg/m³, what is its true airspeed, in meters per second?",
     100 / math.sqrt(0.6125 / 1.225), "m/s", 0.01, "TAS = EAS / sqrt(rho / rho0)"),
    ("ae-a15", "alert", "aerodynamics", "An aircraft flies at Mach 2 at 11 km altitude, where the static pressure is 22632 Pa. With a ratio of specific heats of 1.4, what is the dynamic pressure, in kilopascals?",
     0.5 * 1.4 * 22632 * 2 ** 2 / 1000, "kPa", 0.01, "q = gamma p M^2 / 2"),
    ("ae-a16", "alert", "atmosphere", "What is the speed of sound in air at 216.65 K, in meters per second? Take a ratio of specific heats of 1.4 and R = 287 J/(kg·K).",
     math.sqrt(1.4 * 287 * 216.65), "m/s", 0.01, "a = sqrt(gamma R T)"),
    ("ae-a17", "alert", "orbits", f"What is the gravitational acceleration at 420 km altitude, in meters per second squared? {EARTH}",
     GM / (RE + 420e3) ** 2, "m/s^2", 0.01, "g = GM / r^2"),
    ("ae-a18", "alert", "aerodynamics", "Air at Mach 2 and 300 K passes through a normal shock. With a ratio of specific heats of 1.4, what is the static temperature behind the shock, in kelvin?",
     300 * (2 * 1.4 * 4 - 0.4) * (0.4 * 4 + 2) / (2.4 ** 2 * 4), "K", 0.01,
     "T2/T1 = (2 g M^2 - (g-1)) ((g-1) M^2 + 2) / ((g+1)^2 M^2)"),
    ("ae-a19", "alert", "aerodynamics", "A pitot-static probe measures a total pressure of 102825 Pa and a static pressure of 101325 Pa in air with a density of 1.225 kg/m³. Treating the flow as incompressible, what is the airspeed, in meters per second?",
     math.sqrt(2 * (102825 - 101325) / 1.225), "m/s", 0.01, "v = sqrt(2 (p0 - p) / rho)"),
    ("ae-a20", "alert", "propulsion", "A propeller aircraft cruising at 80 m/s needs 400 kW of thrust power, and its propeller is 80% efficient. What shaft power must the engine deliver, in kilowatts?",
     400 / 0.8, "kW", 0.01, "P_shaft = P_thrust / efficiency"),

    # ---------------- intensive ----------------
    ("ae-i01", "intensive", "orbits", f"What total delta-v does a Hohmann transfer take from a circular orbit 300 km above Earth to a circular geostationary orbit of radius 42164 km, in kilometers per second? {EARTH}",
     hohmann(RE + 300e3, 42164e3) / 1000, "km/s", 0.01, "two burns: (vp - v1) + (v2 - va) on the transfer ellipse"),
    ("ae-i02", "intensive", "propulsion", "A two-stage rocket has a liftoff mass of 120 t. Stage 1 burns 90 t of propellant at a specific impulse of 280 s, then drops its 10 t of dry mass. Stage 2 then starts at 20 t and burns 15 t of propellant at a specific impulse of 340 s. Taking g0 = 9.80665 m/s², what is the total ideal delta-v, in meters per second?",
     280 * G0 * math.log(120 / 30) + 340 * G0 * math.log(20 / 5), "m/s", 0.01,
     "stage 1: 120 -> 30 t; stage 2: 20 -> 5 t; sum Isp g0 ln(m0/mf)"),
    ("ae-i03", "intensive", "flight-mechanics", "A jet cruises at 250 m/s with a lift-to-drag ratio of 17 and a thrust-specific fuel consumption of 0.6 per hour. Its weight falls from 1.3 to 1.0 times its landing weight during the cruise. Using the Breguet range equation, how far does it fly, in kilometers?",
     250 / (0.6 / 3600) * 17 * math.log(1.3) / 1000, "km", 0.01, "R = (V / c)(L/D) ln(Wi / Wf), c in 1/s"),
    ("ae-i04", "intensive", "aerodynamics", "An aircraft flies at 900 m/s where the air temperature is 216.65 K and the pressure is 22.6 kPa. With a ratio of specific heats of 1.4 and R = 287 J/(kg·K), what is the stagnation pressure, in kilopascals?",
     22.6 * (1 + 0.2 * (900 / math.sqrt(1.4 * 287 * 216.65)) ** 2) ** 3.5, "kPa", 0.01,
     "a = sqrt(g R T), M = v / a, p0 = p (1 + (g-1)/2 M^2)^(g/(g-1))"),
    ("ae-i05", "intensive", "propulsion", "A rocket nozzle expands gas from a chamber temperature of 3500 K to an exit pressure that is 1% of the chamber pressure. The gas has a ratio of specific heats of 1.2 and R = 355 J/(kg·K), and the mass flow is 100 kg/s. Ignoring pressure thrust, what thrust does it produce, in kilonewtons?",
     100 * math.sqrt(2 * 1.2 / 0.2 * 355 * 3500 * (1 - 0.01 ** (0.2 / 1.2))) / 1000, "kN", 0.01,
     "ve = sqrt(2g/(g-1) R T0 (1 - (pe/p0)^((g-1)/g))), F = mdot ve"),
    ("ae-i06", "intensive", "flight-mechanics", "An aircraft weighing 600 kN with a wing area of 360 square meters flies level at 240 m/s where the air density is 0.38 kg/m³. Its drag polar is CD = 0.02 + 0.045 CL². What power is needed to overcome drag, in megawatts?",
     (lambda q: q * 360 * (0.02 + 0.045 * (600e3 / (q * 360)) ** 2) * 240 / 1e6)(0.5 * 0.38 * 240 ** 2), "MW", 0.01,
     "CL = W/(qS), CD = 0.02 + 0.045 CL^2, D = q S CD, P = D V"),
    ("ae-i07", "intensive", "orbits", f"A satellite in a circular orbit takes 12 hours per revolution. What is its altitude above Earth's surface, in kilometers? {EARTH}",
     ((GM * (12 * 3600) ** 2 / (4 * PI ** 2)) ** (1 / 3) - RE) / 1000, "km", 0.01, "r = (GM T^2 / 4 pi^2)^(1/3), h = r - R"),
    ("ae-i08", "intensive", "orbits", f"An elliptical orbit has a perigee altitude of 300 km and an apogee altitude of 35786 km. What is the speed at perigee, in kilometers per second? {EARTH}",
     math.sqrt(GM * (2 / (RE + 300e3) - 2 / (2 * RE + 300e3 + 35786e3))) / 1000, "km/s", 0.01,
     "a = (rp + ra)/2, vp = sqrt(GM (2/rp - 1/a))"),
    ("ae-i09", "intensive", "propulsion", "A rocket launched straight up has an initial mass of 100 t and burns 60 t of propellant at 400 kg/s with an exhaust velocity of 3000 m/s. Including gravity losses at a constant 9.81 m/s² and ignoring drag, what is its speed at burnout, in meters per second?",
     3000 * math.log(100 / 40) - 9.81 * (60e3 / 400), "m/s", 0.01, "t = 60000/400 = 150 s, v = ve ln(m0/mf) - g t"),
    ("ae-i10", "intensive", "orbits", f"A spacecraft is in a circular orbit 300 km above Earth's surface. What delta-v does it need to reach escape velocity from that orbit with one prograde burn, in kilometers per second? {EARTH}",
     (math.sqrt(2) - 1) * circ(RE + 300e3) / 1000, "km/s", 0.01, "v_esc - v_circ at r = R + h"),
    ("ae-i11", "intensive", "flight-mechanics", "A glider has the drag polar CD = 0.025 + 0.04 CL². Flying at its best lift-to-drag ratio in still air, how far can it glide from an altitude of 3000 m, in kilometers?",
     3000 / (2 * math.sqrt(0.04 * 0.025)) / 1000, "km", 0.01, "(L/D)max = 1 / (2 sqrt(K CD0)), d = (L/D)max h"),
    ("ae-i12", "intensive", "propulsion", "A compressor takes in 50 kg/s of air at 288 K and raises its pressure by a factor of 12 with an isentropic efficiency of 85%. With a ratio of specific heats of 1.4 and cp = 1005 J/(kg·K), what power does it absorb, in megawatts?",
     50 * 1005 * (288 * 12 ** (0.4 / 1.4) - 288) / 0.85 / 1e6, "MW", 0.01,
     "T2s = T1 r^((g-1)/g), dT = (T2s - T1)/eta, P = mdot cp dT"),
    ("ae-i13", "intensive", "orbits", f"A satellite in a circular orbit 500 km above Earth's surface changes its inclination by 5 degrees in a single burn. What delta-v does that take, in kilometers per second? {EARTH}",
     2 * circ(RE + 500e3) * math.sin(math.radians(2.5)) / 1000, "km/s", 0.01, "v = sqrt(GM/r), dv = 2 v sin(di/2)"),
    ("ae-i14", "intensive", "propulsion", "A spacecraft with a dry mass of 2000 kg needs 1500 m/s of delta-v from an engine with a specific impulse of 320 s. Taking g0 = 9.80665 m/s², how much propellant does it need, in kilograms?",
     2000 * (math.exp(1500 / (320 * G0)) - 1), "kg", 0.01, "m0/mf = exp(dv / (Isp g0)), propellant = mf (m0/mf - 1)"),
    ("ae-i15", "intensive", "orbits", f"How many revolutions does a satellite in a circular orbit 400 km above Earth complete in one day of 86400 s (unitless)? {EARTH}",
     86400 / (2 * PI * math.sqrt((RE + 400e3) ** 3 / GM)), "", 0.01, "T = 2 pi sqrt(r^3/GM), n = 86400 / T"),
]


def main():
    ids = [p[0] for p in PROBLEMS]
    assert len(ids) == len(set(ids)), "duplicate problem id"
    out = Path(__file__).with_name("problems.jsonl")
    with out.open("w") as f:
        for pid, level, topic, question, answer, unit, tol, solution in PROBLEMS:
            f.write(json.dumps({
                "id": pid, "domain": "aerospace", "level": level, "topic": topic,
                "question": question, "answer": answer, "unit": unit,
                "rel_tol": tol, "solution": solution,
            }) + "\n")
    counts = {lvl: sum(p[1] == lvl for p in PROBLEMS) for lvl in ("calm", "alert", "intensive")}
    print(f"wrote {len(PROBLEMS)} problems to {out} {counts}")


if __name__ == "__main__":
    main()
