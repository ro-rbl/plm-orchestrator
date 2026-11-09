"""Follow-up conversations, set 2 (held out), for FOLLOWUP2_RULE (evals/followup/run.py --set 2).

    .venv/bin/python evals/followup/build2.py      # writes evals/followup/cases2.jsonl

Written 2026-11-09, before either wording (A: today's "Original question / Change", B: rewrite-first) was run on
any of them. The 36 cases in cases.jsonl were already seen (B 31/36, A 27/36), so they don't decide anything.

Each anchor is a formula with named parameters; the anchor's reply is the formula's own answer, and each follow-up's
key is the same formula with the follow-up's changes applied (or a stated other formula), converted to the asked
unit with pint. Follow-up kinds, mixed on purpose: a changed value (terse "now for ..." and full sentences), a scaled
value ("doubles", "half"), two changes at once, a different output unit, a different quantity from the same setup,
and a change given with its own unit prefix ("2.2 kilohm", "470 nF").
"""

import json
import math
from pathlib import Path

from pint import UnitRegistry

ureg = UnitRegistry()
G = 9.81


def fmt(x):
    return f"{x:.4g}"


class Anchor:
    def __init__(self, pack, text, params, fn, unit, out_unit=None):
        self.pack, self.text, self.params, self.fn = pack, text, params, fn
        self.unit = unit  # unit fn returns (SI-ish, pint string)
        self.out_unit = out_unit or unit  # unit the anchor asks for

    def value(self, unit=None, **changes):
        q = ureg.Quantity(self.fn(**(self.params | changes)), self.unit)
        return q.to(unit or self.out_unit).magnitude if (unit or self.out_unit) else q.magnitude


