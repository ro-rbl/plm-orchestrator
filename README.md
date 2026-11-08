# PLM Adaptive Multi-Model Orchestrator

A local controller that sends each task to the cheapest small model likely to
get it right, checks the answer without knowing it, and escalates to a bigger
model when the check fails. Models run in [Ollama](https://ollama.com).

## Setup

Needs Python 3.13, [uv](https://docs.astral.sh/uv/) (or pip) and a running
Ollama. There's no PyPI release, so install from a checkout:

```bash
git clone https://github.com/ro-rbl/plm-orchestrator && cd plm-orchestrator
```

Or just the `plm` command, usable from any folder (packs then install from PyPI, or from this GitHub
repo for any not on PyPI yet):

```bash
uv tool install plm-core          # or the latest code: "plm-core @ git+https://github.com/ro-rbl/plm-orchestrator#subdirectory=packages/plm-core"
plm packs install electrical      # and any other packs, as below
```

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
.venv/bin/plm packs install cad
.venv/bin/plm packs install sql
```

| Pack | Package | Models it pulls (Ollama size) |
|---|---|---|
| electrical | `plm-electrical` | `hf.co/bartowski/Qwen_Qwen3-4B-GGUF:Q4_K_M` (2.5 GB), `qwen3:8b` (5.2 GB) |
| aerospace | `plm-aerospace` | `qwen3:8b` (5.2 GB) |
| software | `plm-software` | `qwen2.5-coder:14b` (9.0 GB); `--thorough` also uses `qwen3:8b` to write tests |
| physics | `plm-physics` | the 4B and `qwen3:8b` (as electrical) |
| cad | `plm-cad` | `qwen2.5-coder:14b` (9.0 GB); also installs CadQuery (about 1.3 GB on disk) to build and measure every part |
| sql | `plm-sql` | `qwen2.5-coder:14b` (9.0 GB), and the 4B as a second opinion when a database is given; the checker is Python's built-in SQLite |

```bash
.venv/bin/plm packs list                 # installed packs, versions, and whether their models are pulled
.venv/bin/plm packs doctor               # every pack loads and every model it needs loads in Ollama
.venv/bin/plm packs remove aerospace     # its tasks go back to the general pack; models stay in Ollama
.venv/bin/plm packs install chemistry --source <dir or pip requirement>       # a pack from elsewhere
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
    -e packages/plm-electrical -e packages/plm-aerospace -e packages/plm-software -e packages/plm-physics \
    -e packages/plm-cad -e packages/plm-sql
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
for, no code examples). Runs are logged to `runs.jsonl` in `./logs` if that folder
exists (a checkout), else in `~/.local/state/plm/` (`PLM_LOG_DIR` or `PLM_LOG` to change). See `ROADMAP.md`
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

- With `PLM_SQL_DB` set, SQL answers are checked on that database, and a question with no schema goes to the
  SQL pack when it asks for data and names the database's tables or columns ("How many singers do we have?"):
  115/120 held-out Spider questions. Advice that uses the data's words can go there too ("Which dog breeds
  suit owners with allergies?" with a kennel database: 4 of 34 look-alikes). The CLI's `--sql-db` always uses SQL.
- Tasks an installed pack claims (electrical, aerospace, physics, coding, CAD, SQL) go to that pack
  and are released only after they're checked, so a streamed answer arrives in
  one piece. Everything else goes to the 8B, streams token by token, and is never checked.
- A pack answer ends with a caveat line when it failed a check or had nothing
  to check against. The routing report is the extra `plm` field (on the last
  chunk when streaming).
- Packs see the last user message, or, when it's a follow-up to an earlier pack question ("now for 200 ohm",
  "what if...", "make it 10 mm thick"), that question, the last answer and the change; they use their own token
  budgets. The general pack gets the whole conversation and the client's `temperature`, `top_p` and `max_tokens`.
  The interactive `plm` (no question given) does the same with its session.
- Every request is logged to `server.jsonl` in `./logs` if that folder exists, else `~/.local/state/plm/`
  (`PLM_LOG_DIR` to move it, `PLM_SERVER_LOG=off` to disable):
  which pack it went to shows how much traffic the packs actually cover.
- Loopback only unless `--allow-remote`: there is no authentication, and the
  software pack runs model-written code. Not supported: tool calling, images.
- `GET /health` answers 200 `{"status": "ok"}` only if Ollama answers, and lists the installed packs. The
  server writes `logs/plm-serve.pid` and `logs/plm-serve.port`; stop it with
  `kill "$(cat logs/plm-serve.pid)"`.

## Domain packs

Public-benchmark results, and how each compares with published models: `docs/results.md`.


Which tasks each pack takes is in its `claims.py`; when two claim one task, the
stronger claim wins (more distinct domain terms), then the pack's priority.

