# PLM Adaptive Multi-Model Orchestrator

A local controller that sends each task to the cheapest small model likely to
get it right, checks the answer without knowing it, and escalates to a bigger
model when the check fails. Models run in [Ollama](https://ollama.com).

## Setup

Needs Python 3.13, [uv](https://docs.astral.sh/uv/) (or pip) and a running
Ollama. There's no PyPI release or public repo yet, so install from a checkout.

**1. The core.** Router, server, CLI, the shared numeric engine and the general
pack. On its own it works: every task goes to the general pack (`qwen3:8b`,
answers unchecked).

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -e packages/plm-core
ollama pull qwen3:8b
```

**2. The packs you want.** Each domain pack is its own package. `plm packs install`
installs it from this checkout's `packages/` and pulls any model it needs that
Ollama doesn't have yet:

```bash
.venv/bin/plm packs install electrical
.venv/bin/plm packs install aerospace
.venv/bin/plm packs install software
.venv/bin/plm packs install physics
```

| Pack | Package | Models it pulls (Ollama size) |
|---|---|---|
| electrical | `plm-electrical` | `hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M` (2.5 GB), `qwen3:8b` (5.2 GB) |
| aerospace | `plm-aerospace` | `qwen3:8b` (5.2 GB) |
| software | `plm-software` | the 4B and 8B above, `qwen2.5-coder:14b` (9.0 GB) |
| physics | `plm-physics` | the 4B and 8B above |

```bash
.venv/bin/plm packs list                 # installed packs, versions, and whether their models are pulled
.venv/bin/plm packs doctor               # every pack loads and every model it needs loads in Ollama
.venv/bin/plm packs remove aerospace     # its tasks go back to the general pack; models stay in Ollama
.venv/bin/plm packs install sql --source <dir or pip requirement>       # a pack from elsewhere
```

`--source` takes a directory holding `plm-<name>/`, the pack's own directory, or
any pip requirement, such as `"plm-x @ git+https://<repo>#subdirectory=packages/plm-x"`;
`PLM_PACKS_SOURCE` sets a default. A pack is code that runs on your machine, and
the software pack's sandbox doesn't change that: install only packs you trust.
A pack that fails to load stops the router, with a message naming it;
`plm packs remove <name>` still works then. How packs plug in: `docs/pack-packaging.md`.

**Development:** everything editable in one go (what the tests below expect):

```bash
uv pip install --python .venv/bin/python -e packages/plm-core \
    -e packages/plm-electrical -e packages/plm-aerospace -e packages/plm-software -e packages/plm-physics
```

Models used by default (override with `PLM_SMALL_MODEL`, `PLM_LARGE_MODEL`,
`PLM_CODER_MODEL`): `hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M` (the original Qwen3-4B),
`qwen3:8b`, `qwen2.5-coder:14b`. The Ollama address comes from `OLLAMA_HOST`.

## Use

```bash
.venv/bin/python -m plm "A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?"
.venv/bin/python -m plm "$(cat task.txt)"     # coding task; assert/>>> lines become checks
.venv/bin/python -m plm --pack software --show-work "..."
.venv/bin/python -m plm --thorough "$(cat task.txt)"   # software: also check against model-written tests
```

Each answer comes with a report: the level, every model call, tokens, time,
and why anything was escalated. An answer is marked unverified if it failed a
check, and unchecked if the task gave nothing to check against (no unit asked
for, no code examples). Runs are logged to `logs/runs.jsonl` under the
working directory (`PLM_LOG` to change). See `ROADMAP.md`
for what's next and `NEXT.md` for known open items.

## Use it as a model (OpenAI-compatible server)

```bash
.venv/bin/python -m plm serve            # prints: listening on http://127.0.0.1:<port>/v1
.venv/bin/python -m plm serve --port 8800
```

Point any OpenAI-compatible client (chat apps, editor plugins, the `openai` SDK)
at that URL with any API key, and pick the model `plm-router`, or
`plm-router-thorough` to add model-written tests to coding answers.

```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8800/v1", api_key="unused")
r = client.chat.completions.create(model="plm-router",
        messages=[{"role": "user", "content": "A 220 ohm resistor carries 0.1 A. Voltage across it, in volts?"}])
print(r.choices[0].message.content)    # 22 V
print(r.model_extra["plm"])            # pack, level, models called, checks, tokens
```

- Tasks an installed pack claims (electrical, aerospace, physics, coding) go to that pack
  and are released only after they're checked, so a streamed answer arrives in
  one piece. Everything else goes to the 8B, streams token by token, and is never checked.
- A pack answer ends with a caveat line when it failed a check or had nothing
  to check against. The routing report is the extra `plm` field (on the last
  chunk when streaming).
- Packs see only the last user message and use their own token budgets; the general pack gets the whole
  conversation and the client's `temperature`, `top_p` and `max_tokens`.
- Every request is logged to `logs/server.jsonl` under the working directory
  (`PLM_LOG_DIR` to move `logs/`, `PLM_SERVER_LOG=off` to disable):
  which pack it went to shows how much traffic the packs actually cover.
- Loopback only unless `--allow-remote`: there is no authentication, and the
  software pack runs model-written code. Not supported: tool calling, images.
- `GET /health` answers 200 `{"status": "ok"}` only if Ollama answers, and lists the installed packs. The
  server writes `logs/plm-serve.pid` and `logs/plm-serve.port`; stop it with
  `kill "$(cat logs/plm-serve.pid)"`.

## Domain packs

Which tasks each pack takes is in its `claims.py`; when two claim one task, the
stronger claim wins (more distinct domain terms), then the pack's priority.

| Pack | Routing | Check | Eval result |
|---|---|---|---|
| electrical | level picks the model: 4B + calculator, or 8B + calculator for intensive | unit and sanity checks | 48/50 at 35% of always-8B compute |
| aerospace | everything to the 8B + calculator (routing to the 4B lost accuracy here) | unit and sanity checks | 39/50 at 41% of always-8B compute |
| physics (mechanics, fluids, heat, materials) | pre-sweep default: 4B + calculator for calm/alert, escalating to the 8B; 8B + calculator for intensive | unit and sanity checks | sweep pending (`results/run_physics.sh`) |
| software | cheap-first cascade 4B -> 8B -> coder 14B | code must pass the task's examples | 40/45 at 56% of always-coder compute |
| software `--thorough` | same cascade | examples + 8 tests written by the 8B from the task alone | 42/45 at 228%: about 1 in 8 generated tests is wrong, which forces extra escalations |

## Layout

Core, in `packages/plm-core/src/plm/`:
- `pack.py`: what a pack declares (`Pack`) and how the router picks one from the packs' claims.
- `packs.py`: the registry: the general pack plus every pack installed under the `plm.packs` entry point.
- `numeric/`: shared by numeric packs: answer format and parser, calculator tool,
  unit/sanity checks (with the unit words every numeric pack may use), and the controller.
- `numeric/levels.py`: the level classifier every numeric pack shares; a pack adds only its chain cues.
- `general/`: the fallback for tasks no pack claims (the 8B, unchecked).
- `server.py`: the OpenAI-compatible server; `report.py`: answer text and caveats.

Packs, each in `packages/plm-<name>/src/plm_<name>/` with a `manifest.py` (its `PACK`)
and `claims.py` (which tasks it takes):
- `plm_electrical`, `plm_aerospace`, `plm_physics`: each numeric pack's level cues, tiers and unit words.
- `plm_software`: sandbox, code prompts, level rules, controller, and model-written tests for `--thorough`.

Elsewhere:
- `docs/pack-packaging.md`: the design for separately installable packs and its migration steps.
- `evals/`: problem sets, graders, runners and offline routing simulations.
  `simulate_routing.py` and `simulate_code_routing.py` replay saved answers, so
  they need no model calls.
- `results/`: every model answer from the sweeps, which the simulations read.

## Tests

```bash
.venv/bin/python evals/grade.py evals/electrical/problems.jsonl --self-test
.venv/bin/python evals/grade.py evals/aerospace/problems.jsonl --self-test
.venv/bin/python evals/test_checks.py
.venv/bin/python -m plm.numeric.calc
.venv/bin/python evals/test_controllers.py         # controllers, with Ollama replaced by scripted replies
.venv/bin/python evals/test_manage.py             # `plm packs`, with Ollama, pip and entry points faked
.venv/bin/python evals/test_server.py              # the HTTP server, same fakes
.venv/bin/python evals/test_detect.py              # which pack each task goes to
.venv/bin/python evals/dump_decisions.py           # every routing/unit/check decision, to diff before/after a refactor
uv run --with openai --with pint python evals/compat_openai.py --fake   # with the official `openai` client
.venv/bin/python -m plm_software.sandbox
.venv/bin/python -m plm_software.testgen
.venv/bin/python evals/software/build_tasks.py     # fails if any reference solution fails its tests
```
