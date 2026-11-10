"""Follow-up conversations, set 3 (held out), for FOLLOWUP3_RULE (evals/followup/run.py --set 3).

    .venv/bin/python evals/followup/build3.py      # writes evals/followup/cases3.jsonl

Written 2026-11-10, before any model answered them, to judge variant C (rewrite first only when the follow-up asks
for a different quantity) against today's wording A. Sets 1 and 2 are seen. Same construction as set 2 (keys from
each anchor's formula, converted with pint), with new anchors. Each case carries its kind, for reporting only:
"value" (a changed input), "two" (two inputs changed), "unit" (same quantity, another unit), "quantity" (a different
quantity from the same setup).
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build2 import Anchor, fmt  # noqa: E402

G = 9.81


def cases():
    out = []

    def add(anc, kind, follow, unit=None, value=None, **changes):
        unit = anc.out_unit if unit is None else unit
        key = value if value is not None else anc.value(unit, **changes)
        out.append({"id": f"f3-{len(out) + 1:03d}", "pack": anc.pack, "kind": kind, "messages": [
            {"role": "user", "content": anc.text},
            {"role": "assistant", "content": f"{fmt(anc.value())} {anc.out_unit}".strip()},
            {"role": "user", "content": follow}], "answer": key, "unit": unit, "rel_tol": 0.02})

    # ---------------- electrical ----------------
    a = Anchor("electrical", "A 24 V supply feeds a 16 ohm load. What current flows, in amperes?",
               dict(V=24, R=16), lambda V, R: V / R, "A")
    add(a, "value", "now with an 8 ohm load", R=8)
    add(a, "quantity", "what power does the load take, in watts?", unit="W", value=24 ** 2 / 16)
    add(a, "unit", "and in milliamperes?", unit="mA")
    add(a, "two", "now 12 V into 4 ohm", V=12, R=4)
    add(a, "quantity", "how much charge passes in one minute, in coulombs?", unit="C", value=24 / 16 * 60)

    a = Anchor("electrical", "A 22 microfarad capacitor is charged to 15 V. What charge does it hold, in microcoulombs?",
               dict(C=22e-6, V=15), lambda C, V: C * V, "C", "uC")
    add(a, "value", "now charge it to 40 V", V=40)
    add(a, "quantity", "how much energy does it store, in millijoules?", unit="mJ", value=0.5 * 22e-6 * 15 ** 2 * 1000)
    add(a, "value", "same with a 100 microfarad capacitor", C=100e-6)
    add(a, "unit", "and in coulombs?", unit="C")

    a = Anchor("electrical", "A 1.5 kW kettle runs on 240 V. What is its heating element's resistance, in ohms?",
               dict(P=1500, V=240), lambda P, V: V ** 2 / P, "ohm")
    add(a, "value", "now a 3 kW kettle", P=3000)
    add(a, "value", "what if the supply is 120 V?", V=120)
    add(a, "quantity", "what current does it draw, in amperes?", unit="A", value=1500 / 240)
    add(a, "quantity", "how much energy does it use in 4 minutes, in kilojoules?", unit="kJ", value=1500 * 240 / 1000)

    a = Anchor("electrical", "An RL circuit has L = 200 mH and R = 50 ohm. What is its time constant, in milliseconds?",
               dict(L=0.2, R=50), lambda L, R: L / R, "s", "ms")
    add(a, "value", "now with R = 10 ohm", R=10)
    add(a, "value", "what if L doubles?", L=0.4)
    add(a, "unit", "and in seconds?", unit="s")
    add(a, "quantity", "what is the inductive reactance at 50 Hz, in ohms?", unit="ohm", value=2 * math.pi * 50 * 0.2)

    a = Anchor("electrical", "A 5 V supply drives an LED that drops 2 V at 20 mA through a series resistor. What resistor "
               "value is needed, in ohms?", dict(Vs=5, Vf=2, I=0.020), lambda Vs, Vf, I: (Vs - Vf) / I, "ohm")
    add(a, "value", "now from a 9 V supply", Vs=9)
    add(a, "value", "what if the LED needs 10 mA?", I=0.010)
    add(a, "quantity", "how much power does the resistor dissipate, in milliwatts?", unit="mW", value=3 * 0.020 * 1000)
    add(a, "two", "now a 3.3 V supply with a 1.8 V LED", Vs=3.3, Vf=1.8)
    add(a, "unit", "and in kilohms?", unit="kiloohm")

    a = Anchor("electrical", "A 400 V three-phase motor draws 30 A per line at a power factor of 0.9. What real power does "
               "it take, in kilowatts?", dict(V=400, I=30, pf=0.9), lambda V, I, pf: math.sqrt(3) * V * I * pf, "W", "kW")
    add(a, "value", "now at 45 A", I=45)
    add(a, "value", "what if the power factor is 0.75?", pf=0.75)
    add(a, "quantity", "what is the apparent power, in kVA?", unit="kVA", value=math.sqrt(3) * 400 * 30 / 1000)
    add(a, "unit", "and in watts?", unit="W")

    a = Anchor("electrical", "A 2000 mAh battery powers a device drawing 150 mA. How long does it last, in hours?",
               dict(Q=2.0, I=0.150), lambda Q, I: Q / I, "h")
    add(a, "value", "now with a 5000 mAh battery", Q=5.0)
    add(a, "value", "what if the device draws 400 mA?", I=0.400)
    add(a, "unit", "and in minutes?", unit="min")
    add(a, "quantity", "if the battery is 3.7 V, how much energy does it hold, in watt-hours?", unit="Wh", value=2.0 * 3.7)

    # ---------------- physics ----------------
    a = Anchor("physics", "A car accelerates from rest at 3 m/s^2 for 8 s. What speed does it reach, in meters per second?",
               dict(a=3, t=8), lambda a, t: a * t, "m/s")
    add(a, "value", "now for 12 s", t=12)
    add(a, "value", "what if it accelerates at 1.5 m/s^2?", a=1.5)
    add(a, "quantity", "how far does it travel in that time, in meters?", unit="m", value=0.5 * 3 * 8 ** 2)
    add(a, "unit", "and in km/h?", unit="km/h")
    add(a, "two", "now 2 m/s^2 for 20 s", a=2, t=20)

    a = Anchor("physics", "A 4 kg object moves at 5 m/s. What is its momentum, in kg m/s?",
               dict(m=4, v=5), lambda m, v: m * v, "kg*m/s")
    add(a, "value", "now at 9 m/s", v=9)
    add(a, "value", "what about a 10 kg object?", m=10)
    add(a, "quantity", "what is its kinetic energy, in joules?", unit="J", value=0.5 * 4 * 25)
    add(a, "quantity", "what force stops it in 0.5 s, in newtons?", unit="N", value=20 / 0.5)

    a = Anchor("physics", "A 2 m^3 tank holds air at 300 K and 150 kPa. How many moles of gas does it contain? Use "
               "R = 8.314 J/(mol K).", dict(V=2, T=300, p=150e3), lambda V, T, p: p * V / (8.314 * T), "mol")
    add(a, "value", "now at 400 K", T=400)
    add(a, "value", "what if the pressure is 500 kPa?", p=500e3)
    add(a, "quantity", "what mass of air is that, in kilograms, with a molar mass of 0.029 kg/mol?", unit="kg",
        value=150e3 * 2 / (8.314 * 300) * 0.029)
    add(a, "unit", "and in kilomoles?", unit="kmol")

    a = Anchor("physics", "A 50 cm diameter wheel turns at 600 rpm. What is the speed of a point on its rim, in meters "
               "per second?", dict(D=0.5, n=600), lambda D, n: math.pi * D * n / 60, "m/s")
    add(a, "value", "now at 900 rpm", n=900)
    add(a, "value", "what about a 70 cm wheel?", D=0.7)
    add(a, "quantity", "what is its angular velocity, in rad/s?", unit="rad/s", value=600 * 2 * math.pi / 60)
    add(a, "quantity", "what is the centripetal acceleration at the rim, in m/s^2?", unit="m/s^2",
        value=(math.pi * 0.5 * 10) ** 2 / 0.25)
    add(a, "unit", "and in km/h?", unit="km/h")

    a = Anchor("physics", "A steel wire 2 m long with a cross-section of 1 mm^2 carries a 500 N load. Young's modulus is "
               "200 GPa. How much does it stretch, in millimeters?", dict(L=2, A=1e-6, F=500, E=200e9),
               lambda L, A, F, E: F * L / (A * E), "m", "mm")
    add(a, "value", "now with a 1200 N load", F=1200)
    add(a, "value", "what if the wire is 5 m long?", L=5)
    add(a, "quantity", "what is the stress in the wire, in megapascals?", unit="MPa", value=500 / 1e-6 / 1e6)
    add(a, "value", "same but aluminium, Young's modulus 70 GPa", E=70e9)

    a = Anchor("physics", "A 0.4 kg ball is kicked straight up at 15 m/s. How high does it rise, in meters? Use g = 9.81 "
               "m/s^2.", dict(v=15, g=G), lambda v, g: v ** 2 / (2 * g), "m")
    add(a, "value", "now kicked at 20 m/s", v=20)
    add(a, "quantity", "how long until it reaches the top, in seconds?", unit="s", value=15 / G)
    add(a, "quantity", "what is its kinetic energy at launch, in joules?", unit="J", value=0.5 * 0.4 * 15 ** 2)
    add(a, "value", "same on Mars, g = 3.71 m/s^2", g=3.71)
    add(a, "unit", "and in centimeters?", unit="cm")

    a = Anchor("physics", "A sound wave of 680 Hz travels at 340 m/s. What is its wavelength, in meters?",
               dict(f=680, c=340), lambda f, c: c / f, "m")
    add(a, "value", "now at 1700 Hz", f=1700)
    add(a, "value", "what if it travels in water at 1480 m/s?", c=1480)
    add(a, "quantity", "what is its period, in milliseconds?", unit="ms", value=1000 / 680)
    add(a, "unit", "and in centimeters?", unit="cm")

    # ---------------- aerospace ----------------
    a = Anchor("aerospace", "A rocket engine produces 900 kN of thrust with a propellant flow of 300 kg/s. What is its "
               "effective exhaust velocity, in meters per second?", dict(F=900e3, mdot=300), lambda F, mdot: F / mdot, "m/s")
    add(a, "value", "now with 1500 kN of thrust", F=1500e3)
    add(a, "value", "what if the flow is 250 kg/s?", mdot=250)
    add(a, "quantity", "what is its specific impulse, in seconds? Use g0 = 9.81 m/s^2.", unit="s", value=3000 / 9.81)
    add(a, "quantity", "how much propellant does it burn in 2 minutes, in tonnes?", unit="t", value=300 * 120 / 1000)
    add(a, "unit", "and in km/s?", unit="km/s")

    a = Anchor("aerospace", "An aircraft flies at Mach 0.78 where the speed of sound is 300 m/s. What is its true "
               "airspeed, in meters per second?", dict(M=0.78, a=300), lambda M, a: M * a, "m/s")
    add(a, "value", "now at Mach 0.85", M=0.85)
    add(a, "value", "what if the speed of sound is 295 m/s?", a=295)
    add(a, "unit", "and in knots?", unit="knot")
    add(a, "quantity", "how far does it fly in 2 hours, in kilometers?", unit="km", value=0.78 * 300 * 7200 / 1000)

    a = Anchor("aerospace", "A glider has a lift-to-drag ratio of 40 and starts at 1500 m altitude. How far can it glide "
               "in still air, in kilometers?", dict(LD=40, h=1500), lambda LD, h: LD * h, "m", "km")
    add(a, "value", "now from 2500 m", h=2500)
    add(a, "value", "what if the L/D is 25?", LD=25)
    add(a, "quantity", "what is its glide angle, in degrees?", unit="degree", value=math.degrees(math.atan(1 / 40)))
    add(a, "unit", "and in meters?", unit="m")

    a = Anchor("aerospace", "A satellite orbits Earth at a radius of 8000 km. What is its orbital period, in minutes? "
               "Earth's GM is 3.986e14 m^3/s^2.", dict(r=8.0e6), lambda r: 2 * math.pi * math.sqrt(r ** 3 / 3.986e14),
               "s", "min")
    add(a, "value", "now at 12000 km", r=12.0e6)
    add(a, "quantity", "what is its orbital speed, in km/s?", unit="km/s", value=math.sqrt(3.986e14 / 8.0e6) / 1000)
    add(a, "unit", "and in hours?", unit="h")
    add(a, "quantity", "what is the escape speed at that radius, in km/s?", unit="km/s",
        value=math.sqrt(2 * 3.986e14 / 8.0e6) / 1000)

    a = Anchor("aerospace", "A 5000 kg aircraft needs a lift coefficient of 0.6 to fly level at 80 m/s in air of density "
               "1.0 kg/m^3. What wing area does it need, in m^2? Use g = 9.81 m/s^2.",
               dict(m=5000, CL=0.6, v=80, rho=1.0), lambda m, CL, v, rho: 2 * m * G / (rho * v ** 2 * CL), "m^2")
    add(a, "value", "now at 100 m/s", v=100)
    add(a, "value", "what if the lift coefficient is 0.9?", CL=0.9)
    add(a, "quantity", "what is the wing loading, in N/m^2?", unit="N/m^2",
        value=5000 * G / (2 * 5000 * G / (1.0 * 80 ** 2 * 0.6)))
    add(a, "two", "now a 7000 kg aircraft at sea level, density 1.225 kg/m^3", m=7000, rho=1.225)

    a = Anchor("aerospace", "A spacecraft at 7.7 km/s fires its engine for a delta-v of 120 m/s. With an exhaust velocity "
               "of 3100 m/s and a starting mass of 2000 kg, how much propellant does it burn, in kilograms?",
               dict(dv=120, ve=3100, m0=2000), lambda dv, ve, m0: m0 * (1 - math.exp(-dv / ve)), "kg")
    add(a, "value", "now for a delta-v of 300 m/s", dv=300)
    add(a, "value", "what if the exhaust velocity is 4400 m/s?", ve=4400)
    add(a, "quantity", "what is its mass after the burn, in kilograms?", value=2000 * math.exp(-120 / 3100))
    add(a, "value", "same burn for a 3500 kg spacecraft", m0=3500)

    a = Anchor("aerospace", "Air at 288 K flows at 150 m/s. What is its stagnation temperature, in kelvin? Use "
               "cp = 1005 J/(kg K).", dict(T=288, v=150), lambda T, v: T + v ** 2 / (2 * 1005), "K")
    add(a, "value", "now at 250 m/s", v=250)
    add(a, "value", "what if the air is at 220 K?", T=220)
    add(a, "unit", "and in degrees Celsius?", unit="degC")
    add(a, "quantity", "what is the Mach number? Use gamma 1.4 and R = 287 J/(kg K).", unit="",
        value=150 / math.sqrt(1.4 * 287 * 288))
    return out


def main():
    rows = cases()
    (Path(__file__).parent / "cases3.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    by = {}
    for r in rows:
        by[r["pack"]] = by.get(r["pack"], 0) + 1
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    print(f"wrote {len(rows)} cases", by)


if __name__ == "__main__":
    main()
