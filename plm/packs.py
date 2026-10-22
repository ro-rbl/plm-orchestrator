"""Pack registry, used by the CLI and the server to find packs the same way.

Each pack declares a `plm.pack.Pack` (its `PACK`), including its own claims();
`detect` asks every pack for its claim on a task and picks one with `plm.pack.pick`.
"""

from plm import aerospace, electrical, general, software
from plm.pack import pick

PACKS = {p.name: p for p in (electrical.PACK, aerospace.PACK, software.PACK, general.PACK)}


def detect(text):
    """Pick a pack from the task text: the strongest claim, else general."""
    return pick(PACKS.values(), text)
