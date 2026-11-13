"""Follow-up questions: route and phrase a conversation's last message with the question it changes.

Packs solve one self-contained task, so "now for 200 ohm" after "A 220 ohm resistor carries 0.1 A. What is
the voltage across it?" means nothing on its own. resolve(messages) looks back for the anchor: the latest
earlier user message that a pack (not general) claims on its own. When the last message reads as a change
to it (FOLLOW: now..., what if..., and..., same but..., make it..., instead, again...), the conversation
stays in the anchor's pack and the task given to it is the anchor, every change since, and the last answer.
Anything else, including a complete question for another pack, is routed alone, as before.

phrase(messages, routed) then words the task (FOLLOWUP3_RULE, shipped 2026-11-10; evals/followup/run.py --set 3,
variant C: 51/90 vs 47/90, paired 95% +1 to +8): when the last message asks for a quantity of another kind than the
anchor ("and how far does it travel?" after a speed), a model first rewrites the conversation into one complete
question, because "answer the original question again" returned the original quantity; otherwise the task above.

A conversation of one message is routed exactly as plm.packs.detect routes it. Judged by
evals/test_followup.py (FOLLOWUP_RULE). Known limit: a follow-up that changes what code should do keeps
the anchor's examples, which the new code may then fail.
"""

import os
import re

from plm.packs import detect

REWRITER = os.environ.get("PLM_LARGE_MODEL", "qwen3:8b")
# Exactly the prompt measured as variant B/C (evals/followup/run.py REWRITE_PROMPT; test_followup checks they match).
REWRITE_PROMPT = """Below is a conversation. Rewrite the user's LAST message as one complete, self-contained question
that someone who never saw the conversation could answer: include every number, unit and condition from the
earlier question that still applies, with the change in the last message applied. If the last message asks for a
different unit, ask for that unit; otherwise ask for the same unit as before. Answer with the question only.

{transcript}"""

FOLLOW = re.compile(
    r"^\s*(?:now|and|also|same|what\s+if|what\s+about|how\s+about|instead|redo|try|make\s+it|rename|add|remove|only|"
    r"sort|include|change|repeat|again|do\s+it|then|but|double|halve|increase|decrease|swap|use|with|for|at|from)\b"
    r"|\b(?:instead|again|same\s+thing|same\s+but|as\s+well)\b",
    re.IGNORECASE,
)
MAX_PREVIOUS_ANSWER = 2000
ROUTE_FIX = False
ALWAYS_REWRITE = False


def resolve(messages):
    """{"pack", "task", "context"}: the pack for the last user message and the task to give it; context is
    True when earlier turns were folded into the task."""
    users = [(i, m["content"].strip()) for i, m in enumerate(messages)
             if m.get("role") == "user" and (m.get("content") or "").strip()]
    last_i, last = users[-1]
    anchor = next(((i, t) for i, t in reversed(users[:-1]) if detect(t) != "general"), None)
    alone = {"pack": detect(last), "task": last, "context": False}
    if anchor is not None:
        alone["anchor"] = anchor[1]  # for phrase(): even a message routed alone may ask a new quantity of it
    if len(users) < 2 or anchor is None:
        return alone
    adopted = False
    if not FOLLOW.search(last):
        # Measured, not shipped (FOLLOWUP4_RULE 2026-11-12: 66/83 with and without; off unless ROUTE_FIX): "what is its kinetic energy, in joules?" names no
        # pack on its own and went to general, which gives no checked number. If it asks for a quantity with a
        # unit, keep it in the earlier question's pack and always rewrite it (phrase) into a complete question.
        from plm.numeric.expected import expected_unit
        if not (ROUTE_FIX and alone["pack"] == "general" and expected_unit(last)[0]):
            return alone
        adopted = True
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
    return {"pack": pack, "task": "\n\n".join(parts), "context": True, "anchor": anchor_text, "rewrite": adopted}


def new_quantity(anchor, last):
    """True when last asks for a quantity of another kind (dimension) than anchor; False when either is unknown."""
    from plm.numeric.checks import ureg
    from plm.numeric.expected import expected_unit
    a, b = expected_unit(anchor)[0], expected_unit(last)[0]
    if not a or not b:
        return False
    try:
        return ureg.Quantity(1, a).dimensionality != ureg.Quantity(1, b).dimensionality
    except Exception:
        return False


def phrase(messages, routed, timeout=600):
    """The task for the last message of a resolved conversation: routed["task"], or, when it asks for a new kind of
    quantity than the earlier question, the conversation rewritten by REWRITER as one question (as measured: also
    when resolve routed the message alone). No model call otherwise. Falls back to routed["task"] if the rewrite fails or comes back empty."""
    if routed["pack"] == "general" or "anchor" not in routed:  # general gets the whole conversation anyway
        return routed["task"]
    last = next(m["content"] for m in reversed(messages) if m.get("role") == "user")
    # ALWAYS_REWRITE: experimental (FOLLOWUP5_RULE), off by default
    if not (ALWAYS_REWRITE and routed.get("context") or routed.get("rewrite") or new_quantity(routed["anchor"], last)):
        return routed["task"]
    from plm.ollama import ask
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    try:
        text = ask(REWRITER, REWRITE_PROMPT.format(transcript=transcript), False, 512, timeout)["response"].strip()
    except Exception:
        return routed["task"]
    return text or routed["task"]
