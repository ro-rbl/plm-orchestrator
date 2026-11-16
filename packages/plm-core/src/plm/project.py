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


# ---------------------------------------------------------------------------------------------------------------
# Project mode: build and change a whole project in the folder (interface: /project <folder>; CLI: --project).
#
# Why (the user's Anki Overdrive session, 2026-11-15, all in the general chat pack): the model printed files to
# copy and never wrote one, later said the app "is in the project folder", told the user to click through Xcode
# for a project that didn't exist, and forgot facts the user had stated. Here the model sees what is really in the
# folder, changes it only by writing whole files, and everything about what was written, generated and built is
# reported by this code, never by the model. Not measured by an eval.
# ---------------------------------------------------------------------------------------------------------------

import json  # noqa: E402
import os  # noqa: E402
import shutil  # noqa: E402
import signal  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

SKIP_DIRS = {".git", ".plm", "build", "DerivedData", "node_modules", "__pycache__", ".venv", "venv", ".build", "Pods"}
SKIP_SUFFIXES = (".xcodeproj", ".xcworkspace", ".app", ".xcassets")
TEXT = {".swift", ".py", ".js", ".ts", ".html", ".css", ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".sh", ".sql",
        ".c", ".h", ".cpp", ".m", ".go", ".rs", ".java", ".plist", ".csv", ".cfg", ".ini"}
CONTEXT = 16384  # tokens; larger only when the folder and conversation need it
SNAPSHOT_CHARS = 36000  # contents shown to the model (about 9000 tokens)
MAX_LISTED = 300
NUM_PREDICT = 6144
ROUNDS = 3
MARKER = "# generated by plm"
RULES = """You are the coding part of plm, working inside one project folder on the user's Mac. You can see the folder
(PROJECT FILES below) and you change it only by writing whole files, each exactly in this form:

FILE: relative/path.ext
```
the complete new contents of the file
```

Rules:
- The folder contains exactly the files listed under PROJECT FILES. Nothing else exists. Never say a file, app or
  project exists unless it is listed there or you write it in this reply.
- When the user asks you to build, make, start, fix or change something, write the files, in this reply. Never tell
  the user to create files, copy code, or click through Xcode menus to set up a project.
- Every file is complete and compiles as written: no placeholders, no "...", no "rest of the code here".
- plm writes your files, generates the Xcode project and builds it, then tells the user the result. So do not write
  project.yml, .xcodeproj or Info.plist files, and never claim that something was built, run or tested.
- A Mac, iPad or iPhone app: Swift and SwiftUI, Apple frameworks only (no packages), every source file under
  Sources/, exactly one @main App struct. Put one line before the files: APP: <Name> <macOS or iOS>
- What the user told you is true. If they said an app or service is discontinued or missing, never suggest using it.
- Facts about hardware, protocols and APIs: if you are not sure, say so in one line instead of guessing, and mark any
  guessed constant in the code with the comment UNVERIFIED.
- Writing a FILE replaces that file. To remove a file from the project write a line: DELETE: relative/path.ext
- Do not write README or other documentation files unless asked.
- To run an app plm has built, the user types /run here in plm's own question box, not in a terminal (or opens the
  .xcodeproj in Xcode). Invent no other commands.
- If the user asks for a plan first, give a short plan and write no files until they tell you to start.
- After the files, explain your work in plain words, no emoji: (1) what you built and how it works, in a short
  paragraph; (2) what each file you wrote is for, one line each; (3) how the user uses it, as numbered steps;
  (4) what is not done yet or UNVERIFIED. When you only fixed errors, say what was wrong and what you changed.
- A question that needs no change: answer it briefly, with no FILE blocks."""
RECIPE_DIR = Path(__file__).parent / "recipes"
RECIPES = {  # verified building blocks (evals/test_project.py builds them): file -> when to offer it
    "HTTPServer.swift": re.compile(r"\b(localhost|server|port\s*\d+|https?|web ?page|browser|dashboard)\b", re.IGNORECASE),
    "BLECentral.swift": re.compile(r"\b(bluetooth|ble)\b", re.IGNORECASE),
}
DELETE_LINE = re.compile(r"^[#*\s]*DELETE:[ \t]*`?([^\n`]+?)`?[ \t]*$", re.MULTILINE)
USE_LINE = re.compile(r"^[#*\s]*USE:[ \t]*`?(?:Sources/)?([\w.]+)`?.*$", re.MULTILINE)
THIRD_PARTY = re.compile(r"no such module|GCDAsyncSocket|\bNIO|Vapor|Swifter|Alamofire|Kitura|Telegraph|CocoaAsyncSocket", re.IGNORECASE)
NO_FILES = ("Your reply had code but no FILE blocks, so nothing was saved. Write the files now, each as\n"
            "FILE: relative/path.ext\nfollowed by a fenced block with the complete contents.")
