"""The CAD pack's manifest: what the router needs to know about it."""

from plm.pack import Pack

from plm_cad import controller
from plm_cad.claims import claims

# Priority above software's 100: both claim "write a CadQuery program ..." with certainty.
PACK = Pack(name="cad", version="0.1.0", claims=claims, priority=110, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, eval_set="evals/cad/problems.jsonl")
