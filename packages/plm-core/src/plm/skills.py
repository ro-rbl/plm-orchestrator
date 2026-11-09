"""Skills: instruction files, in the same format as Claude skills, that the TUI can turn on (/skill <name>).

A skill is a folder holding SKILL.md: a frontmatter block (name, description, and optionally packs) and then the
instructions. plm looks in ~/.plm/skills/ and ./.plm/skills/ (the current folder's, which wins on a name clash):

    ---
    name: metric-only
    description: Answer in SI units and say which formula was used.
    packs: general            # optional: general (default), a list like "general, electrical", or all
    ---
    Always answer in SI units...

The general pack gets every active skill's instructions as a system message. Checked packs get them only when the
skill names them (packs:), appended after the task: their checks read the task text, so a skill whose
instructions carry numbers or units could mislead a check.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

FRONT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


@dataclass
class Skill:
    name: str
    description: str
    instructions: str
    packs: list = field(default_factory=lambda: ["general"])
    path: str = ""

    def applies_to(self, pack):
        return "all" in self.packs or pack in self.packs


def parse(path):
    """A Skill from a SKILL.md, or None when it has no name or no instructions."""
    text = Path(path).read_text(errors="replace")
    m = FRONT.match(text)
    meta, body = ({}, text) if not m else (dict(
        (k.strip().lower(), v.strip().strip("\"'")) for k, v in
        (line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)), m.group(2))
    name = meta.get("name") or Path(path).parent.name
    packs = [p.strip() for p in re.split(r"[,\s\[\]]+", meta.get("packs", "general")) if p.strip()]
    if not name or not body.strip():
        return None
    return Skill(name=name, description=meta.get("description", ""), instructions=body.strip(), packs=packs,
                 path=str(path))


def discover(dirs=None):
    """{name: Skill} from ~/.plm/skills and ./.plm/skills (later folders win)."""
    dirs = dirs or [Path.home() / ".plm" / "skills", Path.cwd() / ".plm" / "skills"]
    found = {}
    for d in dirs:
        for f in sorted(Path(d).glob("*/SKILL.md")) if Path(d).is_dir() else ():
            try:
                s = parse(f)
            except OSError:
                continue
            if s:
                found[s.name] = s
    return found


def system_message(skills):
    """The general pack's system message for the active skills, or None."""
    on = [s for s in skills if s.applies_to("general")]
    if not on:
        return None
    return "\n\n".join(f"# Skill: {s.name}\n{s.instructions}" for s in on)


def apply_to_task(task, skills, pack):
    """A checked pack's task with the instructions of the active skills that name the pack appended."""
    on = [s for s in skills if s.applies_to(pack)]
    if not on:
        return task
    return task + "\n\nAdditional instructions:\n" + "\n".join(f"- {s.instructions}" for s in on)
