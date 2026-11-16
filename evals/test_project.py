"""Project mode (plm/project.py): the model's reply is turned into files, checked in code, and reported by code.

    .venv/bin/python evals/test_project.py

The model is replaced by scripted replies; the checks are real (py_compile, and one real XcodeGen + Xcode build of
a small Mac app, skipped with a note when those tools aren't installed). No eval set: this guards behaviour, it
doesn't measure quality.
"""

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import plm.ollama as ollama  # noqa: E402
from plm import project  # noqa: E402

FAILS = []
F = "`" * 3


def expect(name, ok, detail=""):
    if not ok:
        FAILS.append(name)
        print(f"FAIL {name}: {str(detail)[:600]}")


def scripted(replies, seen):
    def chat(model, messages, num_predict, timeout, options=None):
        seen.append(messages)
        text = replies[min(len(seen), len(replies)) - 1]
        return {"response": text, "eval_tokens": len(text.split()), "prompt_tokens": 50, "wall_s": 0.0,
                "done_reason": "stop", "load_s": 0, "thinking_chars": 0, "mode": "fake"}
    return chat


def file_block(name, body, lang=""):
    return f"FILE: {name}\n{F}{lang}\n{body}\n{F}\n"


def ask(root, text, replies, history=()):
    seen, real = [], ollama.chat
    ollama.chat = scripted(replies, seen)
    try:
        return project.solve(root, [*history, {"role": "user", "content": text}], "fake-coder"), seen
    finally:
        ollama.chat = real


