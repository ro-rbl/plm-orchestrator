"""Training data for the aerospace 4B LoRA: generated problems with calculator-program answers.

    .venv/bin/python evals/aerospace/lora_train.py <out_dir>      # writes train.jsonl and valid.jsonl

Templates of the eval set's problem families (build_problems.py), with random values
and their own wording; each answer is a short calculator program in the tool format
(plm/numeric/calc.py TOOL_FORMAT), which is how the routed 4B answers. No question may
equal one in the eval set, its holdout or a fresh set, and every program must run and
pass the pack's checks (plm/numeric/checks.py): the script refuses otherwise.
Written on 2026-10-23, after the judge set (fresh_lora.jsonl), from the eval set's
families, not the judge set's problems.
"""

import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import plm.packs  # noqa: E402,F401  (loads every pack, and with it its unit words)
from plm.numeric import calc  # noqa: E402
from plm.numeric.calc import TOOL_FORMAT  # noqa: E402
from plm.numeric.checks import check  # noqa: E402

G0 = 9.80665
GM = 3.986e14
RE = 6371e3
EARTH = "Use GM = 3.986e14 m³/s² and an Earth radius of 6371 km."
SEED, PER_TEMPLATE, VALID_SHARE = 20261023, 24, 0.1


def pick(r, *choices):
    return r.choice(choices)


def program(lines, var, unit, fmt=".4g"):
    body = "\n".join(lines)
    return f"```python\nimport math\n\n{body}\nprint(f\"ANSWER: {{{var}:{fmt}}} {unit}\")\n```".replace(" \")", "\")")


# Each template: r -> (question, program). Values are drawn so the answers stay physical.
def t_mach(r):
    v, a = r.randint(150, 900), r.choice([295, 300, 320, 330, 340])
    q = pick(r, f"A jet flies at {v} m/s where the speed of sound is {a} m/s. What is its Mach number (unitless)?",
             f"What Mach number does an aircraft have at {v} m/s if the local speed of sound is {a} m/s (unitless)?")
    return q, program([f"v = {v}  # m/s", f"a = {a}  # m/s", "mach = v / a"], "mach", "")


def t_weight(r):
    m, g = r.randint(800, 90000), pick(r, 9.81, 9.80665)
    q = f"What is the weight of a {m} kg aircraft at a gravitational acceleration of {g} m/s², in kilonewtons?"
    return q, program([f"m = {m}  # kg", f"g = {g}  # m/s^2", "w_kn = m * g / 1000"], "w_kn", "kN")


def t_knots(r):
    kt = r.randint(80, 520)
    q = f"An aircraft flies at {kt} knots, where 1 knot is 0.5144 m/s. What is its speed, in kilometers per hour?"
    return q, program([f"kt = {kt}", "v_ms = kt * 0.5144", "v_kmh = v_ms * 3.6"], "v_kmh", "km/h")


def t_dynamic_pressure(r):
    rho, v = round(r.uniform(0.3, 1.225), 3), r.randint(40, 300)
    q = f"Air with a density of {rho} kg/m³ flows at {v} m/s. What is its dynamic pressure, in pascals?"
    return q, program([f"rho = {rho}  # kg/m^3", f"v = {v}  # m/s", "q = 0.5 * rho * v ** 2"], "q", "Pa")


def t_lift(r):
    rho, v, s, cl = round(r.uniform(0.4, 1.225), 3), r.randint(40, 250), r.randint(10, 400), round(r.uniform(0.3, 1.6), 2)
    q = (f"A wing with an area of {s} square meters flies at {v} m/s in air of density {rho} kg/m³ with a lift "
         f"coefficient of {cl}. What lift does it produce, in kilonewtons?")
    return q, program([f"rho, v, s, cl = {rho}, {v}, {s}, {cl}", "lift = 0.5 * rho * v ** 2 * s * cl  # N",
                       "lift_kn = lift / 1000"], "lift_kn", "kN")


def t_drag(r):
    rho, v, s, cd = round(r.uniform(0.3, 1.225), 3), r.randint(50, 260), r.randint(15, 450), round(r.uniform(0.015, 0.06), 3)
    q = (f"An aircraft with a wing area of {s} square meters flies at {v} m/s where the air density is {rho} kg/m³. "
         f"With a drag coefficient of {cd}, what is its drag, in kilonewtons?")
    return q, program([f"rho, v, s, cd = {rho}, {v}, {s}, {cd}", "drag = 0.5 * rho * v ** 2 * s * cd  # N",
                       "drag_kn = drag / 1000"], "drag_kn", "kN")


