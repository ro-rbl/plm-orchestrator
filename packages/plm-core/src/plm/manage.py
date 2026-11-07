"""`plm packs`: list, install, remove and check domain packs.

    plm packs list [--json]              installed packs, versions, and whether their models are pulled
    plm packs install <name> [--source S]
    plm packs remove <name>
    plm packs doctor                     every pack loads, and every model it needs is pulled and loads

Packs aren't on PyPI yet. `install` takes plm-<name> from --source (a directory
holding plm-<name>/, the pack's own directory, or any pip requirement such as a
git URL), else from PLM_PACKS_SOURCE, else from the packages/ directory of the
checkout this core runs from. A directory is installed editable, so the code
stays where it is. Installing uses uv when it's on PATH, else pip, always into
the environment of the Python running plm. A pack is code that runs on this
machine: install only packs you trust.

These commands load packs one by one, so a pack that fails to load (which stops
the router) can still be listed and removed.
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import plm
from plm import ollama
from plm.general.manifest import PACK as GENERAL
from plm.pack import Pack, discover


def installed():
    """One row per pack: name, version, distribution, models, and the error if it failed to load."""
    rows = [{"name": GENERAL.name, "version": GENERAL.version, "dist": "plm-core (built in)",
             "models": dict(GENERAL.models), "error": None}]
    for ep, pack in discover():
        dist = ep.dist.name if ep.dist else "?"
        if isinstance(pack, Pack):
            rows.append({"name": pack.name, "version": pack.version, "dist": dist, "models": dict(pack.models),
                         "error": None})
        else:
            rows.append({"name": ep.name, "version": "?", "dist": dist, "models": {}, "error": repr(pack)})
    return rows


def pulled_models():
    """Full names of the models Ollama has, or None if Ollama can't be reached."""
    try:
        return ollama.pulled()
    except (urllib.error.URLError, OSError):
        return None


def _is_pulled(model, pulled):
    return None if pulled is None else ollama.full_name(model) in pulled


def _installer(verb):
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", verb, "--python", sys.executable]
    if subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True).returncode != 0:
        sys.exit("plm packs: neither uv nor pip is available to install with")
    return [sys.executable, "-m", "pip", verb] + (["-y"] if verb == "uninstall" else [])


REPO = "https://github.com/ro-rbl/plm-orchestrator"
OFFICIAL = ("electrical", "aerospace", "physics", "software", "sql", "cad")  # the only packs fetched by name


OWNER = "ro-rbl"  # the PyPI account that owns the official packs


def on_pypi(dist, timeout=10):
    """Whether PyPI has `dist` published by OWNER (False when it doesn't, someone else owns the name, or PyPI
    can't be reached), so a squatted name falls back to the GitHub repo instead of installing a stranger's code."""
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{dist}/json", timeout=timeout) as r:
            roles = (json.load(r).get("ownership") or {}).get("roles") or []
    except (urllib.error.URLError, OSError, ValueError):
        return False
    return any(role.get("user") == OWNER for role in roles)


def _run(cmd):
    print("$", shlex.join(cmd), flush=True)
    return subprocess.run(cmd).returncode


def _source(name, source):
    """pip arguments that install plm-<name> from --source, PLM_PACKS_SOURCE, this checkout, or (an official pack,
    with no checkout around plm) PyPI, else the GitHub repo."""
    dist = f"plm-{name}"
    source = source or os.environ.get("PLM_PACKS_SOURCE")
    if source is None:
        checkout = Path(plm.__file__).resolve().parents[3]  # packages/plm-core/src/plm -> packages
        if (checkout / dist / "pyproject.toml").exists():
            return ["-e", str(checkout / dist)]
        if name in OFFICIAL and not (checkout / "plm-core" / "pyproject.toml").exists():
            # an installed plm (uv tool install, pip) has no checkout around it: PyPI, else the project's repo
            return [dist] if on_pypi(dist) else [f"{dist} @ git+{REPO}#subdirectory=packages/{dist}"]
        sys.exit(f"plm packs: no source for {dist}: only the official packs ({', '.join(OFFICIAL)}) install "
                 f"without one. Pass --source: a directory "
                 f"holding {dist}/, or a pip requirement such as "
                 f"'{dist} @ git+https://<repo>#subdirectory=packages/{dist}'")
    path = Path(source).expanduser()
    if (path / dist / "pyproject.toml").exists():
        return ["-e", str(path / dist)]
    if (path / "pyproject.toml").exists():
        return ["-e", str(path)]
    if path.exists():
        sys.exit(f"plm packs: {path} has neither {dist}/pyproject.toml nor pyproject.toml")
    return [source]


def _pull(model):
    last = None
    try:
        for msg in ollama.pull(model):
            if msg.get("status") != last:  # progress repeats a status with new byte counts
                last = msg.get("status")
                print(f"  {model}: {last}", flush=True)
    except urllib.error.HTTPError as e:
        raise RuntimeError(json.loads(e.read() or b"{}").get("error", str(e))) from e


