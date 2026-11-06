# plm-core

Router, OpenAI-compatible server, CLI, numeric engine and the general pack; domain packs install separately.

`plm` sends each task to the cheapest local model (via [Ollama](https://ollama.com)) likely to get it
right, checks the answer without knowing it, and escalates when the check fails. This package is the
router, the `plm` command, an OpenAI-compatible server and the general pack; domain packs install
separately with `plm packs install <name>` (electrical, aerospace, physics, software, sql, cad).

```bash
uv tool install plm-core        # or: pip install plm-core
plm packs install electrical
plm "A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?"
```

Needs Python 3.13 and a running Ollama. Documentation, results and caveats: https://github.com/ro-rbl/plm-orchestrator
