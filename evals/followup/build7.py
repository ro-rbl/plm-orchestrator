"""Follow-up conversations, set 7 (held out): LONGER conversations, for FOLLOWUP7_RULE (evals/followup/run7.py).

    .venv/bin/python evals/followup/build7.py      # writes evals/followup/cases7.jsonl

Written 2026-11-13, before any model answered them. Sets 1-6 are seen, and every one of their conversations has
three messages. Seen live on 2026-11-13: after a question and "now a 60 W lamp", a third message ("how much energy
does it use in 3 hours, in watt-hours?") was solved alone. Here each conversation has two or three follow-ups; only
the last message is graded, and every earlier reply is the key of its own turn. Changes accumulate ("now 10 A",
then "what if it is 20 ohm?" means 10 A and 20 ohm). New anchors; keys from each anchor's formula, converted with
pint. Kinds (for reporting only), named by the follow-ups in order:
    vv   a changed value, then another changed value
    vq   a changed value, then a new quantity of the changed setup
    vu   a changed value, then the same answer in another unit
    vvq  two changed values, then a new quantity          (vvu for the one anchor with no second quantity)
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from build2 import Anchor, fmt, ureg  # noqa: E402

G = 9.81


def cases():
    out = []

    def chain(a, ch1, ch2, alt_unit, quantity=None):
        """ch1, ch2: (text, {param: value}); alt_unit: (text, unit); quantity: (text, fn(**params), unit)."""
        (t1, p1), (t2, p2), (tu, unit) = ch1, ch2, alt_unit

        def said(value, u):  # a reply as a person would read it: 10730 MWh, not 1.073e+04 MW*h
            number = fmt(value) if "e" not in fmt(value) else f"{float(fmt(value)):.0f}"
            return f"{number} {u.replace('*h', 'h')}".strip()

        def conv(kind, turns, key, key_unit):
            msgs = [{"role": "user", "content": a.text}, {"role": "assistant", "content": said(a.value(), a.out_unit)}]
            for text, reply in turns[:-1]:
                msgs += [{"role": "user", "content": text}, {"role": "assistant", "content": reply}]
            msgs.append({"role": "user", "content": turns[-1][0]})
            out.append({"id": f"f7-{len(out) + 1:03d}", "pack": a.pack, "kind": kind, "messages": msgs,
                        "answer": key, "unit": key_unit, "rel_tol": 0.02})

        v1 = said(a.value(**p1), a.out_unit)
        v2 = said(a.value(**p2), a.out_unit)
        v12 = said(a.value(**p1, **p2), a.out_unit)
        conv("vv", [(t1, v1), (t2, None)], a.value(**p1, **p2), a.out_unit)
        conv("vu", [(t2, v2), (tu, None)], a.value(unit, **p2), unit)
        if quantity:
            tq, fq, uq = quantity
            conv("vq", [(t1, v1), (tq, None)], fq(**(a.params | p1)), uq)
            conv("vvq", [(t1, v1), (t2, v12), (tq, None)], fq(**(a.params | p1 | p2)), uq)
        else:
            conv("vvu", [(t1, v1), (t2, v12), (tu, None)], a.value(unit, **p1, **p2), unit)

    # ---------------- electrical ----------------
    chain(Anchor("electrical", "A 15 ohm heating element carries 8 A for 10 minutes. How much heat does it produce, in "
                 "kilojoules?", dict(R=15, I=8, t=600), lambda R, I, t: I ** 2 * R * t, "J", "kJ"),
          ("now carrying 12 A", dict(I=12)), ("what if the element is 25 ohm?", dict(R=25)),
          ("and in megajoules?", "MJ"),
          ("what is the voltage across the element, in volts?", lambda R, I, t: I * R, "V"))
    chain(Anchor("electrical", "A 230 V, 50 Hz supply feeds a series circuit of a 40 ohm resistor and an inductive "
                 "reactance of 30 ohm. What current flows, in amperes?", dict(V=230, R=40, X=30),
                 lambda V, R, X: V / math.hypot(R, X), "A"),
          ("now with a 120 V supply", dict(V=120)), ("what if the resistor is 16 ohm?", dict(R=16)),
          ("and in milliamperes?", "mA"),
          ("what real power does the circuit take, in watts?", lambda V, R, X: (V / math.hypot(R, X)) ** 2 * R, "W"))
    chain(Anchor("electrical", "A phone battery holds 4 Ah at 3.8 V. How much energy does it store, in watt-hours?",
                 dict(Q=4, V=3.8), lambda Q, V: Q * V, "W*h"),
          ("now a 5.5 Ah battery", dict(Q=5.5)), ("what if it is a 7.4 V pack?", dict(V=7.4)),
          ("and in kilojoules?", "kJ"),
          ("how long can it run a steady 2 W load, in hours?", lambda Q, V: Q * V / 2, "hour"))
    chain(Anchor("electrical", "Four cells in series, each 1.5 V with an internal resistance of 0.3 ohm, drive a 4.8 ohm "
                 "load. What current flows, in amperes?", dict(n=4, r=0.3, R=4.8), lambda n, r, R: n * 1.5 / (n * r + R), "A"),
          ("now with six cells", dict(n=6)), ("what if the load is 10 ohm?", dict(R=10)),
          ("and in milliamperes?", "mA"),
          ("what is the voltage across the load, in volts?", lambda n, r, R: n * 1.5 / (n * r + R) * R, "V"))
    chain(Anchor("electrical", "An LED strip draws 2.5 A at 12 V and is on for 6 hours a day. How much energy does it use "
                 "per day, in watt-hours?", dict(I=2.5, V=12, h=6), lambda I, V, h: I * V * h, "W*h"),
          ("now drawing 4 A", dict(I=4)), ("what if it is on for 9 hours a day?", dict(h=9)),
          ("and in kilojoules?", "kJ"),
          ("how much is that over a 30-day month, in kilowatt-hours?", lambda I, V, h: I * V * h * 30 / 1000, "kWh"))
    chain(Anchor("electrical", "A 2 MW wind turbine runs at a capacity factor of 0.35. How much energy does it produce "
                 "in a year of 8760 hours, in megawatt-hours?", dict(P=2, cf=0.35), lambda P, cf: P * cf * 8760, "MW*h"),
          ("now a 3.5 MW turbine", dict(P=3.5)), ("what if the capacity factor is 0.42?", dict(cf=0.42)),
          ("and in gigawatt-hours?", "GW*h"),
          ("what is its average power output, in kilowatts?", lambda P, cf: P * cf * 1000, "kW"))
    chain(Anchor("electrical", "A 5 kilohm resistor carries 2 mA. What power does it dissipate, in milliwatts?",
                 dict(R=5000, I=0.002), lambda R, I: I ** 2 * R, "W", "mW"),
          ("now carrying 6 mA", dict(I=0.006)), ("what if it is a 12 kilohm resistor?", dict(R=12000)),
          ("and in watts?", "W"),
          ("what is the voltage across it, in volts?", lambda R, I: I * R, "V"))

    # ---------------- physics ----------------
    chain(Anchor("physics", "A ball is thrown horizontally at 12 m/s from the top of a 20 m high cliff. How far from the "
                 "base of the cliff does it land, in meters? Use g = 9.81 m/s^2.", dict(v=12, h=20),
                 lambda v, h: v * math.sqrt(2 * h / G), "m"),
          ("now thrown at 18 m/s", dict(v=18)), ("what if the cliff is 45 m high?", dict(h=45)),
          ("and in centimeters?", "cm"),
          ("how long is it in the air, in seconds?", lambda v, h: math.sqrt(2 * h / G), "s"))
    chain(Anchor("physics", "A 900 kg elevator accelerates upward at 1.5 m/s^2. What is the tension in its cable, in "
                 "newtons? Use g = 9.81 m/s^2.", dict(m=900, a=1.5), lambda m, a: m * (G + a), "N"),
          ("now with a 1400 kg elevator", dict(m=1400)), ("what if it accelerates at 0.8 m/s^2?", dict(a=0.8)),
          ("and in kilonewtons?", "kN"),
          ("what power does the cable deliver when the elevator is moving at 2 m/s, in kilowatts?",
           lambda m, a: m * (G + a) * 2 / 1000, "kW"))
    chain(Anchor("physics", "How much heat melts 2 kg of ice at 0 °C and then warms the water to 30 °C, in kilojoules? "
                 "Use a latent heat of 334 kJ/kg and a specific heat of 4.186 kJ/(kg K).", dict(m=2, T=30),
                 lambda m, T: m * (334 + 4.186 * T), "kJ"),
          ("now for 5 kg of ice", dict(m=5)), ("what if the water is warmed to 60 °C?", dict(T=60)),
          ("and in megajoules?", "MJ"),
          ("with a 1.5 kW heater, how long does that take, in minutes?",
           lambda m, T: m * (334 + 4.186 * T) / 1.5 / 60, "minute"))
    chain(Anchor("physics", "A 5 kg mass hung from a spring stretches it by 4 cm. What is the spring constant, in N/m? "
                 "Use g = 9.81 m/s^2.", dict(m=5, x=0.04), lambda m, x: m * G / x, "N/m"),
          ("now with an 8 kg mass", dict(m=8)), ("what if it stretches by 10 cm?", dict(x=0.10)),
          ("and in N/cm?", "N/cm"),
          ("what is the period of oscillation of that mass on the spring, in seconds?",
           lambda m, x: 2 * math.pi * math.sqrt(x / G), "s"))
    chain(Anchor("physics", "A 60 kg sprinter reaches 9 m/s from rest in 3 s. What average power does that take, in "
                 "watts?", dict(m=60, v=9, t=3), lambda m, v, t: 0.5 * m * v ** 2 / t, "W"),
          ("now for an 80 kg sprinter", dict(m=80)), ("what if it takes 4.5 s?", dict(t=4.5)),
          ("and in kilowatts?", "kW"),
          ("what average net force accelerates the sprinter, in newtons?", lambda m, v, t: m * v / t, "N"))
    chain(Anchor("physics", "A cylinder with a 0.2 m diameter piston contains gas at 300 kPa. What force does the gas "
                 "exert on the piston, in kilonewtons?", dict(p=300e3, d=0.2), lambda p, d: p * math.pi * d ** 2 / 4, "N", "kN"),
          ("now at 450 kPa", dict(p=450e3)), ("what if the piston diameter is 0.35 m?", dict(d=0.35)),
          ("and in newtons?", "N"),
          ("how much work does the gas do if the piston moves 0.15 m at that pressure, in joules?",
           lambda p, d: p * math.pi * d ** 2 / 4 * 0.15, "J"))
    chain(Anchor("physics", "A 40 kg child sits 1.5 m from the pivot of a seesaw. How far from the pivot must a 60 kg "
                 "adult sit to balance it, in meters?", dict(m1=40, d=1.5, m2=60), lambda m1, d, m2: m1 * d / m2, "m"),
          ("now with the child 2.1 m from the pivot", dict(d=2.1)), ("what if the adult is 70 kg?", dict(m2=70)),
          ("and in centimeters?", "cm"))

    # ---------------- aerospace ----------------
    chain(Anchor("aerospace", "An aircraft flies a complete level turn at 90 m/s with a turn radius of 1200 m. How long "
                 "does the full 360 degree turn take, in seconds?", dict(v=90, r=1200), lambda v, r: 2 * math.pi * r / v, "s"),
          ("now at 130 m/s", dict(v=130)), ("what if the turn radius is 2000 m?", dict(r=2000)),
          ("and in minutes?", "minute"),
          ("what is the centripetal acceleration in the turn, in m/s^2?", lambda v, r: v ** 2 / r, "m/s^2"))
    chain(Anchor("aerospace", "A rocket stage burns 1200 kg of propellant at a steady 15 kg/s with an exhaust velocity "
                 "of 2800 m/s. How long does the burn last, in seconds?", dict(m=1200, mdot=15), lambda m, mdot: m / mdot, "s"),
          ("now with 3000 kg of propellant", dict(m=3000)), ("what if it burns 25 kg/s?", dict(mdot=25)),
          ("and in minutes?", "minute"),
          ("what thrust does the stage produce, in kilonewtons?", lambda m, mdot: mdot * 2800 / 1000, "kN"))
    chain(Anchor("aerospace", "A 3200 kg helicopter hovers on a rotor of 14 m diameter. What is its disk loading, in "
                 "N/m^2? Use g = 9.81 m/s^2.", dict(m=3200, d=14), lambda m, d: m * G / (math.pi * d ** 2 / 4), "N/m^2"),
          ("now at 4500 kg", dict(m=4500)), ("what if the rotor diameter is 11 m?", dict(d=11)),
          ("and in kilopascals?", "kPa"),
          ("what is the rotor disk area, in m^2?", lambda m, d: math.pi * d ** 2 / 4, "m^2"))
    chain(Anchor("aerospace", "An airliner cruises at 240 m/s burning 2.6 kg/s of fuel. How far does it fly on 30000 kg "
                 "of fuel, in kilometers?", dict(v=240, mdot=2.6, m=30000), lambda v, mdot, m: v * m / mdot, "m", "km"),
          ("now with 45000 kg of fuel", dict(m=45000)), ("what if it burns 3.4 kg/s?", dict(mdot=3.4)),
          ("and in nautical miles?", "nautical_mile"),
          ("how long does that fuel last, in hours?", lambda v, mdot, m: m / mdot / 3600, "hour"))
    chain(Anchor("aerospace", "A space station orbits at 7.66 km/s on a circle of radius 6780 km. What is its "
                 "centripetal acceleration, in m/s^2?", dict(v=7660, r=6780e3), lambda v, r: v ** 2 / r, "m/s^2"),
          ("now at 7.35 km/s", dict(v=7350)), ("what if the radius is 7378 km?", dict(r=7378e3)),
          ("and as a multiple of g = 9.81 m/s^2?", "standard_gravity"),
          ("how long does one orbit take, in minutes?", lambda v, r: 2 * math.pi * r / v / 60, "minute"))
    chain(Anchor("aerospace", "A 450 kg glider descends at a sink rate of 0.8 m/s while flying at 28 m/s. What power "
                 "does gravity supply to keep it flying, in watts? Use g = 9.81 m/s^2.", dict(m=450, s=0.8),
                 lambda m, s: m * G * s, "W"),
          ("now with a 600 kg glider", dict(m=600)), ("what if the sink rate is 1.4 m/s?", dict(s=1.4)),
          ("and in kilowatts?", "kW"),
          ("what is its glide ratio?", lambda m, s: 28 / s, ""))
    chain(Anchor("aerospace", "A wind tunnel with a test section of 1.2 m^2 runs air of density 1.2 kg/m^3 at 60 m/s. "
                 "What is the mass flow through the test section, in kg/s?", dict(A=1.2, v=60), lambda A, v: 1.2 * A * v, "kg/s"),
          ("now at 95 m/s", dict(v=95)), ("what if the test section is 2.5 m^2?", dict(A=2.5)),
          ("and in tonnes per hour?", "t/hour"),
          ("what is the volume flow, in m^3/s?", lambda A, v: A * v, "m^3/s"))
    # the multiple-of-g key is a pure number: 1 standard_gravity is 9.80665, the question says 9.81 (0.03% apart)
    for r in out:
        if r["unit"] == "standard_gravity":
            r["answer"], r["unit"] = r["answer"] * ureg.Quantity(1, "standard_gravity").to("m/s^2").magnitude / G, ""
    return out


def main():
    rows = cases()
    (Path(__file__).parent / "cases7.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    by = {}
    for r in rows:
        by[r["pack"]] = by.get(r["pack"], 0) + 1
        by[r["kind"]] = by.get(r["kind"], 0) + 1
        by[f"{len(r['messages'])} messages"] = by.get(f"{len(r['messages'])} messages", 0) + 1
    print(f"wrote {len(rows)} cases", by)


if __name__ == "__main__":
    main()
