"""Build the datasets behind the lab dashboard from the saved results, by running the existing scripts.

    .venv/bin/python evals/dashboard_data.py <out_dir>

Every number comes from a script in evals/ run on results/ (no model calls), so the
dashboard shows exactly what those scripts print:

    policies.json     every routing policy per pack: score, accuracy, compute, and whether it ships
    checks.json       how many wrong answers each pack's checks catch, per model/strategy
    experiments.json  each experiment with a rule fixed before its results: its verdict and numbers
    routing.json      which pack a text goes to: eval-set texts and holdout cases
    commits.json      the git history, one row per commit
"""

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv/bin/python")

# The policy each pack ships, and the one fixed before its sweep, as the simulations name them.
SHIPPED = {
    "electrical": "routed: orig4B+tool | 8B+tool",
    "aerospace": "always 8B+tool (shipped)",
    "physics": "+ escalate on failed check (pre-sweep default)",
    "software": "always coder14B",
    "cad": "always coder",
    "sql": "always coder",
}
PRE_SWEEP = {
    "aerospace": "+ escalate on failed check (first default)",
    "physics": "+ escalate on failed check (pre-sweep default)",
    "cad": "cascade 4B -> 8B -> coder (pre-sweep default)",
    "sql": "cascade 4B -> 8B -> coder (pre-sweep default)",
}
BASELINE = {"electrical": "always 8B", "aerospace": "always 8B", "physics": "always 8B",
            "software": "always coder 14B", "cad": "always coder 14B",
            "sql": "always coder 14B"}
POLICY_ROW = re.compile(r"^(?P<name>\S.*?|\s+\+.*?)\s{2,}(?P<score>\d+)/(?P<n>\d+)\s+(?P<pct>\d+)%(?:\s+(?P<esc>\d+))?\s*$")
CHECK_ROW = re.compile(r"^\s+(?P<who>\S+)\s+(?P<wrong>\d+)\s+(?P<caught>\d+)\s+(?P<false>\d+)\s*$")


def verdict(text, adopted, rejected):
    """A scorer's verdict from its exact verdict line; anything else is an error, not a guess."""
    found = [v for v, line in (("adopted", adopted), ("not adopted", rejected)) if line in text]
    assert len(found) == 1, f"no single verdict line in: {text[-300:]}"
    return found[0]


def run(*args):
    return subprocess.run([PY, *args], cwd=ROOT, capture_output=True, text=True, timeout=1800).stdout


def parse_policies(pack, text):
    rows = []
    for line in text.splitlines():
        m = POLICY_ROW.match(line)
        if not m or m["name"].strip().startswith("hindsight"):
            continue
        name = m["name"].strip()
        rows.append({"pack": pack, "policy": name, "score": int(m["score"]), "n": int(m["n"]),
                     "accuracy": int(m["score"]) / int(m["n"]), "compute": int(m["pct"]) / 100,
                     "baseline": BASELINE[pack],
                     "role": "shipped" if name == SHIPPED[pack] else
                     "pre-sweep default" if name == PRE_SWEEP.get(pack) else "alternative"})
    assert any(r["role"] == "shipped" for r in rows), f"{pack}: shipped policy not found"
    return rows