WANTS_CHANGE = re.compile(r"\b(make|build|create|write|code|coding|add|fix|change|update|implement|generate|set ?up|"
                          r"refactor|rename|remove|rewrite|start)\b", re.IGNORECASE)
FILE_BLOCK = re.compile(r"^[#*\s]*FILE:[ \t]*[*`]*([^\n`*]+?)[*`]*[ \t]*\n+```[^\n]*\n(.*?)\n```[ \t]*$", re.MULTILINE | re.DOTALL)
OPEN_BLOCK = re.compile(r"^[#*\s]*FILE:[ \t]*[*`]*([^\n`*]+?)[*`]*[ \t]*\n+```[^\n]*\n", re.MULTILINE)
APP_LINE = re.compile(r"^[#*\s]*APP:[ \t]*`?([A-Za-z][\w-]*)`?[ \t]+`?(macOS|iOS)\b.*$", re.MULTILINE | re.IGNORECASE)
USAGE_KEYS = {  # a framework a source imports -> the Info.plist text the system needs before it grants access
    "CoreBluetooth": {"NSBluetoothAlwaysUsageDescription": "Connects to nearby devices over Bluetooth."},
    "CoreLocation": {"NSLocationWhenInUseUsageDescription": "Uses your location while the app is open."},
    "AVFoundation": {"NSCameraUsageDescription": "Uses the camera.", "NSMicrophoneUsageDescription": "Uses the microphone."},
    "CoreMotion": {"NSMotionUsageDescription": "Reads motion data."},
    "Network": {"NSLocalNetworkUsageDescription": "Talks to devices on your local network."},
}
XCODE_ERROR = re.compile(r"^([^\n:]+?):(\d+):\d+: error: (.*)$", re.MULTILINE)
OTHER_ERROR = re.compile(r"^(?:error|ld|clang): (?:error: )?(.*)$", re.MULTILINE)
BUILD_TOOL = "xcode" + "build"  # Xcode's command-line builder


def recipe(name):
    """(the building block's source, its usage notes: the comment at its top)."""
    body = (RECIPE_DIR / name).read_text()
    notes = "\n".join(line[3:] if line.startswith("// ") else line[2:] for line in body.splitlines()[:body.splitlines().index("")])
    return body, notes


def offered(text):
    """The part of the system prompt that offers the building blocks the conversation calls for ('' if none)."""
    names = [n for n, trigger in RECIPES.items() if trigger.search(text)]
    if not names:
        return ""
    return ("\n\nBUILDING BLOCKS from plm for a Swift app. They compile as they are and replace third-party libraries, "
            "which are not available. To use one, write a line `USE: <file>` before your files: plm copies it into "
            "Sources/ unchanged. Call it as its notes say; never rewrite it or paste its code.\n\n"
            + "\n\n".join(f"USE: {n}\n{recipe(n)[1]}" for n in names))


def _is_recipe(root, f):
    name = os.path.basename(f)
    try:
        return name in RECIPES and Path(root, f).read_text() == recipe(name)[0]
    except OSError:
        return False


def state(root):
    """What plm last found in this folder ({"built", "errors", "xcodeproj", "product", "root"}), or {}."""
    try:
        return json.loads(Path(root, ".plm", "state.json").read_text())
    except (OSError, ValueError):
        return {}


def _files(root):
    """Relative paths of the project's own files (no build output, backups or generated Xcode projects)."""
    out = []
    for folder, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.endswith(SKIP_SUFFIXES) and not d.startswith("."))
        for name in sorted(names):
            if name.endswith(".bak") or name.startswith("."):
                continue
            out.append(os.path.relpath(os.path.join(folder, name), root))
            if len(out) > 5000:
                return out
    return out


