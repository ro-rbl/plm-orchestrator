"""Source of truth for the electrical eval set.

Answers are computed here, never hand-typed, so the arithmetic in the key is
always right. Run this to regenerate problems.jsonl:

    .venv/bin/python evals/electrical/build_problems.py

Levels map to the controller's adrenaline states:
    calm      - one formula or one known constant
    alert     - one calculation that needs a formula plus a few numbers
    intensive - multi-step: circuit reduction, unit chains, sizing decisions
"""

import json
import math
from pathlib import Path

PI = math.pi

# (id, level, topic, question, answer, unit, rel_tol, solution)
# unit is a pint unit string, or one of grade.LITERAL_UNITS ("" = unitless).
PROBLEMS = [
    # ---------------- calm ----------------
    ("ee-c01", "calm", "ac", "A sinusoidal voltage has a peak value of 170 V. What is its RMS value in volts?",
     170 / math.sqrt(2), "V", 0.01, "Vrms = Vpeak / sqrt(2)"),
    ("ee-c02", "calm", "ohms-law", "A 12 V source is connected across a 4 ohm resistor. What current flows, in amperes?",
     12 / 4, "A", 0.01, "I = V / R"),
    ("ee-c03", "calm", "power", "A current of 5 A flows through a 10 ohm resistor. How much power does the resistor dissipate, in watts?",
     5**2 * 10, "W", 0.01, "P = I^2 R"),
    ("ee-c04", "calm", "resistor-networks", "Resistors of 100 ohm, 220 ohm and 330 ohm are connected in series. What is the total resistance in ohms?",
     100 + 220 + 330, "ohm", 0.01, "Series: R = R1 + R2 + R3"),
    ("ee-c05", "calm", "resistor-networks", "Two 1 kilohm resistors are connected in parallel. What is the equivalent resistance in ohms?",
     1 / (1 / 1000 + 1 / 1000), "ohm", 0.01, "Parallel: R = R1 R2 / (R1 + R2)"),
    ("ee-c06", "calm", "reactance", "What is the reactance of a 10 microfarad capacitor at 60 Hz, in ohms?",
     1 / (2 * PI * 60 * 10e-6), "ohm", 0.01, "Xc = 1 / (2 pi f C)"),
    ("ee-c07", "calm", "reactance", "What is the reactance of a 50 millihenry inductor at 1 kHz, in ohms?",
     2 * PI * 1000 * 50e-3, "ohm", 0.01, "XL = 2 pi f L"),
    ("ee-c08", "calm", "energy", "A 100 microfarad capacitor is charged to 50 V. How much energy does it store, in joules?",
     0.5 * 100e-6 * 50**2, "J", 0.01, "E = C V^2 / 2"),
    ("ee-c09", "calm", "charge", "A steady current of 2 A flows for 30 seconds. How much charge passes, in coulombs?",
     2 * 30, "C", 0.01, "Q = I t"),
    ("ee-c10", "calm", "ac", "A periodic signal has a period of 2.5 ms. What is its frequency in hertz?",
     1 / 2.5e-3, "Hz", 0.01, "f = 1 / T"),
    ("ee-c11", "calm", "constants", "What is the elementary charge (the magnitude of the charge on one electron), in coulombs?",
     1.602176634e-19, "C", 0.005, "Defined SI constant"),
    ("ee-c12", "calm", "constants", "What is the resistivity of annealed copper at 20 degrees C, in ohm-meters?",
     1.68e-8, "ohm*m", 0.03, "Handbook value ~1.68e-8 ohm*m (1.72e-8 IACS also accepted)"),
    ("ee-c13", "calm", "decibels", "An amplifier has a power gain of 100 (output power / input power). What is the gain in decibels?",
     10 * math.log10(100), "dB", 0.01, "G_dB = 10 log10(Pout/Pin)"),
    ("ee-c14", "calm", "energy", "A 1500 W heater runs for 3 hours. How much energy does it use, in kilowatt-hours?",
     1.5 * 3, "kWh", 0.01, "E = P t"),
    ("ee-c15", "calm", "ohms-law", "What is the conductance of a 250 ohm resistor, in millisiemens?",
     1 / 250 * 1000, "mS", 0.01, "G = 1 / R"),

    # ---------------- alert ----------------
    ("ee-a01", "alert", "voltage-divider", "A 9 V supply feeds a voltage divider: R1 = 10 kilohm on top, R2 = 4.7 kilohm to ground. What is the output voltage across R2, in volts (unloaded)?",
     9 * 4.7 / (10 + 4.7), "V", 0.01, "Vout = Vin R2 / (R1 + R2)"),
    ("ee-a02", "alert", "resistor-networks", "Resistors of 100 ohm, 220 ohm and 470 ohm are connected in parallel. What is the equivalent resistance in ohms?",
     1 / (1 / 100 + 1 / 220 + 1 / 470), "ohm", 0.01, "1/R = sum(1/Ri)"),
    ("ee-a03", "alert", "transients", "What is the time constant of an RC circuit with R = 47 kilohm and C = 22 microfarad, in seconds?",
     47e3 * 22e-6, "s", 0.01, "tau = R C"),
    ("ee-a04", "alert", "transients", "A discharged 100 microfarad capacitor is charged from a 5 V source through a 10 kilohm resistor. What is the capacitor voltage 0.5 s after the switch closes, in volts?",
     5 * (1 - math.exp(-0.5 / (10e3 * 100e-6))), "V", 0.01, "Vc = Vs (1 - e^(-t/RC)), RC = 1 s"),
    ("ee-a05", "alert", "practical", "An LED with a forward voltage of 2.0 V should run at 20 mA from a 5 V supply. What series resistor is needed, in ohms?",
     (5 - 2.0) / 0.020, "ohm", 0.01, "R = (Vs - Vf) / I"),
    ("ee-a06", "alert", "wiring", "A copper wire is 100 m long with a cross-section of 1.5 square millimeters. Using a resistivity of 1.68e-8 ohm-meters, what is its resistance in ohms?",
     1.68e-8 * 100 / 1.5e-6, "ohm", 0.01, "R = rho L / A"),
    ("ee-a07", "alert", "filters", "An RC low-pass filter uses R = 1.6 kilohm and C = 100 nanofarad. What is its -3 dB cutoff frequency in hertz?",
     1 / (2 * PI * 1.6e3 * 100e-9), "Hz", 0.01, "fc = 1 / (2 pi R C)"),
    ("ee-a08", "alert", "resonance", "What is the resonant frequency of an LC circuit with L = 10 millihenry and C = 100 nanofarad, in hertz?",
     1 / (2 * PI * math.sqrt(10e-3 * 100e-9)), "Hz", 0.01, "f0 = 1 / (2 pi sqrt(L C))"),
    ("ee-a09", "alert", "transformers", "An ideal transformer has 500 primary turns and 25 secondary turns. The primary is fed with 120 V RMS. What is the secondary voltage in volts RMS?",
     120 * 25 / 500, "V", 0.01, "Vs = Vp Ns / Np"),
    ("ee-a10", "alert", "op-amps", "An ideal inverting op-amp amplifier has Rin = 4.7 kilohm and Rf = 47 kilohm. The input is 0.2 V DC. What is the output voltage in volts (include the sign)?",
     -47 / 4.7 * 0.2, "V", 0.01, "Vout = -(Rf/Rin) Vin"),
    ("ee-a11", "alert", "op-amps", "An ideal non-inverting op-amp amplifier has Rf = 90 kilohm and Rg = 10 kilohm. The input is 0.5 V DC. What is the output voltage in volts?",
     (1 + 90 / 10) * 0.5, "V", 0.01, "Vout = (1 + Rf/Rg) Vin"),
    ("ee-a12", "alert", "batteries", "A 2000 mAh battery powers a device drawing an average of 150 mA. Ignoring losses, how long does it last, in hours?",
     2000 / 150, "h", 0.01, "t = capacity / current"),
    ("ee-a13", "alert", "power-factor", "A load draws 800 W of real power and 1000 VA of apparent power. What is its power factor (unitless)?",
     800 / 1000, "", 0.01, "PF = P / S"),
    ("ee-a14", "alert", "impedance", "A series circuit has a resistance of 30 ohm and an inductive reactance of 40 ohm. What is the magnitude of its impedance in ohms?",
     math.hypot(30, 40), "ohm", 0.01, "|Z| = sqrt(R^2 + X^2)"),
    ("ee-a15", "alert", "power", "A 529 ohm resistive heater is connected to 230 V RMS. How much power does it dissipate, in watts?",
     230**2 / 529, "W", 0.01, "P = V^2 / R"),
    ("ee-a16", "alert", "capacitor-networks", "A 10 microfarad and a 15 microfarad capacitor are connected in series. What is the equivalent capacitance in microfarads?",
     1 / (1 / 10 + 1 / 15), "uF", 0.01, "Series: C = C1 C2 / (C1 + C2)"),
    ("ee-a17", "alert", "decibels", "An amplifier's output voltage is 50 times its input voltage (same impedance). What is the voltage gain in decibels?",
     20 * math.log10(50), "dB", 0.01, "G_dB = 20 log10(Vout/Vin)"),
    ("ee-a18", "alert", "three-phase", "A balanced wye-connected three-phase system has a phase (line-to-neutral) voltage of 230 V. What is the line-to-line voltage in volts?",
     230 * math.sqrt(3), "V", 0.01, "VLL = sqrt(3) VLN"),
    ("ee-a19", "alert", "power", "A 60 W lamp runs on 120 V. What current does it draw, in amperes?",
     60 / 120, "A", 0.01, "I = P / V"),
    ("ee-a20", "alert", "transients", "What is the time constant of an RL circuit with L = 200 millihenry and R = 50 ohm, in milliseconds?",
     200e-3 / 50 * 1000, "ms", 0.01, "tau = L / R"),

    # ---------------- intensive ----------------
    ("ee-i01", "intensive", "thevenin", "A 12 V source in series with R1 = 4 ohm feeds a node; R2 = 12 ohm runs from that node to ground. A load RL = 6 ohm is connected from the same node to ground. What current flows through RL, in amperes?",
     (12 * 12 / 16) / ((4 * 12 / 16) + 6), "A", 0.01, "Vth = 12*12/16 = 9 V, Rth = 4||12 = 3 ohm, I = 9 / (3 + 6)"),
    ("ee-i02", "intensive", "thevenin", "For the same circuit (12 V source, R1 = 4 ohm series, R2 = 12 ohm to ground), what is the maximum power that can be delivered to a load connected across R2, in watts?",
     (12 * 12 / 16) ** 2 / (4 * (4 * 12 / 16)), "W", 0.01, "Pmax = Vth^2 / (4 Rth) = 81 / 12"),
    ("ee-i03", "intensive", "ac-circuits", "A series RLC circuit with R = 100 ohm, L = 0.5 H and C = 10 microfarad is driven by 120 V RMS at 60 Hz. What is the RMS current in amperes?",
     120 / math.hypot(100, 2 * PI * 60 * 0.5 - 1 / (2 * PI * 60 * 10e-6)), "A", 0.01, "XL = 188.5, Xc = 265.3, |Z| = sqrt(100^2 + (XL - Xc)^2), I = V / |Z|"),
    ("ee-i04", "intensive", "power-factor", "A single-phase 230 V, 50 Hz load draws 10 kW at a power factor of 0.70 lagging. What parallel capacitance is needed to raise the power factor to 0.95 lagging, in microfarads?",
     (10e3 * (math.tan(math.acos(0.70)) - math.tan(math.acos(0.95)))) / (2 * PI * 50 * 230**2) * 1e6, "uF", 0.01,
     "Qc = P (tan(acos 0.70) - tan(acos 0.95)), C = Qc / (2 pi f V^2)"),
    ("ee-i05", "intensive", "bridges", "A Wheatstone bridge is fed by 10 V. Left arm: R1 = 100 ohm (top) and R2 = 200 ohm (bottom). Right arm: R3 = 150 ohm (top) and R4 = 250 ohm (bottom). The bottom of both arms is ground. What is the voltage of the left midpoint minus the right midpoint, in volts?",
     10 * 200 / 300 - 10 * 250 / 400, "V", 0.01, "Va = 10*200/300, Vb = 10*250/400, Va - Vb"),
    ("ee-i06", "intensive", "three-phase", "A balanced three-phase load is supplied at 400 V line-to-line with a line current of 25 A and a power factor of 0.85. What is the total real power in watts?",
     math.sqrt(3) * 400 * 25 * 0.85, "W", 0.01, "P = sqrt(3) VLL IL PF"),
    ("ee-i07", "intensive", "practical", "A 12 V battery with 0.05 ohm internal resistance powers a 2 ohm load through a cable whose two conductors are 0.1 ohm each. How much power reaches the load, in watts?",
     (12 / (0.05 + 0.1 + 0.1 + 2)) ** 2 * 2, "W", 0.01, "I = 12 / 2.25, P = I^2 * 2"),
    ("ee-i08", "intensive", "op-amps", "A 50 mV DC signal passes through an ideal inverting stage with gain -10, then an ideal non-inverting stage with Rf = 20 kilohm and Rg = 10 kilohm. What is the final output voltage in volts (include the sign)?",
     0.050 * -10 * (1 + 20 / 10), "V", 0.01, "Stage 2 gain = 1 + 20/10 = 3, Vout = 0.05 * -10 * 3"),
    ("ee-i09", "intensive", "transients", "A 470 microfarad capacitor charged to 12 V discharges through a 1 kilohm resistor. How long until its voltage falls to 3 V, in seconds?",
     1e3 * 470e-6 * math.log(12 / 3), "s", 0.01, "t = RC ln(V0 / V)"),
    ("ee-i10", "intensive", "nodal-analysis", "Node A connects to a 10 V source through 5 ohm, to a 5 V source through 10 ohm, and to ground through 10 ohm. Both sources are referenced to ground. What is the voltage at node A, in volts?",
     (10 / 5 + 5 / 10) / (1 / 5 + 1 / 10 + 1 / 10), "V", 0.01, "KCL: (VA-10)/5 + (VA-5)/10 + VA/10 = 0"),
    ("ee-i11", "intensive", "batteries", "A device draws 3 W and must run 20 hours. It is powered through a converter with 85% efficiency from 3.7 V, 2500 mAh lithium cells. What is the minimum whole number of cells required?",
     math.ceil((3 * 20 / 0.85) / (3.7 * 2.5)), "count", 0.0, "Energy = 3*20/0.85 = 70.6 Wh, per cell 9.25 Wh, ceil(7.63) = 8"),
    ("ee-i12", "intensive", "transmission", "A line delivers 100 kW at 10 kV (unity power factor, single-phase) over a line with a total resistance of 5 ohm. What is the power lost in the line, in watts?",
     (100e3 / 10e3) ** 2 * 5, "W", 0.01, "I = P / V = 10 A, Ploss = I^2 R"),
    ("ee-i13", "intensive", "resonance", "What is the quality factor Q of a series RLC circuit with R = 10 ohm, L = 10 millihenry and C = 1 microfarad (unitless)?",
     (1 / 10) * math.sqrt(10e-3 / 1e-6), "", 0.01, "Q = (1/R) sqrt(L/C)"),
    ("ee-i14", "intensive", "resistor-networks", "A delta network has Rab = 10 ohm, Rbc = 20 ohm and Rca = 30 ohm. In the equivalent wye network, what is the resistance from node a to the center, in ohms?",
     10 * 30 / (10 + 20 + 30), "ohm", 0.01, "Ra = Rab Rca / (Rab + Rbc + Rca)"),
    ("ee-i15", "intensive", "energy", "A motor delivers 5 hp of mechanical output at 88% efficiency. It runs 8 hours a day for 30 days, and electricity costs $0.15 per kWh. What is the electricity cost in US dollars? (1 hp = 745.7 W)",
     (5 * 745.7 / 0.88) / 1000 * 8 * 30 * 0.15, "USD", 0.01, "Pin = 5*745.7/0.88 W, E = Pin * 240 h, cost = E * 0.15"),
]


