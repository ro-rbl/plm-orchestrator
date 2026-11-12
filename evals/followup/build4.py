"""Follow-up conversations, set 4 (held out), for FOLLOWUP4_RULE and SI_RULE (evals/followup/run4.py).

    .venv/bin/python evals/followup/build4.py      # writes evals/followup/cases4.jsonl

Written 2026-11-10, before any model answered them. Sets 1-3 are seen. Same construction as sets 2 and 3 (keys from
each anchor's formula, converted with pint; kinds for reporting only), with new anchors.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build2 import Anchor, fmt  # noqa: E402

G = 9.81
GM = 3.986e14


def cases():
    out = []

    def add(anc, kind, follow, unit=None, value=None, **changes):
        unit = anc.out_unit if unit is None else unit
        key = value if value is not None else anc.value(unit, **changes)
        out.append({"id": f"f4-{len(out) + 1:03d}", "pack": anc.pack, "kind": kind, "messages": [
            {"role": "user", "content": anc.text},
            {"role": "assistant", "content": f"{fmt(anc.value())} {anc.out_unit}".strip()},
            {"role": "user", "content": follow}], "answer": key, "unit": unit, "rel_tol": 0.02})

    # ---------------- electrical ----------------
    a = Anchor("electrical", "Resistors of 6 kilohm and 3 kilohm are connected in parallel. What is the equivalent "
               "resistance, in kilohms?", dict(R1=6000, R2=3000), lambda R1, R2: R1 * R2 / (R1 + R2), "ohm", "kiloohm")
    add(a, "two", "now 12 kilohm and 4 kilohm", R1=12000, R2=4000)
    add(a, "value", "what if the second one is 6 kilohm?", R2=6000)
    add(a, "unit", "and in ohms?", unit="ohm")
    add(a, "quantity", "with 12 V across them, what total current flows, in milliamperes?", unit="mA", value=12 / 2000 * 1000)

    a = Anchor("electrical", "A 10 microfarad capacitor is connected to a 50 Hz supply. What is its reactance, in ohms?",
               dict(C=10e-6, f=50), lambda C, f: 1 / (2 * math.pi * f * C), "ohm")
    add(a, "value", "now at 400 Hz", f=400)
    add(a, "value", "same with a 2.2 microfarad capacitor", C=2.2e-6)
    add(a, "quantity", "what current flows with 230 V across it, in amperes?", unit="A", value=230 * 2 * math.pi * 50 * 10e-6)
    add(a, "unit", "and in kilohms?", unit="kiloohm")

    a = Anchor("electrical", "A 12 V car battery delivers 300 A for 3 s to the starter motor. How much energy does it "
               "supply, in kilojoules?", dict(V=12, I=300, t=3), lambda V, I, t: V * I * t, "J", "kJ")
    add(a, "value", "now for 5 s", t=5)
    add(a, "value", "what if it delivers 450 A?", I=450)
    add(a, "unit", "and in watt-hours?", unit="Wh")
    add(a, "quantity", "what power is that, in kilowatts?", unit="kW", value=3.6)

    a = Anchor("electrical", "A current of 3 A splits between a 20 ohm and a 30 ohm resistor in parallel. What current "
               "flows through the 20 ohm resistor, in amperes?", dict(I=3, R1=20, R2=30), lambda I, R1, R2: I * R2 / (R1 + R2), "A")
    add(a, "value", "now the total current is 5 A", I=5)
    add(a, "value", "what if the 30 ohm resistor is replaced by 60 ohm?", R2=60)
    add(a, "quantity", "what is the voltage across them, in volts?", unit="V", value=3 * 12)
    add(a, "quantity", "and through the 30 ohm one?", value=3 * 20 / 50)
    add(a, "unit", "and in milliamperes?", unit="mA")

    a = Anchor("electrical", "A sinusoidal mains voltage has a peak value of 325 V. What is its RMS value, in volts?",
               dict(Vp=325), lambda Vp: Vp / math.sqrt(2), "V")
    add(a, "value", "now with a peak of 170 V", Vp=170)
    add(a, "quantity", "what is its peak-to-peak voltage, in volts?", value=650)
    add(a, "quantity", "what average power does it deliver to a 100 ohm resistor, in watts?", unit="W", value=325 ** 2 / 2 / 100)
    add(a, "unit", "and in kilovolts?", unit="kV")

    a = Anchor("electrical", "A current of 250 mA flows for 2 minutes. How much charge passes, in coulombs?",
               dict(I=0.25, t=120), lambda I, t: I * t, "C")
    add(a, "value", "now for 10 minutes", t=600)
    add(a, "value", "what if the current is 1.2 A?", I=1.2)
    add(a, "quantity", "through a 40 ohm resistor, how much energy is dissipated in that time, in joules?", unit="J",
        value=0.25 ** 2 * 40 * 120)
    add(a, "two", "now 80 mA for 30 minutes", I=0.08, t=1800)

    a = Anchor("electrical", "A power line with a resistance of 0.5 ohm carries 40 A. How much power is lost in the line, "
               "in watts?", dict(R=0.5, I=40), lambda R, I: I ** 2 * R, "W")
    add(a, "value", "now at 80 A", I=80)
    add(a, "value", "what if the line resistance is 0.2 ohm?", R=0.2)
    add(a, "unit", "and in kilowatts?", unit="kW")
    add(a, "quantity", "what is the voltage drop along the line, in volts?", unit="V", value=20)

    # ---------------- physics ----------------
    a = Anchor("physics", "A stone is dropped from a 45 m cliff. How long does it take to reach the ground, in seconds? "
               "Use g = 9.81 m/s^2.", dict(h=45, g=G), lambda h, g: math.sqrt(2 * h / g), "s")
    add(a, "value", "now from 80 m", h=80)
    add(a, "value", "same on the Moon, g = 1.62 m/s^2", g=1.62)
    add(a, "quantity", "what speed does it hit the ground at, in m/s?", unit="m/s", value=math.sqrt(2 * G * 45))
    add(a, "unit", "and in milliseconds?", unit="ms")

    a = Anchor("physics", "A 0.05 m^3 block is fully submerged in water of density 1000 kg/m^3. What buoyant force acts "
               "on it, in newtons? Use g = 9.81 m/s^2.", dict(V=0.05, rho=1000), lambda V, rho: rho * V * G, "N")
    add(a, "value", "now in seawater, density 1025 kg/m^3", rho=1025)
    add(a, "value", "what about a 0.2 m^3 block?", V=0.2)
    add(a, "unit", "and in kilonewtons?", unit="kN")
    add(a, "quantity", "what mass of water does it displace, in kilograms?", unit="kg", value=50)

    a = Anchor("physics", "What is the gauge pressure 12 m below the surface of water of density 1000 kg/m^3, in "
               "kilopascals? Use g = 9.81 m/s^2.", dict(h=12, rho=1000), lambda h, rho: rho * G * h, "Pa", "kPa")
    add(a, "value", "now at 30 m", h=30)
    add(a, "value", "what if it's oil of density 850 kg/m^3?", rho=850)
    add(a, "unit", "and in bar?", unit="bar")
    add(a, "quantity", "what force does that put on a 0.5 m^2 hatch, in kilonewtons?", unit="kN", value=1000 * G * 12 * 0.5 / 1000)

    a = Anchor("physics", "A crane lifts an 800 kg load 15 m in 20 s. What average power does it deliver, in kilowatts? "
               "Use g = 9.81 m/s^2.", dict(m=800, h=15, t=20), lambda m, h, t: m * G * h / t, "W", "kW")
    add(a, "value", "now in 8 s", t=8)
    add(a, "value", "what about a 1200 kg load?", m=1200)
    add(a, "quantity", "how much work is done on the load, in kilojoules?", unit="kJ", value=800 * G * 15 / 1000)
    add(a, "unit", "and in watts?", unit="W")
    add(a, "two", "now 500 kg lifted 30 m", m=500, h=30)

    a = Anchor("physics", "A 2 kW heater warms 50 kg of water. How long does it take to raise the temperature by 30 K, "
               "in minutes? Water's specific heat is 4186 J/(kg K).", dict(P=2000, m=50, dT=30),
               lambda P, m, dT: m * 4186 * dT / P, "s", "min")
    add(a, "value", "now with a 3 kW heater", P=3000)
    add(a, "value", "what if it's only 20 kg of water?", m=20)
    add(a, "unit", "and in hours?", unit="h")
    add(a, "quantity", "how much energy does that take, in megajoules?", unit="MJ", value=50 * 4186 * 30 / 1e6)

    a = Anchor("physics", "A 1200 kg car takes a curve of radius 80 m at 20 m/s. What centripetal force is needed, in "
               "newtons?", dict(m=1200, r=80, v=20), lambda m, r, v: m * v ** 2 / r, "N")
    add(a, "value", "now at 30 m/s", v=30)
    add(a, "value", "what if the radius is 50 m?", r=50)
    add(a, "unit", "and in kilonewtons?", unit="kN")
    add(a, "quantity", "what is the centripetal acceleration, in m/s^2?", unit="m/s^2", value=5)

    a = Anchor("physics", "A 20 kg crate is pushed 6 m across a floor with a friction coefficient of 0.4. How much work "
               "is done against friction, in joules? Use g = 9.81 m/s^2.", dict(m=20, d=6, mu=0.4),
               lambda m, d, mu: mu * m * G * d, "J")
    add(a, "value", "now pushed 15 m", d=15)
    add(a, "value", "what if the coefficient is 0.25?", mu=0.25)
    add(a, "quantity", "what is the friction force, in newtons?", unit="N", value=0.4 * 20 * G)
    add(a, "two", "now a 50 kg crate pushed 10 m", m=50, d=10)

    # ---------------- aerospace ----------------
    a = Anchor("aerospace", "An aircraft with a wing area of 30 m^2 and a drag coefficient of 0.03 flies at 90 m/s in air "
               "of density 1.0 kg/m^3. What is the drag, in newtons?", dict(S=30, Cd=0.03, v=90, rho=1.0),
               lambda S, Cd, v, rho: 0.5 * rho * v ** 2 * S * Cd, "N")
    add(a, "value", "now at 120 m/s", v=120)
    add(a, "value", "what if the drag coefficient is 0.045?", Cd=0.045)
    add(a, "unit", "and in kilonewtons?", unit="kN")
    add(a, "quantity", "what power is needed to overcome it, in kilowatts?", unit="kW", value=3645 * 90 / 1000)

    a = Anchor("aerospace", "A 60000 kg airliner has engines giving 200 kN of total thrust. What is its thrust-to-weight "
               "ratio? Use g = 9.81 m/s^2.", dict(m=60000, T=200e3), lambda m, T: T / (m * G), "")
    add(a, "value", "now with 280 kN of thrust", T=280e3)
    add(a, "value", "what about a 75000 kg airliner?", m=75000)
    add(a, "quantity", "what is its weight, in kilonewtons?", unit="kN", value=60000 * G / 1000)

    a = Anchor("aerospace", "An 8000 kg aircraft has 600 kW of excess power. What is its rate of climb, in meters per "
               "second? Use g = 9.81 m/s^2.", dict(m=8000, P=600e3), lambda m, P: P / (m * G), "m/s")
    add(a, "value", "now with 900 kW of excess power", P=900e3)
    add(a, "value", "what if it weighs 10000 kg?", m=10000)
    add(a, "unit", "and in feet per minute?", unit="ft/min")
    add(a, "quantity", "how long does it take to climb 3000 m at that rate, in minutes?", unit="min",
        value=3000 / (600e3 / (8000 * G)) / 60)

    a = Anchor("aerospace", "What is the gravitational acceleration at an altitude of 400 km above Earth, in m/s^2? "
               "Earth's radius is 6371 km and GM is 3.986e14 m^3/s^2.", dict(h=400e3, R=6371e3, gm=GM),
               lambda h, R, gm: gm / (R + h) ** 2, "m/s^2")
    add(a, "value", "now at 2000 km altitude", h=2000e3)
    add(a, "quantity", "what is the circular orbital speed there, in km/s?", unit="km/s", value=math.sqrt(GM / 6771e3) / 1000)
    add(a, "two", "same altitude above Mars, radius 3390 km and GM = 4.283e13 m^3/s^2", R=3390e3, gm=4.283e13)

    a = Anchor("aerospace", "An aircraft carries 4000 kg of fuel and burns 800 kg per hour. What is its endurance, in "
               "hours?", dict(F=4000, r=800), lambda F, r: F / r, "h")
    add(a, "value", "now with 6500 kg of fuel", F=6500)
    add(a, "value", "what if it burns 650 kg per hour?", r=650)
    add(a, "unit", "and in minutes?", unit="min")
    add(a, "quantity", "cruising at 220 m/s, how far can it fly, in kilometers?", unit="km", value=5 * 3600 * 220 / 1000)

    a = Anchor("aerospace", "A rocket engine with a specific impulse of 450 s burns 250 kg/s of propellant. What thrust "
               "does it produce, in kilonewtons? Use g0 = 9.81 m/s^2.", dict(Isp=450, mdot=250),
               lambda Isp, mdot: Isp * 9.81 * mdot, "N", "kN")
    add(a, "value", "now burning 400 kg/s", mdot=400)
    add(a, "value", "what if the specific impulse is 300 s?", Isp=300)
    add(a, "unit", "and in meganewtons?", unit="MN")
    add(a, "quantity", "what is its exhaust velocity, in m/s?", unit="m/s", value=450 * 9.81)

    a = Anchor("aerospace", "A wing has a span of 30 m and an area of 100 m^2. What is its aspect ratio?",
               dict(b=30, S=100), lambda b, S: b ** 2 / S, "")
    add(a, "value", "now with a 36 m span", b=36)
    add(a, "value", "what if the area is 120 m^2?", S=120)
    add(a, "quantity", "what is its mean chord, in meters?", unit="m", value=100 / 30)
    return out


def main():
    rows = cases()
    (Path(__file__).parent / "cases4.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    by = {}
    for r in rows:
        by[r["pack"]] = by.get(r["pack"], 0) + 1
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    print(f"wrote {len(rows)} cases", by)


if __name__ == "__main__":
    main()
