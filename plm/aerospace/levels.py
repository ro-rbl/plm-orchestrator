"""Aerospace pack: chain cues for the shared numeric level rules (plm/numeric/levels.py).

Each family marks a problem where an intermediate result has to be computed and
reused. Written from aerospace practice, then checked against the eval set;
the holdout (evals/aerospace/holdout_levels.jsonl) was written before them.
Evaluate them with:  .venv/bin/python evals/eval_levels.py --pack aerospace
"""

from plm.numeric import levels as numeric_levels

CHAIN_CUES = {
    # orbit changes: speeds on both orbits, then the differences
    "transfer": r"hohmann|transfer orbit|from that orbit|escape velocity from (?:its|that|a) .*orbit"
                r"|\binclination\b|plane change",
    # each stage's mass ratio, then the sum
    "staging": r"two-stage|three-stage|\bstage [12]\b|drops? .*dry mass",
    # radius or period first, then the asked quantity
    "orbit-geometry": r"perigee|apogee|elliptical orbit|\bwhat (?:is its )?altitude\b|revolutions|in one day",
    # Mach or ideal states first, then stagnation, exit or actual conditions
    "flow-chain": r"stagnation|nozzle|isentropic efficiency",
    # lift coefficient or L/D first, then drag, power or range
    "performance": r"breguet|range equation|drag polar|best lift-to-drag|power (?:is )?(?:needed|required)"
                   r"|needed to overcome|thrust does it need",
    # an ideal result, then what is lost or needed
    "losses-sizing": r"gravity loss|including gravity|how much propellant|propellant does it need",
}


def features(text):
    return numeric_levels.features(text, CHAIN_CUES)


def classify(text):
    """Return (level, reason)."""
    return numeric_levels.classify(text, CHAIN_CUES)
