"""Tidying a model's reply for people to read (the interface and the command line; the server passes replies as is).

Local models decorate answers: emoji in headings, "---" rules between every section, "### **Title**", LaTeX
delimiters. tidy(text) removes the decoration and keeps the Markdown structure (headings, lists, bold, code), which
the full-screen interface renders. unmark(text) goes on to plain text for a terminal that doesn't render Markdown.
Text inside ``` fences is never touched.
"""

import re

from plm.latex import plain

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\U0001F1E6-\U0001F1FF\U00002190-\U000021FF"
    "\U00002300-\U000023FF\U0000FE0F\U0000200D\U000020E3]+ ?")
KEEP = "→←↑↓↔⇒✓✗×"  # arrows and marks that carry meaning in an answer
RULE = re.compile(r"^[ \t]*(?:-{3,}|\*{3,}|_{3,})[ \t]*$", re.MULTILINE)
HEADING = re.compile(r"^(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$", re.MULTILINE)
MATH = re.compile(r"\\\((.+?)\\\)|\\\[(.+?)\\\]|\$\$(.+?)\$\$", re.DOTALL)
FENCE = re.compile(r"(```.*?```)", re.DOTALL)


def _emoji(m):
    kept = "".join(ch for ch in m.group(0) if ch in KEEP)
    return kept + (" " if kept and m.group(0).endswith(" ") else "")


def _frac(m):
    a, b = (x.strip() if re.fullmatch(r"[\w.]+", x.strip()) else f"({x.strip()})" for x in m.groups())
    return f"{a}/{b}"


def _math(m):
    """A LaTeX span as readable plain text: fractions as (a)/(b), roots as sqrt(x), the rest via plm.latex.plain."""
    t = next(g for g in m.groups() if g is not None)
    t = re.sub(r"([\^_])\{([^{}]*)\}", r"\1\2", t)  # v_{0} -> v_0, before fractions that contain it
    for _ in range(3):  # nested fractions
        t = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", _frac, t)
    t = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"sqrt(\1)", t)
    t = t.replace("\\cdot", "·").replace("\\times", "×").replace("\\approx", "≈").replace("\\,", " ")
    t = re.sub(r"(\\[a-zA-Z]+)(?=\\[a-zA-Z])", r"\1 ", t)  # \sin\theta -> \sin \theta
    t = re.sub(r"([\^_])\{([^{}]*)\}", r"\1\2", plain(t))
    return re.sub(r"\s+", " ", re.sub(r"\\([a-zA-Z]+)", r" \1 ", t)).strip()


def _heading(m):
    return f"{m.group(1)} {re.sub(r'[*_]{2}(.+?)[*_]{2}', lambda b: b.group(1), m.group(2)).strip()}"


def _tidy(text):
    text = EMOJI.sub(_emoji, text)
    text = RULE.sub("", text)
    text = MATH.sub(_math, text)
    text = HEADING.sub(_heading, text)  # "### **1. Title**" -> "### 1. Title": a heading is already emphasized
    return re.sub(r"\n{3,}", "\n\n", text)


def tidy(text):
    """text without emoji, horizontal rules, bold-inside-headings and LaTeX delimiters; Markdown otherwise kept."""
    parts = FENCE.split(text)
    return "".join(p if p.startswith("```") else _tidy(p) for p in parts).strip()


def _unmark(text):
    text = HEADING.sub(lambda m: m.group(2), text)
    text = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)
    return re.sub(r"^([ \t]*)[*+][ \t]+", r"\1- ", text, flags=re.MULTILINE)


def unmark(text):
    """tidy(text) as plain text: no #, ** or backticks; bullets as "- "."""
    parts = FENCE.split(tidy(text))
    return "".join(p if p.startswith("```") else _unmark(p) for p in parts).strip()