# Fresh set for the Q8_0 small-tier test (evals/score_quant.py), written on 2026-10-23 before the
# Q8_0 4B answered anything; shared with the aerospace and physics fresh_quant sets. -> fresh_quant.jsonl
FRESH_QUANT = [
    # calm
    ("ee-q-c01", "calm", "ohms-law", "A 9 V battery drives 0.15 A through a lamp. What is the lamp's resistance, in ohms?",
     9 / 0.15, "ohm", 0.01, "R = V / I"),
    ("ee-q-c02", "calm", "ac", "What is the period of a 400 Hz signal, in milliseconds?",
     1 / 400 * 1000, "ms", 0.01, "T = 1 / f"),
    ("ee-q-c03", "calm", "energy", "A 2 kW heater runs for 3 hours. How much energy does it use, in kilowatt-hours?",
     2 * 3, "kWh", 0.01, "E = P t"),
    ("ee-q-c04", "calm", "power", "A 24 V supply delivers 3.5 A to a load. How much power does the load draw, in watts?",
     24 * 3.5, "W", 0.01, "P = V I"),
    # alert
    ("ee-q-a01", "alert", "ac-power", "A 230 V RMS supply feeds a load drawing 4 A at a power factor of 0.8. What real power does it draw, in watts?",
     230 * 4 * 0.8, "W", 0.01, "P = V I pf"),
    ("ee-q-a02", "alert", "dividers", "A voltage divider has R1 = 4.7 kilohm on top and R2 = 2.2 kilohm on the bottom, fed from 15 V. What is the output voltage across R2, in volts?",
     15 * 2.2 / (4.7 + 2.2), "V", 0.01, "Vout = Vin R2 / (R1 + R2)"),
    ("ee-q-a03", "alert", "resonance", "What is the resonant frequency of an LC circuit with a 2 millihenry inductor and a 50 nanofarad capacitor, in kilohertz?",
     1 / (2 * PI * math.sqrt(2e-3 * 50e-9)) / 1000, "kHz", 0.01, "f = 1 / (2 pi sqrt(L C))"),
    ("ee-q-a04", "alert", "resistivity", "A copper wire 50 m long has a cross-section of 1.5 square millimeters. With a resistivity of 1.68e-8 ohm·m, what is its resistance, in ohms?",
     1.68e-8 * 50 / 1.5e-6, "ohm", 0.01, "R = rho L / A, A = 1.5e-6 m^2"),
    # intensive
    ("ee-q-i01", "intensive", "resistor-networks", "A 10 ohm resistor is in series with a parallel pair of 30 ohm and 60 ohm resistors, all across a 24 V source. What current flows through the 30 ohm resistor, in amperes?",
     (24 * 20 / 30) / 30, "A", 0.01, "Rpar = 20, I = 0.8 A, Vpar = 16 V, I30 = 16 / 30"),
    ("ee-q-i02", "intensive", "impedance", "A series RL circuit has R = 30 ohm and L = 0.1 henry on a 120 V RMS, 60 Hz supply. What RMS current flows, in amperes?",
     120 / math.hypot(30, 2 * PI * 60 * 0.1), "A", 0.01, "XL = 2 pi f L, Z = sqrt(R^2 + XL^2), I = V / Z"),
    ("ee-q-i03", "intensive", "transformers", "An ideal transformer steps 240 V down to 12 V, and its secondary feeds a 6 ohm load. What current does the primary draw, in amperes?",
     (12 / 6) * 12 / 240, "A", 0.01, "Is = 12 / 6 = 2 A, Ip = Is Vs / Vp"),
    ("ee-q-i04", "intensive", "batteries", "A 12 V, 100 Ah battery powers a 60 W load through an inverter with 90% efficiency. Using only 80% of the battery's capacity, how many hours does it run?",
     12 * 100 * 0.8 / (60 / 0.9), "h", 0.01, "usable 960 Wh, draw 60 / 0.9 W, t = E / P"),
]


def write(problems, name):
    ids = [p[0] for p in problems]
    assert len(ids) == len(set(ids)), "duplicate problem id"
    out = Path(__file__).with_name(name)
    with out.open("w") as f:
        for pid, level, topic, question, answer, unit, tol, solution in problems:
            f.write(json.dumps({
                "id": pid, "domain": "electrical", "level": level, "topic": topic,
                "question": question, "answer": answer, "unit": unit,
                "rel_tol": tol, "solution": solution,
            }) + "\n")
    counts = {lvl: sum(p[1] == lvl for p in problems) for lvl in ("calm", "alert", "intensive")}
    print(f"wrote {len(problems)} problems to {out} {counts}")


def main():
    ids = [p[0] for p in PROBLEMS + FRESH_QUANT]
    assert len(ids) == len(set(ids)), "id used twice"
    write(PROBLEMS, "problems.jsonl")
    write(FRESH_QUANT, "fresh_quant.jsonl")


if __name__ == "__main__":
    main()
