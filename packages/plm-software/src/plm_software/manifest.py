"""The software pack's manifest: what the router needs to know about it."""

from plm.pack import Pack
from plm_software import controller
from plm_software.claims import claims

PACK = Pack(name="software", version="0.1.0", claims=claims, priority=100, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, eval_set="evals/software/tasks.jsonl")
