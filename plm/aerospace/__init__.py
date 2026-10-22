"""Aerospace pack: level rules and tiers; the rest is plm.numeric."""

from plm.pack import Pack
from plm.aerospace import controller
from plm.aerospace.claims import claims

PACK = Pack(name="aerospace", version="0.1.0", claims=claims, priority=50, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, eval_set="evals/aerospace/problems.jsonl")