def t_wing_loading(r):
    w, s = r.randint(8000, 3000000), r.randint(12, 520)
    q = f"An aircraft weighing {w} N has a wing area of {s} square meters. What is its wing loading, in pascals?"
    return q, program([f"w = {w}  # N", f"s = {s}  # m^2", "wl = w / s"], "wl", "Pa")


def t_stall(r):
    w, s, clmax = r.randint(6000, 700000), r.randint(10, 400), round(r.uniform(1.2, 2.4), 2)
    rho = pick(r, 1.225, 1.1, 1.0)
    q = (f"An aircraft weighing {w} N has a wing area of {s} square meters and a maximum lift coefficient of {clmax}. "
         f"Where the air density is {rho} kg/m³, what is its stall speed, in meters per second?")
    return q, program([f"w, s, clmax, rho = {w}, {s}, {clmax}, {rho}", "v_stall = math.sqrt(2 * w / (rho * s * clmax))"],
                      "v_stall", "m/s")


def t_turn(r):
    v, bank = r.randint(50, 250), r.choice([15, 20, 25, 30, 35, 40, 45, 50, 60])
    q = f"An aircraft makes a level turn at {v} m/s with a bank angle of {bank} degrees. Taking g = 9.81 m/s², what is its turn radius, in meters?"
    return q, program([f"v = {v}  # m/s", f"bank = math.radians({bank})", "radius = v ** 2 / (9.81 * math.tan(bank))"],
                      "radius", "m")


def t_load_factor(r):
    bank = r.choice([20, 30, 40, 45, 50, 55, 60, 65, 70])
    q = f"What load factor does a level turn at a bank angle of {bank} degrees need (unitless)?"
    return q, program([f"bank = math.radians({bank})", "n = 1 / math.cos(bank)"], "n", "")


def t_speed_of_sound(r):
    t, gamma = round(r.uniform(200, 320), 1), pick(r, 1.4, 1.4, 1.33)
    q = f"With a ratio of specific heats of {gamma} and R = 287 J/(kg·K), what is the speed of sound at {t} K, in meters per second?"
    return q, program([f"gamma, rgas, t = {gamma}, 287, {t}", "a = math.sqrt(gamma * rgas * t)"], "a", "m/s")


def t_thrust(r):
    mdot, ve = r.randint(20, 900), r.randint(1800, 4500)
    q = f"A rocket engine expels {mdot} kg/s of propellant at {ve} m/s. Ignoring pressure thrust, what is its thrust, in kilonewtons?"
    return q, program([f"mdot = {mdot}  # kg/s", f"ve = {ve}  # m/s", "thrust_kn = mdot * ve / 1000"], "thrust_kn", "kN")


def t_exhaust_velocity(r):
    isp = r.randint(200, 460)
    q = f"A rocket engine has a specific impulse of {isp} s. Taking g0 = 9.80665 m/s², what is its exhaust velocity, in meters per second?"
    return q, program([f"isp = {isp}  # s", "g0 = 9.80665", "ve = isp * g0"], "ve", "m/s")


def t_delta_v(r):
    isp, m0 = r.randint(220, 460), r.randint(5, 400)
    mf = round(m0 * r.uniform(0.15, 0.6), 1)
    q = (f"A rocket with a specific impulse of {isp} s burns from {m0} t down to {mf} t. Taking g0 = 9.80665 m/s², "
         f"what is its ideal delta-v, in meters per second?")
    return q, program([f"isp, m0, mf = {isp}, {m0}, {mf}", "dv = isp * 9.80665 * math.log(m0 / mf)"], "dv", "m/s")


def t_propellant(r):
    dry, dv, isp = r.randint(500, 20000), r.randint(300, 4000), r.randint(250, 450)
    q = (f"A spacecraft with a dry mass of {dry} kg needs {dv} m/s of delta-v from an engine with a specific impulse of "
         f"{isp} s. Taking g0 = 9.80665 m/s², how much propellant does it need, in kilograms?")
    return q, program([f"dry, dv, isp = {dry}, {dv}, {isp}", "ratio = math.exp(dv / (isp * 9.80665))",
                       "propellant = dry * (ratio - 1)"], "propellant", "kg")


