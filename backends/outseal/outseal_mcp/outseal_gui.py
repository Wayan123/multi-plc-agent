"""Drive Outseal Studio to open a .plc and run Test (compile without hardware).

Run with Windows Python that has pywinauto. Prints one JSON object.

    python outseal_gui.py compile <project.plc> [--exe PATH] [--keep-open]

Steps, matching the controls exposed by Outseal Studio V3.6 (WPF, UIA backend):
1. Start Outseal_Studio.exe (or reuse a running instance).
2. Ribbon "Buka" -> Open dialog (Edit 1148, button 1) -> if a project is loaded,
   answer the close-project confirmation with Yes.
3. Ribbon "Test". Success shows "Tidak terdapat kesalahan" and refreshes
   %TEMP%\\Outseal\\Hasil.hex. Failure shows "Terdapat (N) kesalahan" and an
   error list (TitikKesalahan items).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
from pywinauto import Application, Desktop  # noqa: E402

DEFAULT_EXE = r"C:\Program Files (x86)\Outseal Studio\Outseal_Studio.exe"
HEX = Path(os.environ.get("TEMP", "")) / "Outseal" / "Hasil.hex"
OK_TEXT = "Tidak terdapat kesalahan"
ERR_TEXT = re.compile(r"Terdapat \((\d+)\) kesalahan")


def _process_ids(exe: str) -> list[int]:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {Path(exe).name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return [int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"')]


def _main_window(app):
    return app.window(auto_id="metroWindow", top_level_only=True)


def _modals(app, pid):
    found = []
    for w in Desktop(backend="uia").windows():
        try:
            if w.process_id() == pid and w.element_info.class_name == "#32770":
                found.append(w)
        except Exception:
            pass
    main = _main_window(app)
    for c in main.children():
        if c.element_info.class_name == "#32770":
            found.append(c)
    return found


def _drain(app, pid, answers=("Yes", "OK")):
    """Answer stacked message boxes; returns their texts."""
    texts = []
    for _ in range(6):
        boxes = _modals(app, pid)
        if not boxes:
            break
        box = boxes[0]
        body = " ".join(t.window_text() for t in box.descendants(control_type="Text") if t.window_text())
        texts.append(body or box.window_text())
        for name in answers:
            btns = [b for b in box.descendants(control_type="Button") if b.window_text().replace("&", "") == name]
            if btns:
                btns[0].invoke()
                break
        else:
            box.close()
        time.sleep(0.6)
    return texts


def _ribbon(main, name, control_type="Button"):
    found = main.child_window(title=name, control_type=control_type, found_index=0)
    if found.exists(timeout=2):
        return found
    raise RuntimeError(f"ribbon {control_type} {name!r} not found")


def _output_texts(main):
    return [t.window_text() for t in main.descendants(control_type="Text") if t.window_text()]


def compile_project(path: str, exe: str, keep_open: bool) -> dict:
    path = str(Path(path).resolve())
    started = False
    pids = _process_ids(exe)
    if not pids:
        subprocess.Popen([exe], cwd=str(Path(exe).parent))
        started = True
        for _ in range(60):
            time.sleep(1)
            pids = _process_ids(exe)
            if pids:
                break
    if not pids:
        return {"ok": False, "error": "Outseal Studio did not start"}
    pid = pids[0]
    app = Application(backend="uia").connect(process=pid, timeout=30)
    main = _main_window(app)
    main.wait("ready", timeout=60)
    _drain(app, pid, answers=("No", "OK"))

    # Open dialog is already up from the probe or a previous run? Reuse it.
    dialog = main.child_window(title="Open", control_type="Window")
    if not dialog.exists(timeout=0.5):
        # The raw UIA Invoke pattern on the SplitButton runs its main command
        # (Open). pywinauto's .invoke()/.click_input() open the dropdown instead.
        _ribbon(main, "Buka", "SplitButton").wrapper_object().iface_invoke.Invoke()
    if not dialog.exists(timeout=10):
        return {"ok": False, "error": "Outseal Studio did not show the Open dialog"}
    edit = dialog.child_window(auto_id="1148", control_type="Edit")
    edit.set_edit_text(path)
    button = dialog.child_window(auto_id="1", control_type="SplitButton")
    if not button.exists(timeout=1):
        button = dialog.child_window(auto_id="1", control_type="Button")
    button.invoke()
    time.sleep(1.5)
    opened_messages = _drain(app, pid, answers=("Yes", "OK"))
    time.sleep(1.5)

    before = HEX.stat().st_mtime if HEX.exists() else 0.0
    _ribbon(main, "Test").invoke()
    result = None
    for _ in range(60):
        time.sleep(0.5)
        texts = _output_texts(main)
        if any(OK_TEXT in t for t in texts):
            result = {"ok": True, "error_count": 0, "errors": []}
            break
        m = next((ERR_TEXT.search(t) for t in texts if ERR_TEXT.search(t)), None)
        if m:
            errors = []
            for item in main.descendants(control_type="ListItem"):
                if item.window_text().endswith("TitikKesalahan"):
                    # parts: "0", ". ", "TON-1", ", ", "Variable yang digunakan salah"
                    errors.append("".join(t.window_text() for t in item.children(control_type="Text")).strip())
            result = {"ok": False, "error_count": int(m.group(1)), "errors": errors}
            break
    _drain(app, pid, answers=("OK",))
    if result is None:
        result = {"ok": False, "error": "no Test result appeared within 30 s"}
    hex_fresh = HEX.exists() and HEX.stat().st_mtime > before
    result.update({
        "project": path,
        "title": main.window_text(),
        "open_messages": opened_messages,
        "hex": str(HEX) if hex_fresh else None,
        "hex_bytes": HEX.stat().st_size if hex_fresh else None,
        "outseal_pid": pid,
    })
    if result.get("ok") and not hex_fresh:
        result["ok"] = False
        result["error"] = "Test reported no errors but Hasil.hex was not refreshed"
    if started and not keep_open:
        main.close()
        time.sleep(1)
        _drain(app, pid, answers=("No", "OK"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("op", choices=["compile"])
    parser.add_argument("project")
    parser.add_argument("--exe", default=DEFAULT_EXE)
    parser.add_argument("--keep-open", action="store_true")
    args = parser.parse_args()
    try:
        out = compile_project(args.project, args.exe, args.keep_open)
    except Exception as error:  # report, the caller decides
        out = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