def main():
    # the reply format
    got = project.parse("APP: Demo iOS\n\n" + file_block("Sources/A.swift", "let a = 1", "swift")
                        + "\n**FILE: `Sources/B.swift`**\n" + F + "swift\nlet b = 2\n" + F + "\n\nTwo files.\n\n### FILE: C.swift\n"
                        + F + "swift\nlet c =")
    expect("parse: files, app, cut-off file, prose", list(got["files"]) == ["Sources/A.swift", "Sources/B.swift"]
           and got["app"] == ("Demo", "iOS") and got["cut"] == "C.swift" and got["prose"] == "Two files.", got)

    with tempfile.TemporaryDirectory() as tmp:
        # the model is shown what is really there
        expect("an empty folder is described as empty", "the folder is empty" in project.snapshot(tmp))
        Path(tmp, "notes.txt").write_text("the track has 8 pieces\n")
        Path(tmp, "old.py.bak").write_text("x")
        Path(tmp, "build").mkdir()
        Path(tmp, "build", "junk.txt").write_text("x")
        snap = project.snapshot(tmp)
        expect("snapshot lists and shows the project's files, not backups or build output",
               "- notes.txt (23 bytes)" in snap and "the track has 8 pieces" in snap and "junk" not in snap and ".bak" not in snap, snap)

        # a request: files are written, checked, and the report is plm's
        r, seen = ask(tmp, "make a script that prints the track length", [file_block("track.py", "print(8)", "python") + "\nPrints it."])
        expect("the model sees the rules and the folder", "PROJECT FILES" in seen[0][0]["content"] and "notes.txt" in seen[0][0]["content"]
               and "Never say a file" in seen[0][0]["content"])
        expect("the file is written and the report says so", Path(tmp, "track.py").read_text() == "print(8)\n"
               and "wrote 1 file" in r["answer"]["text"] and "syntax check: passed" in r["answer"]["text"]
               and r["trusted"] and r["project"]["written"] == ["track.py"], r["answer"]["text"])

        # an error found by the check goes back to the model; the old file is kept once
        r, seen = ask(tmp, "change track.py to print 9", [file_block("track.py", "print(9", "python"), file_block("track.py", "print(9)", "python")])
        expect("a syntax error is sent back and the fix is written", len(seen) == 2 and "Problems found" in seen[1][-1]["content"]
               and "track.py" in seen[1][-1]["content"] and Path(tmp, "track.py").read_text() == "print(9)\n"
               and "passed after 2 attempts" in r["answer"]["text"], (r["answer"]["text"], seen[-1][-1]["content"]))
        expect("the version before this turn is the backup", Path(tmp, "track.py.bak").read_text() == "print(8)\n")

        # errors that never get fixed are reported as failed, not as done
        r, seen = ask(tmp, "rewrite track.py", [file_block("track.py", "print(", "python")])
        expect("an unfixed error is reported as FAILED", len(seen) == project.ROUNDS and "FAILED" in r["answer"]["text"]
               and not r["trusted"] and r["project"]["errors"], r["answer"]["text"])

        # code without FILE blocks: asked once more; if still none, the report says nothing was written
        r, seen = ask(tmp, "make a hello script", [F + "python\nprint('hi')\n" + F + "\nSave this as hello.py.", file_block("hello.py", "print('hi')")])
        expect("code without files is asked for again as files", len(seen) == 2 and "no FILE blocks" in seen[1][-1]["content"]
               and Path(tmp, "hello.py").exists(), r["answer"]["text"])
        r, seen = ask(tmp, "make a bye script", [F + "python\nprint('bye')\n" + F + "\nI created bye.py for you."])
        expect("nothing written is reported as nothing written", "nothing was written" in r["answer"]["text"]
               and not Path(tmp, "bye.py").exists() and not r["trusted"], r["answer"]["text"])

        # a plain question gets a plain answer, no report
        r, seen = ask(tmp, "what does track.py print?", ["It prints 9."])
        expect("a question is answered without a report", r["answer"]["text"] == "It prints 9." and len(seen) == 1 and not r["checked"])

        # files can't leave the folder; plm's own files can't be written by the model
        r, seen = ask(tmp, "make it", [file_block("../escape.py", "print(1)") + file_block("project.yml", "name: X") + file_block("ok.py", "print(1)")])
        expect("a path outside the folder is refused and reported", not Path(tmp).parent.joinpath("escape.py").exists()
               and "could not write ../escape.py" in r["answer"]["text"] and not Path(tmp, "project.yml").exists()
               and Path(tmp, "ok.py").exists(), r["answer"]["text"])

        # a reply cut off mid-file: that file is not saved and is asked for again
        r, seen = ask(tmp, "make two scripts", [file_block("one.py", "print(1)") + "FILE: two.py\n" + F + "python\nprint(",
                                                file_block("two.py", "print(2)")])
        expect("a cut-off file is not saved half-written and is asked for again", "cut off before FILE two.py" in seen[1][-1]["content"]
               and Path(tmp, "two.py").read_text() == "print(2)\n", r["answer"]["text"])

    # an Xcode app: the spec, the usage text, a real build
    with tempfile.TemporaryDirectory() as tmp:
        app = ("import SwiftUI\nimport CoreBluetooth\n\n@main\nstruct CarsApp: App {\n    var body: some Scene {\n"
               "        WindowGroup { Text(\"cars\").padding() }\n    }\n}")
        if not (shutil.which("xcodegen") and shutil.which(project.BUILD_TOOL)):
            print("skipped: the Xcode build test (xcodegen or Xcode's command-line tools are not installed)")
            r, _ = ask(tmp, "make a Mac app", ["APP: Cars macOS\n\n" + file_block("Sources/CarsApp.swift", app, "swift")])
            expect("without the tools the report says what is missing", "is not installed" in r["answer"]["text"], r["answer"]["text"])
        else:
            # a missing import is added by plm itself, with no second model call
            with tempfile.TemporaryDirectory() as tmp2:
                r2, seen2 = ask(tmp2, "make a Mac app", ["APP: Imp macOS\n\n" + file_block("Sources/ImpApp.swift", app.replace(
                    "import CoreBluetooth\n", "").replace('Text("cars")', 'Text(CBUUID(string: "180F").uuidString)'), "swift")])
                expect("plm adds a missing framework import itself and the build passes", len(seen2) == 1 and r2["trusted"]
                       and "plm added import CoreBluetooth to Sources/ImpApp.swift" in r2["answer"]["text"], r2["answer"]["text"])
            # a building block used but not added, and a second @main: both fixed by plm, no second model call
            with tempfile.TemporaryDirectory() as tmp3:
                main = ("import SwiftUI\n\n@main\nstruct FixApp: App {\n    @StateObject private var ble = BLECentral()\n"
                        "    var body: some Scene {\n        WindowGroup { Text(\"\\(ble.devices.count)\").padding() }\n    }\n}")
                old_style = "import AppKit\n\n@main\nclass AppDelegate: NSObject, NSApplicationDelegate {}\n"
                r3, seen3 = ask(tmp3, "make a Mac app", ["APP: Fix macOS\n\n" + file_block("Sources/FixApp.swift", main, "swift")
                                                         + file_block("Sources/AppDelegate.swift", old_style, "swift")])
                text3 = r3["answer"]["text"]
                expect("plm adds the missing building block and removes the second @main itself", len(seen3) == 1 and r3["trusted"]
                       and "Sources/BLECentral.swift" in text3 and "removed its @main" in text3, text3)
            broken = app.replace('Text("cars")', 'Text(cars)')
            r, seen = ask(tmp, "make a Mac app that will control my cars over Bluetooth",
                          ["APP: Cars macOS\n\n" + file_block("Sources/CarsApp.swift", broken, "swift"),
                           "APP: Other macOS\n\n" + file_block("Sources/CarsApp.swift", app, "swift") + "\nA window that says cars."])
            text = r["answer"]["text"]
            expect("a compile error from the real build goes back to the model", len(seen) == 2
                   and "Sources/CarsApp.swift:" in seen[1][-1]["content"], seen[-1][-1]["content"])
            expect("the app builds and the report says so", r["trusted"] and r["project"]["built"] and "build: passed after 2 attempts" in text
                   and "generated Cars.xcodeproj" in text and "/run" in text, text)
            expect("one Xcode project, named once", sorted(p.name for p in Path(tmp).glob("*.xcodeproj")) == ["Cars.xcodeproj"])
            plist = Path(r["project"]["product"] or "", "Contents", "Info.plist")
            expect("the Bluetooth usage text is in the built app's Info.plist", plist.is_file()
                   and b"NSBluetoothAlwaysUsageDescription" in plist.read_bytes(), plist)
            expect("the model is told about plm's Xcode project but not shown its generated files",
                   "CONTENTS OF project.yml" not in project.snapshot(tmp)
                   and "- Cars.xcodeproj (the Xcode project plm generates" in project.snapshot(tmp))

    # the building blocks: offered when the conversation calls for them, copied in by USE, and they really build
    expect("building blocks are offered only when called for", "USE: HTTPServer.swift" in project.offered("a dashboard on localhost port 3118")
           and "USE: BLECentral.swift" in project.offered("control the cars over BLE") and project.offered("print the track length") == "")
    with tempfile.TemporaryDirectory() as tmp:
        uses = ("import SwiftUI\nimport CoreBluetooth\n\nenum Keep { static var server: HTTPServer? }\n\n@main\nstruct CarsApp: App {\n"
                "    @StateObject private var ble = BLECentral()\n    var body: some Scene {\n        WindowGroup {\n"
                "            List(ble.devices) { device in Text(\"\\(device.name) \\(device.rssi)\") }\n                .onAppear {\n"
                "                    ble.startScanning()\n                    Keep.server = try? HTTPServer(port: 3118) { request in\n"
                "                        request.path == \"/\" ? .html(\"<h1>cars</h1>\") : .notFound\n                    }\n"
                "                    Keep.server?.start()\n                }\n        }\n    }\n}")
        reply = ("APP: Cars macOS\nUSE: HTTPServer.swift\nUSE: BLECentral.swift\n\n" + file_block("Sources/CarsApp.swift", uses, "swift")
                 + file_block("Sources/HTTPServer.swift", "// my own broken copy", "swift") + "\nScans and serves a page.")
        r, seen = ask(tmp, "make a Mac app: BLE scan and a page on localhost port 3118", [reply])
        text = r["answer"]["text"]
        expect("the offer reaches the model", "BUILDING BLOCKS" in seen[0][0]["content"] and "NWListener" not in seen[0][0]["content"])
        expect("USE copies the building blocks unchanged, and the model can't overwrite them",
               Path(tmp, "Sources", "HTTPServer.swift").read_text() == project.recipe("HTTPServer.swift")[0]
               and Path(tmp, "Sources", "BLECentral.swift").exists() and "added plm's building blocks" in text, text)
        if shutil.which("xcodegen") and shutil.which(project.BUILD_TOOL):
            expect("an app on both building blocks builds", r["trusted"] and "build: passed" in text and len(seen) == 1, text)
            expect("the build's result is remembered for the next turn", project.state(tmp).get("built") is True
                   and "the app built" in project.snapshot(tmp))
            r, seen = ask(tmp, "how do I run it?", ["Type /run."])
            expect("a question about running gets plm's own status line", "the last build passed" in r["answer"]["text"], r["answer"]["text"])
        expect("a building block in the folder is described, not pasted, to the model", "plm's building block" in project.snapshot(tmp)
               and "CONTENTS OF Sources/HTTPServer.swift" not in project.snapshot(tmp))

    # DELETE moves a file aside; the model's own copy of a building block is never written
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "old.py").write_text("print(0)\n")
        Path(tmp, "NOTES.md").write_text("the car's service UUID is ...\n")
        r, seen = ask(tmp, "clear the project and make new.py", ["DELETE: old.py\nDELETE: NOTES.md\n" + file_block("new.py", "print(1)")
                                                                + file_block("Sources/App/HTTPServer.swift", "// copy")])
        expect("DELETE moves the file to .plm/trash and says so", not Path(tmp, "old.py").exists()
               and Path(tmp, ".plm", "trash", "old.py").read_text() == "print(0)\n" and "removed old.py" in r["answer"]["text"], r["answer"]["text"])
        expect("the model's copy of a building block is not written", not Path(tmp, "Sources").exists())
        expect("reference notes survive 'clear the project'", Path(tmp, "NOTES.md").exists())
    expect("project-level build errors are read too", project._errors(
        'error: Filename "A.swift" used twice: \'/x/p/Sources/A.swift\' and \'/x/p/Sources/B/A.swift\'\n'
        "/x/p/Sources/C.swift:5:9: error: cannot find 'Foo' in scope\n", "/x/p")
        == ["Sources/C.swift:5: cannot find 'Foo' in scope", "Filename \"A.swift\" used twice: 'Sources/A.swift' and 'Sources/B/A.swift'"])

    # a folder that already has a project made in Xcode: plm builds its own from Sources/ and says so
    with tempfile.TemporaryDirectory() as tmp:
        Path(tmp, "Old", "Old.xcodeproj").mkdir(parents=True)
        Path(tmp, "Old", "Old.xcodeproj", "project.pbxproj").write_text("// !$*UTF8*$!\n")
        Path(tmp, "Old", "Main.swift").write_text("import NIO\n@main struct Old { static func main() {} }\n")
        expect("an Xcode-made project is recognised", project.foreign_xcode(tmp) == ["Old/Old.xcodeproj"]
               and "was made in Xcode, not by plm" in project.snapshot(tmp))
        r, seen = ask(tmp, "is there an xcode project now?", ["No."])
        expect("'is there an Xcode project' gets plm's own list", "Old/Old.xcodeproj (made in Xcode; plm leaves it alone)" in r["answer"]["text"], r["answer"]["text"])
        expect("an Xcode-made project is in the listing the model sees",
               "- Old/Old.xcodeproj (an Xcode project, made in Xcode by the user)" in project.snapshot(tmp))
        appkit = "import AppKit\n\nclass AppDelegate: NSObject, NSApplicationDelegate {}\n"
        r, seen = ask(tmp, "make it a working Mac app", [file_block("Sources/AppDelegate.swift", appkit, "swift"),
                                                         "DELETE: Sources/AppDelegate.swift\nNothing more."])
        expect("Swift with no SwiftUI entry point is sent back as a problem", len(seen) >= 2
               and "there is no app to build" in seen[1][-1]["content"], r["answer"]["text"])
        simple = ("import SwiftUI\n\n@main\nstruct NewApp: App {\n    var body: some Scene {\n        WindowGroup { Text(\"new\").padding() }\n    }\n}")
        r, seen = ask(tmp, "make it a working Mac app", ["APP: Cars macOS\n\n" + file_block("Sources/NewApp.swift", simple, "swift") + "\nA window."])
        text = r["answer"]["text"]
        if shutil.which("xcodegen") and shutil.which(project.BUILD_TOOL):
            expect("plm's app is built from Sources/ only, beside the Xcode-made project", r["trusted"] and "build: passed" in text
                   and "plm cannot edit Xcode's own project files" in text and "Old/Old.xcodeproj" in text, text)
            expect("the Xcode-made project is left untouched", Path(tmp, "Old", "Old.xcodeproj", "project.pbxproj").read_text() == "// !$*UTF8*$!\n"
                   and Path(tmp, "Old", "Main.swift").exists())
    r, seen = None, None
    with tempfile.TemporaryDirectory() as tmp:
        r, seen = ask(tmp, "make x.py", [file_block("x.py", "print(")])
        expect("the model is asked to explain its work in depth", "what each file you wrote is for" in seen[0][0]["content"])

    for f in FAILS:
        print("FAIL", f)
    print("project tests: all passed" if not FAILS else f"project tests: {len(FAILS)} failed")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
