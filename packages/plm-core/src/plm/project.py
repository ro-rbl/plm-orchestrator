"""A project folder for the interface (/project <folder>): the files a question names are read into the task, and
the code of an answer is written back into the folder.

Nothing here raises for an ordinary problem: a missing, unreadable, binary or oversized file is reported as a note,
and a file name that would land outside the folder is refused. Before an existing file is overwritten its old
contents are kept beside it as <name>.bak.
"""

import re
from pathlib import Path

EXTENSIONS = {"python": ".py", "py": ".py", "javascript": ".js", "js": ".js", "typescript": ".ts", "ts": ".ts",
              "sql": ".sql", "bash": ".sh", "sh": ".sh", "zsh": ".sh", "html": ".html", "css": ".css", "json": ".json",
              "c": ".c", "cpp": ".cpp", "go": ".go", "rust": ".rs", "java": ".java", "swift": ".swift", "yaml": ".yaml",
              "toml": ".toml", "markdown": ".md"}
NAME = re.compile(r"(?<![\w./-])((?:[\w-]+/)*[\w-]+\.(?:" + "|".join(sorted({e[1:] for e in EXTENSIONS.values()} | {"txt", "csv"})) + r"))(?![\w/])")
FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
MAX_FILE = 12000  # characters of one file given to the model (about 3000 tokens)


def mentioned(text):
    """File names in text, in order, without repeats."""
    return list(dict.fromkeys(NAME.findall(text)))


def inside(root, name):
    """The path of name inside root; ValueError when it would be outside it."""
    root = Path(root).resolve()
    path = (root / name).resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"{name} is outside the project folder {root}")
    return path


def with_files(root, text):
    """(text plus the contents of the project files it names, notes for the user). Files that don't exist yet
    are left out without a note: the answer will create them."""
    parts, notes = [], []
    for name in mentioned(text):
        try:
            path = inside(root, name)
            if not path.is_file():
                continue
            body = path.read_text()
        except (OSError, UnicodeDecodeError, ValueError) as e:
            notes.append(f"couldn't read {name}: {e}")
            continue
        if len(body) > MAX_FILE:
            notes.append(f"{name} is {len(body)} characters; only the first {MAX_FILE} were given to the model")
            body = body[:MAX_FILE]
        lang = next((k for k, v in EXTENSIONS.items() if v == path.suffix), "")
        parts.append(f"Current contents of {name}:\n```{lang}\n{body.rstrip()}\n```")
        notes.append(f"read {name} ({len(body)} characters)")
    return ("\n\n".join([text, *parts]) if parts else text), notes


def code_of(body):
    """(language, source) of the longest fenced code block in an answer, or None."""
    blocks = [(m.group(1), m.group(2).rstrip() + "\n") for m in FENCE.finditer(body or "")]
    return max(blocks, key=lambda b: len(b[1])) if blocks else None


def target(text, language, root):
    """The file an answer to text should go to: the first file it names, else a new plm_<n> file."""
    names = mentioned(text)
    if names:
        return names[0]
    ext = EXTENSIONS.get((language or "").lower(), ".txt")
    n = 1
    while (Path(root) / f"plm_{n}{ext}").exists():
        n += 1
    return f"plm_{n}{ext}"


def write(root, name, code):
    """Write code to name inside root. Returns (path, backup path or None). Raises ValueError (outside the folder)
    or OSError (can't write) with nothing changed."""
    path = inside(root, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        if path.read_text(errors="replace") == code:
            return path, None
        backup = path.with_name(path.name + ".bak")
        backup.write_text(path.read_text(errors="replace"))
    path.write_text(code)
    return path, backup