def snapshot(root, prefer=()):
    """What the model is shown of the folder: every file with its size, then the contents of the text files that
    fit SNAPSHOT_CHARS (the ones in prefer first, then the smallest)."""
    files = _files(root)
    theirs, own = foreign_xcode(root), app_of(root)
    mine = f"{own[0]}.xcodeproj" if own and Path(root, f"{own[0]}.xcodeproj").exists() else None
    if not files and not theirs:
        return "PROJECT FILES (" + str(root) + "): the folder is empty."
    sizes = {f: os.path.getsize(os.path.join(root, f)) for f in files}
    lines = [f"PROJECT FILES ({root}), {len(files)} in all:"]
    lines += [f"- {f} ({sizes[f]} bytes)" for f in files[:MAX_LISTED]]
    lines += [f"- {x} (an Xcode project, made in Xcode by the user)" for x in theirs]
    if mine:
        lines.append(f"- {mine} (the Xcode project plm generates from Sources/; the one to open)")
    if len(files) > MAX_LISTED:
        lines.append(f"- ... and {len(files) - MAX_LISTED} more, not listed")
    blocks = [f for f in files if _is_recipe(root, f)]
    readable = [f for f in files if os.path.splitext(f)[1].lower() in TEXT and f not in ("project.yml", "Info.plist")
                and f not in blocks]
    order = [f for f in prefer if f in readable] + sorted((f for f in readable if f not in prefer), key=sizes.get)
    budget, hidden = SNAPSHOT_CHARS, []
    for f in order:
        try:
            body = Path(root, f).read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if len(body) > budget:
            hidden.append(f)
            continue
        budget -= len(body)
        lines.append(f"\nCONTENTS OF {f}:\n```\n{body.rstrip()}\n```")
    if hidden:
        lines.append("\nToo large to show (ask the user before changing them): " + ", ".join(hidden))
    for f in blocks:
        lines.append(f"\n{f} is plm's building block, already in the project; use it as its notes say, don't rewrite it:\n"
                     + recipe(os.path.basename(f))[1])
    if theirs:
        lines.append(f"\nNOTE: {', '.join(theirs)} was made in Xcode, not by plm. plm cannot edit an Xcode project file, so "
                     "it builds its own project from the Swift files under Sources/. Write the app under Sources/ as the "
                     "rules say (you may reuse code from the listed files); Swift files outside Sources/ are not part of "
                     "plm's app, and only one file in Sources/ may have @main.")
    last = state(root)
    if last:
        lines.append("\nPROJECT STATE (from plm's last check): " + ("the app built; the user runs it with /run" if last.get("built")
                     else "the last build FAILED: " + "; ".join(last.get("errors", [])[:6]) if last.get("errors")
                     else "nothing has been built yet"))
    return "\n".join(lines)


def parse(reply):
    """{"files": {path: contents}, "app": (name, platform) or None, "cut": path of a file the reply broke off in
    or None, "prose": the reply without its files}."""
    files = {m.group(1).strip(): m.group(2).rstrip() + "\n" for m in FILE_BLOCK.finditer(reply or "")}
    rest = FILE_BLOCK.sub("", reply or "")
    cut = OPEN_BLOCK.search(rest)
    if cut:
        rest = rest[:cut.start()]
    app = APP_LINE.search(rest)
    uses = [n for n in dict.fromkeys(USE_LINE.findall(rest)) if n in RECIPES]
    deletes = list(dict.fromkeys(d.strip() for d in DELETE_LINE.findall(rest)))
    prose = re.sub(r"\n{3,}", "\n\n", DELETE_LINE.sub("", USE_LINE.sub("", APP_LINE.sub("", rest)))).strip()
    return {"files": files, "uses": uses, "deletes": deletes, "app": (app.group(1), "iOS" if app.group(2).lower() == "ios" else "macOS") if app else None,
            "cut": cut.group(1).strip() if cut else None, "prose": prose}


def _run(cmd, cwd, timeout):
    """(exit code or None on a timeout, output). The whole process group is killed on a timeout."""
    try:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             errors="replace", start_new_session=True)
    except OSError as e:
        return 127, str(e)
    try:
        out, _ = p.communicate(timeout=timeout)
        return p.returncode, out
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        out, _ = p.communicate()
        return None, out


def _swift_sources(root):
    return [f for f in _files(root) if f.endswith(".swift") and os.path.basename(f) != "Package.swift"]


def _app_sources(root):
    """The Swift files plm's app is built from: those under Sources/ when there are any (the rule the model is
    given), else every Swift file in the folder."""
    files = _swift_sources(root)
    inside_sources = [f for f in files if f.split(os.sep)[0] == "Sources"]
    return inside_sources or files


