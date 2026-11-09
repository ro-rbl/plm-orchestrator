"""The full-screen plm: chat on the left, the answer's part, code, steps and log on the right, and the packs and
models at the bottom (the active ones green). Opened by `plm` with no question when Textual is installed
(`pip install "plm-core[tui]"`); `plm "question"` and `plm --plain` stay plain text.

Each question is routed like the server routes it, follow-ups included (plm.followup). Commands: /help, /new
(forget the conversation), /quit. Keys: ctrl+n new conversation, ctrl+p part preview, ctrl+q quit.
"""

import json
import os
import re
import subprocess
import tempfile
import threading
import time
import urllib.request
from importlib.metadata import PackageNotFoundError, version

from rich.syntax import Syntax
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Input, Static, TabbedContent, TabPane

from plm import ollama
from plm.braille import draw
from plm.followup import resolve
from plm.packs import PACKS
from plm.paths import log_dir
from plm.report import answer_body, caveat, final_step, short

ORANGE, GREEN, YELLOW, RED, DIM = "#ff9e4a", "#7ee787", "#f2cc60", "#ff7b72", "#8a8d99"
BANNER = r"""       _
 _ __ | |_ __ ___
| '_ \| | '_ ` _ \
| |_) | | | | | | |
| .__/|_|_| |_| |_|
|_|"""
HELP = """[b]plm[/b]: ask anything. Calculations, code, SQL and CAD parts go to a pack that checks the answer.
Follow-ups ("now for 200 ohm", "make it 10 mm thick") stay with the question they change.

  /pack <name>|auto       send questions to one pack (physics, cad, sql, ...); auto routes again
  /model <name>|auto      use one model for every step (4b, 8b, coder, or a full Ollama name)
  /level calm|alert|intensive|auto   how hard a question is treated
  /thorough on|off        code answers are also checked against model-written tests (~4x compute)
  /db <file.sqlite>|off   check SQL on your database (read-only); data questions route to sql
  /show on|off            show each model's program or reasoning under the answer
  /fuse <problem>         experimental: plan a CAD + engineering problem, calculate, then model
  /export \\[file]          save the conversation as Markdown
  /settings               what's set now
  /new  /help  /quit      (also ctrl+n, ctrl+q); ctrl+p opens a CAD part's full drawing"""
SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


FRIENDLY = (("coder", "coder-14B"), ("qwen3:8b", "Qwen3-8B"), ("qwen3-4b", "Qwen3-4B"), ("qwen3:4b", "Qwen3-4B"))


def label(model):
    """A short name for the status bar: coder-14B, Qwen3-8B, Qwen3-4B, else plm.report.short's."""
    low = model.lower()
    return next((name for key, name in FRIENDLY if key in low), short(model))


def plm_version():
    try:
        return version("plm-core")
    except PackageNotFoundError:
        return "dev"


def loaded_models(timeout=2):
    """(names of models Ollama has loaded, total GB) or None when Ollama can't be reached."""
    try:
        with urllib.request.urlopen(f"{ollama.ollama_url()}/api/ps", timeout=timeout) as r:
            models = json.load(r).get("models", [])
    except (OSError, ValueError):
        return None
    return [m["name"] for m in models], sum(m.get("size", 0) for m in models) / 1e9


def status_line(result):
    """✓ checked · pack · models · tokens · time, as the line under an answer."""
    if result["pack"] == "general":
        mark = Text("○ unchecked", DIM)
    elif not result["checked"]:
        mark = Text("○ unchecked", YELLOW)
    elif result["trusted"]:
        mark = Text("✓ checked", GREEN)
    else:
        mark = Text("! failed a check", RED)
    steps = result["steps"]
    models = " → ".join(dict.fromkeys(label(s["model"]) for s in steps))
    tool = {"tool": " + calculator", "units": " + units calc"}.get(final_step(result).get("strategy"), "")
    line = Text.assemble(mark, (f" · {result['pack']}", DIM))
    if result.get("followup"):
        line.append(" (follow-up)", DIM)
    line.append(" · ", DIM)
    line.append(models + tool, YELLOW if len(steps) > 1 else DIM)
    line.append(f" · {result['tokens']} tok · {result['seconds']:.1f} s", DIM)
    return line


FENCE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)


