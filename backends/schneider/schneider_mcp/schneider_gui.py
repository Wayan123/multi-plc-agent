"""Drive EcoStruxure Machine Expert - Basic (V1.3, WPF) through UI Automation.

Run with Windows Python that has pywinauto and pywin32; prints one JSON object.

    python schneider_gui.py <job.json>

Job: {"op": "compile", "path": "<project.smbp>", "to_ladder": false, "save": false,
      "exe": "<SchneiderElectric.SoMachineBasic.MainApplication.exe>"}

Every action targets this driver's own Machine Expert - Basic process through
UIA patterns (Invoke, SelectionItem, Scroll) or window messages; no global
keystrokes or mouse input are sent. Observed UI facts this relies on:
- The executable ignores a project path on its command line, so the project is
  opened with the toolbar Open button (automation id "Open"); the standard Open
  dialog is confirmed with WM_COMMAND IDOK (BM_CLICK on "&Open" is ignored).
- An "Untrusted DLL" panel appears at start-up; it does not block anything.
- "Compile Program" is a header-bar button identified by its help text; the
  result is the text in ShellControllerControl: "No error",
  "Program error(s) detected" or "Program advisory(ies) detected".
- In the Programming task each rung is a RungControl ("RungN" label) with an
  IL line list; an invalid IL line has a red line-number cell (no UIA text says
  so, so the cell colour is sampled from a PrintWindow capture of our window).
- A rung's LD/IL selector ("languageCombo") converts IL to ladder in place.
- Closing asks "Do you really want to close the application ?" (Yes) and, for
  a modified project, whether to save (answered by the "save" job flag); the
  process can linger after its windows close, so it is ended if still running.
"""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
import warnings

warnings.simplefilter("ignore")
import win32con  # noqa: E402
import win32gui  # noqa: E402
import win32process  # noqa: E402
import win32ui  # noqa: E402
from pywinauto import Application, Desktop  # noqa: E402

DEFAULT_EXE = (r"C:\Program Files (x86)\Schneider Electric\EcoStruxure Machine Expert - Basic"
               r"\SchneiderElectric.SoMachineBasic.MainApplication.exe")
TITLE_SUFFIX = "EcoStruxure Machine Expert - Basic"
STATUS_TEXTS = ("No error", "Program error(s) detected", "Program advisory(ies) detected")


def _invoke_async(element) -> None:
    """Invoke without blocking: WPF modal dialogs keep Invoke() from returning."""
    threading.Thread(target=element.invoke, daemon=True).start()


def _help(element) -> str:
    try:
        return element.element_info.element.CurrentHelpText or ""
    except Exception:
        return ""