| Pack | Routing | Check | Eval result |
|---|---|---|---|
| electrical | level picks the model: 4B + calculator, or 8B + calculator for intensive | unit and sanity checks | 48/50 at 35% of always-8B compute |
| aerospace | everything to the 8B + calculator (routing to the 4B lost accuracy here) | unit and sanity checks | 39/50 at 41% of always-8B compute |
| physics (mechanics, fluids, heat, materials) | level picks the model: 4B + calculator, escalating to 8B + calculator (as electrical) | unit and sanity checks | SciBench physics 69/144 (48%) vs 52 for the old 8B-direct policy, at 48% of its compute; TheoremQA 48/112 confirms it; own set 44/50 |
| cad (parts in millimeters) | everything to the coder 14B (the smaller models misuse CadQuery's API) | the part must build as one valid solid whose overall size matches the task; it can't see wrong features inside | own set 17/36; CADPrompt 28/195 (14%) exactly right (bounding box and volume within 0.1%) |
| sql (SQLite queries) | everything to the coder 14B (chosen for accuracy: Spider 76% vs the 8B's 67%, BIRD 51% vs 35%); with a database, a flagged query gets a 4B second opinion | the query must run on the task's own CREATE TABLE statements (no schema given: unchecked). With your database (`plm --sql-db file.sqlite`, or `PLM_SQL_DB` for the server; read-only) it runs on the real data, and a result with no rows, over 100 rows, only NULLs or none of the question's tables is flagged: 2230 vs 2212 of 2880 unseen Spider questions | Spider dev (300 sampled) 76%, BIRD mini-dev 51%, on a grade stricter than the official one |
| software | everything to the coder 14B (the cheap-first cascade lost on public benchmarks) | code must pass the task's examples | HumanEval+ 85%, MBPP+ 72% (540 tasks pooled: 76% vs the old cascade's 72%) |
| software `--thorough` | the coder, checked harder | examples + 8 tests written by the 8B from the task alone | measured with the old cascade (42/45 at 228%); not re-measured with the coder alone |

## Caveats

- **The project's own eval sets were written by Claude** (an AI model): every electrical, aerospace, physics,
  software, SQL and CAD problem, label and reference answer under `evals/`, and most routing cases. Holdouts
  guard against tuning a rule to its test, not against the author's blind spots. Public benchmarks
  (`docs/results.md`) are the independent check, and there is none yet for electrical or aerospace.
- Small sets: 36-50 problems per pack; differences of 1-2 between policies are noise.
- Everything was measured on one 24 GB Apple-silicon Mac; timings there are unreliable (it swapped), so
  token counts are the cost measure.

## Data and credits

Public benchmarks are downloaded into `.benchmarks/` (ignored by git) and not redistributed; each
`evals/bench_*.py` says where from. Thanks to their authors:
[Spider](https://yale-lily.github.io/spider) (Yu et al., 2018),
[BIRD](https://bird-bench.github.io/) (Li et al., 2023),
[EvalPlus](https://github.com/evalplus/evalplus) (HumanEval+ and MBPP+),
[SciBench](https://huggingface.co/datasets/xw27/scibench), [TheoremQA](https://github.com/wenhuchen/TheoremQA),
[UGPhysics](https://huggingface.co/datasets/UGPhysics/ugphysics), [GSM8K](https://github.com/openai/grade-school-math)
and [CADPrompt](https://github.com/Kamel773/CAD_Code_Generation).

One exception: `evals/router/sqldb_spider.jsonl` and `evals/router/sqldb_schemas.json` hold 120 Spider dev
questions and 20 Spider database schemas (table and column names), unchanged. They are from Spider, by Tao Yu
et al., licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), and those two files stay
under that license; the rest of the repo is MIT (`LICENSE`).

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
- `plm_cad`: a part described in words becomes a CadQuery program; `kernel.py` builds it in an isolated
  process and measures it, `checks.py` checks its size against the task without an answer key.
- `plm_sql`: a question about tables becomes a SQLite query; `sandbox.py` runs it on the task's schema in a
  throwaway read-only database in an isolated process, or on the user's database opened read-only, where
  `flags.py` reads the result.

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
.venv/bin/python -m plm.latex                     # LaTeX quantities read as plain text
.venv/bin/python evals/test_controllers.py         # controllers, with Ollama replaced by scripted replies
.venv/bin/python evals/test_manage.py             # `plm packs`, with Ollama, pip and entry points faked
.venv/bin/python evals/test_server.py              # the HTTP server, same fakes
.venv/bin/python evals/test_detect.py              # which pack each task goes to
.venv/bin/python evals/test_sqldb_routing.py       # with PLM_SQL_DB set: schema-free data questions go to sql
.venv/bin/python evals/test_followup.py            # follow-ups keep their conversation's pack and question
.venv/bin/python evals/cad/build_problems.py --verify .venv/bin/python   # every CAD reference builds to its key
.venv/bin/python evals/dump_decisions.py           # every routing/unit/check decision, to diff before/after a refactor
uv run --with openai --with pint python evals/compat_openai.py --fake   # with the official `openai` client
.venv/bin/python -m plm_software.sandbox
.venv/bin/python -m plm_software.testgen
.venv/bin/python evals/software/build_tasks.py     # fails if any reference solution fails its tests
.venv/bin/python evals/sql/build_tasks.py          # fails if a reference query is empty or depends on row order
.venv/bin/python evals/run_sql.py --self-test      # the SQL grader on the references and broken copies of them
```