def foreign_xcode(root):
    """Xcode projects in the folder that plm did not generate (made in Xcode by the user), as relative paths."""
    own = app_of(root)
    found = []
    for folder, dirs, _ in os.walk(root):
        depth = os.path.relpath(folder, root).count(os.sep)
        for d in list(dirs):
            if d.endswith(".xcodeproj"):
                rel = os.path.relpath(os.path.join(folder, d), root)
                if not (own and rel == f"{own[0]}.xcodeproj"):
                    found.append(rel)
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.endswith(SKIP_SUFFIXES) and not d.startswith(".")]
        if depth >= 2:
            dirs[:] = []
    return sorted(found)


def app_of(root, declared=None, hint=""):
    """(name, platform) of the folder's Xcode app, or None when it isn't one: what plm's own project.yml says,
    else what the model declared, else a SwiftUI @main found in the sources (iOS when the user speaks only of iPad
    or iPhone, else macOS)."""
    spec = Path(root, "project.yml")
    if spec.is_file():  # once the app has a name it keeps it, whatever a later reply declares
        first = spec.read_text(errors="replace").splitlines()[:1]
        m = re.match(re.escape(MARKER) + r" \(APP: ([\w-]+) (macOS|iOS)\)", first[0] if first else "")
        return (m.group(1), m.group(2)) if m else None  # the user's own spec is left alone
    if declared:
        return declared
    if Path(root, "Package.swift").exists():
        return None
    for f in _app_sources(root):
        body = Path(root, f).read_text(errors="replace")
        if "@main" in body and "SwiftUI" in body:
            name = re.sub(r"\W+", "", Path(root).resolve().name.title()) or "App"
            only_ios = re.search(r"\b(ipad|iphone|ios)\b", hint, re.I) and not re.search(r"\b(mac|macbook|laptop)\b", hint, re.I)
            return (name if name[0].isalpha() else "App" + name), ("iOS" if only_ios else "macOS")
    return None


def write_spec(root, name, platform):
    """project.yml (XcodeGen) for a SwiftUI app made of the folder's Swift sources. The Info.plist is a real file
    with the usage texts the imported frameworks need (a missing one crashes the app at first use). Returns them."""
    sources = _app_sources(root)
    entries = sorted({f.split(os.sep)[0] if os.sep in f else f for f in sources})
    usage = {}
    for f in sources:
        body = Path(root, f).read_text(errors="replace")
        for framework, keys in USAGE_KEYS.items():
            if re.search(rf"^\s*import\s+{framework}\b", body, re.MULTILINE):
                usage.update(keys)
    props = dict(usage)
    if platform == "iOS":
        props["UILaunchScreen"] = {}
        props["UISupportedInterfaceOrientations"] = ["UIInterfaceOrientationPortrait", "UIInterfaceOrientationLandscapeLeft",
                                                     "UIInterfaceOrientationLandscapeRight"]
    lines = [f"{MARKER} (APP: {name} {platform}); edit the Swift files, not this file", f"name: {name}", "options:",
             "  bundleIdPrefix: local.plm", "  deploymentTarget:", f'    {platform}: "{"17.0" if platform == "iOS" else "14.0"}"',
             "targets:", f"  {name}:", "    type: application", f"    platform: {platform}", "    sources:"]
    lines += [f"      - {json.dumps(e)}" for e in entries]
    lines += ["    info:", "      path: Info.plist", f"      properties: {json.dumps(props)}", "    settings:", "      base:"]
    lines += (['        TARGETED_DEVICE_FAMILY: "1,2"'] if platform == "iOS" else
              ['        CODE_SIGN_IDENTITY: "-"', '        CODE_SIGNING_REQUIRED: "NO"', '        ENABLE_HARDENED_RUNTIME: "NO"'])
    Path(root, "project.yml").write_text("\n".join(lines) + "\n")
    return usage


def _errors(output, root):
    """The build's errors, deduplicated, with paths relative to the project: compile errors (file:line: message)
    and the project-level ones Xcode prints without a file ("Filename ... used twice")."""
    real = os.path.realpath(root)
    for prefix in {real, real.replace("/private/", "/", 1), str(root)}:
        output = output.replace(prefix + "/", "")
    found = [f"{p}:{line}: {msg}" for p, line, msg in XCODE_ERROR.findall(output)]
    found += [m[:400] for m in OTHER_ERROR.findall(output)]
    return list(dict.fromkeys(found))[:15]


