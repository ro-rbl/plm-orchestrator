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


def expect(name, cond, detail=""):
    if not cond:
        FAILS.append(f"{name}: {detail}")


def reply(text):
    return {"response": text, "eval_tokens": len(text.split()), "prompt_tokens": 7, "load_s": 0, "wall_s": 0.0,
            "done_reason": "stop", "thinking_chars": 0, "mode": "fake"}


def fake_numeric(model, prompt, think, num_predict, timeout):
    PROMPTS.append(prompt)
    ohms = 200 if "now for 200 ohm" in prompt else 220
    return reply(f'```python\nprint(f"ANSWER: {{{ohms} * 0.1:.4g}} V")\n```')


def fake_cad(model, prompt, think, num_predict, timeout):
    return reply("```python\nimport cadquery as cq\nresult = (cq.Workplane('XY').box(40, 40, 40)\n"
                 "          .faces('>Z').workplane().hole(10))\n```")


def chat_text(app):
    return "\n".join(str(w.render()) for w in app.query_one("#chat", VerticalScroll).query(Static))


async def wait_idle(app, pilot, seconds=60):
    for _ in range(int(seconds * 10)):
        await pilot.pause(0.1)
        if not app.busy:
            return
    raise TimeoutError("the app stayed busy")


async def session(shots):
    app = tui.PlmApp()
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


def main():
    shots = sys.argv[sys.argv.index("--screenshots") + 1] if "--screenshots" in sys.argv else None
    real = numeric.ask, cad.ask
    numeric.ask, cad.ask = fake_numeric, fake_cad
    try:
        asyncio.run(session(shots))
    finally:
        numeric.ask, cad.ask = real
    for f in FAILS:
        print("FAIL", f)
    print("tui tests: all passed" if not FAILS else f"tui tests: {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