def t_mass_flow_from_thrust(r):
    f, isp = r.randint(50, 3000), r.randint(220, 450)
    q = (f"An engine produces {f} kN of thrust with a specific impulse of {isp} s. Taking g0 = 9.80665 m/s², "
         f"what is its propellant mass flow, in kilograms per second?")
    return q, program([f"thrust = {f} * 1000  # N", f"isp = {isp}", "mdot = thrust / (isp * 9.80665)"], "mdot", "kg/s")


def t_circular_speed(r):
    h = r.randint(200, 36000)
    q = f"A satellite is in a circular orbit {h} km above Earth's surface. What is its orbital speed, in kilometers per second? {EARTH}"
    return q, program(["gm, re = 3.986e14, 6371e3", f"r = re + {h} * 1000", "v_kms = math.sqrt(gm / r) / 1000"], "v_kms", "km/s")


def t_period(r):
    h = r.randint(250, 20000)
    q = f"What is the orbital period of a satellite in a circular orbit {h} km above Earth, in minutes? {EARTH}"
    return q, program(["gm, re = 3.986e14, 6371e3", f"r = re + {h} * 1000",
                       "t_min = 2 * math.pi * math.sqrt(r ** 3 / gm) / 60"], "t_min", "min")


def t_escape(r):
    h = r.randint(0, 3000)
    q = f"What is the escape velocity from {h} km above Earth's surface, in kilometers per second? {EARTH}"
    return q, program(["gm, re = 3.986e14, 6371e3", f"r = re + {h} * 1000", "v_esc = math.sqrt(2 * gm / r) / 1000"],
                      "v_esc", "km/s")


def t_hohmann(r):
    h1 = r.randint(200, 2000)
    h2 = h1 + r.randint(300, 34000)
    q = (f"What total delta-v does a Hohmann transfer take from a circular orbit {h1} km above Earth to a circular "
         f"orbit {h2} km above Earth, in kilometers per second? {EARTH}")
    return q, program(["gm, re = 3.986e14, 6371e3", f"r1, r2 = re + {h1} * 1000, re + {h2} * 1000", "a = (r1 + r2) / 2",
                       "v1, v2 = math.sqrt(gm / r1), math.sqrt(gm / r2)",
                       "vp, va = math.sqrt(gm * (2 / r1 - 1 / a)), math.sqrt(gm * (2 / r2 - 1 / a))",
                       "dv = ((vp - v1) + (v2 - va)) / 1000"], "dv", "km/s")


def t_plane_change(r):
    h, di = r.randint(300, 2000), r.choice([2, 3, 5, 6, 10, 12, 15])
    q = (f"A satellite in a circular orbit {h} km above Earth's surface changes its inclination by {di} degrees in a "
         f"single burn. What delta-v does that take, in kilometers per second? {EARTH}")
    return q, program(["gm, re = 3.986e14, 6371e3", f"v = math.sqrt(gm / (re + {h} * 1000))",
                       f"dv = 2 * v * math.sin(math.radians({di}) / 2) / 1000"], "dv", "km/s")


def t_orbit_altitude(r):
    hours = r.choice([2, 3, 4, 5, 8, 10, 16, 20])
    q = f"A satellite in a circular orbit takes {hours} hours per revolution. What is its altitude above Earth's surface, in kilometers? {EARTH}"
    return q, program(["gm, re = 3.986e14, 6371e3", f"t = {hours} * 3600", "r = (gm * t ** 2 / (4 * math.pi ** 2)) ** (1 / 3)",
                       "h_km = (r - re) / 1000"], "h_km", "km")


def t_perigee_speed(r):
    hp = r.randint(200, 1500)
    ha = hp + r.randint(500, 30000)
    q = (f"An elliptical orbit has a perigee altitude of {hp} km and an apogee altitude of {ha} km. What is the speed "
         f"at perigee, in kilometers per second? {EARTH}")
    return q, program(["gm, re = 3.986e14, 6371e3", f"rp, ra = re + {hp} * 1000, re + {ha} * 1000", "a = (rp + ra) / 2",
                       "vp = math.sqrt(gm * (2 / rp - 1 / a)) / 1000"], "vp", "km/s")


def t_stagnation_temperature(r):
    v, t = r.randint(150, 900), round(r.uniform(210, 290), 1)
    q = (f"An aircraft flies at {v} m/s where the air temperature is {t} K. With a ratio of specific heats of 1.4 and "
         f"R = 287 J/(kg·K), what is the stagnation temperature, in kelvin?")
    return q, program([f"v, t, gamma, rgas = {v}, {t}, 1.4, 287", "a = math.sqrt(gamma * rgas * t)", "mach = v / a",
                       "t0 = t * (1 + (gamma - 1) / 2 * mach ** 2)"], "t0", "K")