def build_xcode(root, name, platform, timeout=600):
    """Generate <name>.xcodeproj with XcodeGen and build it. {"project", "built", "errors", "product", "usage"},
    and "blocked" when the failure is nothing the model can fix (a missing tool, a build that never finished)."""
    out = {"project": None, "built": False, "errors": [], "product": None, "usage": {}}
    for tool in ("xcodegen", BUILD_TOOL):
        if not shutil.which(tool):
            out["errors"] = [f"{tool} is not installed" + (" (brew install xcodegen)" if tool == "xcodegen" else
                                                           " (install Xcode from the App Store)")]
            out["blocked"] = True
            return out
    out["usage"] = write_spec(root, name, platform)
    code, text = _run(["xcodegen", "generate"], root, 120)
    if code != 0:
        out["errors"] = ["xcodegen: " + (text.strip().splitlines() or ["timed out"])[-1][:300]]
        return out
    out["project"] = f"{name}.xcodeproj"
    cmd = [BUILD_TOOL, "-project", out["project"], "-scheme", name, "-configuration", "Debug", "-derivedDataPath",
           os.path.join(".plm", "build")]
    if platform == "iOS":
        cmd += ["-destination", "generic/platform=iOS Simulator", "CODE_SIGNING_ALLOWED=NO"]
    code, text = _run(cmd + ["build"], root, timeout)
    if code is None:
        out["errors"] = [f"the build did not finish in {timeout} s"]
        out["blocked"] = True
    elif code != 0 or "BUILD SUCCEEDED" not in text:
        out["errors"] = _errors(text, root) or ["the build failed: " + (text.strip().splitlines() or ["?"])[-1][:300]]
    else:
        out["built"] = True
        product = Path(root, ".plm", "build", "Build", "Products", "Debug" + ("-iphonesimulator" if platform == "iOS" else ""),
                       f"{name}.app")
        out["product"] = str(product) if product.exists() else None
    return out


MISSING = re.compile(r"^(\S+\.swift):\d+: cannot find (?:type )?'(\w+)' in scope")
FRAMEWORK_OF = (("CB", "CoreBluetooth"), ("NW", "Network"), ("CL", "CoreLocation"), ("AV", "AVFoundation"),
                ("CM", "CoreMotion"), ("MK", "MapKit"), ("UN", "UserNotifications"))
SYMBOL_FRAMEWORK = {"ObservableObject": "Combine", "Published": "Combine", "AnyCancellable": "Combine", "Timer": "Foundation",
                    "Data": "Foundation", "URL": "Foundation", "UUID": "Foundation", "DispatchQueue": "Foundation",
                    "View": "SwiftUI", "Color": "SwiftUI", "StateObject": "SwiftUI", "State": "SwiftUI", "Binding": "SwiftUI"}


def add_imports(root, errors):
    """Fix, in code, the errors that are only a missing import of an Apple framework ("cannot find 'CBUUID' in
    scope" -> import CoreBluetooth at the top of that file). Returns what was added, as lines for the report."""
    done = []
    for e in errors:
        m = MISSING.match(e)
        if not m:
            continue
        name, symbol = m.groups()
        framework = SYMBOL_FRAMEWORK.get(symbol) or next((f for prefix, f in FRAMEWORK_OF if re.match(prefix + "[A-Z]", symbol)), None)
        try:
            path = inside(root, name)
            body = path.read_text()
        except (OSError, ValueError):
            continue
        if not framework or re.search(rf"^\s*import\s+{framework}\b", body, re.MULTILINE):
            continue
        path.write_text(f"import {framework}\n" + body)
        done.append(f"import {framework} to {name}")
    return list(dict.fromkeys(done))


BLOCK_TYPES = {"HTTPServer": "HTTPServer.swift", "HTTPRequest": "HTTPServer.swift", "HTTPResponse": "HTTPServer.swift",
               "BLECentral": "BLECentral.swift", "BLEDevice": "BLECentral.swift"}
MAIN_APP = re.compile(r"@main\s+(?:\w+\s+)*struct\s+\w+\s*:\s*(?:SwiftUI\.)?App\b")


def autofix(root, errors):
    """The build errors plm can fix in code, with no model call. Returns what it did, as lines for the report:
    a missing import of an Apple framework; a building block that is used but was never added; and @main on a
    second type when a SwiftUI App already has it (the model keeps an old AppDelegate's @main)."""
    done = add_imports(root, errors)
    for symbol, name in BLOCK_TYPES.items():
        target = Path(root, "Sources", name)
        if any(re.search(rf"cannot find (?:type )?'{symbol}' in scope", e) for e in errors) and not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(recipe(name)[0])
            done.append(f"its building block Sources/{name} (the code used it without adding it)")
    if any("'main' attribute can only apply to one type" in e for e in errors):
        sources = {f: Path(root, f).read_text(errors="replace") for f in _app_sources(root)}
        if sum(bool(MAIN_APP.search(body)) for body in sources.values()) == 1:
            for f, body in sources.items():
                if "@main" in body and not MAIN_APP.search(body):
                    Path(root, f).write_text(re.sub(r"^[ \t]*@main[ \t]*\n?", "", body, flags=re.MULTILINE))
                    done.append(f"a fix to {f}: removed its @main (only the SwiftUI App may have one)")
    return list(dict.fromkeys(done))


