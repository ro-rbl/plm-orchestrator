"""Pack registry, used by the CLI and the server to find packs the same way.

Domain packs are separate distributions that register a `plm.pack.Pack` under
the `plm.packs` entry-point group; the general pack is built in and always
present. Loading the packs here merges their unit words into plm.numeric.checks;
`detect` asks every pack for its claim on a task and picks one with `plm.pack.pick`.
A pack that is installed but fails to load is an error, not a silently missing pack.
"""

from plm.general.manifest import PACK as GENERAL
from plm.numeric.checks import add_unit_words
from plm.latex import plain
from plm.pack import Pack, discover, pick


def _installed():
    found = [GENERAL]
    for ep, pack in discover():
        if not isinstance(pack, Pack):
            raise RuntimeError(f"pack {ep.name!r} ({ep.value}) failed to load: {pack!r}; "
                               f"fix it, or uninstall it with `plm packs remove {ep.name}`")
        if pack.name in {p.name for p in found}:
            raise RuntimeError(f"two installed packs are named {pack.name!r} (entry point {ep.value})")
        found.append(pack)
    # highest priority first, general (priority 0) last
    return {p.name: p for p in sorted(found, key=lambda p: (-p.priority, p.name))}


PACKS = _installed()
for _pack in PACKS.values():
    add_unit_words(_pack.unit_words)


def detect(text):
    """Pick a pack from the task text (LaTeX read as plain text): the strongest claim, else general."""
    return pick(PACKS.values(), plain(text))