def split_code(body):
    """[("text", str) | ("code", (language, source))] from an answer with ``` fences."""
    out, pos = [], 0
    for m in FENCE.finditer(body):
        out.append(("text", body[pos:m.start()]))
        out.append(("code", (m.group(1), m.group(2).rstrip())))
        pos = m.end()
    out.append(("text", body[pos:]))
    return out


class Chip(Static):
    pass


class PlmApp(App):
    TITLE = "plm"
    CSS = f"""
    Screen {{ background: #15161b; }}
    #main {{ width: 1fr; }}
    #banner {{ color: {ORANGE}; padding: 0 1; height: auto; }}
    #sub {{ color: {DIM}; padding: 0 1 1 1; height: auto; }}
    #chat {{ padding: 0 1; height: 1fr; }}
    #chat > Static {{ height: auto; margin-bottom: 0; }}
    #chat > .you {{ color: #79c0ff; margin: 1 0 0 0; }}
    .answer {{ text-style: bold; }}
    #ask {{ margin: 0 1 1 1; border: round #3a3e4c; background: #15161b; }}
    #side {{ width: 46; background: #1b1d24; border-left: solid #2c2f3a; }}
    #side Static {{ padding: 1; height: auto; }}
    #status {{ height: 1; background: #101115; color: {DIM}; }}
    #status Static {{ width: auto; padding: 0 1; }}
    .label {{ color: #5c5f6b; }}
    Chip {{ background: #262a35; color: #c9cad1; margin-right: 1; padding: 0 1; }}
    Chip.live {{ background: #1f3326; color: {GREEN}; }}
    #overrides {{ color: {ORANGE}; }}
    """
    BINDINGS = [Binding("ctrl+n", "new", "new"), Binding("ctrl+p", "preview", "part preview"),
                Binding("ctrl+q", "quit", "quit")]

    def __init__(self, solve=None):
        super().__init__()
        self.history = []
        self.last = None
        self.part_info = Text("")
        self.settings = {"pack": None, "model": None, "level": None, "thorough": False, "db": None, "show": False}
        self.transcript = []  # (question, answer text, status line) for /export
        self.busy = False
        self.solve_fn = solve  # tests pass a fake; None means the packs' own solve

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="main"):
                yield Static(BANNER, id="banner")
                yield Static("", id="sub")
                yield VerticalScroll(id="chat")
                yield Input(placeholder="ask anything, or /help", id="ask")
            with TabbedContent("Part", "Code", "Steps", "Log", id="side"):
                for name in ("part", "code", "steps", "log"):
                    with TabPane(name.capitalize(), id=f"tab-{name}"):
                        yield VerticalScroll(Static("", id=name))
        with Horizontal(id="status"):
            yield Static("packs", classes="label")
            for p in PACKS:
                yield Chip(p, id=f"pack-{p}")
            yield Static("│ models", classes="label")
            for m in self.all_models():
                if any(self.model_id(m) == self.model_id(o) for o in self.all_models()[:self.all_models().index(m)]):
                    continue
                yield Chip(label(m), id=f"model-{self.model_id(m)}")
            yield Static("", id="level")
            yield Static("", id="overrides")
            yield Static("", id="ollama")
            yield Static("? /help", classes="label")

    @staticmethod
    def all_models():
        seen = []
        for p in PACKS.values():
            for m in p.models.values():
                if m not in seen:
                    seen.append(m)
        return seen

    @staticmethod
    def model_id(model):
        return "".join(c if c.isalnum() else "-" for c in label(model)).strip("-").lower()

    def on_mount(self):
        up = loaded_models()
        self.query_one("#sub", Static).update(Text.assemble(
            f"plm {plm_version()} · {len(PACKS) - 1} packs · ", ("ollama ✓" if up is not None else "ollama ✗", DIM),
            " · /help"))
        self.refresh_ollama()
        self.set_interval(10, self.refresh_ollama)
        self.query_one("#ask", Input).focus()

    def refresh_ollama(self):
        up = loaded_models()
        widget = self.query_one("#ollama", Static)
        if up is None:
            widget.update(Text.assemble(("│ ollama ", "#5c5f6b"), ("● down", RED)))
        else:
            widget.update(Text.assemble(("│ ollama ", "#5c5f6b"), ("● ", GREEN), f"{up[1]:.1f} GB"))

    def say(self, renderable, classes=""):
        chat = self.query_one("#chat", VerticalScroll)
        widget = Static(renderable, classes=classes)
        chat.mount(widget)
        chat.scroll_end(animate=False)
        return widget

    MODEL_ALIASES = {"4b": "qwen3-4b", "small": "qwen3-4b", "8b": "qwen3:8b", "large": "qwen3:8b", "coder": "coder"}

    def resolve_model(self, name):
        """A model name from an alias (4b, 8b, coder) or a full Ollama name; None if unknown."""
        key = self.MODEL_ALIASES.get(name.lower(), name.lower())
        return next((m for m in self.all_models() if key in m.lower()), None) or (name if ":" in name else None)

    def command(self, name, arg):
        s = self.settings
        on = arg.lower() in ("on", "yes", "1", "")
        if name == "/pack":
            if arg in ("", "auto"):
                s["pack"] = None
            elif arg in PACKS:
                s["pack"] = arg
            else:
                return self.say(Text(f"no pack {arg!r}; installed: {', '.join(PACKS)}", YELLOW))
        elif name == "/model":
            if arg in ("", "auto"):
                s["model"] = None
            else:
                model = self.resolve_model(arg)
                if not model:
                    return self.say(Text(f"no model {arg!r}; try 4b, 8b, coder, or a full Ollama name", YELLOW))
                s["model"] = model
        elif name == "/level":
            if arg in ("", "auto"):
                s["level"] = None
            elif arg in ("calm", "alert", "intensive"):
                s["level"] = arg
            else:
                return self.say(Text("levels: calm, alert, intensive, auto", YELLOW))
        elif name == "/thorough":
            s["thorough"] = on
        elif name == "/db":
            if arg in ("", "off"):
                s["db"] = None
                os.environ.pop("PLM_SQL_DB", None)
            else:
                path = os.path.abspath(os.path.expanduser(arg))
                if not os.path.isfile(path):
                    return self.say(Text(f"no file {path}", YELLOW))
                s["db"] = path
                os.environ["PLM_SQL_DB"] = path  # routing reads it: data questions about it go to sql
        elif name == "/show":
            s["show"] = on
        elif name == "/export":
            return self.export(arg)
        elif name == "/settings":
            pass
        else:
            return self.say(Text(f"unknown command {name}; /help lists them", YELLOW))
        self.show_settings()

    def show_settings(self):
        s = self.settings
        parts = [f"pack {s['pack'] or 'auto'}", f"model {label(s['model']) if s['model'] else 'auto'}",
                 f"level {s['level'] or 'auto'}", f"thorough {'on' if s['thorough'] else 'off'}",
                 f"db {os.path.basename(s['db']) if s['db'] else 'off'}", f"show {'on' if s['show'] else 'off'}"]
        self.say(Text("settings: " + " · ".join(parts), DIM))
        forced = [f"{k} {os.path.basename(v) if k == 'db' else label(v) if k == 'model' else v}"
                  for k, v in s.items() if v and k in ("pack", "model", "level", "db")]
        forced += [k for k in ("thorough", "show") if s[k]]
        self.query_one("#overrides", Static).update(Text("│ " + " · ".join(forced), ORANGE) if forced else "")

    def export(self, arg):
        if not self.transcript:
            return self.say(Text("nothing to export yet", DIM))
        path = os.path.expanduser(arg) if arg else os.path.expanduser(f"~/plm-chat-{time.strftime('%Y%m%d-%H%M')}.md")
        lines = [f"# plm conversation, {time.strftime('%Y-%m-%d %H:%M')}\n"]
        for q, a, status in self.transcript:
            lines += [f"**You:** {q}\n", a.strip() + "\n", f"_{status}_\n"]
        try:
            with open(path, "w") as f:
                f.write("\n".join(lines))
        except OSError as e:
            return self.say(Text(f"couldn't write {path}: {e}", RED))
        self.say(Text(f"saved the conversation to {path}", DIM))

    def light(self, packs=(), models=()):
        for p in PACKS:
            self.query_one(f"#pack-{p}", Chip).set_class(p in packs, "live")
            self.query_one(f"#pack-{p}", Chip).update(p + (" ●" if p in packs else ""))
        live = {self.model_id(m) for m in models}
        for m in {self.model_id(m): m for m in self.all_models()}.values():
            chip = self.query_one(f"#model-{self.model_id(m)}", Chip)
            chip.set_class(self.model_id(m) in live, "live")
            chip.update(label(m) + (" ●" if self.model_id(m) in live else ""))

    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text in ("/quit", "/exit"):
            return self.exit()
        if text == "/help":
            return self.say(Text.from_markup(HELP))
        if text == "/new":
            return self.action_new()
        fuse = False
        if text.startswith("/"):
            name, _, arg = text.partition(" ")
            arg = arg.strip()
            if name == "/fuse":
                if not arg:
                    return self.say(Text("/fuse needs a problem: /fuse <a CAD + engineering problem>", YELLOW))
                text, fuse = arg, True
            else:
                return self.command(name, arg)
        if self.busy:
            return self.say(Text("still working on the last question", YELLOW))
        self.say(Text.assemble(("› ", "#79c0ff"), ("/fuse " if fuse else "", ORANGE), text), classes="you")
        messages = [*self.history, {"role": "user", "content": text}]
        routed = resolve(messages)
        pack, followup = routed["pack"], routed["context"]
        task = routed["task"] if followup and pack != "general" else text
        if fuse:
            pack, task, followup = "cad", text, False
        elif self.settings["pack"]:
            pack = self.settings["pack"]
            task = routed["task"] if followup and routed["pack"] == pack else text
            followup = followup and routed["pack"] == pack
        lit = [p for p in (("physics", "electrical", "aerospace") if fuse else ()) if p in PACKS] + [pack]
        self.light(packs=lit, models=[self.settings["model"]] if self.settings["model"] else PACKS[pack].models.values())
        self.busy = True
        spinner = self.say(Text(f"{SPIN[0]} {'fusion' if fuse else pack} · working…", "#56d4dd"))
        self.run_task(text, pack, task, messages, followup, spinner, fuse)

    @work(thread=True, exclusive=True)
    def run_task(self, text, pack, task, messages, followup, spinner, fuse=False):
        start = time.time()
        stop = []

        def tick():
            i = 0
            while not stop:
                i += 1
                self.call_from_thread(spinner.update, Text(
                    f"{SPIN[i % len(SPIN)]} {pack} · working… {time.time() - start:.0f} s", "#56d4dd"))
                time.sleep(0.15)
        threading.Thread(target=tick, daemon=True).start()
        s = self.settings
        models = PACKS[pack].models
        saved = dict(models)
        try:
            if s["model"]:  # every tier of this pack uses the forced model, for this question only
                models.update({k: s["model"] for k in models})
            extra = {}
            if s["level"] and pack != "general":
                extra["level"] = s["level"]
            if pack == "software" and s["thorough"]:
                extra["thorough"] = True
            if pack == "sql" and s["db"]:
                extra["db"] = s["db"]
            if self.solve_fn:
                result = self.solve_fn(pack, task, messages)
            elif fuse:
                from plm import fusion
                result = fusion.solve(task)
            elif pack == "general":
                result = PACKS["general"].solve(task, messages=messages)
            else:
                result = PACKS[pack].solve(task, **extra)
            error = None
        except Exception as e:  # show any failure (Ollama down, a pack error) instead of crashing the screen
            result, error = None, f"{type(e).__name__}: {e}"
        finally:
            models.clear()
            models.update(saved)
        stop.append(True)
        self.call_from_thread(self.show, text, result, error, spinner, followup)

    def show(self, text, result, error, spinner, followup):
        self.busy = False
        spinner.remove()
        if error:
            self.say(Text(f"! {error}", RED))
            if "onnect" in error or "refused" in error.lower():
                self.say(Text("Is Ollama running? (ollama serve)", DIM))
            return
        result["followup"] = followup
        self.last = result
        log = log_dir() / "runs.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as f:
            f.write(json.dumps(result, default=str) + "\n")
        body = answer_body(result) or "(no answer)"
        note = caveat(result)
        for kind, chunk in split_code(body):
            if kind == "code":
                self.say(Syntax(chunk[1], chunk[0] or "text", theme="monokai", word_wrap=True, background_color="#15161b"))
            elif chunk.strip():
                self.say(Text(chunk.strip(), "bold"), classes="answer")
        if note:
            self.say(Text(note.strip(), YELLOW))
        fusion = result.get("fusion")
        if fusion:
            if fusion.get("fell_back"):
                self.say(Text(f"fusion (experimental) fell back to the CAD pack alone: {fusion['fell_back']}", YELLOW))
            else:
                self.say(Text(f"fusion (experimental): {fusion['plan'].get('pack', '?')} calculation → "
                              f"{fusion['value_mm']:.4g} mm → cad", ORANGE))
        line = status_line(result)
        self.say(line)
        if self.settings["show"]:
            for i, step in enumerate(result["steps"], 1):
                work = (step.get("program") or step.get("code") or step.get("model_text") or "").strip()
                if work:
                    self.say(Text(f"step {i} · {label(step['model'])}{' · ' + step['role'] if step.get('role') else ''}\n"
                                  + work[:2000], DIM))
        self.history += [{"role": "user", "content": text}, {"role": "assistant", "content": body}]
        self.transcript.append((text, body, line.plain))
        used = [result["pack"]]
        if result.get("fusion", {}).get("plan"):  # both packs of a fusion: the calculation's and cad
            used.insert(0, result["fusion"]["plan"].get("pack"))
        self.light(packs=used, models=[s["model"] for s in result["steps"]])
        self.query_one("#level", Static).update(Text.assemble(("│ level ", "#5c5f6b"), result["level"] or "-"))
        self.fill_side(result)

    def fill_side(self, result):
        answer = result.get("answer") or {}
        code = answer.get("code") if isinstance(answer, dict) else None
        lang = "python" if result["pack"] in ("software", "cad") else "sql"
        self.query_one("#code", Static).update(
            Syntax(code, lang, theme="monokai", word_wrap=True) if code else Text("no code in this answer", DIM))
        if result["pack"] == "cad" and isinstance(answer, dict):
            m = answer.get("measured") or {}
            dims = " × ".join(f"{x:g}" for x in m.get("bbox", [])) if m else "-"
            self.part_info = Text.assemble(
                f"{dims} mm · {m.get('volume', 0):,.0f} mm³\n" if m else "",
                ("✓ size and volume look right" if result["trusted"] else "! the part failed a check",
                 GREEN if result["trusted"] else RED), ("\nctrl+p: full drawing", DIM))
            self.query_one("#part", Static).update(Text.assemble(("drawing the part…\n\n", DIM), self.part_info))
            self.query_one("#side", TabbedContent).active = "tab-part"
            if answer.get("code"):
                self.draw_part(answer["code"])
        else:
            self.query_one("#part", Static).update(Text("no part: this answer isn't a CAD model", DIM))
            if code:
                self.query_one("#side", TabbedContent).active = "tab-code"
        rows = Text()
        for i, s in enumerate(result["steps"], 1):
            issues = "; ".join(s["issues"]) if s["issues"] else "ok"
            rows.append(f"step {i}  {short(s['model'])}\n", "bold")
            rows.append(f"  {s['tokens']} tok · {s['seconds']:.1f} s · {issues}\n\n", DIM if not s["issues"] else YELLOW)
        rows.append(f"level {result['level']} ({result['reason']})", DIM)
        self.query_one("#steps", Static).update(rows)
        self.query_one("#log", Static).update(Text(json.dumps(result, indent=1, default=str)[:20000], DIM))

    @work(thread=True, exclusive=True, group="part")
    def draw_part(self, code):
        try:
            from plm_cad.kernel import preview_edges
            edges, why = preview_edges(code)
        except Exception as e:  # the CAD pack missing or broken: say so in the panel
            edges, why = None, f"{type(e).__name__}: {e}"
        rows = draw(edges, cols=40, rows=16) if edges else []
        art = Text("\n".join(rows) + "\n\n", ORANGE) if rows else Text(f"couldn't draw the part: {why}\n\n", DIM)
        self.call_from_thread(self.query_one("#part", Static).update, Text.assemble(art, self.part_info))

    def action_new(self):
        self.history, self.last = [], None
        self.query_one("#chat", VerticalScroll).remove_children()
        self.light()
        self.say(Text("new conversation", DIM))

    def action_preview(self):
        r = self.last
        code = r and r["pack"] == "cad" and isinstance(r.get("answer"), dict) and r["answer"].get("code")
        if not code:
            return self.say(Text("no CAD part to preview yet", DIM))
        from plm_cad.kernel import preview_svg
        path = os.path.join(tempfile.gettempdir(), f"plm-part-{int(time.time())}.svg")
        why = preview_svg(code, path)
        if why:
            return self.say(Text(f"! couldn't draw the part: {why}", RED))
        subprocess.Popen(["qlmanage", "-p", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.say(Text(f"preview opened ({path})", DIM))


def main():
    PlmApp().run()
