"""Adrenaline level for a SQL task, from its question and the tables in its schema: rules only, no model.

    calm      one table: filters, sorting, a single aggregate
    alert     one join or one GROUP BY: the question names two of the schema's tables, or asks per group
    intensive subqueries, window functions, rows that are missing, comparisons against an aggregate
              or another row, the top row of each group, counts thresholded per group

The cue families are written from those definitions (evals/sql/build_tasks.py), not fitted per task.
Evaluate them with:  .venv/bin/python evals/eval_levels.py --pack sql
"""

import re

from plm_sql.sqlgen import split_task

INTENSIVE_CUES = {
    "missing": r"\bnever\b|\bha(?:s|ve)n't\b|\bha(?:s|ve) no\b|\bnot (?:\w+ ){0,2}(?:to )?any\b|\bwithout (?:any|an?)\b",
    "versus aggregate": r"\b(?:more|less|higher|lower|above|below|greater)\b.{0,30}\bthan (?:the |their |its )?"
                        r"(?:average|overall|mean|manager|budget)\b",
    "top of group": r"\b(?:which|who)\b.{0,60}\b(?:the most|most often|the highest|the lowest|the fewest|the largest"
                    r"|most expensive|highest-paid)\b|\bfor each\b.{0,40}\b(?:most|highest|lowest)\b",
    "all of a set": r"\bboth\b.{0,40}\band\b|\bby every\b|\bevery \w+ who\b",
    "window": r"\branks?\b|\branking\b|\bprevious\b|\brunning (?:total|sum)\b|\bcumulative\b",
    "group threshold": r"\bwith (?:at least|more than|fewer than) \d+\b",
    "recursive": r"\brecursive\b|\beveryone under\b",
}
GROUP_CUE = re.compile(r"\beach\b|\bper\b", re.IGNORECASE)
TABLE_NAME = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?[\"`\[]?(\w+)", re.IGNORECASE)
SORT_PHRASE = re.compile(r"\bin (?:\w+ )?order\b|\border(?:ed)? by\b", re.IGNORECASE)


def stem(table):
    """How a table is named in prose: the last word of its name, singular, cut to 6 letters ("enroll")."""
    word = table.lower().rsplit("_", 1)[-1]
    word = word[:-3] + "y" if word.endswith("ies") else word[:-1] if word.endswith("s") else word
    return word[:6]


def tables_named(question, setup):
    prose = SORT_PHRASE.sub(" ", question.lower())
    return sorted({t for t in TABLE_NAME.findall(setup) if re.search(rf"\b{stem(t)}", prose)})


def classify(text):
    """Return (level, reason)."""
    task = split_task(text)
    q = task["question"]
    intensive = sorted(n for n, p in INTENSIVE_CUES.items() if re.search(p, q, re.IGNORECASE))
    if intensive:
        return "intensive", "cues: " + ", ".join(intensive)
    named = tables_named(q, task["setup"])
    if len(named) >= 2:
        return "alert", "joins " + ", ".join(named)
    if GROUP_CUE.search(q):
        return "alert", "per-group cue"
    return "calm", "one table, no group" if task["setup"] else "no schema, no join or group cues"