class MachineExpert:
    def __init__(self, exe: str):
        self.proc = subprocess.Popen([exe], cwd=os.path.dirname(exe))
        self.pid = self.proc.pid
        self.desktop = Desktop(backend="uia")
        self.win32 = None
        self.main = self._wait_main(180)

    # windows -------------------------------------------------------------
    def tops(self) -> list[int]:
        found: list[int] = []

        def cb(h, _):
            if win32process.GetWindowThreadProcessId(h)[1] == self.pid and win32gui.IsWindowVisible(h):
                found.append(h)
        win32gui.EnumWindows(cb, None)
        return found

    def _wait_main(self, timeout: float):
        end = time.time() + timeout
        while time.time() < end:
            if self.proc.poll() is not None:
                raise RuntimeError("Machine Expert - Basic exited during start-up")
            for h in self.tops():
                if win32gui.GetWindowText(h).endswith(TITLE_SUFFIX):
                    window = self.desktop.window(handle=h)
                    if any(c.element_info.automation_id == "Open"
                           for c in window.descendants(control_type="Button")):
                        return window
            time.sleep(1)
        raise TimeoutError("Machine Expert - Basic main window did not appear")

    def title(self) -> str:
        return self.main.window_text()

    def advisories(self) -> list[tuple[object, list[str]]]:
        out = []
        for h in self.tops():
            if win32gui.GetWindowText(h) == "Advisory":
                w = self.desktop.window(handle=h)
                out.append((w, [t.window_text() for t in w.descendants(control_type="Text") if t.window_text()]))
        return out

    def answer(self, button_id: str) -> list[str]:
        for w, texts in self.advisories():
            for b in w.descendants(control_type="Button"):
                if b.element_info.automation_id == button_id and b.is_visible():
                    _invoke_async(b)
                    time.sleep(1.5)
                    return texts
        return []

    # project -------------------------------------------------------------
    def open_project(self, path: str) -> None:
        name = os.path.splitext(os.path.basename(path))[0]
        button = [b for b in self.main.descendants(control_type="Button") if b.element_info.automation_id == "Open"][0]
        _invoke_async(button)
        app = Application(backend="win32").connect(process=self.pid)
        dialog = None
        for _ in range(40):
            dialog = app.window(title="Open", class_name="#32770")
            if dialog.exists():
                break
            time.sleep(0.5)
        else:
            raise RuntimeError("Open dialog did not appear")
        dialog.child_window(class_name="Edit", found_index=0).set_edit_text(path)
        dialog.send_message(win32con.WM_COMMAND, 1, 0)  # IDOK
        end = time.time() + 90
        while time.time() < end:
            if self.title().startswith(name + " - ") or self.title().startswith(name + "* - "):
                time.sleep(3)
                return
            for _, texts in self.advisories():
                raise RuntimeError("opening the project raised: " + " | ".join(texts))
            time.sleep(1)
        raise TimeoutError(f"project {name} did not open (title {self.title()!r})")

    def programming(self):
        tab = [t for t in self.main.descendants(control_type="TabItem") if t.window_text() == "Programming"][0]
        tab.select()
        time.sleep(3)
        container = [c for c in self.main.children() if c.element_info.automation_id == "container"][0]
        return [c for c in container.children() if c.is_visible()][0]

    def status(self) -> str:
        for c in self.main.children():
            if c.element_info.class_name == "ShellControllerControl":
                for t in c.descendants(control_type="Text"):
                    if t.window_text() in STATUS_TEXTS:
                        return t.window_text()
        return ""

    def compile(self) -> str:
        buttons = [b for b in self.main.descendants(control_type="Button") if _help(b) == "Compile Program"]
        if not buttons:
            raise RuntimeError("Compile Program button not found")
        _invoke_async(buttons[0])
        time.sleep(5)
        return self.status()

    def save(self) -> None:
        save = [b for b in self.main.descendants(control_type="Button")
                if b.window_text() == "Save" and b.element_info.automation_id == "PrimaryFunctionButton"][0]
        _invoke_async(save)
        for _ in range(30):
            time.sleep(1)
            if "*" not in self.title().split(" - ")[0]:
                return
        raise TimeoutError("project was not saved")

    # rungs ---------------------------------------------------------------
    def _pixels(self):
        hwnd = self.main.handle
        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        hdc = win32gui.GetWindowDC(hwnd)
        mdc = win32ui.CreateDCFromHandle(hdc)
        sdc = mdc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mdc, width, height)
        sdc.SelectObject(bmp)
        ctypes.windll.user32.PrintWindow(hwnd, sdc.GetSafeHdc(), 2)
        data = bmp.GetBitmapBits(True)
        sdc.DeleteDC()
        mdc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hdc)
        win32gui.DeleteObject(bmp.GetHandle())

        def pixel(x: int, y: int):
            x, y = x - left, y - top
            if not (0 <= x < width and 0 <= y < height):
                return None
            i = (y * width + x) * 4
            return data[i + 2], data[i + 1], data[i]
        return pixel

    @staticmethod
    def _rung_controls(task):
        return [c for c in task.descendants(control_type="Custom")
                if c.element_info.automation_id == "RungControlName"]

    @staticmethod
    def _rung_index(rung) -> int | None:
        for t in rung.children(control_type="Text"):
            if t.window_text().startswith("Rung") and t.window_text()[4:].isdigit():
                return int(t.window_text()[4:])
        return None

    def _scroller(self, task):
        panes = [p for p in task.descendants(control_type="Pane") if p.element_info.automation_id == "ScrollViewerRung"]
        return panes[0].iface_scroll if panes else None

    def _sweep(self, task, visit) -> None:
        scroll = self._scroller(task)
        for percent in range(0, 101, 10):
            if scroll is not None:
                try:
                    scroll.SetScrollPercent(-1, float(percent))
                except Exception:
                    pass
            time.sleep(1.2)
            visit()
            if scroll is None:
                break

    def read_rungs(self, task) -> tuple[dict[int, dict], list[dict]]:
        rungs: dict[int, dict] = {}
        errors: list[dict] = []
        flagged: set[tuple[int, int]] = set()

        def visit():
            pixel = self._pixels()
            for rung in self._rung_controls(task):
                index = self._rung_index(rung)
                if index is None:
                    continue
                language = [c for c in rung.children(control_type="ComboBox")
                            if c.element_info.automation_id == "languageCombo"]
                entry = rungs.setdefault(index, {"language": None, "il": {}})
                if language:
                    try:
                        entry["language"] = language[0].selected_text()
                    except Exception:
                        pass
                for line in rung.descendants(control_type="Custom"):
                    if line.element_info.automation_id != "IlLineControl":
                        continue
                    texts = line.descendants(control_type="Text")
                    numbers = [t for t in texts if t.window_text().isdigit()]
                    if not numbers or numbers[0].rectangle().width() == 0:
                        continue
                    number = int(numbers[0].window_text())
                    words = [t.window_text().strip() for t in texts[1:4]
                             if t.window_text().strip() and t.window_text() != "Comment"]
                    entry["il"][number] = " ".join(words)
                    box = numbers[0].rectangle()
                    colour = pixel(box.left + 1, box.top + 1)
                    if colour and colour[0] > 200 and colour[1] < 80 and colour[2] < 80 and (index, number) not in flagged:
                        flagged.add((index, number))
                        errors.append({"rung": index, "line": number, "il": entry["il"][number]})
        self._sweep(task, visit)
        return rungs, errors

    def to_ladder(self, task) -> dict[int, str]:
        result: dict[int, str] = {}

        def visit():
            for rung in self._rung_controls(task):
                index = self._rung_index(rung)
                if index is None or index in result:
                    continue
                combo = [c for c in rung.children(control_type="ComboBox")
                         if c.element_info.automation_id == "languageCombo"]
                if not combo or combo[0].rectangle().height() <= 0:
                    continue
                combo = combo[0]
                if combo.selected_text() != "LD":
                    combo.expand()
                    time.sleep(0.6)
                    for item in combo.descendants(control_type="ListItem"):
                        if item.window_text() == "LD":
                            item.select()
                    time.sleep(2)
                    try:
                        combo.collapse()
                    except Exception:
                        pass
                result[index] = combo.selected_text()
        # the rung list re-lays out after each conversion, so sweep until nothing changes
        for _ in range(3):
            before = len(result)
            self._sweep(task, visit)
            if len(result) == before:
                break
        return result

    def close(self, save: bool) -> None:
        if self.proc.poll() is not None:
            return
        try:
            button = [b for b in self.main.children(control_type="Button")
                      if b.element_info.automation_id == "PART_CloseButton"][0]
            _invoke_async(button)
            answered = 0
            end = time.time() + 30
            while time.time() < end and self.proc.poll() is None:
                time.sleep(1)
                for w, texts in self.advisories():
                    # first prompt: "Do you really want to close the application ?" -> Yes;
                    # a later Yes/No prompt is the save question
                    want = "PART_YesButton" if (answered == 0 or save) else "PART_NoButton"
                    ids = {b.element_info.automation_id: b for b in w.descendants(control_type="Button") if b.is_visible()}
                    if want not in ids:
                        want = "PART_OKButton" if "PART_OKButton" in ids else next(iter(ids))
                    _invoke_async(ids[want])
                    answered += 1
                    time.sleep(1.5)
                if not self.tops():
                    break
            for _ in range(20):
                if self.proc.poll() is not None:
                    return
                time.sleep(1)
        finally:
            if self.proc.poll() is None:
                # our own process, windows already gone (it lingers on shutdown)
                subprocess.run(["taskkill", "/PID", str(self.pid), "/F"], capture_output=True)


