# PLM Adaptive Multi-Model Orchestrator

A local controller that sends each task to the cheapest small model likely to
get it right, checks the answer without knowing it, and escalates to a bigger
model when the check fails. Models run in [Ollama](https://ollama.com).

## Setup

```bash
uv venv .venv && uv pip install --python .venv/bin/python -r requirements.txt
```

Models used by default (override with `PLM_SMALL_MODEL`, `PLM_LARGE_MODEL`,
`PLM_CODER_MODEL`): `hf.co/bartowski/mlabonne_Qwen3-4B-abliterated-GGUF:Q4_K_M`,
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

## Domain packs

| Pack | Routing | Check | Eval result |
|---|---|---|---|
| electrical | level picks the model: 4B + calculator, or 8B + calculator for intensive | unit and sanity checks | 47/50 at 36% of always-8B compute |
| software | cheap-first cascade 4B -> 8B -> coder 14B | code must pass the task's examples | 40/45 at 56% of always-coder compute |
| software `--thorough` | same cascade | examples + 8 tests written by the 8B from the task alone | 42/45 at 228%: about 1 in 8 generated tests is wrong, which forces extra escalations |

## Layout

- `plm/packs.py`: the pack registry and the interface every pack provides.
- `plm/numeric/`: shared by numeric packs: answer format and parser, calculator tool,
  unit/sanity checks, and the controller.
- `plm/electrical/`: the electrical pack's level rules and tiers.
- `plm/software/`: the software pack: sandbox, code prompts, level rules, controller,
  and model-written tests for `--thorough`.
- `evals/`: problem sets, graders, runners and offline routing simulations.
  `simulate_routing.py` and `simulate_code_routing.py` replay saved answers, so
  they need no model calls.
- `results/`: every model answer from the sweeps, which the simulations read.

## Tests

```bash
.venv/bin/python evals/grade.py evals/electrical/problems.jsonl --self-test
.venv/bin/python evals/test_checks.py
.venv/bin/python -m plm.numeric.calc
.venv/bin/python evals/test_controllers.py         # controllers, with Ollama replaced by scripted replies
.venv/bin/python -m plm.software.sandbox
.venv/bin/python -m plm.software.testgen
.venv/bin/python evals/software/build_tasks.py     # fails if any reference solution fails its tests
```