def cases():
    out = []

    def add(a, follow, unit=None, value=None, **changes):
        unit = a.out_unit if unit is None else unit
        key = value if value is not None else a.value(unit, **changes)
        reply = f"{fmt(a.value())} {a.out_unit}".strip()
        out.append({"id": f"f2-{len(out) + 1:03d}", "pack": a.pack, "messages": [
            {"role": "user", "content": a.text}, {"role": "assistant", "content": reply},
            {"role": "user", "content": follow}], "answer": key, "unit": unit, "rel_tol": 0.02})

    # ---------------- electrical (33) ----------------
    a = Anchor("electrical", "A 470 ohm resistor is connected across a 9 V battery. What current flows, in milliamperes?",
               dict(R=470, V=9), lambda R, V: V / R, "A", "mA")
    add(a, "now with a 1 kilohm resistor", R=1000)
    add(a, "what if the battery is 12 V?", V=12)
    add(a, "and in amperes?", unit="A")
    add(a, "same circuit, how much power does the resistor dissipate, in watts?", unit="W", value=9 ** 2 / 470)
    add(a, "now 2.2 kilohm and 5 V", R=2200, V=5)

    a = Anchor("electrical", "Two resistors of 100 ohm and 300 ohm are in series across 24 V. What is the voltage across "
               "the 300 ohm resistor, in volts?", dict(R1=100, R2=300, V=24), lambda R1, R2, V: V * R2 / (R1 + R2), "V")
    add(a, "now with 48 V", V=48)
    add(a, "what if the first resistor is 200 ohm?", R1=200)
    add(a, "and across the 100 ohm one?", value=24 * 100 / 400)
    add(a, "what current flows, in milliamperes?", unit="mA", value=24 / 400 * 1000)

    a = Anchor("electrical", "A 2 kW electric heater runs on 230 V. What current does it draw, in amperes?",
               dict(P=2000, V=230), lambda P, V: P / V, "A")
    add(a, "now on 120 V", V=120)
    add(a, "what about a 3.5 kW heater?", P=3500)
    add(a, "what is its resistance, in ohms?", unit="ohm", value=230 ** 2 / 2000)
    add(a, "how much energy does it use in 3 hours, in kilowatt-hours?", unit="kWh", value=6)

    a = Anchor("electrical", "A 10 mH inductor carries 2 A. How much energy is stored in its magnetic field, in "
               "millijoules?", dict(L=0.010, I=2), lambda L, I: 0.5 * L * I ** 2, "J", "mJ")
    add(a, "now with 5 A", I=5)
    add(a, "what if the current doubles?", I=4)
    add(a, "same with a 47 mH inductor", L=0.047)
    add(a, "and in joules?", unit="J")

    a = Anchor("electrical", "An LC circuit has L = 1 mH and C = 100 nF. What is its resonant frequency, in kilohertz?",
               dict(L=1e-3, C=100e-9), lambda L, C: 1 / (2 * math.pi * math.sqrt(L * C)), "Hz", "kHz")
    add(a, "now with C = 10 nF", C=10e-9)
    add(a, "what if L is 4.7 mH?", L=4.7e-3)
    add(a, "and in hertz?", unit="Hz")
    add(a, "now L = 220 microhenry and C = 1 nF", L=220e-6, C=1e-9)

    a = Anchor("electrical", "A transformer has 500 primary turns and 50 secondary turns. With 230 V on the primary, what "
               "is the secondary voltage, in volts?", dict(Np=500, Ns=50, V=230), lambda Np, Ns, V: V * Ns / Np, "V")
    add(a, "now with 25 secondary turns", Ns=25)
    add(a, "what if the primary is 120 V?", V=120)
    add(a, "and with 1000 primary turns?", Np=1000)

    a = Anchor("electrical", "A copper wire is 50 m long with a cross-section of 1.5 mm^2. Copper's resistivity is "
               "1.68e-8 ohm m. What is the wire's resistance, in ohms?",
               dict(Lw=50, A=1.5e-6, rho=1.68e-8), lambda Lw, A, rho: rho * Lw / A, "ohm")
    add(a, "now for 120 m of it", Lw=120)
    add(a, "what about a 2.5 mm^2 wire?", A=2.5e-6)
    add(a, "and in milliohms?", unit="milliohm")
    add(a, "same but aluminium, resistivity 2.65e-8 ohm m", rho=2.65e-8)
    add(a, "if it carries 10 A, what is the voltage drop, in volts?", unit="V", value=1.68e-8 * 50 / 1.5e-6 * 10)

    a = Anchor("electrical", "A 60 W bulb runs for 5 hours. How much energy does it use, in kilojoules?",
               dict(P=60, t=5 * 3600), lambda P, t: P * t, "J", "kJ")
    add(a, "now for a 100 W bulb", P=100)
    add(a, "what if it runs 8 hours?", t=8 * 3600)
    add(a, "and in watt-hours?", unit="Wh")
    add(a, "now a 9 W LED for 12 hours", P=9, t=12 * 3600)

    # ---------------- physics (33) ----------------
    # (electrical 33, physics 33, aerospace 34: 100)
    a = Anchor("physics", "A projectile is launched at 30 m/s at 45 degrees above level ground. What is its range, in "
               "meters? Use g = 9.81 m/s^2.", dict(v=30, th=45, g=G),
               lambda v, th, g: v ** 2 * math.sin(math.radians(2 * th)) / g, "m")
    add(a, "now at 40 m/s", v=40)
    add(a, "what if the angle is 30 degrees?", th=30)
    add(a, "same on the Moon, g = 1.62 m/s^2", g=1.62)
    add(a, "and its maximum height, in meters?", value=(30 * math.sin(math.radians(45))) ** 2 / (2 * G))
    add(a, "and in kilometers?", unit="km")

    a = Anchor("physics", "An ideal gas at 300 K and 100 kPa occupies 2 m^3. It is heated at constant volume to 450 K. "
               "What is the new pressure, in kilopascals?", dict(T1=300, T2=450, p=100e3),
               lambda T1, T2, p: p * T2 / T1, "Pa", "kPa")
    add(a, "now heat it to 600 K", T2=600)
    add(a, "what if it starts at 200 kPa?", p=200e3)
    add(a, "and in bar?", unit="bar")
    add(a, "now from 250 K to 500 K", T1=250, T2=500)

    a = Anchor("physics", "A satellite orbits at 7000 km from Earth's center. Earth's GM is 3.986e14 m^3/s^2. What is "
               "its orbital speed, in meters per second?", dict(r=7.0e6, GM=3.986e14),
               lambda r, GM: math.sqrt(GM / r), "m/s")
    add(a, "now at 42164 km", r=42.164e6)
    add(a, "and in km/s?", unit="km/s")
    add(a, "what is its orbital period, in minutes?", unit="min",
        value=2 * math.pi * math.sqrt(7.0e6 ** 3 / 3.986e14) / 60)
    add(a, "same radius around Mars, GM = 4.283e13 m^3/s^2", GM=4.283e13)

    a = Anchor("physics", "How much heat raises 2 kg of water from 20 C to 80 C? Water's specific heat is 4186 J/(kg K). "
               "Answer in kilojoules.", dict(m=2, dT=60, c=4186), lambda m, dT, c: m * c * dT, "J", "kJ")
    add(a, "now for 5 kg", m=5)
    add(a, "what if it only goes to 50 C?", dT=30)
    add(a, "same for aluminium, c = 900 J/(kg K)", c=900)
    add(a, "and in kilowatt-hours?", unit="kWh")
    add(a, "now 0.5 kg from 10 C to 100 C", m=0.5, dT=90)

    a = Anchor("physics", "A 0.2 kg mass hangs on a spring of stiffness 50 N/m. What is its oscillation frequency, in "
               "hertz?", dict(m=0.2, k=50), lambda m, k: math.sqrt(k / m) / (2 * math.pi), "Hz")
    add(a, "now with a 0.8 kg mass", m=0.8)
    add(a, "what if the spring is 200 N/m?", k=200)
    add(a, "and the period, in seconds?", unit="s", value=2 * math.pi * math.sqrt(0.2 / 50))
    add(a, "now 1 kg on a 400 N/m spring", m=1, k=400)

    a = Anchor("physics", "A 3 kg block slides down a frictionless 30 degree incline. What is its acceleration, in m/s^2? "
               "Use g = 9.81 m/s^2.", dict(th=30, mu=0.0), lambda th, mu: G * (math.sin(math.radians(th)) -
                                                                              mu * math.cos(math.radians(th))), "m/s^2")
    add(a, "now at 45 degrees", th=45)
    add(a, "what if the friction coefficient is 0.2?", mu=0.2)
    add(a, "and a 6 kg block?")
    add(a, "now 20 degrees with friction 0.1", th=20, mu=0.1)

    a = Anchor("physics", "Light of wavelength 500 nm: what is the energy of one photon, in electronvolts? Use "
               "h = 6.626e-34 J s and c = 3e8 m/s.", dict(lam=500e-9), lambda lam: 6.626e-34 * 3e8 / lam, "J", "eV")
    add(a, "now for 700 nm", lam=700e-9)
    add(a, "what about 1 micrometer?", lam=1e-6)
    add(a, "and in joules?", unit="J")
    add(a, "what is its frequency, in terahertz?", unit="THz", value=3e8 / 500e-9 / 1e12)

    a = Anchor("physics", "A 0.15 kg ball moving at 40 m/s is caught and stopped in 0.02 s. What average force acts "
               "on it, in newtons?", dict(m=0.15, v=40, t=0.02), lambda m, v, t: m * v / t, "N")
    add(a, "now stopped in 0.1 s", t=0.1)
    add(a, "what if it was moving at 25 m/s?", v=25)
    add(a, "and in kilonewtons?", unit="kN")

    # ---------------- aerospace (34) ----------------
    a = Anchor("aerospace", "A 1100 kg aircraft has a wing area of 16 m^2 and a maximum lift coefficient of 1.6. What is "
               "its stall speed in air of density 1.225 kg/m^3, in meters per second? Use g = 9.81 m/s^2.",
               dict(m=1100, S=16, CL=1.6, rho=1.225), lambda m, S, CL, rho: math.sqrt(2 * m * G / (rho * S * CL)), "m/s")
    add(a, "now with flaps down, maximum lift coefficient 2.1", CL=2.1)
    add(a, "what about at altitude, where the density is 0.909 kg/m^3?", rho=0.909)
    add(a, "and in knots?", unit="knot")
    add(a, "now loaded to 1300 kg", m=1300)

    a = Anchor("aerospace", "A rocket has an initial mass of 500 t, a final mass of 150 t and an exhaust velocity of "
               "3000 m/s. What is its delta-v, in meters per second?", dict(m0=500, mf=150, ve=3000),
               lambda m0, mf, ve: ve * math.log(m0 / mf), "m/s")
    add(a, "now with a final mass of 100 t", mf=100)
    add(a, "what if the exhaust velocity is 4400 m/s?", ve=4400)
    add(a, "and in km/s?", unit="km/s")
    add(a, "what is the specific impulse, in seconds? Use g0 = 9.81 m/s^2.", unit="s", value=3000 / 9.81)
    add(a, "now 800 t to 200 t", m0=800, mf=200)

    a = Anchor("aerospace", "Air flows at 100 m/s with density 1.225 kg/m^3. What is the dynamic pressure, in "
               "kilopascals?", dict(v=100, rho=1.225), lambda v, rho: 0.5 * rho * v ** 2, "Pa", "kPa")
    add(a, "now at 250 m/s", v=250)
    add(a, "what if the density is 0.41 kg/m^3?", rho=0.41)
    add(a, "and in pascals?", unit="Pa")
    add(a, "now 200 m/s at 0.7 kg/m^3", v=200, rho=0.7)

    a = Anchor("aerospace", "A 70000 kg airliner flies level with a lift-to-drag ratio of 17. What is the drag, in "
               "kilonewtons? Use g = 9.81 m/s^2.", dict(m=70000, LD=17), lambda m, LD: m * G / LD, "N", "kN")
    add(a, "now with L/D of 20", LD=20)
    add(a, "what about an 80 t airliner?", m=80000)
    add(a, "and in newtons?", unit="N")
    add(a, "what is the lift, in kilonewtons?", value=70000 * G / 1000)

    a = Anchor("aerospace", "A propeller of 2 m diameter turns at 2400 rpm. What is the blade tip speed from rotation "
               "alone, in meters per second?", dict(D=2, n=2400), lambda D, n: math.pi * D * n / 60, "m/s")
    add(a, "now at 2700 rpm", n=2700)
    add(a, "what if the diameter is 2.5 m?", D=2.5)
    add(a, "and in km/h?", unit="km/h")
    add(a, "what tip Mach number is that, with sound at 340 m/s?", unit="", value=math.pi * 2 * 2400 / 60 / 340)

    a = Anchor("aerospace", "What is the speed of sound in air at 288 K, in meters per second? Use gamma = 1.4 and "
               "R = 287 J/(kg K).", dict(T=288, gam=1.4, R=287), lambda T, gam, R: math.sqrt(gam * R * T), "m/s")
    add(a, "now at 220 K", T=220)
    add(a, "same in helium, gamma 1.667 and R = 2077 J/(kg K)", gam=1.667, R=2077)
    add(a, "and in km/h?", unit="km/h")
    add(a, "a plane at 250 m/s there: what Mach number?", unit="", value=250 / math.sqrt(1.4 * 287 * 288))

    a = Anchor("aerospace", "An aircraft turns level at 100 m/s with a bank angle of 30 degrees. What is the turn radius, "
               "in meters? Use g = 9.81 m/s^2.", dict(v=100, phi=30),
               lambda v, phi: v ** 2 / (G * math.tan(math.radians(phi))), "m")
    add(a, "now at 60 degrees bank", phi=60)
    add(a, "what if it flies 150 m/s?", v=150)
    add(a, "and in kilometers?", unit="km")
    add(a, "what is the load factor?", unit="", value=1 / math.cos(math.radians(30)))
    add(a, "now 80 m/s at 45 degrees", v=80, phi=45)

    a = Anchor("aerospace", "A jet engine takes in 100 kg/s of air at 250 m/s and exhausts it at 600 m/s. Ignoring fuel "
               "mass, what is the thrust, in kilonewtons?", dict(mdot=100, v0=250, ve=600),
               lambda mdot, v0, ve: mdot * (ve - v0), "N", "kN")
    add(a, "now at 150 kg/s", mdot=150)
    add(a, "what if the exhaust is 700 m/s?", ve=700)
    add(a, "and on the ground, with intake at 0 m/s?", v0=0)
    add(a, "and in newtons?", unit="N")
    return out


def main():
    rows = cases()
    (Path(__file__).parent / "cases2.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    by = {}
    for r in rows:
        by[r["pack"]] = by.get(r["pack"], 0) + 1
    print(f"wrote {len(rows)} cases", by)


if __name__ == "__main__":
    main()