def run(job: dict) -> dict:
    path = os.path.abspath(job["path"])
    if not os.path.exists(path):
        return {"ok": False, "error": f"{path} does not exist"}
    exe = job.get("exe") or DEFAULT_EXE
    me = MachineExpert(exe)
    result: dict = {"path": path}
    try:
        me.open_project(path)
        task = me.programming()
        # compile and read the IL view first (red line numbers mark invalid IL lines)
        result["status"] = me.compile()
        rungs, errors = me.read_rungs(task)
        result["ui_il"] = [[rungs[i]["il"][n] for n in sorted(rungs[i]["il"])] for i in sorted(rungs)]
        result["error_lines"] = errors
        result["error_count"] = len(errors) or (1 if result["status"] == STATUS_TEXTS[1] else 0)
        result["advisory"] = result["status"] == STATUS_TEXTS[2]
        result["ok"] = result["status"] in (STATUS_TEXTS[0], STATUS_TEXTS[2]) and not errors
        if job.get("to_ladder") and result["ok"]:
            result["languages"] = {str(k): v for k, v in sorted(me.to_ladder(task).items())}
            result["status_after_ladder"] = me.compile()
            result["ok"] = result["status_after_ladder"] in (STATUS_TEXTS[0], STATUS_TEXTS[2]) and all(
                v == "LD" for v in result["languages"].values())
        if job.get("save") and result["ok"]:
            me.save()
            result["saved"] = True
    except Exception as error:  # report, then still close our instance
        result.update({"ok": False, "error": f"{type(error).__name__}: {error}"})
    finally:
        me.close(save=False)
    return result


def main() -> int:
    with open(sys.argv[1], encoding="utf-8") as f:
        job = json.load(f)
    if job.get("op") != "compile":
        print(json.dumps({"ok": False, "error": f"unknown op {job.get('op')!r}"}))
        return 0
    print(json.dumps(run(job), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
