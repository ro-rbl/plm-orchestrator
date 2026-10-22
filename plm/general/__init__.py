"""General pack: anything no other pack claims, answered by the large model, unchecked."""

from plm.general import controller
from plm.pack import Pack

# Built into the core and always present: claims nothing, answers whatever no other pack claims.
PACK = Pack(name="general", version="0.1.0", claims=lambda text: 0, priority=0, solve=controller.solve,
            levels=controller.LEVELS, models=controller.MODELS, solve_stream=controller.solve_stream)