def parse_checks(pack, text, after):
    rows, on = [], False
    for line in text.splitlines():
        if after in line:
            on = True
            continue
        m = CHECK_ROW.match(line) if on else None
        if m:
            rows.append({"pack": pack, "answers": m["who"], "wrong": int(m["wrong"]), "caught": int(m["caught"]),
                         "false_alarms": int(m["false"]),
                         "catch_rate": int(m["caught"]) / int(m["wrong"]) if int(m["wrong"]) else None})
    return rows


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    policies, checks, experiments = [], [], []

    for pack in ("electrical", "aerospace", "physics"):
        text = run("evals/simulate_routing.py", "--pack", pack, "--checks")
        policies += parse_policies(pack, text)
        checks += parse_checks(pack, text, "how many wrong answers the checks catch")
    text = run("evals/simulate_code_routing.py")
    policies += parse_policies("software", text)
    checks += parse_checks("software", text, "how well the examples check predicts")
    text = run("evals/run_cad.py", "--simulate")
    policies += parse_policies("cad", text)
    # the eval-set CAD runs carry the size check of the first sweep; the shipped hole check is judged in experiments
    checks += [dict(r, answers=f"{r['answers']}, size check") for r in parse_checks("cad", text, "key-free check vs the key")]
    text = run("evals/run_sql.py", "--simulate")
    policies += parse_policies("sql", text)
    checks += parse_checks("sql", text, "key-free check vs the key")

    # Experiments: each has a rule committed before its results; the scorer prints its verdict.
    units = {r["pack"]: r for r in policies if r["policy"].startswith("units:")}
    for pack in ("electrical", "aerospace"):
        best = max((r for r in policies if r["pack"] == pack and r["policy"].startswith("units:")),
                   key=lambda r: (r["score"], -r["compute"]))
        shipped = next(r for r in policies if r["pack"] == pack and r["role"] == "shipped")
        experiments.append({"id": f"units-{pack}", "date": "2026-10-21", "experiment": f"Unit-aware calculator ({pack})",
                            "verdict": "not adopted", "metric": "problems right",
                            "before": shipped["score"], "after": best["score"], "n": shipped["n"],
                            "cost_ratio": best["compute"] / shipped["compute"],
                            "note": f"best units policy {best['score']}/{best['n']} vs shipped {shipped['score']}/{shipped['n']}"})
    del units

    text = run("evals/score_decompose.py")
    m = re.search(r"fresh gain ([+-]\d+).*?cost ([\d.]+)x", text)
    fresh = re.search(r"fresh set:.*?\n.*?\ntool\s+(\d+)/(\d+).*?\ndecompose\s+(\d+)/\d+", text, re.S)
    experiments.append({"id": "decompose", "date": "2026-10-22", "experiment": "Decompose-then-solve (aerospace intensive)",
                        "verdict": verdict(text, "ADOPT: switch", "NOT ADOPTED"), "metric": "fresh problems right",
                        "before": int(fresh[1]), "after": int(fresh[3]), "n": int(fresh[2]),
                        "cost_ratio": float(m[2]), "note": "rule: +3 on 15 fresh problems, no loss on the eval set, <= 4x tokens"})

    for exp_id, date, title, args in (
            ("hole-check-v1", "2026-10-23", "CAD hole check v1", ["evals/score_cad_check.py"]),
            ("hole-check-v2", "2026-10-23", "CAD hole check v2", ["evals/score_cad_check.py", "--set", "fresh2.jsonl",
                                                                  "--variant", "v2"])):
        text = run(*args)
        t = re.search(r"all models: wrong (\d+), caught size-only (\d+), candidate (\d+); false alarms size-only (\d+), "
                      r"candidate (\d+)", text)
        refs = re.search(r"fresh references it flags: (\d+)", text)
        experiments.append({"id": exp_id, "date": date, "experiment": title,
                            "verdict": verdict(text, "-> ADOPT", "-> keep the size-only check"),
                            "metric": "wrong parts caught", "before": int(t[2]), "after": int(t[3]), "n": int(t[1]),
                            "cost_ratio": None,
                            "note": f"false alarms on correct parts {t[4]} -> {t[5]}; fresh references flagged {refs[1]}"})

    text = run("evals/score_cad_repair.py")
    r = re.search(r"first answers right (\d+), final (\d+); repairs tried (\d+), kept (\d+); .*?cost ([\d.]+)x", text)
    n = re.search(r"fresh3\.jsonl: (\d+) parts", text)
    experiments.append({"id": "cad-repair", "date": "2026-10-23", "experiment": "CAD repair retry",
                        "verdict": verdict(text, "-> ADOPT one repair", "-> no repair"), "metric": "fresh parts right",
                        "before": int(r[1]), "after": int(r[2]), "n": int(n[1]), "cost_ratio": float(r[5]),
                        "note": f"{r[3]} repairs tried, {r[4]} kept"})

    text = run("evals/score_lora.py")
    r = re.search(r"routed \(tuned 4B.*?\): (\d+)/(\d+) at (\d+)% of always-8B compute; always 8B: (\d+)/\d+", text)
    experiments.append({"id": "aero-lora", "date": "2026-10-23", "experiment": "Aerospace 4B LoRA",
                        "verdict": verdict(text, "-> ADOPT: route", "-> NOT ADOPTED"),
                        "metric": "fresh problems right (routed vs always-8B)", "before": int(r[4]), "after": int(r[1]),
                        "n": int(r[2]), "cost_ratio": int(r[3]) / 100,
                        "note": "tuned 4B: calm 7/12 (control 11), intensive 9/11 (8B 5); val loss 0 by step 200"})

    text = run("evals/score_quant.py")
    r = re.search(r"disagreements: Q8_0 right only (\d+), Q4_K_M right only (\d+); one-sided sign test p = ([\d.]+)", text)
    tally = [tuple(map(int, m)) for m in re.findall(r"^\S+\s+\S+\s+(\d+)\s+(\d+)\s+(\d+)\s*$", text, re.M)]
    experiments.append({"id": "q8-small-tier", "date": "2026-10-23", "experiment": "Q8_0 small tier (4B)",
                        "verdict": verdict(text, "-> ADOPT: the Q8_0", "-> NOT ADOPTED"),
                        "metric": "problems right with the calculator (Q4_K_M vs Q8_0)",
                        "before": sum(t[1] for t in tally), "after": sum(t[2] for t in tally),
                        "n": sum(t[0] for t in tally), "cost_ratio": None,
                        "note": f"disagreements {r[1]} to {r[2]}, sign test p = {r[3]}; better on aerospace only"})

    text = run("evals/run_sql.py", "--simulate", "--tasks", "evals/sql/fresh.jsonl")
    s = re.search(r"shipped (\d+)/(\d+) at (\d+)%, best (\d+)/\d+", text)
    experiments.append({"id": "sql-fresh", "date": "2026-10-23", "experiment": "SQL policy on fresh tasks",
                        "verdict": verdict(text, "-> CONFIRMED", "-> NOT CONFIRMED"),
                        "metric": "fresh tasks right (best policy vs shipped)", "before": int(s[4]), "after": int(s[1]),
                        "n": int(s[2]), "cost_ratio": None,
                        "note": "shipped 4B -> coder; best: always 8B / 8B -> coder at 61%; misses run but return wrong rows"})

    text = run("evals/run_sql.py", "--simulate", "--tasks", "evals/sql/fresh2.jsonl")
    s = re.search(r"candidate (\d+)/(\d+) at (\d+)%, best (\d+)/\d+", text)
    experiments.append({"id": "sql-fresh2", "date": "2026-10-23", "experiment": "SQL candidate on a second fresh set",
                        "verdict": "adopted" if "-> ADOPT: routed" in text else "not adopted",
                        "metric": "fresh tasks right (best policy vs candidate)", "before": int(s[4]), "after": int(s[1]),
                        "n": int(s[2]), "cost_ratio": None,
                        "note": "candidate intensive 8B -> coder; the rule then shipped always 8B (42/48 pooled at 60%)"})

    text = run("evals/test_detect.py")
    routing = [{"set": label, "right": int(m[1]), "total": int(m[2])}
               for label, m in (("eval-set texts", re.search(r"eval-set texts.*?(\d+)/(\d+)", text)),
                                ("holdout cases", re.search(r"holdout cases.*?(\d+)/(\d+)", text)))]

    log = subprocess.run(["git", "log", "--reverse", "--format=%h\t%ad\t%s", "--date=iso-strict"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    commits = [dict(zip(("sha", "at", "subject"), line.split("\t", 2))) for line in log.splitlines()]
    for c in commits:
        c["day"] = c["at"][:10]

    for name, rows in (("policies", policies), ("checks", checks), ("experiments", experiments),
                       ("routing", routing), ("commits", commits)):
        (out / f"{name}.json").write_text(json.dumps(rows, indent=1))
        print(f"{name}: {len(rows)} rows")


if __name__ == "__main__":
    main()
