# Design: separately installable packs

_Status: proposed (2026-10-21). Not started. Implement on its own branch, in the
order of "Migration", with each step's check passing before the next._

## Goal

- The core (router, server, CLI, shared numeric engine, general pack) installs on
  its own and works: with no packs installed, every task goes to the general pack.
- Each domain pack (electrical, aerospace, software, and later physics, SQL, CAD)
  is its own installable package, and installing one makes the router use it
  with no change to the core.
- `plm packs install <name>` installs a pack and pulls the Ollama models it needs.

## Where things are coupled today

Three seams have to be cut. Everything else already goes through them.

1. **The pack list** is hard-coded: `plm/packs.py:PACKS` imports every pack.
   The server (`plm/server.py`) and CLI (`plm/__main__.py`) reach packs only
   through `PACKS` and `detect`.
2. **Routing** is one central function, `plm/packs.py:detect`, which holds every
   pack's vocabulary (`SOFTWARE_TASK`, `ELECTRICAL_TERM`, `UNIT_SYMBOL`,
   `AEROSPACE_TERM`, `QUANTITY`) and the electrical/aerospace tie-break.
3. **Unit words** live in one shared table, `plm/numeric/checks.py:UNIT_WORDS`,
   which mixes electrical and aerospace units.

## Target design

### Packages (one repo, several distributions)

```
packages/
  plm-core/        import name: plm           router, server, CLI, numeric engine, general pack
  plm-electrical/  import name: plm_electrical
  plm-aerospace/   import name: plm_aerospace
  plm-software/    import name: plm_software  (owns its sandbox and test writer)
```

Each has its own `pyproject.toml`. Packs depend on `plm-core` with a version
bound; numeric packs use the core's numeric engine (`plm.numeric`), so that
becomes a public API with a version.

### What a pack declares

Each pack exposes one object, registered under the entry-point group `plm.packs`:

```python
# packages/plm-aerospace/src/plm_aerospace/__init__.py
PACK = Pack(
    name="aerospace",
    version="0.1.0",
    claims=claims,          # text -> float: 0 means "not mine", higher means more evidence
    priority=50,            # breaks ties between claims; software is highest today
    solve=solve,            # same contract as today's controller.solve
    levels=LEVELS,          # calm / alert / intensive plans
    models={"large": "qwen3:8b"},              # Ollama models it needs, overridable by env
    unit_words={"newtons": "N", ...},          # numeric packs: extra unit vocabulary
    eval_set="evals/problems.jsonl",           # package data, optional
)
```

```toml
# packages/plm-aerospace/pyproject.toml
[project.entry-points."plm.packs"]
aerospace = "plm_aerospace:PACK"
```

The core finds installed packs with
`importlib.metadata.entry_points(group="plm.packs")`. The general pack is built
into the core and always present, as the fallback.

### Routing by claims

Replace the central `detect()` with: ask every installed pack for its claim
score, take the highest, break ties by `priority`, and fall back to general when
every score is 0. Today's rules map onto it directly:

- software: claims when `SOFTWARE_TASK` matches (highest priority, as now)
- electrical / aerospace: the score is today's `_evidence` count when the
  pack's existing condition holds (term + number/quantity/requested unit),
  else 0; electrical's higher priority reproduces "ties go to electrical"

### Unit vocabulary

The core keeps units every numeric pack needs (seconds, hours, meters,
kilograms, joules, ...). Each numeric pack contributes its own words, merged
when packs load. `requested_unit` then only knows the units of installed packs,
which is the point: an uninstalled pack's questions shouldn't look checkable.

### Commands

```bash
plm packs list                 # installed packs, versions, models present or missing
plm packs install aerospace    # pip install the pack, then ollama pull its missing models
plm packs remove aerospace
plm packs doctor               # every installed pack's models are pulled and load
```

`install` wraps pip. Until the packs are on PyPI it installs from a git
subdirectory, e.g.
`pip install "plm-aerospace @ git+https://github.com/<you>/plm-orchestrator#subdirectory=packages/plm-aerospace"`.
The server's `/health` and the CLI's `--pack` choices list installed packs.

## Migration (each step keeps behavior identical until step 4)

Before step 1, save the baseline: `.venv/bin/python evals/dump_decisions.py >
/tmp/decisions.before` (every text's pack, requested unit and level, and the
checks on every saved numeric answer: 272 texts, 1516 answers today).

1. **Manifest without moving files.** Add the `Pack` object and the claims API
   inside the current single package; build `PACKS` from local manifests.
   Check: `evals/test_detect.py` (184/184 known, 87/88 holdout), controller and
   server tests pass, and `evals/dump_decisions.py | diff /tmp/decisions.before -`
   prints nothing.
2. **Per-pack claims.** Move each pack's vocabulary and condition from
   `plm/packs.py` into its own `claims()`. Same check: the dump is identical.
3. **Per-pack units.** Move pack units out of `UNIT_WORDS` into each pack's
   manifest. Check: with all packs loaded, the dump is identical (it covers
   `requested_unit()` for every text and `check()` for every saved answer).
4. **Split into packages.** Create `packages/*` with a `pyproject.toml` each and
   install them editable (`uv pip install -e packages/plm-core -e
   packages/plm-electrical ...`). Check: the full test suite passes from the
   installed packages; a fresh venv with only `plm-core` routes every eval text
   to general and the server answers through the general pack.
5. **`plm packs` command and model pulls.** Check, in a fresh venv: core only ->
   everything general; `plm packs install aerospace` -> aerospace questions go to
   aerospace and its model is present; `plm packs remove aerospace` -> back to
   general.
6. **Docs:** install instructions per pack in the README.

## Decisions to make while implementing

- **Pack ids and import names:** `plm-electrical` / `plm_electrical` as above,
  or a namespace package (`plm.packs.electrical`). The flat names are simpler.
- **Where eval sets live:** shipped as package data (so `plm eval aerospace`
  works anywhere) or only in the repo. Results stay in the repo either way.
- **Claim calibration for third-party packs:** today's scores are term counts
  tuned for three packs. A fourth pack from someone else could out-claim them;
  priorities and a minimum score may need a rule.

## Risks

- **A pack is code.** Installing one runs whatever it contains, and the
  software sandbox does nothing about that. Only install packs you trust; say so
  in the README.
- **Version skew** between packs and the core's numeric engine: pin
  `plm-core>=X,<Y` in each pack and test packs against the core in CI.
- **Publishing to PyPI** needs an account and token: phase 5, tested live
  before use, like the other external dependencies.
