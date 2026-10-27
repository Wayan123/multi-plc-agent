"""Drive Haiwell Happy (V2.2.13, VB6) through pywinauto's win32 backend.

Run with Windows Python that has pywinauto and pywin32; prints one JSON object.

    python haiwell_gui.py <job.json>

Job: {"op": "write" | "compile" | "export_il", "path": "<project.gpc>",
      "steps": [...]  (write only, from ladder.plan), "exe": "<HaiwellHappy.exe>"}

Observed UI facts this relies on:
- Ctrl+O shows a standard Open dialog (Edit 1148, "&Open"); if the current
  project changed, a "would you like to save it?" box follows (answered No).
- The project tree (TreeView20WndClass) cannot be read cross-process, so the
  first program block is opened by double-clicking its row; success is checked
  by the "PGB:<name>" MDI child appearing.
- Keys go to the foreground window, so every step first checks that the
  foreground window belongs to HaiwellHappy and aborts otherwise.
- A network comment opens a ThunderRT6UserControlDC editor; it is committed by
  clicking the first cell of the rung just below it.
- Alt+T, Enter = Tools > Convert program to IL (Save dialog, Edit 1001).
- Alt+D, Up, Up, Enter = Debug > Compile; results are in a ListView20WndClass
  inside the "Compile" child.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import win32api  # noqa: E402
import win32con  # noqa: E402
import win32gui  # noqa: E402
import win32process  # noqa: E402
from pywinauto import Application, mouse  # noqa: E402
from pywinauto.controls.common_controls import ListViewWrapper  # noqa: E402
from pywinauto.keyboard import send_keys  # noqa: E402

DEFAULT_EXE = r"C:\Program Files (x86)\Haiwell\HaiwellHappy\HaiwellHappy.exe"
TREE_ROW = 18          # px per row in the project tree
FIRST_BLOCK_ROW = 3    # project, Program, Main program, PGB:<first block>


class Abort(Exception):
    pass


def _pids(exe: str) -> list[int]:
    out = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {Path(exe).name}", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return [int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"')]


def _windows(pid: int) -> list[tuple[int, str, str, tuple]]:
    found = []

    def cb(h, _):
        if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.IsWindowVisible(h):
            found.append((h, win32gui.GetClassName(h), win32gui.GetWindowText(h), win32gui.GetWindowRect(h)))
    win32gui.EnumWindows(cb, None)
    return found


def _children(h: int) -> list[tuple[int, str, str, tuple]]:
    found = []

    def cb(c, _):
        if win32gui.IsWindowVisible(c):
            found.append((c, win32gui.GetClassName(c), win32gui.GetWindowText(c), win32gui.GetWindowRect(c)))
    win32gui.EnumChildWindows(h, cb, None)
    return found


class Haiwell:
    def __init__(self, exe: str):
        pids = _pids(exe)
        if not pids:
            subprocess.Popen([exe], cwd=str(Path(exe).parent))
            for _ in range(40):
                time.sleep(1)
                pids = _pids(exe)
                if pids and self._main_of(pids[0]):
                    break
            time.sleep(3)
        if not pids:
            raise Abort("HaiwellHappy did not start")
        self.pid = pids[0]
        self.app = Application(backend="win32").connect(process=self.pid)
        self.main = self._main_of(self.pid)
        if not self.main:
            raise Abort("HaiwellHappy main window not found")

    @staticmethod
    def _main_of(pid: int) -> int | None:
        return next((w[0] for w in _windows(pid) if w[1] == "ThunderRT6MDIForm"), None)

    # -- dialogs --------------------------------------------------------
    def dialogs(self) -> list[int]:
        return [w[0] for w in _windows(self.pid) if w[1] == "#32770"]

    def dialog_text(self, h: int) -> str:
        return " ".join(c[2] for c in _children(h) if c[1] == "Static" and c[2])

    def press(self, h: int, label: str) -> bool:
        for c in _children(h):
            if c[1] == "Button" and c[2].replace("&", "") == label:
                win32api.PostMessage(c[0], win32con.BM_CLICK, 0, 0)
                time.sleep(1.2)
                return True
        return False

    def wait_dialog(self, title: str, timeout: float = 8) -> int:
        end = time.time() + timeout
        while time.time() < end:
            for h in self.dialogs():
                if win32gui.GetWindowText(h).startswith(title):
                    return h
            time.sleep(0.3)
        raise Abort(f"dialog {title!r} did not appear")

    def message_boxes(self) -> list[tuple[int, str]]:
        """Plain message boxes (no Edit field), with their text."""
        boxes = []
        for h in self.dialogs():
            kids = _children(h)
            if not any(c[1] == "Edit" for c in kids):
                boxes.append((h, self.dialog_text(h)))
        return boxes

    def file_dialog(self, h: int, path: str, edit_id: int, button: str) -> None:
        dlg = self.app.window(handle=h)
        edit = [c for c in dlg.descendants() if c.class_name() == "Edit" and c.control_id() == edit_id][0]
        edit.set_edit_text(path)
        time.sleep(0.3)
        if not self.press(h, button):
            raise Abort(f"button {button!r} not found in file dialog")
        time.sleep(1.5)

    # -- input ----------------------------------------------------------
    def foreground(self) -> None:
        def ours() -> bool:
            return win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1] == self.pid
        if ours():
            return
        try:
            self.app.window(handle=self.main).set_focus()
        except Exception:
            pass
        time.sleep(0.4)
        if not ours():
            raise Abort("another window has the keyboard focus; stopped before typing")

    def keys(self, keys: str, pause: float = 0.7) -> None:
        self.foreground()
        send_keys(keys, with_spaces=True, pause=0.04)
        time.sleep(pause)

    def click(self, x: int, y: int, double: bool = False) -> None:
        self.foreground()
        (mouse.double_click if double else mouse.click)(coords=(x, y))
        time.sleep(0.8)

    def check_no_message(self, where: str) -> None:
        boxes = self.message_boxes()
        if boxes:
            texts = [t for _, t in boxes]
            for h, _ in boxes:
                self.press(h, "OK")
            raise Abort(f"HaiwellHappy message at {where}: {texts}")

    # -- project --------------------------------------------------------
    def title(self) -> str:
        return win32gui.GetWindowText(self.main)

    def reset_ui(self) -> None:
        """Leave menu mode / inline edits: a highlighted menu swallows shortcuts."""
        for h, _ in self.message_boxes():
            self.press(h, "OK")
        l, t, r, _ = win32gui.GetWindowRect(self.main)
        self.click((l + r) // 2, t + 18)  # caption bar
        self.keys("{ESC}{ESC}", 0.3)

    def open_project(self, path: str) -> None:
        if f"[{path}]".lower() in self.title().lower():
            return
        self.reset_ui()
        self.keys("^o", 1.5)
        self.file_dialog(self.wait_dialog("Open"), path, 1148, "Open")
        for _ in range(3):
            boxes = self.message_boxes()
            if not boxes:
                break
            h, text = boxes[0]
            if "would you like to save" in text:
                self.press(h, "No")  # never save a project this job did not open
            else:
                raise Abort(f"open failed: {text}")
            time.sleep(1.5)
        if f"[{path}]".lower() not in self.title().lower():
            raise Abort(f"project did not open; title is {self.title()!r}")

    def editor(self) -> tuple[int, int] | None:
        """(MDI child, drawing PictureBox) of the open PGB editor."""
        for c in _children(self.main):
            if c[1] == "ThunderRT6FormDC" and c[2].startswith("PGB:"):
                pic = [p for p in _children(c[0]) if p[1] == "ThunderRT6PictureBoxDC"]
                if pic:
                    return c[0], pic[0][0]
        return None

    def open_first_block(self) -> str:
        if not self.editor():
            tree = next(c for c in _children(self.main) if c[1] == "TreeView20WndClass")
            left, top = tree[3][0], tree[3][1]
            self.click(left + 130, top + 8 + TREE_ROW * FIRST_BLOCK_ROW, double=True)
            time.sleep(1.5)
        ed = self.editor()
        if not ed:
            raise Abort("program block editor did not open")
        return win32gui.GetWindowText(ed[0])

    def commit_comment(self) -> None:
        _, pic = self.editor()
        boxes = [c for c in _children(pic) if c[1] == "ThunderRT6UserControlDC"]
        if not boxes:
            raise Abort("network comment editor not found")
        l, _, _, b = boxes[0][3]
        self.click(l + 30, b + 40)

    def run_steps(self, steps: list[dict]) -> None:
        _, pic = self.editor()
        l, t, _, _ = win32gui.GetWindowRect(pic)
        self.click(l + 40, t + 15)  # focus the LD canvas (first network title row)
        for n, step in enumerate(steps):
            if "comment" in step:
                self.keys("{UP}", 0.5)
                self.keys("{ENTER}", 0.8)
                self.keys(_escape(step["comment"]), 0.5)
                self.commit_comment()
            else:
                self.keys(step["k"])
            self.check_no_message(f"step {n} {step}")

    def save(self) -> None:
        self.keys("^s", 2.5)
        self.check_no_message("save")

    def export_il(self) -> str:
        out = Path(tempfile.gettempdir()) / f"haiwell_il_{os.getpid()}.txt"
        if out.exists():
            out.unlink()
        self.reset_ui()
        self.keys("%t", 0.8)
        self.keys("{ENTER}", 1.5)
        self.file_dialog(self.wait_dialog("Export"), str(out), 1001, "Save")
        for h, text in self.message_boxes():
            self.press(h, "OK")
            if "successfuly" not in text and "successfully" not in text:
                raise Abort(f"IL export failed: {text}")
        if not out.exists():
            raise Abort("IL export wrote no file")
        text = out.read_text(encoding="mbcs", errors="replace")
        out.unlink()
        return text

    def compile(self) -> dict:
        self.reset_ui()
        self.keys("%d", 0.8)
        self.keys("{UP}{UP}{ENTER}", 3)
        lines: list[str] = []
        for _ in range(20):
            for c in _children(self.main):
                if c[1] == "ListView20WndClass":
                    lines = [t for t in ListViewWrapper(c[0]).texts() if t]
            if any(t.startswith("Error number:") for t in lines):
                break
            time.sleep(0.5)
        summary = next((t for t in lines if t.startswith("Error number:")), None)
        if summary is None:
            return {"ok": False, "error": "no compile result found", "lines": lines}
        parts = summary.replace(":", " ").split()
        errors, warnings_ = int(parts[2]), int(parts[5])
        return {"ok": errors == 0, "error_count": errors, "warning_count": warnings_,
                "messages": [t for t in lines if t.startswith(("Error:", "Alarm:"))],
                "summary": [t for t in lines if t not in ("Compiling...",)]}


def _escape(text: str) -> str:
    return "".join("{%s}" % ch if ch in "+^%~(){}[]" else ch for ch in text)


def run(job: dict) -> dict:
    hw = Haiwell(job.get("exe") or DEFAULT_EXE)
    path = str(Path(job["path"]).resolve())
    hw.open_project(path)
    result: dict = {"project": path, "haiwell_pid": hw.pid}
    if job["op"] == "write":
        result["block"] = hw.open_first_block()
        hw.run_steps(job["steps"])
        hw.save()
        result["il"] = hw.export_il()
    elif job["op"] == "export_il":
        result["il"] = hw.export_il()
    elif job["op"] == "compile":
        result.update(hw.compile())
    else:
        raise Abort(f"unknown op {job['op']!r}")
    result.setdefault("ok", True)
    result["title"] = hw.title()
    return result


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        out = run(job)
    except Abort as error:
        out = {"ok": False, "error": str(error)}
    except Exception as error:  # report, the caller decides
        out = {"ok": False, "error": f"{type(error).__name__}: {error}"}
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
