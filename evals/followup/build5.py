"""Follow-up conversations, set 5 (held out), for FOLLOWUP5_RULE (evals/followup/run5.py) and the model comparison
(evals/followup/baselines5.py).

    .venv/bin/python evals/followup/build5.py      # writes evals/followup/cases5.jsonl

Written 2026-11-13, before any model answered them. Sets 1-4 are seen. Same construction as sets 2-4 (keys from each
anchor's formula, converted with pint; kinds for reporting only), with new anchors.
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
        out.append({"id": f"f5-{len(out) + 1:03d}", "pack": anc.pack, "kind": kind, "messages": [
            {"role": "user", "content": anc.text},
            {"role": "assistant", "content": f"{fmt(anc.value())} {anc.out_unit}".strip()},
            {"role": "user", "content": follow}], "answer": key, "unit": unit, "rel_tol": 0.02})

    # ---------------- electrical ----------------
    a = Anchor("electrical", "A load draws 12 A from a 230 V supply at a power factor of 0.8. What real power does it "
               "take, in watts?", dict(I=12, V=230, pf=0.8), lambda I, V, pf: V * I * pf, "W")
    add(a, "value", "now at 20 A", I=20)
    add(a, "value", "what if the power factor is 0.95?", pf=0.95)
    add(a, "quantity", "what is the apparent power, in volt-amperes?", unit="V*A", value=230 * 12)
    add(a, "unit", "and in kilowatts?", unit="kW")

    a = Anchor("electrical", "A copper winding has a resistance of 40 ohm at 20 °C. What is its resistance at 80 °C, in "
               "ohms? Copper's temperature coefficient is 0.0039 per °C.", dict(R=40, T=80),
               lambda R, T: R * (1 + 0.0039 * (T - 20)), "ohm")
    add(a, "value", "now at 120 °C", T=120)
    add(a, "value", "what if it starts at 25 ohm?", R=25)
    add(a, "two", "now a 60 ohm winding at 50 °C", R=60, T=50)

    a = Anchor("electrical", "A 1.8 kW heater runs 5 hours a day for 30 days. How much energy does it use, in "
               "kilowatt-hours?", dict(P=1800, h=5), lambda P, h: P * h * 30 * 3600, "J", "kWh")
    add(a, "value", "now 8 hours a day", h=8)
    add(a, "value", "what about a 750 W heater?", P=750)
    add(a, "unit", "and in megajoules?", unit="MJ")
    add(a, "quantity", "what average power is that over the whole 30 days, in watts?", unit="W", value=1800 * 5 / 24)

    a = Anchor("electrical", "A 6 microfarad and a 3 microfarad capacitor are connected in series. What is the "
               "equivalent capacitance, in microfarads?", dict(C1=6e-6, C2=3e-6), lambda C1, C2: C1 * C2 / (C1 + C2), "F", "uF")
    add(a, "value", "what if they're in parallel instead?", value=9)
    add(a, "two", "now 10 microfarad and 15 microfarad", C1=10e-6, C2=15e-6)
    add(a, "unit", "and in nanofarads?", unit="nF")
    add(a, "quantity", "with 12 V across the pair, what charge is stored, in microcoulombs?", unit="uC", value=24)

    a = Anchor("electrical", "A 13 A fuse protects a 230 V circuit. What is the maximum power the circuit can supply, in "
               "kilowatts?", dict(I=13, V=230), lambda I, V: I * V, "W", "kW")
    add(a, "value", "now with a 5 A fuse", I=5)
    add(a, "value", "what if the supply is 110 V?", V=110)
    add(a, "unit", "and in watts?", unit="W")
    add(a, "quantity", "what is the smallest load resistance that won't blow it, in ohms?", unit="ohm", value=230 / 13)

    a = Anchor("electrical", "A solar panel of 1.6 m^2 with an efficiency of 0.20 receives 1000 W/m^2 of sunlight. What "
               "electrical power does it produce, in watts?", dict(A=1.6, eff=0.20, S=1000), lambda A, eff, S: A * eff * S, "W")
    add(a, "value", "now with 800 W/m^2 of sunlight", S=800)
    add(a, "value", "what about a 2 m^2 panel?", A=2)
    add(a, "quantity", "how much energy does it produce in 5 hours, in kilowatt-hours?", unit="kWh", value=1.6)
    add(a, "two", "now an efficiency of 0.22 at 600 W/m^2", eff=0.22, S=600)

    a = Anchor("electrical", "The current in a 0.5 H inductor changes at 4 A/s. What voltage is induced across it, in "
               "volts?", dict(L=0.5, r=4), lambda L, r: L * r, "V")
    add(a, "value", "now at 10 A/s", r=10)
    add(a, "value", "same with a 20 mH inductor", L=0.020)
    add(a, "unit", "and in millivolts?", unit="mV")
    add(a, "quantity", "how much energy does it store when it carries 3 A, in joules?", unit="J", value=0.5 * 0.5 * 9)

    # ---------------- physics ----------------
    a = Anchor("physics", "A car traveling at 25 m/s brakes with a deceleration of 5 m/s^2. What is its stopping "
               "distance, in meters?", dict(v=25, a=5), lambda v, a: v ** 2 / (2 * a), "m")
    add(a, "value", "now from 35 m/s", v=35)
    add(a, "value", "what if it brakes at 8 m/s^2?", a=8)
    add(a, "quantity", "how long does it take to stop, in seconds?", unit="s", value=5)
    add(a, "two", "now 15 m/s braking at 3 m/s^2", v=15, a=3)
    add(a, "unit", "and in kilometers?", unit="km")

    a = Anchor("physics", "A spring with a stiffness of 800 N/m is compressed by 5 cm. What force does it exert, in "
               "newtons?", dict(k=800, x=0.05), lambda k, x: k * x, "N")
    add(a, "value", "now compressed by 12 cm", x=0.12)
    add(a, "value", "what about a 2 kN/m spring?", k=2000)
    add(a, "quantity", "how much energy is stored in it, in joules?", unit="J", value=0.5 * 800 * 0.05 ** 2)
    add(a, "unit", "and in kilonewtons?", unit="kN")

    a = Anchor("physics", "A window of 2 m^2 has glass 5 mm thick with a thermal conductivity of 0.8 W/(m K). With a 15 K "
               "temperature difference across it, what is the heat flow, in watts?", dict(A=2, d=0.005, dT=15),
               lambda A, d, dT: 0.8 * A * dT / d, "W")
    add(a, "value", "now with a 25 K difference", dT=25)
    add(a, "value", "what if the glass is 10 mm thick?", d=0.010)
    add(a, "unit", "and in kilowatts?", unit="kW")
    add(a, "quantity", "how much heat is lost in one hour, in megajoules?", unit="MJ", value=4800 * 3600 / 1e6)

    a = Anchor("physics", "A 60 N force is applied at right angles to the end of a 0.4 m wrench. What torque does it "
               "produce, in N m?", dict(F=60, r=0.4), lambda F, r: F * r, "N*m")
    add(a, "value", "now with a 0.25 m wrench", r=0.25)
    add(a, "value", "what if the force is 150 N?", F=150)
    add(a, "two", "now 90 N on a 0.6 m wrench", F=90, r=0.6)
    add(a, "quantity", "what force applied 0.1 m from the pivot gives the same torque, in newtons?", unit="N", value=240)

    a = Anchor("physics", "An object is placed 30 cm from a converging lens with a focal length of 10 cm. How far from "
               "the lens is the image, in centimeters?", dict(u=0.30, f=0.10), lambda u, f: 1 / (1 / f - 1 / u), "m", "cm")
    add(a, "value", "now with the object 15 cm away", u=0.15)
    add(a, "value", "what if the focal length is 20 cm?", f=0.20)
    add(a, "unit", "and in meters?", unit="m")

    a = Anchor("physics", "Two moles of an ideal gas are at 300 K and 100 kPa. What volume does the gas occupy, in "
               "liters? Use R = 8.314 J/(mol K).", dict(n=2, T=300, p=100e3), lambda n, T, p: n * 8.314 * T / p, "m^3", "L")
    add(a, "value", "now at 400 K", T=400)
    add(a, "value", "what if the pressure is 250 kPa?", p=250e3)
    add(a, "unit", "and in cubic meters?", unit="m^3")
    add(a, "two", "now 5 moles at 350 K", n=5, T=350)

    a = Anchor("physics", "Water of density 1000 kg/m^3 falls 40 m through a turbine at 3 m^3/s. What power is "
               "available, in megawatts? Use g = 9.81 m/s^2.", dict(h=40, Q=3), lambda h, Q: 1000 * G * Q * h, "W", "MW")
    add(a, "value", "now falling 90 m", h=90)
    add(a, "value", "what if the flow is 8 m^3/s?", Q=8)
    add(a, "unit", "and in kilowatts?", unit="kW")
    add(a, "quantity", "how much energy is that in one hour, in megawatt-hours?", unit="MW*h", value=1000 * G * 3 * 40 / 1e6)

    # ---------------- aerospace ----------------
    a = Anchor("aerospace", "A pitot tube measures a dynamic pressure of 1500 Pa in air of density 1.225 kg/m^3. What is "
               "the airspeed, in meters per second?", dict(q=1500, rho=1.225), lambda q, rho: math.sqrt(2 * q / rho), "m/s")
    add(a, "value", "now with 4000 Pa", q=4000)
    add(a, "value", "what if the density is 0.9 kg/m^3?", rho=0.9)
    add(a, "unit", "and in knots?", unit="knot")
    add(a, "unit", "and in km/h?", unit="km/h")

    a = Anchor("aerospace", "A 20000 kg jet with 80 kN of thrust accelerates along a runway. Ignoring drag, what is its "
               "acceleration, in m/s^2?", dict(m=20000, T=80e3), lambda m, T: T / m, "m/s^2")
    add(a, "value", "now with 120 kN of thrust", T=120e3)
    add(a, "value", "what about a 30000 kg jet?", m=30000)
    add(a, "quantity", "how long does it take to reach 70 m/s from rest, in seconds?", unit="s", value=70 / 4)
    add(a, "quantity", "how much runway does that take, in meters?", unit="m", value=70 ** 2 / 8)

    a = Anchor("aerospace", "A rocket stage needs a delta-v of 3000 m/s with an exhaust velocity of 3500 m/s. What mass "
               "ratio (initial over final mass) does it need?", dict(dv=3000, ve=3500), lambda dv, ve: math.exp(dv / ve), "")
    add(a, "value", "now for a delta-v of 4500 m/s", dv=4500)
    add(a, "value", "what if the exhaust velocity is 4400 m/s?", ve=4400)
    add(a, "quantity", "with a final mass of 10 t, how much propellant is needed, in tonnes?", unit="t",
        value=10 * (math.exp(3000 / 3500) - 1))

    a = Anchor("aerospace", "A 2000 kg aircraft with a wing area of 18 m^2 flies level at 60 m/s in air of density 1.225 "
               "kg/m^3. What lift coefficient does it need? Use g = 9.81 m/s^2.", dict(m=2000, S=18, v=60, rho=1.225),
               lambda m, S, v, rho: 2 * m * G / (rho * v ** 2 * S), "")
    add(a, "value", "now at 45 m/s", v=45)
    add(a, "value", "what about at 3000 m, where the density is 0.909 kg/m^3?", rho=0.909)
    add(a, "two", "now a 2500 kg aircraft at 70 m/s", m=2500, v=70)
    add(a, "quantity", "what is the lift, in kilonewtons?", unit="kN", value=2000 * G / 1000)

    a = Anchor("aerospace", "An engine delivers 150 kW to a propeller with an efficiency of 0.82 while flying at 65 m/s. "
               "What thrust does the propeller produce, in newtons?", dict(P=150e3, eta=0.82, v=65),
               lambda P, eta, v: eta * P / v, "N")
    add(a, "value", "now at 90 m/s", v=90)
    add(a, "value", "what if the efficiency is 0.75?", eta=0.75)
    add(a, "unit", "and in kilonewtons?", unit="kN")
    add(a, "quantity", "what is the thrust power, in kilowatts?", unit="kW", value=123)

    a = Anchor("aerospace", "At 11 km altitude the air temperature is 216.65 K. An aircraft flies there at 230 m/s. What "
               "is its Mach number? Use gamma = 1.4 and R = 287 J/(kg K).", dict(T=216.65, v=230),
               lambda T, v: v / math.sqrt(1.4 * 287 * T), "")
    add(a, "value", "now at 250 m/s", v=250)
    add(a, "value", "what if the temperature is 288.15 K?", T=288.15)
    add(a, "quantity", "what is the speed of sound there, in m/s?", unit="m/s", value=math.sqrt(1.4 * 287 * 216.65))

    a = Anchor("aerospace", "A 5700 kg aircraft has a wing area of 28 m^2. What is its wing loading, in kg/m^2?",
               dict(m=5700, S=28), lambda m, S: m / S, "kg/m^2")
    add(a, "value", "now at 6500 kg", m=6500)
    add(a, "value", "what if the wing area is 35 m^2?", S=35)
    add(a, "quantity", "and as a pressure, in N/m^2? Use g = 9.81 m/s^2.", unit="N/m^2", value=5700 * G / 28)
    return out


def main():
    rows = cases()
    (Path(__file__).parent / "cases5.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    by = {}
    for r in rows:
        by[r["pack"]] = by.get(r["pack"], 0) + 1
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    print(f"wrote {len(rows)} cases", by)


if __name__ == "__main__":
    main()
