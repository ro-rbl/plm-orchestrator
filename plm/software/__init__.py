"""Software pack: code tasks, checked by running the examples (and optionally generated tests)."""

from plm.pack import Pack
from plm.software import controller
from plm.software.claims import claims

PACK = Pack(name="software", version="0.1.0", claims=claims, priority=100, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, eval_set="evals/software/tasks.jsonl")
