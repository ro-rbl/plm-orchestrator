"""Offline tests for the full-screen plm (plm/tui.py), driven by Textual's test pilot.

    .venv/bin/python evals/test_tui.py [--screenshots DIR]

The packs run for real; only the model calls are replaced by scripted replies (as in test_server.py), so no model
is loaded. A session: an electrical question, a follow-up, a CAD part, /help, an unknown command, /new. Skipped
(exit 0, with a note) when Textual isn't installed: it's the optional "tui" extra.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    import textual  # noqa: F401
except ImportError:
    print("tui tests: skipped (Textual isn't installed: pip install 'plm-core[tui]')")
    sys.exit(0)

import plm.numeric.controller as numeric  # noqa: E402
import plm_cad.controller as cad  # noqa: E402
from plm import tui  # noqa: E402
from textual.containers import VerticalScroll  # noqa: E402
from textual.widgets import Static, TabbedContent  # noqa: E402

FAILS = []
PROMPTS = []
MODELS_SEEN = []


def expect(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name}: {detail}")


def reply(text):
    return {"response": text, "eval_tokens": len(text.split()), "prompt_tokens": 7, "load_s": 0, "wall_s": 0.0,
            "done_reason": "stop", "thinking_chars": 0, "mode": "fake"}


def fake_numeric(model, prompt, think, num_predict, timeout):
    PROMPTS.append(prompt)
    MODELS_SEEN.append(model)
    if "Give the answer in m." in prompt:  # /fuse's calculation step: a thickness of 3 mm
        return reply('```python\nprint("ANSWER: 0.003 m")\n```')
    ohms = 200 if "now for 200 ohm" in prompt else 220
    return reply(f'```python\nprint(f"ANSWER: {{{ohms} * 0.1:.4g}} V")\n```')


def fake_cad(model, prompt, think, num_predict, timeout):
    return reply("```python\nimport cadquery as cq\nresult = (cq.Workplane('XY').box(40, 40, 40)\n"
                 "          .faces('>Z').workplane().hole(10))\n```")


def fake_planner(model, prompt, think, num_predict, timeout):
    return reply('{"pack": "physics", "question": "A plate 40 mm wide carries 6000 N at 50 MPa. Find the thickness. '
                 'Give the answer in m.", "cad_task": "Make a plate 100 mm long, 40 mm wide and {value} mm thick."}')


CHATS = []


def fake_general_chat(model, messages, num_predict, timeout, options=None):
    CHATS.append(messages)
    text = ("Sure!\n\n---\n\n### ✅ **1. Plates** 🚀\n\n- **Charge** sits on the plates\n- \\( E = \\frac{1}{2} C V^{2} \\)"
            if "decorate" in messages[-1]["content"] else "Canberra.")
    return {"response": text, "eval_tokens": 3, "prompt_tokens": 40, "load_s": 0, "wall_s": 0.0,
            "done_reason": "stop", "thinking_chars": 0, "mode": "fake"}


def chat_text(app):
    return "\n".join(getattr(w, "source", None) or str(w.render())
                     for w in app.query_one("#chat", VerticalScroll).query(Static))


async def wait_idle(app, pilot, seconds=60):
    for _ in range(int(seconds * 10)):
        await pilot.pause(0.1)
        if not app.busy:
            return
    raise TimeoutError("the app stayed busy")


async def session(shots):
    app = tui.PlmApp()
    app.context_of = lambda model: 4096  # not whatever Ollama happens to have loaded (the assistant's 8B at 32768)
    async with app.run_test(size=(150, 42)) as pilot:
        await pilot.pause()
        expect("banner is orange", "plm" in str(app.query_one("#sub", Static).render()))

        async def ask(text):
            app.query_one("#ask").value = text
            await pilot.press("enter")
            await pilot.pause(0.2)
            await wait_idle(app, pilot)

        await ask("A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?")
        text = chat_text(app)
        expect("electrical answer shown", "22 V" in text and "✓ checked" in text and "electrical" in text, text[-300:])
        expect("electrical pack lit", app.query_one("#pack-electrical").has_class("live"))
        expect("cad pack not lit", not app.query_one("#pack-cad").has_class("live"))
        await ask("now for 200 ohm")
        text = chat_text(app)
        expect("follow-up answered in electrical", "20 V" in text and "(follow-up)" in text, text[-300:])
        expect("follow-up prompt carries the question", "220 ohm resistor" in PROMPTS[-1], PROMPTS[-1][:200])
        if shots:
            app.save_screenshot("tui_electrical.svg", path=shots)
        await ask("Make a CadQuery model of a 40 mm cube with a 10 mm hole through the center.")
        text = chat_text(app)
        expect("cad answer checked", "✓ checked" in text.split("Make a CadQuery")[-1], text[-300:])
        expect("cad pack lit, electrical not", app.query_one("#pack-cad").has_class("live")
               and not app.query_one("#pack-electrical").has_class("live"))
        for _ in range(300):  # the drawing is made in the background
            await pilot.pause(0.1)
            if "drawing the part" not in str(app.query_one("#part", Static).render()):
                break
        part = str(app.query_one("#part", Static).render())
        expect("part tab shows measurements", "40 × 40 × 40" in part, part)
        expect("part tab shows a drawing", sum(0x2800 < ord(c) <= 0x28FF for c in part) > 50, part[:300])
        expect("part tab active", app.query_one("#side", TabbedContent).active == "tab-part")
        if shots:
            app.save_screenshot("tui_cad.svg", path=shots)
        await ask("/help")
        expect("/help shows the commands", "/new" in chat_text(app))
        await ask("/frobnicate")
        expect("unknown command explained", "unknown command /frobnicate" in chat_text(app))
        await ask("/new")
        text = chat_text(app)
        expect("/new clears the chat and history", "220 ohm" not in text and app.history == [], text)

        # settings commands
        await ask("/pack nosuch")
        expect("/pack with an unknown name explains", "no pack 'nosuch'" in chat_text(app))
        await ask("/pack physics")
        expect("/pack shows in the status bar", "pack physics" in str(app.query_one("#overrides", Static).render()))
        await ask("A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?")
        expect("/pack physics routes an electrical question to physics", app.last["pack"] == "physics", app.last["pack"])
        await ask("/pack auto")
        await ask("/model coder")
        import plm_electrical.controller as ec
        before = dict(ec.MODELS)
        MODELS_SEEN.clear()
        await ask("A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?")
        expect("/model coder: every step used the coder", MODELS_SEEN and all("coder" in m for m in MODELS_SEEN), MODELS_SEEN)
        expect("/model is undone after the question", dict(ec.MODELS) == before, ec.MODELS)
        await ask("/model auto")
        await ask("/level intensive")
        await ask("A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?")
        expect("/level intensive is passed to the pack", app.last["level"] == "intensive", app.last["level"])
        await ask("/level auto")
        await ask("/show on")
        await ask("A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?")
        expect("/show prints the program", "print(f\"ANSWER" in chat_text(app), chat_text(app)[-400:])
        await ask("/show off")
        await ask("/settings")
        expect("/settings lists them", "settings: pack auto · model auto · level auto" in chat_text(app), chat_text(app)[-300:])
        import os
        import sqlite3
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            db = os.path.join(tmp, "music.sqlite")
            con = sqlite3.connect(db)
            con.execute("CREATE TABLE singer (singer_id INTEGER, name TEXT, age INTEGER)")
            con.commit()
            con.close()
            await ask(f"/db {db}")
            expect("/db sets PLM_SQL_DB for routing", os.environ.get("PLM_SQL_DB") == db)
            await ask("/db off")
            expect("/db off clears it", "PLM_SQL_DB" not in os.environ)
            out = os.path.join(tmp, "chat.md")
            await ask(f"/export {out}")
            expect("/export writes the conversation", os.path.exists(out) and "220 ohm" in open(out).read())
        # /fuse: planner -> the coder's calculation (3 mm) -> cad
        await ask("/fuse A steel plate 40 mm wide carries 6000 N; stress at most 50 MPa. Size it and model a 100 x 40 plate.")
        text = chat_text(app)
        expect("/fuse reports the plan and the value", "fusion (experimental): physics calculation → 3 mm → cad" in text,
               text[-400:])
        expect("/fuse's part is built and checked", app.last["pack"] == "cad" and app.last["fusion"]["value_mm"] == 3)
        expect("context meter shows tokens out of the window", "/ 4.1k" in str(app.query_one("#context", Static).render()),
               str(app.query_one("#context", Static).render()))

        app.history += [{"role": "user", "content": "x" * 30000}]  # a long general chat: ~10k tokens + reply
        app.update_context({"pack": "general", "steps": [{"model": "qwen3:8b", "prompt_tokens": 10000, "tokens": 50}]})
        expect("context meter shows the general pack's raised window", "/ 16.4k" in str(app.query_one("#context", Static).render()),
               str(app.query_one("#context", Static).render()))
        app.history.pop()
        import time as _t
        from plm import ollama as _ol
        expect("no progress listener left after answers", _ol.LISTENERS == [], _ol.LISTENERS)
        live = tui.progress_text("*", "electrical", [["qwen3:4b", _t.time() - 3, {"eval_tokens": 1200, "wall_s": 3}],
                                                     ["qwen3:8b", _t.time() - 2, None]], 5).plain
        expect("working line shows finished and running steps", "step 2 · qwen3:8b" in live
               and "✓ step 1 · qwen3:4b · 1.2k tokens · 3 s" in live and "5 s total" in live, live)
        expect("working line before any model call", "working…" in tui.progress_text("*", "cad", [], 0).plain)

        expect("/fuse lights both packs", app.query_one("#pack-physics").has_class("live")
               and app.query_one("#pack-cad").has_class("live"))

        # skills: instruction files turned on per session
        import tempfile as _tf
        from plm import skills as plm_skills
        with _tf.TemporaryDirectory() as sk:
            for name, packs, text in (("terse", "general", "Answer in one short sentence."),
                                      ("si-units", "general, electrical", "State the formula you used.")):
                Path(sk, name).mkdir()
                Path(sk, name, "SKILL.md").write_text(f"---\nname: {name}\ndescription: test skill\npacks: {packs}\n---\n{text}\n")
            app.skill_dirs = [sk]
            app.skills = plm_skills.discover([sk])
            await ask("/skills")
            expect("/skills lists them", "terse" in chat_text(app) and "si-units" in chat_text(app))
            await ask("/skill nosuch")
            expect("/skill with an unknown name explains", "no skill 'nosuch'" in chat_text(app))
            await ask("/skill terse")
            await ask("/skill si-units")
            expect("active skills show in the status bar",
                   "skill terse" in str(app.query_one("#overrides", Static).render()))
            await ask("What's the capital of Australia?")
            system = CHATS[-1][0] if CHATS else {}
            expect("the general pack gets the skills as a system message", system.get("role") == "system"
                   and "one short sentence" in system["content"] and "formula you used" in system["content"], CHATS[-1:])
            expect("the general pack is asked for plain answers without emoji", "No emoji" in system["content"])
            await ask("Please decorate: how does a capacitor store energy?")
            import io
            from rich.console import Console
            reply = app.query(".reply").last()
            out = io.StringIO()
            Console(file=out, width=100, color_system=None).print(tui.Reply(reply.source))
            shown = out.getvalue()
            expect("a decorated reply is tidied", reply.source == "Sure!\n\n### 1. Plates\n\n- **Charge** sits on the "
                   "plates\n- E = 1/2 C V^2", reply.source)
            expect("the reply is rendered, not printed as Markdown source", "**" not in shown and "#" not in shown
                   and "✅" not in shown and "1. Plates" in shown and "Charge sits on the plates" in shown, shown)
            await ask("A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?")
            expect("a pack named by a skill gets its instructions", "State the formula you used." in PROMPTS[-1]
                   and "one short sentence" not in PROMPTS[-1], PROMPTS[-1][-200:])
            await ask("/skill si-units off")
            await ask("A 220 ohm resistor carries 0.1 A. What is the voltage across it, in volts?")
            expect("/skill off stops it", "State the formula you used." not in PROMPTS[-1])



def help_renders():
    from rich.text import Text
    try:
        Text.from_markup(tui.HELP)
    except Exception as e:  # a bracket in the help is read as a style
        FAILS.append(f"/help text doesn't render: {e}")


def main():
    shots = sys.argv[sys.argv.index("--screenshots") + 1] if "--screenshots" in sys.argv else None
    import plm.fusion as fusion
    import plm.general.controller as general
    real = numeric.ask, cad.ask, fusion.ask, general.chat
    numeric.ask, cad.ask, fusion.ask, general.chat = fake_numeric, fake_cad, fake_planner, fake_general_chat
    help_renders()
    try:
        asyncio.run(session(shots))
    finally:
        numeric.ask, cad.ask, fusion.ask, general.chat = real
    for f in FAILS:
        print("FAIL", f)
    print("tui tests: all passed" if not FAILS else f"tui tests: {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
