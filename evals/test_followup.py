"""Follow-up questions: which pack a conversation's last message goes to, and whether earlier turns are used.

    .venv/bin/python evals/test_followup.py [-v]

Until 2026-11-08 the server routed and solved only the last user message, so "now for 200 ohm" after an
electrical question went to the general pack with nothing to go on. plm.followup.resolve(messages) decides
whether the last message is a follow-up; if so the pack gets the earlier question and the change.

Cases: evals/router/followup_cases.jsonl, written before plm/followup.py existed: 25 follow-ups (fu*: a change to
an electrical, aerospace, physics, software, sql or cad question) and 15 messages that start something new
(nf*: thanks, chat, or a complete question for another pack).

FOLLOWUP_RULE, fixed 2026-11-08 before the code: it ships iff all of
    (a) at least 20 of the 25 follow-ups go to their pack with context
    (b) at least 13 of the 15 others go to their labeled pack without context
    (c) a conversation of one message routes exactly as before (plm.packs.detect), with no context,
        for every existing routing text (evals/test_detect.py's sets)
Exits 1 if any fails, so after it ships this is a regression test.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "evals"))

from plm.followup import resolve  # noqa: E402
from plm.packs import detect  # noqa: E402
from test_detect import holdout_texts, known_texts, latex_texts  # noqa: E402


def phrase_checks():
    """(d) phrase(): variant C as measured (FOLLOWUP3_RULE), with the model faked."""
    import plm.followup as fu
    import plm.ollama as ol
    sys.path.insert(0, str(ROOT / "evals/followup"))
    import run as measured
    fails = []
    if fu.REWRITE_PROMPT != measured.REWRITE_PROMPT:
        fails.append("REWRITE_PROMPT differs from the measured one in evals/followup/run.py")
    anchor = "A car accelerates from rest at 3 m/s^2 for 8 s. What speed does it reach, in meters per second?"
    for last, want in [("how far does it travel in that time, in meters?", True), ("now for 12 s", False),
                       ("and in km/h?", False), ("what is its kinetic energy, in joules?", True)]:
        if fu.new_quantity(anchor, last) != want:
            fails.append(f"new_quantity({last!r}) != {want}")
    calls, real = [], ol.ask
    def fake(model, prompt, think, n, timeout):
        calls.append(prompt)
        return {"response": " How far does a car travel from rest at 3 m/s^2 in 8 s, in meters? "}
    ol.ask = fake
    try:
        for last, rewritten in [("and what distance does it cover in that time, in meters?", True), ("now for 12 s", False)]:
            msgs = [{"role": "user", "content": anchor}, {"role": "assistant", "content": "24 m/s"},
                    {"role": "user", "content": last}]
            routed = fu.resolve(msgs)
            task = fu.phrase(msgs, routed)
            if rewritten and task != "How far does a car travel from rest at 3 m/s^2 in 8 s, in meters?":
                fails.append(f"new quantity not rewritten: {task!r}")
            if not rewritten and task != routed["task"]:
                fails.append("value change was rewritten")
        if len(calls) != 1 or "assistant: 24 m/s" not in calls[0]:
            fails.append(f"rewriter calls {len(calls)}")
        def broken(*a):
            raise TimeoutError("down")
        ol.ask = broken
        msgs[-1]["content"] = "and what distance does it cover in that time, in meters?"
        routed = fu.resolve(msgs)
        if fu.phrase(msgs, routed) != routed["task"]:
            fails.append("a failed rewrite didn't fall back to today's task")
    finally:
        ol.ask = real
    lamp = "A 24 V supply feeds a 30 W lamp. What current flows, in amperes?"
    chat = [{"role": "user", "content": lamp}, {"role": "assistant", "content": "1.25 A"},
            {"role": "user", "content": "now a 60 W lamp"}, {"role": "assistant", "content": "2.5 A"},
            {"role": "user", "content": "how much energy does it use in 3 hours, in watt-hours?"}]
    routed = fu.resolve(chat)  # FOLLOWUP7_RULE: a second follow-up still follows the first question
    if routed.get("anchor") != lamp or not fu.new_quantity(routed["anchor"], chat[-1]["content"]):
        fails.append(f"a second follow-up lost the first question: {routed.get('anchor')!r}")
    for f in fails:
        print("   FAIL", f)
    print(f"(d) phrase (variant C): {'ok' if not fails else f'{len(fails)} failed'}")
    return not fails


def main():
    verbose = "-v" in sys.argv
    cases = [json.loads(line) for line in open(ROOT / "evals/router/followup_cases.jsonl") if line.strip()]

    def score(group, label, need):
        miss = []
        for c in group:
            r = resolve(c["messages"])
            if r["pack"] != c["pack"] or r["context"] != c["context"]:
                miss.append((c, r))
        ok = len(group) - len(miss)
        print(f"{label}: {ok}/{len(group)} (need {need})")
        for c, r in miss if verbose else []:
            print(f"   miss {c['id']}: want {c['pack']}{' +context' if c['context'] else ''}, got {r['pack']}"
                  f"{' +context' if r['context'] else ''}: {c['messages'][-1]['content'][:70]!r}")
        return ok >= need

    a = score([c for c in cases if c["id"].startswith("fu")], "(a) follow-ups to their pack, with context", 20)
    b = score([c for c in cases if c["id"].startswith("nf")], "(b) new messages to their pack, alone", 13)
    texts = [t for _, t, _ in known_texts() + holdout_texts() + latex_texts()]
    changed = [t for t in texts if (r := resolve([{"role": "user", "content": t}]))["pack"] != detect(t) or r["context"]]
    c = not changed
    print(f"(c) one-message conversations unchanged: {len(texts) - len(changed)}/{len(texts)}")
    for t in changed[:10] if verbose else []:
        print(f"   changed: {t[:90]!r}")
    d = phrase_checks()
    passed = a and b and c and d
    print("FOLLOWUP_RULE:", "PASS" if passed else "FAIL")
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