def cmd_list(args):
    rows, pulled = installed(), pulled_models()
    if args.json:
        for r in rows:
            r["models"] = {tier: {"model": m, "pulled": _is_pulled(m, pulled)} for tier, m in r["models"].items()}
        print(json.dumps(rows, indent=2))
        return 0
    for r in rows:
        print(f"{r['name']:12} {r['version']:8} {r['dist']}")
        if r["error"]:
            print(f"  FAILED TO LOAD: {r['error']}")
        for tier, m in r["models"].items():
            state = {True: "pulled", False: "MISSING", None: "unknown (Ollama unreachable)"}[_is_pulled(m, pulled)]
            print(f"  {tier:6} {m}  {state}")
    return 0


def cmd_install(args):
    if args.name == GENERAL.name:
        sys.exit("plm packs: the general pack is built into the core")
    if _run(_installer("install") + _source(args.name, args.source)) != 0:
        sys.exit("plm packs: install failed")
    # A fresh process sees the newly installed pack (and its env-overridden models).
    out = subprocess.run([sys.executable, "-m", "plm", "packs", "list", "--json"], capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"plm packs: installed, but listing packs failed:\n{out.stderr}")
    row = next((r for r in json.loads(out.stdout) if r["name"] == args.name), None)
    if row is None:
        sys.exit(f"plm packs: installed plm-{args.name}, but it registers no pack named {args.name!r}")
    if row["error"]:
        sys.exit(f"plm packs: installed, but the pack fails to load: {row['error']}; "
                 f"remove it with `plm packs remove {args.name}`")
    missing = [v["model"] for v in row["models"].values() if v["pulled"] is not True]
    if any(v["pulled"] is None for v in row["models"].values()):
        sys.exit(f"plm packs: installed {args.name}, but Ollama can't be reached to check its models; "
                 "start Ollama, then run `plm packs doctor`")
    for model in dict.fromkeys(missing):
        print(f"pulling {model}", flush=True)
        try:
            _pull(model)
        except (RuntimeError, urllib.error.URLError, OSError) as e:
            sys.exit(f"plm packs: installed {args.name}, but pulling {model} failed: {e}")
    print(f"installed {args.name} {row['version']}; models: {', '.join(row['models'][t]['model'] for t in row['models'])}")
    return 0


def cmd_remove(args):
    if args.name == GENERAL.name:
        sys.exit("plm packs: the general pack is built into the core and can't be removed")
    row = next((r for r in installed() if r["name"] == args.name), None)
    if row is None:
        sys.exit(f"plm packs: no pack named {args.name!r} is installed")
    if _run(_installer("uninstall") + [row["dist"]]) != 0:
        sys.exit("plm packs: uninstall failed")
    if row["models"]:
        print(f"removed {args.name}; its models stay in Ollama, other packs may use them: "
              f"{', '.join(dict.fromkeys(row['models'].values()))}")
    return 0


def cmd_doctor(args):
    rows, pulled = installed(), pulled_models()
    problems = 0
    names = [r["name"] for r in rows]
    for name in {n for n in names if names.count(n) > 1}:
        print(f"FAIL  two installed packs are named {name!r}")
        problems += 1
    for r in rows:
        if r["error"]:
            print(f"FAIL  {r['name']}: fails to load: {r['error']}")
            problems += 1
            continue
        for model in dict.fromkeys(r["models"].values()):
            state = _is_pulled(model, pulled)
            if state is None:
                print(f"FAIL  {r['name']}: {model}: Ollama can't be reached")
            elif not state:
                print(f"FAIL  {r['name']}: {model} is not pulled (`ollama pull {model}`)")
            else:
                try:
                    ollama.load(model)
                    print(f"ok    {r['name']}: {model} loads")
                    continue
                except (RuntimeError, urllib.error.URLError, OSError) as e:
                    print(f"FAIL  {r['name']}: {model} doesn't load: {e}")
            problems += 1
    print("all packs healthy" if not problems else f"{problems} problem(s)")
    return 1 if problems else 0


def main(argv):
    ap = argparse.ArgumentParser(prog="plm packs", description="List, install, remove and check domain packs")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("list", help="installed packs and whether their models are pulled")
    p.add_argument("--json", action="store_true")
    p.set_defaults(run=cmd_list)
    p = sub.add_parser("install", help="install a pack, then pull the models it needs")
    p.add_argument("name")
    p.add_argument("--source", help="a directory holding plm-<name>/, the pack's directory, or a pip requirement")
    p.set_defaults(run=cmd_install)
    p = sub.add_parser("remove", help="uninstall a pack (its models stay in Ollama)")
    p.add_argument("name")
    p.set_defaults(run=cmd_remove)
    p = sub.add_parser("doctor", help="check every pack loads and every model it needs loads")
    p.set_defaults(run=cmd_doctor)
    args = ap.parse_args(argv)
    sys.exit(args.run(args))
