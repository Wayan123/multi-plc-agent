"""Drive Delta WPLSoft 2.52 with window messages only (no global keys or mouse).

Run with Windows Python that has pywinauto and pywin32; prints one JSON object.

    python wplsoft_gui.py <job.json>

Job: {"op": "compile", "path": "<project.dvp>", "save": bool, "exe": "<WPLSoft.exe>"}

Each job starts its own WPLSoft process with the project on the command line,
works only on that process's windows and closes it at the end, so other
WPLSoft windows (and other programs on a shared desktop) are left alone.

Observed UI facts this relies on:
- The menu bar is a DevExpress TdxBarControl ("MenuBar") with no native menu
  or UIA items; posted WM_LBUTTONDOWN/UP at client x=22 (File), x=107
  (Compiler) opens a TdxBarSubMenuControl whose rows are 23 px apart:
  Compiler row 0 "Ladder => Instruction", row 1 "Instruction => Ladder";
  File row 3 "Save As".
- The MDI children are TLDB ("Ladder Diagram Mode") and TInst ("Instruction
  List Mode"); WM_MDIACTIVATE selects the one a Compiler command works on.
- Results: the Message panel TListView gets "Compiling is complete!" /
  "Diagram is complete!"; a syntax error opens a "Grammar Check Error"
  dialog whose Static reads "Error code: c401 ... Reference Step Number: Step a ~ b".
- Save As is a standard file dialog (Edit 1148, button id 1).
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402
import win32process  # noqa: E402
from pywinauto.controls.common_controls import ListViewWrapper  # noqa: E402

DEFAULT_EXE = r"C:\Program Files (x86)\Delta Industrial Automation\WPLSoft 2.52\WPLSoft.exe"
MENU_X = {"file": 22, "compiler": 107}
ROW = 23


class Abort(Exception):
    pass


def _pids(exe: str) -> set[int]:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {Path(exe).name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return {int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"')}


def _windows(pid: int) -> list[tuple[int, str, str]]:
    found = []

    def cb(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.IsWindowVisible(h):
            found.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h)))
    win32gui.EnumWindows(cb, None)
    return found


def _children(h: int, visible: bool = True) -> list[tuple[int, str, str, int]]:
    found = []

    def cb(c, _):
        if not visible or win32gui.IsWindowVisible(c):
            found.append((c, win32gui.GetClassName(c), win32gui.GetWindowText(c), win32gui.GetDlgCtrlID(c)))
    win32gui.EnumChildWindows(h, cb, None)
    return found


def _click(h: int, x: int, y: int) -> None:
    lp = (y << 16) | x
    win32api.PostMessage(h, win32con.WM_MOUSEMOVE, 0, lp)
    time.sleep(0.2)
    win32api.PostMessage(h, win32con.WM_LBUTTONDOWN, win32con.MK_LBUTTON, lp)
    time.sleep(0.1)
    win32api.PostMessage(h, win32con.WM_LBUTTONUP, 0, lp)
    time.sleep(0.8)


def _press(h: int, *labels: str) -> bool:
    for c in _children(h, False):
        if c[1] in ("Button", "TButton") and c[2].replace("&", "") in labels:
            win32api.PostMessage(c[0], win32con.BM_CLICK, 0, 0)
            time.sleep(1.0)
            return True
    return False


class WPLSoft:
    def __init__(self, exe: str, path: str):
        before = _pids(exe)
        subprocess.Popen([exe, path], cwd=str(Path(exe).parent))
        self.pid = None
        stem = Path(path).stem.lower()
        for _ in range(60):
            time.sleep(0.5)
            for pid in _pids(exe) - before:
                if any(w[1] == "TWplMain" and w[2].lower().startswith(stem + "[") for w in _windows(pid)):
                    self.pid = pid
            if self.pid:
                break
        if not self.pid:
            raise Abort("WPLSoft did not open the project")
        time.sleep(1.5)
        self.main = next(w[0] for w in _windows(self.pid) if w[1] == "TWplMain")
        kids = _children(self.main, False)
        self.mdi = next(k[0] for k in kids if k[1] == "MDIClient")
        self.menubar = next(k[0] for k in kids if k[1] == "TdxBarControl" and k[2] == "MenuBar")
        self.messages = next(k[0] for k in kids if k[1] == "TListView")
        self.views = {k[1]: k[0] for k in kids if k[1] in ("TLDB", "TInst")}

    def popups(self) -> list[tuple[int, str, str]]:
        return [w for w in _windows(self.pid) if w[1] not in ("TWplMain", "TApplication")]

    def menu(self, name: str, row: int) -> None:
        _click(self.menubar, MENU_X[name], 12)
        sub = [w for w in _windows(self.pid) if w[1] == "TdxBarSubMenuControl"]
        if not sub:
            raise Abort(f"{name} menu did not open")
        _click(sub[0][0], 60, 12 + ROW * row)

    def message_lines(self) -> list[str]:
        return [t for t in ListViewWrapper(self.messages).texts() if t]

    def convert(self, view: str, row: int) -> dict:
        win32gui.SendMessage(self.mdi, win32con.WM_MDIACTIVATE, self.views[view], 0)
        time.sleep(0.5)
        before = len(self.message_lines())
        self.menu("compiler", row)
        errors, other = [], []
        for _ in range(20):
            time.sleep(0.5)
            pops = self.popups()
            for h, cls, title in pops:
                text = " ".join(c[2] for c in _children(h) if c[1] == "Static" and c[2])
                if title == "Grammar Check Error":
                    errors.append(" ".join(text.split()))
                else:
                    other.append(f"{cls} {title!r} {text}".strip())
                _press(h, "OK")
            if not pops and len(self.message_lines()) > before:
                break
        return {"errors": errors, "other_dialogs": other, "messages": self.message_lines()[before:]}

    def save_as(self, path: str) -> None:
        self.menu("file", 3)
        dlg = None
        for _ in range(20):
            time.sleep(0.3)
            dlg = next((w[0] for w in _windows(self.pid) if w[1] == "#32770" and w[2] == "Save As"), None)
            if dlg:
                break
        if not dlg:
            raise Abort("Save As dialog did not appear")
        kids = _children(dlg)
        edit = next(k[0] for k in kids if k[1] == "Edit" and k[3] == 1148)
        win32gui.SendMessage(edit, win32con.WM_SETTEXT, 0, path)
        _press(dlg, "Save")
        for _ in range(10):
            time.sleep(0.5)
            pops = [w for w in self.popups() if w[1] == "#32770"]
            if not pops:
                break
            for h, _, _ in pops:
                if not _press(h, "Yes"):
                    raise Abort("unexpected dialog while saving")
        if Path(path).stem.lower() + "[" not in win32gui.GetWindowText(self.main).lower():
            raise Abort("save did not complete")

    def close(self) -> None:
        win32api.PostMessage(self.main, win32con.WM_CLOSE, 0, 0)
        for _ in range(20):
            time.sleep(0.5)
            wins = _windows(self.pid)
            if not any(w[1] == "TWplMain" for w in wins):
                return
            for h, cls, _ in wins:
                if cls in ("#32770", "TMessageForm"):
                    _press(h, "No", "OK")


def run(job: dict) -> dict:
    path = str(Path(job["path"]))
    if not Path(path).exists():
        return {"ok": False, "error": f"{path} not found"}
    app = WPLSoft(job.get("exe") or DEFAULT_EXE, path)
    try:
        to_ladder = app.convert("TInst", 1)    # Compiler > Instruction => Ladder (grammar check)
        to_il = app.convert("TLDB", 0) if not to_ladder["errors"] else None
        errors = to_ladder["errors"] + (to_il["errors"] if to_il else [])
        result = {"ok": not errors, "error_count": len(errors), "errors": errors,
                  "instruction_to_ladder": to_ladder, "ladder_to_instruction": to_il, "saved": False}
        if job.get("save") and not errors:
            app.save_as(path)
            result["saved"] = True
        return result
    finally:
        app.close()


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except Abort as e:
        result = {"ok": False, "error": str(e)}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
