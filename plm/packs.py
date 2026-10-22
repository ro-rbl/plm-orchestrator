"""Pack registry, used by the CLI and the server to find packs the same way.

Each pack declares a `plm.pack.Pack` (`PACK` in its manifest.py) with its own claims() and unit
words. Loading the packs here merges their unit words into plm.numeric.checks;
`detect` asks every pack for its claim on a task and picks one with `plm.pack.pick`.
"""

from plm.aerospace import manifest as aerospace
from plm.electrical import manifest as electrical
from plm.general import manifest as general
from plm.numeric.checks import add_unit_words
from plm.pack import pick
from plm.software import manifest as software

PACKS = {p.name: p for p in (electrical.PACK, aerospace.PACK, software.PACK, general.PACK)}
for _pack in PACKS.values():
    add_unit_words(_pack.unit_words)


def detect(text):
    """Pick a pack from the task text: the strongest claim, else general."""
    return pick(PACKS.values(), text)
