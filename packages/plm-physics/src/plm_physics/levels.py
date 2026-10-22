"""Physics pack: chain cues for the shared numeric level rules (plm/numeric/levels.py).

Each family marks a problem where an intermediate result has to be computed and
reused. Written from mechanics, fluids and heat practice after the eval set and
the holdout (evals/physics/holdout_levels.jsonl) were written; the holdout is
never used to tune them. Evaluate them with:
    .venv/bin/python evals/eval_levels.py --pack physics
"""

from plm.numeric import levels as numeric_levels

CHAIN_CUES = {
    # flight time first, then range or landing point
    "projectile": r"\b(?:thrown|kicked|rolls off|fired)\b.*\b(?:land|lands|returns?|how high|how far)\b"
                  r"|horizontally from|\bin the air\b",
    # an energy balance or an acceleration first, then the speed, height or distance
    "energy-chain": r"from rest down|at the bottom|just before it hits|how high does .* swing|before stopping"
                    r"|highest speed|brakes? (?:hard|from)",
    # momentum conserved first, then the energy or the motion after
    "collision": r"\bhits? a (?:stationary|parked)|move off together|stick together|embeds? itself|energy is lost",
    # moment of inertia and angular speed first, then the energy
    "rotation-energy": r"flywheel|rolls? without slipping|moment of inertia|\bsolid (?:disc|sphere|cylinder)\b"
                       r"|\bhollow (?:cylinder|sphere)\b",
    # continuity or Torricelli first, then pressure or flow
    "fluid-chain": r"\bnarrows\b|bernoulli|continuity|drains? .* through a hole|outflow rate"
                   r"|volume of the .* (?:above|below) the water",
    # a heat balance or a phase change, then a temperature or a time
    "heat-chain": r"\bmixed\b|final temperature|\bice\b.*\binto water\b|how long does it take|in one hour"
                  r"|internal energy|heated at constant|thermal stress",
    # a friction or banking limit first, then the speed it allows
    "curve-limit": r"\bcurve\b.*\b(?:highest|maximum|top) speed|(?:highest|maximum|top) speed .*\bcurve\b|\bbanked\b",
    # an area or a force from given sizes, then stress or extension
    "materials-chain": r"diameter of .* (?:holds|carries|load)|clamped between",
}


def features(text):
    return numeric_levels.features(text, CHAIN_CUES)


def classify(text):
    """Return (level, reason)."""
    return numeric_levels.classify(text, CHAIN_CUES)
