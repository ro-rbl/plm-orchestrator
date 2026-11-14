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

answer(messages, routed, solve) is what the server, the CLI and the interface call (FOLLOWUP6_RULE, shipped
2026-11-13; evals/followup/run6.py, set 6: 88/92 vs 78/92, paired 95% +4 to +17; qwen3:8b alone 89/92): a follow-up
to a numeric pack is answered by whole(), the pack's large model with the whole conversation and the calculator
format in one call; when that answer has an issue, and for every other pack, the pack solves phrase()'s task.

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
# Shipped 2026-11-13 (FOLLOWUP6_RULE, evals/followup/run6.py, set 6 of 92: 88 vs 78 right, paired 95% +4 to +17; the
# 8B alone 89): answer() gives a numeric pack's follow-up to its large model with the whole conversation. False = before.
WHOLE = True
WHOLE_PROMPT = "Below is a conversation. Answer the user's last message.\n\n{transcript}\n\n"
WHOLE_TOKENS = 1024

# Experimental (FOLLOWUP7_RULE, evals/followup/run7.py), off: in a conversation with several follow-ups, keep the
# question they all change as the anchor. Conversations with one earlier user message are unaffected.
ROOT_ANCHOR = False


def _anchor(earlier):
    """(index, text) of the earlier user message the last one may be following, or None. Shipped: the latest one a
    pack claims on its own, so after "now a 60 W lamp" (claimed by electrical) the lamp question itself is lost.
    ROOT_ANCHOR: an earlier message that was itself a follow-up (a change, or a new kind of quantity asked of the
    anchor so far) never becomes the anchor."""
    if not ROOT_ANCHOR:
        return next(((i, t) for i, t in reversed(earlier) if detect(t) != "general"), None)
    root = None
    for i, t in earlier:
        if root is not None and (FOLLOW.search(t) or new_quantity(root[1], t)):
            continue
        if detect(t) != "general":
            root = (i, t)
    return root


def resolve(messages):
    """{"pack", "task", "context"}: the pack for the last user message and the task to give it; context is
    True when earlier turns were folded into the task."""
    users = [(i, m["content"].strip()) for i, m in enumerate(messages)
             if m.get("role") == "user" and (m.get("content") or "").strip()]
    last_i, last = users[-1]
    anchor = _anchor(users[:-1])
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


def answer(messages, routed, solve, timeout=300):
    """The result for a conversation's last message, routed to a pack other than general. solve(task) is that
    pack's solver. A follow-up to a numeric pack is answered by whole() (FOLLOWUP6_RULE); if that isn't one, or its
    answer has an issue (no program, a program error, a failed unit check), the pack solves phrase()'s task as
    before, and the failed step is kept at the front of the result's steps and counted in its tokens."""
    first = whole(messages, routed, timeout) if WHOLE else None
    if first and not first["steps"][-1]["issues"]:
        return first
    result = solve(phrase(messages, routed))
    if first:
        result["steps"] = first["steps"] + result["steps"]
        result["tokens"] += first["tokens"]
    return result


def whole(messages, routed, timeout=300):
    """A follow-up to a numeric pack answered by that pack's large model from the whole conversation, with the
    calculator format: one model call, no reworded task. Returns a result shaped like plm.numeric.controller.solve's,
    or None when this isn't such a follow-up (not a numeric pack, no earlier pack question, or a message that
    neither changes it nor asks a new kind of quantity of it: exactly the cases where the shipped path uses the
    conversation). The caller falls back to phrase() + the pack when the last step has issues."""
    import time

    from plm.numeric import calc, si
    from plm.numeric.answers import parse_answer
    from plm.numeric.expected import check_expected, expected_unit
    from plm.ollama import ask
    from plm.packs import PACKS

    pack = PACKS[routed["pack"]]
    model = pack.models.get("large")
    if not pack.unit_words or not model or "anchor" not in routed:
        return None
    last = next(m["content"] for m in reversed(messages) if m.get("role") == "user")
    if not (routed.get("context") or new_quantity(routed["anchor"], last)):
        return None
    start = time.time()
    transcript = "\n".join(f"{m['role']}: {(m.get('content') or '')[:MAX_PREVIOUS_ANSWER]}" for m in messages)
    question = last if expected_unit(last)[0] else routed["anchor"]  # the message that says what unit is asked
    if si.ENABLED:  # SI_RULE: the model sees no unit prefixes
        transcript = si.normalize(transcript)
    r = ask(model, WHOLE_PROMPT.format(transcript=transcript) + calc.TOOL_FORMAT, False, WHOLE_TOKENS, timeout)
    code = calc.extract_program(r["response"])
    output, program_error = calc.run_program(code) if code else ("", "no code block")
    asked = si.normalize(question) if si.ENABLED else question
    step = {"model": model, "strategy": "tool", "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
            "model_text": r["response"], "capped": r["done_reason"] == "length", "program": code, "output": output,
            "issues": ([program_error] if program_error else []) + check_expected(asked, output),
            "seconds": time.time() - start}
    parsed = parse_answer(output)
    answer = {"value": parsed[0], "unit": parsed[1]} if parsed else None
    if answer and asked != question:
        answer = si.restore(answer, question, asked)
    checked = expected_unit(question)[0] is not None
    return {"pack": pack.name, "task": last, "level": "follow-up", "reason": "follow-up: the whole conversation",
            "answer": answer, "checked": checked,
            "unchecked_reason": None if checked else "the question names no unit or quantity, so the answer couldn't be checked",
            "trusted": checked and not step["issues"], "steps": [step], "tokens": step["tokens"],
            "seconds": time.time() - start}
