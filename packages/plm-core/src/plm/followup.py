"""Follow-up questions: route and phrase a conversation's last message with the question it changes.

Packs solve one self-contained task, so "now for 200 ohm" after "A 220 ohm resistor carries 0.1 A. What is
the voltage across it?" means nothing on its own. resolve(messages) looks back for the anchor: the latest
earlier user message that a pack (not general) claims on its own. When the last message reads as a change
to it (FOLLOW: now..., what if..., and..., same but..., make it..., instead, again...), the conversation
stays in the anchor's pack and the task given to it is the anchor, every change since, and the last answer.
Anything else, including a complete question for another pack, is routed alone, as before.

A conversation of one message is routed exactly as plm.packs.detect routes it. Judged by
evals/test_followup.py (FOLLOWUP_RULE). Known limit: a follow-up that changes what code should do keeps
the anchor's examples, which the new code may then fail.
"""

import re

from plm.packs import detect

FOLLOW = re.compile(
    r"^\s*(?:now|and|also|same|what\s+if|what\s+about|how\s+about|instead|redo|try|make\s+it|rename|add|remove|only|"
    r"sort|include|change|repeat|again|do\s+it|then|but|double|halve|increase|decrease|swap|use|with|for|at|from)\b"
    r"|\b(?:instead|again|same\s+thing|same\s+but|as\s+well)\b",
    re.IGNORECASE,
)
MAX_PREVIOUS_ANSWER = 2000


def resolve(messages):
    """{"pack", "task", "context"}: the pack for the last user message and the task to give it; context is
    True when earlier turns were folded into the task."""
    users = [(i, m["content"].strip()) for i, m in enumerate(messages)
             if m.get("role") == "user" and (m.get("content") or "").strip()]
    last_i, last = users[-1]
    alone = {"pack": detect(last), "task": last, "context": False}
    if len(users) < 2 or not FOLLOW.search(last):
        return alone
    anchor = next(((i, t) for i, t in reversed(users[:-1]) if detect(t) != "general"), None)
    if anchor is None:
        return alone
    anchor_i, anchor_text = anchor
    pack = detect(anchor_text)
    changes = [t for i, t in users if anchor_i < i]
    answer = next((m["content"].strip() for m in reversed(messages[:last_i])
                   if m.get("role") == "assistant" and (m.get("content") or "").strip()), "")
    parts = [f"Original question:\n{anchor_text}"]
    if answer:
        parts.append(f"Previous answer:\n{answer[:MAX_PREVIOUS_ANSWER]}")
    parts.append("Change" + ("s, in order" if len(changes) > 1 else "") + ":\n" + "\n".join(changes))
    parts.append("Answer the original question again with the change applied.")
    return {"pack": pack, "task": "\n\n".join(parts), "context": True}