def check(root, written, app):
    """Check what was just written, in code. {"kind", "errors", "xcode"}: an Xcode app is generated and built; a
    Swift package is built; Python, JavaScript and JSON files are parsed. errors is empty when all of it passed;
    kind is None when there was nothing plm knows how to check."""
    if app:
        x = build_xcode(root, *app)
        return {"kind": "xcode", "errors": x["errors"], "xcode": x}
    if any(f.endswith(".swift") for f in written) and not Path(root, "Package.swift").exists():
        return {"kind": "xcode", "xcode": None, "errors": [
            "there is no app to build: no file under Sources/ has a SwiftUI @main App struct. Write "
            "Sources/<Name>App.swift with `import SwiftUI` and `@main struct <Name>App: App { var body: some Scene { "
            "WindowGroup { ContentView() } } }`, put the line APP: <Name> macOS before your files, and do not use an "
            "AppKit AppDelegate or NSApplicationMain"]}
    errors, kind = [], None
    if Path(root, "Package.swift").exists() and any(f.endswith(".swift") for f in written) and shutil.which("swift"):
        kind = "swift package"
        code, text = _run(["swift", "build"], root, 600)
        if code != 0:
            errors += _errors(text, root) or ["swift build failed: " + (text.strip().splitlines() or ["timed out"])[-1][:300]]
    for f in written:
        path = str(Path(root, f))
        if f.endswith(".py"):
            kind = kind or "syntax"
            code, text = _run([sys.executable, "-m", "py_compile", path], root, 60)
            if code != 0:
                errors.append(f"{f}: " + (text.strip().splitlines() or ["does not compile"])[-1][:300])
        elif f.endswith((".js", ".mjs")) and shutil.which("node"):
            kind = kind or "syntax"
            code, text = _run(["node", "--check", path], root, 60)
            if code != 0:
                errors.append(f"{f}: " + next((line for line in text.splitlines() if "Error" in line), "does not parse")[:300])
        elif f.endswith(".json"):
            kind = kind or "syntax"
            try:
                json.loads(Path(path).read_text())
            except (ValueError, OSError) as e:
                errors.append(f"{f}: {e}")
    return {"kind": kind, "errors": errors, "xcode": None}