def t_stagnation_pressure(r):
    v, t, p = r.randint(150, 800), round(r.uniform(210, 290), 1), r.randint(15, 101)
    q = (f"An aircraft flies at {v} m/s where the air temperature is {t} K and the pressure is {p} kPa. With a ratio "
         f"of specific heats of 1.4 and R = 287 J/(kg·K), what is the stagnation pressure, in kilopascals?")
    return q, program([f"v, t, p, gamma, rgas = {v}, {t}, {p}, 1.4, 287", "mach = v / math.sqrt(gamma * rgas * t)",
                       "p0 = p * (1 + (gamma - 1) / 2 * mach ** 2) ** (gamma / (gamma - 1))"], "p0", "kPa")


def t_nozzle(r):
    t0, ratio, gamma, rgas, mdot = r.randint(2500, 3700), pick(r, 0.01, 0.02, 0.03, 0.05), pick(r, 1.2, 1.25, 1.3), r.randint(300, 400), r.randint(20, 300)
    q = (f"A rocket nozzle expands gas from a chamber temperature of {t0} K to an exit pressure that is {ratio * 100:g}% "
         f"of the chamber pressure. The gas has a ratio of specific heats of {gamma} and R = {rgas} J/(kg·K), and the "
         f"mass flow is {mdot} kg/s. Ignoring pressure thrust, what thrust does it produce, in kilonewtons?")
    return q, program([f"t0, pr, gamma, rgas, mdot = {t0}, {ratio}, {gamma}, {rgas}, {mdot}",
                       "ve = math.sqrt(2 * gamma / (gamma - 1) * rgas * t0 * (1 - pr ** ((gamma - 1) / gamma)))",
                       "thrust_kn = mdot * ve / 1000"], "thrust_kn", "kN")


def t_breguet(r):
    v, ld, c, wr = r.randint(150, 260), r.randint(10, 20), round(r.uniform(0.45, 0.8), 2), round(r.uniform(1.1, 1.5), 2)
    q = (f"A jet cruises at {v} m/s with a lift-to-drag ratio of {ld} and a thrust-specific fuel consumption of {c} "
         f"per hour. Its weight falls from {wr} to 1.0 times its final weight during the cruise. Using the Breguet "
         f"range equation, how far does it fly, in kilometers?")
    return q, program([f"v, ld, c, wr = {v}, {ld}, {c} / 3600, {wr}  # c in 1/s", "range_km = v / c * ld * math.log(wr) / 1000"],
                      "range_km", "km")


def t_power_required(r):
    w, s, rho, v = r.randint(50, 900), r.randint(30, 500), round(r.uniform(0.3, 1.1), 2), r.randint(90, 260)
    cd0, k = round(r.uniform(0.015, 0.035), 3), round(r.uniform(0.03, 0.07), 3)
    q = (f"An aircraft weighing {w} kN with a wing area of {s} square meters flies level at {v} m/s where the air "
         f"density is {rho} kg/m³. Its drag polar is CD = {cd0} + {k} CL². What power is needed to overcome drag, in megawatts?")
    return q, program([f"w, s, rho, v = {w} * 1000, {s}, {rho}, {v}", "q = 0.5 * rho * v ** 2", "cl = w / (q * s)",
                       f"cd = {cd0} + {k} * cl ** 2", "power_mw = q * s * cd * v / 1e6"], "power_mw", "MW")


def t_glide(r):
    cd0, k, h = round(r.uniform(0.012, 0.04), 3), round(r.uniform(0.02, 0.06), 3), r.randint(500, 4000)
    q = (f"A glider has the drag polar CD = {cd0} + {k} CL². Flying at its best lift-to-drag ratio in still air, how "
         f"far can it glide from an altitude of {h} m, in kilometers?")
    return q, program([f"cd0, k, h = {cd0}, {k}, {h}", "ld_max = 1 / (2 * math.sqrt(k * cd0))", "dist_km = ld_max * h / 1000"],
                      "dist_km", "km")


