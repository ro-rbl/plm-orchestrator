"""The SQL pack's manifest: what the router needs to know about it."""

from plm.pack import Pack

from plm_sql import controller
from plm_sql.claims import claims

# Priority below software's 100: both claim with certainty a Python function that runs SQL, and that
# is a software task; above the numeric packs, which a schema's column names can trip.
PACK = Pack(name="sql", version="0.1.0", claims=claims, priority=90, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, eval_set="evals/sql/tasks.jsonl")
