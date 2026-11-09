"""Follow-up conversations with answer keys, for FOLLOWUP_ANSWER_RULE (evals/followup/run.py).

    .venv/bin/python evals/followup/build.py      # writes evals/followup/cases.jsonl

Written 2026-11-08 night, before either wording was run on them. Each case: an anchor question, the anchor's
correct answer as the assistant's reply, a follow-up that changes it, and the follow-up's answer (value, unit,
rel_tol 2%), computed here.
"""

import json
import math
from pathlib import Path

G = 9.81


def cases():
    out = []

    def add(pack, anchor, reply, follow, value, unit):
        out.append({"id": f"fa-{len(out) + 1:02d}", "pack": pack, "messages": [
            {"role": "user", "content": anchor}, {"role": "assistant", "content": reply},
            {"role": "user", "content": follow}], "answer": value, "unit": unit, "rel_tol": 0.02})

    E1 = "A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?"
    add("electrical", E1, "22 V", "now for 200 ohm", 20, "V")
    add("electrical", E1, "22 V", "What if the current doubles?", 44, "V")
    add("electrical", E1, "22 V", "and in millivolts?", 22000, "mV")
    add("electrical", E1, "22 V", "what about a 1 kilohm resistor?", 100, "V")
    E2 = "A 12 V battery drives current through a 4 ohm resistor. What power does the resistor dissipate, in watts?"
    add("electrical", E2, "36 W", "now with a 6 ohm resistor", 24, "W")
    add("electrical", E2, "36 W", "what if the battery is 24 V instead?", 144, "W")
    add("electrical", E2, "36 W", "and how much current flows, in amperes?", 3, "A")
    E3 = "A 100 microfarad capacitor is charged to 50 V. How much energy does it store, in joules?"
    add("electrical", E3, "0.125 J", "now charge it to 100 V", 0.5, "J")
    add("electrical", E3, "0.125 J", "same but with a 470 microfarad capacitor", 0.5875, "J")
    E4 = "An RC circuit has R = 10 kilohm and C = 1 microfarad. What is its time constant, in milliseconds?"
    add("electrical", E4, "10 ms", "now with R = 47 kilohm", 47, "ms")
    add("electrical", E4, "10 ms", "what if C is 220 nanofarad instead?", 2.2, "ms")
    E5 = "Three 30 ohm resistors are connected in parallel. What is the equivalent resistance, in ohms?"
    add("electrical", E5, "10 ohm", "what about four of them?", 7.5, "ohm")
    add("electrical", E5, "10 ohm", "and if they're in series instead?", 90, "ohm")
    P1 = "A ball is dropped from 20 m. What is its speed just before it hits the ground, in meters per second? Use g = 9.81 m/s^2."
    add("physics", P1, "19.81 m/s", "now from 45 m", math.sqrt(2 * G * 45), "m/s")
    add("physics", P1, "19.81 m/s", "same but on the Moon, g = 1.62 m/s^2", math.sqrt(2 * 1.62 * 20), "m/s")
    add("physics", P1, "19.81 m/s", "and in km/h?", math.sqrt(2 * G * 20) * 3.6, "km/h")
    P2 = "A 1200 kg car accelerates at 2.5 m/s^2. What net force acts on it, in newtons?"
    add("physics", P2, "3000 N", "now for a 1500 kg car", 3750, "N")
    add("physics", P2, "3000 N", "what if it accelerates at 4 m/s^2?", 4800, "N")
    add("physics", P2, "3000 N", "and in kilonewtons?", 3.0, "kN")
    P3 = "A spring with stiffness 200 N/m is compressed 0.05 m. How much energy does it store, in joules?"
    add("physics", P3, "0.25 J", "now compress it 0.1 m", 1.0, "J")
    add("physics", P3, "0.25 J", "same with a 500 N/m spring", 0.625, "J")
    P4 = "A pendulum is 1.5 m long. What is its period, in seconds? Use g = 9.81 m/s^2."
    add("physics", P4, "2.457 s", "now make it 0.5 m long", 2 * math.pi * math.sqrt(0.5 / G), "s")
    add("physics", P4, "2.457 s", "what if it swings on Mars, where g = 3.71 m/s^2?", 2 * math.pi * math.sqrt(1.5 / 3.71), "s")
    P5 = "A 5 kg box is lifted 3 m. How much potential energy does it gain, in joules? Use g = 9.81 m/s^2."
    add("physics", P5, "147.2 J", "now lift it 10 m", 5 * G * 10, "J")
    add("physics", P5, "147.2 J", "what about a 12 kg box?", 12 * G * 3, "J")
    add("physics", P5, "147.2 J", "and in kilojoules?", 5 * G * 3 / 1000, "kJ")
    P6 = "A car travels at 25 m/s. What is the kinetic energy of the 1000 kg car, in kilojoules?"
    add("physics", P6, "312.5 kJ", "now at 30 m/s", 450, "kJ")
    add("physics", P6, "312.5 kJ", "what if the car weighs 1500 kg?", 468.75, "kJ")
    A1 = "An aircraft flies at 250 m/s where the speed of sound is 295 m/s. What is its Mach number?"
    add("aerospace", A1, "0.847", "now at 280 m/s", 280 / 295, "")
    add("aerospace", A1, "0.847", "what if the speed of sound is 340 m/s instead?", 250 / 340, "")
    A2 = ("A wing of 20 m^2 with a lift coefficient of 0.5 flies at 60 m/s in air of density 1.225 kg/m^3. "
          "What lift does it produce, in newtons?")
    add("aerospace", A2, "22050 N", "now at 80 m/s", 0.5 * 1.225 * 80 ** 2 * 20 * 0.5, "N")
    add("aerospace", A2, "22050 N", "same with a lift coefficient of 1.2", 0.5 * 1.225 * 60 ** 2 * 20 * 1.2, "N")
    add("aerospace", A2, "22050 N", "and in kilonewtons?", 22.05, "kN")
    A3 = "A rocket engine has an exhaust velocity of 3000 m/s and burns 50 kg/s of propellant. What is its thrust, in kilonewtons?"
    add("aerospace", A3, "150 kN", "now burning 80 kg/s", 240, "kN")
    add("aerospace", A3, "150 kN", "what if the exhaust velocity is 4400 m/s?", 220, "kN")
    add("aerospace", A3, "150 kN", "and in newtons?", 150000, "N")
    return out


def main():
    rows = cases()
    (Path(__file__).parent / "cases.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"wrote {len(rows)} cases")


if __name__ == "__main__":
    main()
