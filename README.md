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
```

Each answer comes with a report: the level, every model call, tokens, time,
and why anything was escalated. Runs are logged to `logs/runs.jsonl`.

## Domain packs

| Pack | Routing | Check | Eval result |
|---|---|---|---|
| electrical | level picks the model: 4B + calculator, or 8B + calculator for intensive | unit and sanity checks | 47/50 at 36% of always-8B compute |
| software | cheap-first cascade 4B -> 8B -> coder 14B | code must pass the task's examples | 40/45 at 56% of always-coder compute |

## Layout

- `plm/`: the controller. `levels.py`, `checks.py`, `calc.py` and `controller.py`
  are the electrical pack, and `plm/software/` is the software pack.
- `evals/`: problem sets, graders, runners and offline routing simulations.
  `simulate_routing.py` and `simulate_code_routing.py` replay saved answers, so
  they need no model calls.
- `results/`: every model answer from the sweeps, which the simulations read.

## Tests

```bash
.venv/bin/python evals/grade.py evals/electrical/problems.jsonl --self-test
.venv/bin/python evals/test_checks.py
.venv/bin/python plm/calc.py
.venv/bin/python -m plm.software.sandbox
.venv/bin/python evals/software/build_tasks.py     # fails if any reference solution fails its tests
```