def solve(root, messages, model, timeout=900, rounds=ROUNDS):
    """One turn of project mode: the model sees the folder and the conversation, plm writes the files it returns,
    checks them (an Xcode app is generated and built) and gives it the errors to fix, up to `rounds` model calls.
    Returns a result shaped like a pack's; result["project"] has what plm wrote and found, and the answer's text
    ends with that report, written by this code."""
    from plm.general.controller import context_options
    from plm.ollama import _notify, chat

    start = time.time()
    root = str(Path(root).resolve())
    convo = [m for m in messages if m.get("role") in ("user", "assistant") and (m.get("content") or "").strip()][-12:]
    last = next((m["content"] for m in reversed(convo) if m["role"] == "user"), "")
    steps, written, backups, failed, prose, added, removed, imports = [], [], {}, [], "", [], [], []
    declared, checked, extra, cut, app, before = None, None, None, None, None, None
    blocks = offered(" ".join(m["content"] for m in convo if m["role"] == "user"))
    for attempt in range(rounds):
        system = RULES + blocks + "\n\n" + snapshot(root, prefer=[*mentioned(last), *written])
        msgs = [{"role": "system", "content": system}, *convo] + ([{"role": "user", "content": extra}] if extra else [])
        # one context size for the whole session where it fits: a changing size makes Ollama reload the model
        need = sum(len(m["content"]) for m in msgs) // 3 + NUM_PREDICT
        options = {"num_ctx": CONTEXT} if need <= CONTEXT else context_options(msgs, NUM_PREDICT)
        r = chat(model, msgs, NUM_PREDICT, timeout, options)
        steps.append({"model": model, "tokens": r["eval_tokens"], "prompt_tokens": r["prompt_tokens"],
                      "model_text": r["response"], "capped": r["done_reason"] == "length", "issues": [],
                      "seconds": r["wall_s"]})
        got = parse(r["response"])
        prose = got["prose"] or prose
        declared, cut = got["app"] or declared, got["cut"]
        now = []
        for name in got["uses"]:  # a building block the model asked for: copied in unchanged
            try:
                target = inside(root, os.path.join("Sources", name))
                if not target.exists() or target.read_text() != recipe(name)[0]:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(recipe(name)[0])
                    added.append(os.path.join("Sources", name))
                    now.append(os.path.join("Sources", name))
            except (OSError, ValueError) as e:
                failed.append(f"Sources/{name}: {e}")
        for name, body in got["files"].items():
            if os.path.basename(name) in ("project.yml", "Info.plist", *RECIPES) or ".xcodeproj" in name:
                continue  # plm's own: the spec, and the building blocks (never the model's copy of one)
            try:
                path = inside(root, name)
                if path.exists() and name not in backups and name not in written:
                    backups[name] = path.read_text(errors="replace")
                    path.with_name(path.name + ".bak").write_text(backups[name])
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(body)
                now.append(name)
            except (OSError, ValueError) as e:
                failed.append(f"{name}: {e}")
        for name in got["deletes"]:  # moved aside, never destroyed: .plm/trash/<path>
            try:
                path = inside(root, name)
                if name.lower().endswith(".md") and os.path.basename(name).lower() not in last.lower():
                    continue  # reference notes stay unless the user names the file: "clear the project" isn't that
                if path.is_file() and name not in got["files"]:
                    bin_ = Path(root, ".plm", "trash", name)
                    bin_.parent.mkdir(parents=True, exist_ok=True)
                    path.replace(bin_)
                    removed.append(name)
                    written = [w for w in written if w != name]
            except (OSError, ValueError) as e:
                failed.append(f"delete {name}: {e}")
        written += [n for n in now if n not in written]
        if not now and not got["deletes"]:
            if attempt == 0 and not cut and WANTS_CHANGE.search(last) and "```" in r["response"]:
                steps[-1]["issues"] = ["code in the reply but no files"]
                extra = NO_FILES
                continue
            if not cut:
                break  # an answer in words, or a repair round that changed nothing
        if written or removed:
            app = app_of(root, declared, last)
            began, tool = time.time(), BUILD_TOOL if app else "checks"
            _notify("start", tool)
            checked = check(root, written, app)
            for _ in range(3):  # what plm can fix in code needs no model call: fix, build again
                fixed = autofix(root, checked["errors"]) if app else []
                if not fixed:
                    break
                imports += fixed
                checked = check(root, written, app)
            _notify("end", tool, {"eval_tokens": 0, "wall_s": time.time() - began})
        problems = ([f"your reply was cut off before FILE {cut} was complete, so it was not saved; write it again"] if cut else []) \
            + (checked["errors"] if checked else [])
        steps[-1]["issues"] = problems
        if not problems or (checked and (checked.get("xcode") or {}).get("blocked")):
            break
        extra = ("plm saved your files and checked them. Problems found:\n" + "\n".join(f"- {p}" for p in problems)
                 + "\n\nFix them: write each file that needs a change again, in full, as FILE blocks. Change nothing else.")
        if THIRD_PARTY.search(" ".join(problems)):
            extra += ("\nThird-party libraries are not available here: use only Apple frameworks"
                      + (" and the BUILDING BLOCKS above (write the line USE: <file>)." if blocks else "."))
        if problems == before:
            extra += ("\nYour last fix left exactly the same problems. Rewrite the files named in them from scratch, "
                      "a different way.")
        before = problems
    xcode = (checked or {}).get("xcode") or {}
    errors = list(steps[-1]["issues"]) if written or removed or cut else []
    if checked and checked["kind"] == "xcode":
        try:
            Path(root, ".plm").mkdir(exist_ok=True)
            Path(root, ".plm", "state.json").write_text(json.dumps({
                "root": root, "built": bool(xcode.get("built")), "errors": errors, "xcodeproj": xcode.get("project"),
                "product": xcode.get("product"), "at": time.strftime("%Y-%m-%d %H:%M")}))
        except OSError:
            pass
    report = []
    mine = [f for f in written if f not in added]
    if mine:
        report.append(f"- wrote {len(mine)} file{'s' if len(mine) > 1 else ''} in {root}: " + ", ".join(mine)
                      + (f" (old versions kept as .bak: {', '.join(backups)})" if backups else ""))
    if added:
        report.append("- added plm's building block" + ("s" if len(added) > 1 else "") + ": " + ", ".join(added))
    if imports:
        report.append("- plm added " + ", ".join(dict.fromkeys(imports)))
    if removed:
        report.append(f"- removed {', '.join(removed)} (kept in {os.path.join(root, '.plm', 'trash')})")
    if not written and not removed and WANTS_CHANGE.search(last) and "```" in steps[-1]["model_text"]:
        report.append("- nothing was written: the model gave code but not as files. Ask again, or name the file.")
    report += [f"- could not write {f}" for f in failed]
    if xcode.get("project"):
        usage = f"; Info.plist has {', '.join(xcode['usage'])}" if xcode.get("usage") else ""
        report.append(f"- generated {xcode['project']} ({' '.join(app or ())} app{usage})")
    if checked and checked["kind"]:
        what = "build" if checked["kind"] in ("xcode", "swift package") else "syntax check"
        if not errors:
            report.append(f"- {what}: passed" + (f" after {len(steps)} attempts" if len(steps) > 1 else ""))
        else:
            report.append(f"- {what}: FAILED, {len(errors)} problem{'s' if len(errors) > 1 else ''} left after "
                          f"{len(steps)} attempt{'s' if len(steps) > 1 else ''}:")
            report += [f"    {e}" for e in errors[:8]]
    elif any(f.endswith(".swift") for f in written):
        report.append("- not built: there is no app entry point yet (a SwiftUI @main App file), so there is nothing to build")
    elif written:
        report.append("- not checked: plm has no check for these file types")
    if not written and not cut:
        was = state(root)
        if re.search(r"xcode|\.xcodeproj", last, re.IGNORECASE):
            own = app_of(root)
            mine = f"{own[0]}.xcodeproj" if own and Path(root, f"{own[0]}.xcodeproj").exists() else None
            theirs = foreign_xcode(root)
            report.append("- Xcode projects in this folder: " + (", ".join(
                ([f"{mine} (generated by plm from Sources/; the one to open)"] if mine else [])
                + [f"{x} (made in Xcode; plm leaves it alone)" for x in theirs]) or "none yet. Ask for an app and plm makes one"))
        if was and re.search(r"\b(run|launch|open|start|work|works|working|build|built)\b", last, re.IGNORECASE):
            report.append("- project status: " + (f"the last build passed ({was.get('at')}); /run opens the app" if was.get("built")
                          else f"the last build FAILED ({was.get('at')}), so there is nothing to run yet: "
                          + "; ".join(was.get("errors", [])[:3])))
    theirs = foreign_xcode(root) if xcode.get("project") else []
    if theirs:
        report.append(f"- note: {', '.join(theirs)} was made in Xcode and plm cannot edit Xcode's own project files, so plm "
                      f"built its own project, {xcode['project']}, from the Swift files in Sources/. Use that one; the "
                      "Swift files outside Sources/ are not part of it")
    if xcode.get("built"):
        report.append(f"- to run it: type /run here, or open {os.path.join(root, xcode['project'])} in Xcode and press Run")
    elif checked and checked["kind"] and errors:
        report.append('- next: the app does not run yet. Say "fix the build errors" to have plm try again from where it '
                      "stopped; the errors above are what is left")
    text = prose
    if report:
        head = "**What plm did**" if written or removed or cut or failed else "**From plm**"
        text = (prose + "\n\n" if prose else "") + head + " (checked by plm, not by the model):\n" + "\n".join(report)
    did_check = bool(checked and checked["kind"])
    return {"pack": "project", "task": last, "level": "project", "reason": f"project folder {root}",
            "answer": {"text": text or "(no answer)"}, "checked": did_check,
            "unchecked_reason": None if did_check else "nothing was built or checked for this answer",
            "trusted": did_check and not errors, "steps": steps, "tokens": sum(s["tokens"] for s in steps),
            "seconds": time.time() - start,
            "project": {"root": root, "written": written, "failed": failed, "errors": errors,
                        "xcodeproj": xcode.get("project"), "built": bool(xcode.get("built")), "product": xcode.get("product")}}


def launch(result_project):
    """Open what the last project answer built: the Mac app, else the Xcode project. Returns a line for the user."""
    p = result_project or {}
    target = p.get("product") if p.get("product") and "iphonesimulator" not in p["product"] else None
    target = target or (os.path.join(p["root"], p["xcodeproj"]) if p.get("xcodeproj") else None)
    if not target or not os.path.exists(target):
        return "nothing to run yet: ask for an app in the project folder first"
    code, text = _run(["open", target], p["root"], 30)
    return f"opened {target}" if code == 0 else f"couldn't open {target}: {text.strip()[:200]}"