def t_rate_of_climb(r):
    w, t, d, v = r.randint(20, 600), r.randint(10, 200), 0, r.randint(60, 250)
    d = round(t * r.uniform(0.5, 0.9))
    q = (f"An aircraft weighing {w} kN flies at {v} m/s with {t} kN of thrust and {d} kN of drag. What is its rate of "
         f"climb, in meters per second?")
    return q, program([f"w, t, d, v = {w}, {t}, {d}, {v}  # kN, kN, kN, m/s", "rc = (t - d) * v / w"], "rc", "m/s")


def t_compressor(r):
    mdot, t1, pr, eta = r.randint(10, 150), r.choice([270, 280, 288, 300]), r.choice([4, 6, 8, 10, 15, 20]), round(r.uniform(0.8, 0.9), 2)
    q = (f"A compressor takes in {mdot} kg/s of air at {t1} K and raises its pressure by a factor of {pr} with an "
         f"isentropic efficiency of {eta * 100:g}%. With a ratio of specific heats of 1.4 and cp = 1005 J/(kg·K), "
         f"what power does it absorb, in megawatts?")
    return q, program([f"mdot, t1, pr, eta = {mdot}, {t1}, {pr}, {eta}", "t2s = t1 * pr ** (0.4 / 1.4)",
                       "dt = (t2s - t1) / eta", "power_mw = mdot * 1005 * dt / 1e6"], "power_mw", "MW")


def t_gravity_loss(r):
    m0, ve = r.randint(40, 300), r.randint(2400, 3500)
    prop = round(m0 * r.uniform(0.5, 0.8))
    # thrust (rate x ve) at least 1.3x the liftoff weight, or the rocket never leaves the pad
    rate = r.randint(math.ceil(1.3 * m0 * 1000 * 9.81 / ve), math.ceil(2.5 * m0 * 1000 * 9.81 / ve))
    q = (f"A rocket launched straight up has an initial mass of {m0} t and burns {prop} t of propellant at {rate} kg/s "
         f"with an exhaust velocity of {ve} m/s. Including gravity losses at a constant 9.81 m/s² and ignoring drag, "
         f"what is its speed at burnout, in meters per second?")
    return q, program([f"m0, prop, rate, ve = {m0}, {prop}, {rate}, {ve}", "t_burn = prop * 1000 / rate",
                       "v = ve * math.log(m0 / (m0 - prop)) - 9.81 * t_burn"], "v", "m/s")


TEMPLATES = [t_mach, t_weight, t_knots, t_dynamic_pressure, t_lift, t_drag, t_wing_loading, t_stall, t_turn,
             t_load_factor, t_speed_of_sound, t_thrust, t_exhaust_velocity, t_delta_v, t_propellant,
             t_mass_flow_from_thrust, t_circular_speed, t_period, t_escape, t_hohmann, t_plane_change,
             t_orbit_altitude, t_perigee_speed, t_stagnation_temperature, t_stagnation_pressure, t_nozzle,
             t_breguet, t_power_required, t_glide, t_rate_of_climb, t_compressor, t_gravity_loss]


def existing_questions():
    seen = set()
    for f in ("problems.jsonl", "holdout_levels.jsonl", "fresh_intensive.jsonl", "fresh_lora.jsonl"):
        for line in open(ROOT / "evals/aerospace" / f):
            if line.strip():
                seen.add(json.loads(line)["question"].strip())
    return seen


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    r = random.Random(SEED)
    seen = existing_questions()
    rows, questions = [], set()
    for t in TEMPLATES:
        for _ in range(PER_TEMPLATE):
            q, prog = t(r)
            if q in questions:
                continue
            if q in seen:
                sys.exit(f"refusing: {t.__name__} produced an eval/holdout/fresh question: {q}")
            printed, err = calc.run_program(calc.extract_program(prog))
            issues = ([err] if err else []) + check(q, printed)
            if issues:  # every answer must run and pass the pack's own checks
                sys.exit(f"refusing: {t.__name__} wrote a program that fails: {q} -> {printed.strip()} {issues}")
            questions.add(q)
            rows.append({"messages": [{"role": "user", "content": f"{q}\n\n{TOOL_FORMAT}"},
                                      {"role": "assistant", "content": prog}]})
    r.shuffle(rows)
    n_valid = max(1, int(len(rows) * VALID_SHARE))
    for name, part in (("valid", rows[:n_valid]), ("train", rows[n_valid:])):
        with open(out / f"{name}.jsonl", "w") as f:
            for row in part:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"{len(TEMPLATES)} templates -> {len(rows)} examples: train {len(rows) - n_valid}, valid {n_valid}")


if __name__ == "__main__":
    main()
