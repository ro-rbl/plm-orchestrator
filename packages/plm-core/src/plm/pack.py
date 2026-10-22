"""What a pack declares, and how the router picks one from its claims.

Every pack exposes one `Pack`. The router asks each installed pack how strongly
it claims a task, takes the highest score, breaks ties by `priority`, and falls
back to the general pack when no pack claims the task.
"""

from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Callable, Optional


@dataclass(frozen=True)
class Pack:
    name: str
    version: str
    # text -> float: 0 means "not mine", higher means more evidence; inf means
    # the task is certainly this pack's (software's code-task pattern)
    claims: Callable[[str], float]
    priority: int          # breaks ties between equal claims; higher wins
    # solve(task, level=None, timeout=..., **options) -> dict with at least pack, task,
    # level, reason, answer, checked, unchecked_reason, trusted, steps, tokens, seconds.
    # `trusted` means the answer passed every check and there was something to check;
    # `checked` is False when the task gave the pack nothing to verify against.
    solve: Callable[..., dict]
    levels: dict           # adrenaline level -> plan (calm, alert, intensive)
    models: dict           # tier name -> Ollama model name
    unit_words: dict = field(default_factory=dict)  # numeric packs: extra unit vocabulary
    eval_set: Optional[str] = None                  # the pack's eval problems, relative to the repo
    solve_stream: Optional[Callable] = None         # like solve, yielding ("delta", text) then ("result", r)


def pick(packs, text, fallback="general"):
    """Name of the pack with the highest claim on `text` (ties by priority), else `fallback`."""
    scored = [(p.claims(text), p.priority, p.name) for p in packs]
    score, _, name = max(scored, default=(0, 0, fallback))
    return name if score > 0 else fallback


def evidence(term_re, text, symbols=None):
    """How many distinct domain terms (and unit symbols) the text uses: a claim score for packs."""
    n = len({m.lower() for m in term_re.findall(text)})
    return n + (len(symbols.findall(text)) if symbols else 0)


def discover():
    """(entry point, its Pack, or the exception loading it raised) for every installed pack.

    Never raises for a broken pack, so `plm packs` can still list and remove it.
    """
    for ep in entry_points(group="plm.packs"):
        try:
            yield ep, ep.load()
        except Exception as e:  # a pack is third-party code: any error means "failed to load"
            yield ep, e
