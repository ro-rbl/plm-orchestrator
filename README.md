# PLM Adaptive Multi-Model Orchestrator

A local controller that sends each task to the cheapest small model likely to
get it right, checks the answer without knowing it, and escalates to a bigger
model when the check fails. Models run in [Ollama](https://ollama.com).

## Setup

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
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
for, no code examples). Runs are logged to `logs/runs.jsonl`. See `ROADMAP.md`
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

- Electrical and coding tasks go to their packs and are released only after
  they're checked, so a streamed answer arrives in one piece. Everything else
  goes to the 8B, streams token by token, and is never checked.
- A pack answer ends with a caveat line when it failed a check or had nothing
  to check against. The routing report is the extra `plm` field (on the last
  chunk when streaming).
- Packs see only the last user message and use their own token budgets; the general pack gets the whole
  conversation and the client's `temperature`, `top_p` and `max_tokens`.
- Every request is logged to `logs/server.jsonl` (`PLM_SERVER_LOG=off` to disable):
  which pack it went to shows how much traffic the packs actually cover.
- Loopback only unless `--allow-remote`: there is no authentication, and the
  software pack runs model-written code. Not supported: tool calling, images.
- `GET /health` answers 200 `{"status": "ok"}` only if Ollama answers. The
  server writes `logs/plm-serve.pid` and `logs/plm-serve.port`; stop it with
  `kill "$(cat logs/plm-serve.pid)"`.

## Domain packs

| Pack | Routing | Check | Eval result |
|---|---|---|---|
| electrical | level picks the model: 4B + calculator, or 8B + calculator for intensive | unit and sanity checks | 48/50 at 35% of always-8B compute |
| aerospace | everything to the 8B + calculator (routing to the 4B lost accuracy here) | unit and sanity checks | 39/50 at 41% of always-8B compute |
| software | cheap-first cascade 4B -> 8B -> coder 14B | code must pass the task's examples | 40/45 at 56% of always-coder compute |
| software `--thorough` | same cascade | examples + 8 tests written by the 8B from the task alone | 42/45 at 228%: about 1 in 8 generated tests is wrong, which forces extra escalations |

## Layout

- `plm/packs.py`: the pack registry and the interface every pack provides.
- `plm/numeric/`: shared by numeric packs: answer format and parser, calculator tool,
  unit/sanity checks, and the controller.
- `plm/numeric/levels.py`: the level classifier every numeric pack shares; a pack adds only its chain cues.
- `docs/pack-packaging.md`: proposed design for installing each pack separately (not built yet).
- `plm/electrical/`, `plm/aerospace/`: each numeric pack's level cues and tiers.
- `plm/software/`: the software pack: sandbox, code prompts, level rules, controller,
  and model-written tests for `--thorough`.
- `plm/general/`: the fallback for tasks no pack claims (the 8B, unchecked).
- `plm/server.py`: the OpenAI-compatible server; `plm/report.py`: answer text and caveats.
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
.venv/bin/python evals/test_server.py              # the HTTP server, same fakes
.venv/bin/python evals/test_detect.py              # which pack each task goes to
.venv/bin/python evals/dump_decisions.py           # every routing/unit/check decision, to diff before/after a refactor
python evals/compat_openai.py --fake                # with the official `openai` client (needs openai + pint)
.venv/bin/python -m plm.software.sandbox
.venv/bin/python -m plm.software.testgen
.venv/bin/python evals/software/build_tasks.py     # fails if any reference solution fails its tests
```
