"""Follow-up conversations, set 6 (held out), for FOLLOWUP6_RULE (evals/followup/run6.py).

    .venv/bin/python evals/followup/build6.py      # writes evals/followup/cases6.jsonl

Written 2026-11-13, before any model answered them. Sets 1-5 are seen. Same construction as sets 2-5 (keys from each
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
        out.append({"id": f"f6-{len(out) + 1:03d}", "pack": anc.pack, "kind": kind, "messages": [
            {"role": "user", "content": anc.text},
            {"role": "assistant", "content": f"{fmt(anc.value())} {anc.out_unit}".strip()},
            {"role": "user", "content": follow}], "answer": key, "unit": unit, "rel_tol": 0.02})

    # ---------------- electrical ----------------
    a = Anchor("electrical", "A battery with an EMF of 12 V and an internal resistance of 0.5 ohm supplies 4 A. What is "
               "its terminal voltage, in volts?", dict(E=12, r=0.5, I=4), lambda E, r, I: E - I * r, "V")
    add(a, "value", "now supplying 10 A", I=10)
    add(a, "value", "what if the internal resistance is 0.2 ohm?", r=0.2)
    add(a, "quantity", "how much power is wasted inside the battery, in watts?", unit="W", value=4 ** 2 * 0.5)
    add(a, "two", "now a 9 V battery supplying 2 A", E=9, I=2)

    a = Anchor("electrical", "A motor delivers 3 kW of shaft power at an efficiency of 0.85. What electrical power does "
               "it draw, in kilowatts?", dict(P=3000, eta=0.85), lambda P, eta: P / eta, "W", "kW")
    add(a, "value", "now at an efficiency of 0.92", eta=0.92)
    add(a, "value", "what about a 5.5 kW motor?", P=5500)
    add(a, "quantity", "on a 230 V supply, what current is that, in amperes?", unit="A", value=3000 / 0.85 / 230)
    add(a, "unit", "and in watts?", unit="W")

    a = Anchor("electrical", "An RC low-pass filter uses a 1.6 kilohm resistor and a 100 nF capacitor. What is its "
               "cutoff frequency, in hertz?", dict(R=1600, C=100e-9), lambda R, C: 1 / (2 * math.pi * R * C), "Hz")
    add(a, "value", "now with a 3.3 kilohm resistor", R=3300)
    add(a, "value", "what if the capacitor is 47 nF?", C=47e-9)
    add(a, "unit", "and in kilohertz?", unit="kHz")
    add(a, "quantity", "what is the filter's time constant, in microseconds?", unit="us", value=1600 * 100e-9 * 1e6)

    a = Anchor("electrical", "A 60 Ah battery is charged at a constant 8 A. How long does a full charge take, in hours?",
               dict(Q=60, I=8), lambda Q, I: Q / I, "hour")
    add(a, "value", "now at 15 A", I=15)
    add(a, "value", "what about a 100 Ah battery?", Q=100)
    add(a, "unit", "and in minutes?", unit="minute")
    add(a, "quantity", "at 12 V, how much energy does the full battery hold, in watt-hours?", unit="W*h", value=720)

    a = Anchor("electrical", "An ideal transformer steps 11000 V down to 400 V and supplies 150 A to its load. What "
               "current flows in the primary, in amperes?", dict(V1=11000, V2=400, I=150), lambda V1, V2, I: I * V2 / V1, "A")
    add(a, "value", "now supplying 250 A", I=250)
    add(a, "value", "what if the secondary is 230 V?", V2=230)
    add(a, "quantity", "what apparent power does it transfer, in kilovolt-amperes?", unit="kV*A", value=60)
    add(a, "two", "now 33000 V down to 400 V, supplying 500 A", V1=33000, I=500)

    a = Anchor("electrical", "Three resistors of 10 ohm, 15 ohm and 30 ohm are connected in parallel across 12 V. What "
               "total current flows, in amperes?", dict(V=12), lambda V: V * (1 / 10 + 1 / 15 + 1 / 30), "A")
    add(a, "value", "now across 30 V", V=30)
    add(a, "value", "what if the 30 ohm resistor is removed?", value=12 * (1 / 10 + 1 / 15))
    add(a, "quantity", "what is the equivalent resistance, in ohms?", unit="ohm", value=5)
    add(a, "unit", "and in milliamperes?", unit="mA")

    a = Anchor("electrical", "A 50 m length of heating wire has a resistance of 0.8 ohm per meter and is connected to "
               "230 V. What power does it dissipate, in watts?", dict(L=50, V=230), lambda L, V: V ** 2 / (0.8 * L), "W")
    add(a, "value", "now a 30 m length", L=30)
    add(a, "value", "what if the supply is 120 V?", V=120)
    add(a, "quantity", "what current does it draw, in amperes?", unit="A", value=230 / 40)
    add(a, "unit", "and in kilowatts?", unit="kW")

    a = Anchor("electrical", "A coil with an inductance of 80 mH is connected to a 50 Hz supply. What is its inductive "
               "reactance, in ohms?", dict(L=0.080, f=50), lambda L, f: 2 * math.pi * f * L, "ohm")
    add(a, "value", "now at 400 Hz", f=400)
    add(a, "value", "same with a 15 mH coil", L=0.015)
    add(a, "quantity", "with 230 V across it, what current flows, in amperes?", unit="A",
        value=230 / (2 * math.pi * 50 * 0.080))
    add(a, "two", "now a 0.2 H coil at 60 Hz", L=0.2, f=60)

    # ---------------- physics ----------------
    a = Anchor("physics", "A hydraulic press has a small piston of 4 cm^2 and a large piston of 200 cm^2. A 150 N force "
               "pushes the small piston. What force does the large piston exert, in newtons?",
               dict(F=150, A1=4e-4, A2=200e-4), lambda F, A1, A2: F * A2 / A1, "N")
    add(a, "value", "now with a 400 N force", F=400)
    add(a, "value", "what if the large piston is 500 cm^2?", A2=500e-4)
    add(a, "unit", "and in kilonewtons?", unit="kN")
    add(a, "quantity", "what is the pressure in the fluid, in kilopascals?", unit="kPa", value=150 / 4e-4 / 1000)

    a = Anchor("physics", "A 1500 kg car moving at 20 m/s collides with and sticks to a stationary 2500 kg truck. What "
               "is their common speed just after the collision, in meters per second?", dict(m1=1500, v=20, m2=2500),
               lambda m1, v, m2: m1 * v / (m1 + m2), "m/s")
    add(a, "value", "now with the car at 32 m/s", v=32)
    add(a, "value", "what if the truck is 4500 kg?", m2=4500)
    add(a, "quantity", "how much kinetic energy is lost in the collision, in kilojoules?", unit="kJ",
        value=(0.5 * 1500 * 20 ** 2 - 0.5 * 4000 * 7.5 ** 2) / 1000)
    add(a, "two", "now a 1000 kg car at 30 m/s", m1=1000, v=30)

    a = Anchor("physics", "A flywheel with a moment of inertia of 12 kg m^2 spins at 300 rpm. What is its rotational "
               "kinetic energy, in joules?", dict(I=12, n=300), lambda I, n: 0.5 * I * (2 * math.pi * n / 60) ** 2, "J")
    add(a, "value", "now at 900 rpm", n=900)
    add(a, "value", "what if the moment of inertia is 30 kg m^2?", I=30)
    add(a, "unit", "and in kilojoules?", unit="kJ")
    add(a, "quantity", "what is its angular momentum, in kg m^2/s?", unit="kg*m^2/s", value=12 * 2 * math.pi * 300 / 60)

    a = Anchor("physics", "A guitar string 0.65 m long carries waves at 280 m/s. What is its fundamental frequency, in "
               "hertz?", dict(L=0.65, v=280), lambda L, v: v / (2 * L), "Hz")
    add(a, "value", "now with a 0.5 m string", L=0.5)
    add(a, "value", "what if the wave speed is 420 m/s?", v=420)
    add(a, "value", "what about the third harmonic?", value=3 * 280 / 1.3)
    add(a, "quantity", "what is the wavelength of the fundamental, in meters?", unit="m", value=1.3)

    a = Anchor("physics", "A 2 m long steel rod with an expansion coefficient of 12e-6 per K is heated by 80 K. How much "
               "does it lengthen, in millimeters?", dict(L=2, dT=80), lambda L, dT: L * 12e-6 * dT, "m", "mm")
    add(a, "value", "now heated by 150 K", dT=150)
    add(a, "value", "what about a 5 m rod?", L=5)
    add(a, "unit", "and in micrometers?", unit="um")
    add(a, "two", "now a 3 m rod heated by 40 K", L=3, dT=40)

    a = Anchor("physics", "A 3 kg block on a horizontal surface with a kinetic friction coefficient of 0.25 is pulled by "
               "a horizontal 20 N force. What is its acceleration, in m/s^2? Use g = 9.81 m/s^2.",
               dict(m=3, mu=0.25, F=20), lambda m, mu, F: (F - mu * m * G) / m, "m/s^2")
    add(a, "value", "now pulled with 35 N", F=35)
    add(a, "value", "what if the friction coefficient is 0.4?", mu=0.4)
    add(a, "quantity", "what is the friction force on it, in newtons?", unit="N", value=0.25 * 3 * G)
    add(a, "two", "now a 5 kg block pulled with 30 N", m=5, F=30)

    a = Anchor("physics", "Water flows at 2 m/s through a pipe with an inner diameter of 0.1 m. What is the volume flow "
               "rate, in liters per second?", dict(v=2, d=0.1), lambda v, d: math.pi / 4 * d ** 2 * v, "m^3/s", "L/s")
    add(a, "value", "now at 3.5 m/s", v=3.5)
    add(a, "value", "what if the diameter is 0.15 m?", d=0.15)
    add(a, "unit", "and in cubic meters per hour?", unit="m^3/hour")
    add(a, "quantity", "what is the mass flow rate, in kilograms per second? Water's density is 1000 kg/m^3.",
        unit="kg/s", value=1000 * math.pi / 4 * 0.1 ** 2 * 2)

    a = Anchor("physics", "A heat engine takes in 5000 J of heat and rejects 3200 J in each cycle. How much work does it "
               "do per cycle, in joules?", dict(Qh=5000, Qc=3200), lambda Qh, Qc: Qh - Qc, "J")
    add(a, "value", "now rejecting 2750 J", Qc=2750)
    add(a, "value", "what if it takes in 8000 J?", Qh=8000)
    add(a, "quantity", "running at 20 cycles per second, what power does it deliver, in kilowatts?", unit="kW", value=36)
    add(a, "unit", "and in kilojoules?", unit="kJ")

    # ---------------- aerospace ----------------
    a = Anchor("aerospace", "An aircraft with a true airspeed of 420 km/h flies 600 km against a 60 km/h headwind. How "
               "long does the flight take, in hours?", dict(d=600, tas=420, w=60), lambda d, tas, w: d / (tas - w), "hour")
    add(a, "value", "now with a 100 km/h headwind", w=100)
    add(a, "value", "what if the distance is 900 km?", d=900)
    add(a, "value", "what if it's a tailwind instead?", w=-60)
    add(a, "unit", "and in minutes?", unit="minute")

    a = Anchor("aerospace", "A parachute with a drag coefficient of 1.4 and an area of 50 m^2 carries a total mass of "
               "110 kg. What is its steady descent speed in air of density 1.225 kg/m^3, in meters per second? Use "
               "g = 9.81 m/s^2.", dict(m=110, A=50), lambda m, A: math.sqrt(2 * m * G / (1.225 * 1.4 * A)), "m/s")
    add(a, "value", "now with a total mass of 160 kg", m=160)
    add(a, "value", "what if the area is 30 m^2?", A=30)
    add(a, "two", "now 90 kg under a 40 m^2 canopy", m=90, A=40)
    add(a, "quantity", "what drag force does it produce in that steady descent, in newtons?", unit="N", value=110 * G)

    a = Anchor("aerospace", "What is the escape velocity from the surface of Mars, in km/s? Mars has GM = 4.283e13 "
               "m^3/s^2 and a radius of 3390 km.", dict(GM=4.283e13, r=3390e3), lambda GM, r: math.sqrt(2 * GM / r),
               "m/s", "km/s")
    add(a, "value", "now from an altitude of 500 km above the surface", r=3890e3)
    add(a, "two", "what about the Moon, with GM = 4.905e12 m^3/s^2 and a radius of 1737 km?", GM=4.905e12, r=1737e3)
    add(a, "unit", "and in m/s?", unit="m/s")
    add(a, "quantity", "what is the gravitational acceleration at the surface, in m/s^2?", unit="m/s^2",
        value=4.283e13 / 3390e3 ** 2)

    a = Anchor("aerospace", "An aircraft climbs at an airspeed of 75 m/s with a climb angle of 6 degrees. What is its "
               "rate of climb, in meters per second?", dict(v=75, g=6), lambda v, g: v * math.sin(math.radians(g)), "m/s")
    add(a, "value", "now at a climb angle of 9 degrees", g=9)
    add(a, "value", "what if the airspeed is 110 m/s?", v=110)
    add(a, "unit", "and in feet per minute?", unit="ft/min")
    add(a, "quantity", "how long does it take to climb 3000 m, in minutes?", unit="minute",
        value=3000 / (75 * math.sin(math.radians(6))) / 60)

    a = Anchor("aerospace", "A 12000 kg rocket lifts off vertically with 180 kN of thrust. What is its initial upward "
               "acceleration, in m/s^2? Use g = 9.81 m/s^2.", dict(m=12000, T=180e3), lambda m, T: T / m - G, "m/s^2")
    add(a, "value", "now with 240 kN of thrust", T=240e3)
    add(a, "value", "what if the mass is 15000 kg?", m=15000)
    add(a, "quantity", "what is its thrust-to-weight ratio at liftoff?", unit="", value=180e3 / (12000 * G))
    add(a, "two", "now a 20000 kg rocket with 350 kN of thrust", m=20000, T=350e3)

    a = Anchor("aerospace", "Air with a density of 1.225 kg/m^3 and a viscosity of 1.8e-5 Pa s flows at 50 m/s over a "
               "wing with a chord of 1.6 m. What is the Reynolds number?", dict(rho=1.225, v=50, c=1.6),
               lambda rho, v, c: rho * v * c / 1.8e-5, "")
    add(a, "value", "now at 80 m/s", v=80)
    add(a, "value", "what if the chord is 0.3 m?", c=0.3)
    add(a, "value", "what about at altitude, where the density is 0.4 kg/m^3?", rho=0.4)
    add(a, "two", "now 30 m/s over a 2.5 m chord", v=30, c=2.5)

    a = Anchor("aerospace", "An aircraft's tanks hold 12000 L of jet fuel with a density of 0.8 kg/L. What is the fuel "
               "mass, in kilograms?", dict(V=12000, rho=0.8), lambda V, rho: V * rho, "kg")
    add(a, "value", "now with 18000 L", V=18000)
    add(a, "value", "what if the density is 0.72 kg/L?", rho=0.72)
    add(a, "unit", "and in tonnes?", unit="t")
    add(a, "quantity", "burning 2400 kg per hour, how long does that fuel last, in hours?", unit="hour", value=4)
    return out


def main():
    rows = cases()
    (Path(__file__).parent / "cases6.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    by = {}
    for r in rows:
        by[r["pack"]] = by.get(r["pack"], 0) + 1
        by[r["kind"]] = by.get(r["kind"], 0) + 1
    print(f"wrote {len(rows)} cases", by)


if __name__ == "__main__":
    main()
