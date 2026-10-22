"""Electrical engineering pack: level rules and tiers; the rest is plm.numeric."""

from plm.pack import Pack
from plm.electrical import controller
from plm.electrical.claims import claims

PACK = Pack(name="electrical", version="0.1.0", claims=claims, priority=60, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, eval_set="evals/electrical/problems.jsonl")
