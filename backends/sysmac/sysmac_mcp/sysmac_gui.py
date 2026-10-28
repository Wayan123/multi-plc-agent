"""Drive Omron Sysmac Studio 1.47 (WPF) through UI Automation.

Run with a Windows Python that has pywinauto + pywin32:
    python sysmac_gui.py job.json        -> prints one JSON line

Ops: {"op": "import", "xml": path, "program": name, "project_name"?, "device"?}  replace/add one program
     {"op": "build"}                                                             check + build, counts
     {"op": "read", "program": name}                                             save, stored listing

Notes proven on 1.47:
- SysmacStudio.exe restarts itself elevated through UAC unless started with "-elevate"
  (App.NeedsUserAccessControl returns false then). An elevated instance is unreachable for
  UIA/input from a normal process (UIPI), so this driver starts and only talks to a
  non-elevated instance it can see.
- Everything goes through UIA patterns, win32 tree messages or WM_SETTEXT/WM_COMMAND on the
  common file dialog. No global mouse or keyboard input is used.
- After File > Save the project lives in C:\\OMRON\\Data\\Solution\\<id>\\; each ladder section is
  a JSON listing file that is returned for read-back.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.simplefilter("ignore")
import win32con  # noqa: E402
import win32gui  # noqa: E402
import win32process  # noqa: E402
from pywinauto import Desktop  # noqa: E402
from pywinauto.controls.common_controls import TreeViewWrapper  # noqa: E402
from pywinauto.uia_defines import IUIA  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ladder import program_entity_pattern  # noqa: E402  (driver runs as a script, not as a package)

DEFAULT_EXE = r"C:\Program Files\OMRON\Sysmac Studio\SysmacStudio.exe"
SOLUTIONS = Path(r"C:\OMRON\Data\Solution")
IUIA_ = IUIA()
WALKER = IUIA_.iuia.RawViewWalker


class Abort(Exception):
    pass


def _elevated(pid: int) -> bool:
    import win32api
    import win32security
    try:
        h = win32api.OpenProcess(0x1000, False, pid)
        t = win32security.OpenProcessToken(h, win32con.TOKEN_QUERY)
        return bool(win32security.GetTokenInformation(t, win32security.TokenElevation))
    except Exception:
        return True


def _sysmac_pids() -> list[int]:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq SysmacStudio.exe", "/FO", "CSV", "/NH"],
                         capture_output=True, text=True).stdout
    return [int(line.split('","')[1]) for line in out.splitlines() if line.startswith('"')]


class Sysmac:
    def __init__(self, exe: str):
        self.exe = exe
        self.pid = self._attach_or_start()

    # --- process / window ------------------------------------------------------
    def _usable(self) -> list[int]:
        found = []
        for pid in _sysmac_pids():
            if _elevated(pid):
                continue
            if any("Sysmac Studio" in (w.element_info.name or "") for w in Desktop(backend="uia").windows(process=pid)):
                found.append(pid)
        return found

    def _attach_or_start(self) -> int:
        usable = self._usable()
        if usable:
            return usable[0]
        subprocess.Popen([self.exe, "-elevate"])
        end = time.time() + 180
        while time.time() < end:
            time.sleep(3)
            usable = self._usable()
            if usable and self._ready(usable[0]):
                return usable[0]
        raise Abort("Sysmac Studio did not start (or only an elevated instance is running)")

    def _ready(self, pid: int) -> bool:
        for w in Desktop(backend="uia").windows(process=pid):
            if any(d.element_info.automation_id in ("NewProjectToggle", "MainMenu") for d in w.descendants()):
                return True
        return False

    def main(self):
        for _ in range(20):
            for w in Desktop(backend="uia").windows(process=self.pid):
                if "Sysmac Studio" in (w.element_info.name or ""):
                    return w
            time.sleep(0.5)
        raise Abort("Sysmac Studio window not found")

    def find(self, root=None, **kw):
        keys = {"auto": "automation_id", "name": "name", "type": "control_type", "cls": "class_name"}
        for d in [root or self.main()] + (root or self.main()).descendants():
            if all(getattr(d.element_info, keys[k]) == v for k, v in kw.items()):
                return d
        return None

    def menu(self, *path: str) -> None:
        cur = self.main()
        for i, name in enumerate(path):
            items = [d for d in cur.descendants(control_type="MenuItem") if d.element_info.name == name]
            if not items:
                raise Abort(f"menu item {name!r} not found")
            if i < len(path) - 1:
                items[0].expand(); time.sleep(1.0); cur = items[0]
            else:
                if not items[0].is_enabled():
                    raise Abort(f"menu item {name!r} is disabled")
                items[0].invoke()

    def msgbox(self, press: str | None = None):
        for d in self.main().children():
            if d.element_info.control_type == "Window" and d.element_info.automation_id == "MessageBoxView":
                text = "\n".join(p.element_info.name for p in d.descendants(control_type="Pane") if p.element_info.name)
                buttons = d.descendants(control_type="Button")
                if press:
                    for b in buttons:
                        if b.element_info.name == press:
                            b.invoke(); break
                return text, [b.element_info.name for b in buttons if b.element_info.name]
        return None

    def wait_msgbox(self, timeout: float = 120):
        end = time.time() + timeout
        while time.time() < end:
            mb = self.msgbox()
            if mb:
                return mb
            time.sleep(1)
        return None

    # --- project ---------------------------------------------------------------
    def project_open(self) -> bool:
        return self.find(auto="MainMenu") is not None and self.find(auto="SolutionTreeView") is not None

    def new_project(self, name: str, device: str) -> None:
        family, _, model = device.partition("-")
        toggle = self.find(auto="NewProjectToggle")
        if toggle is None:
            raise Abort("start page not shown; close the open project first")
        toggle.select(); time.sleep(2)
        props = self.find(cls="SolutionPropertiesView")
        [c for c in props.children() if c.element_info.control_type == "Edit"][0].set_edit_text(name)
        view = self.find(cls="InsertDeviceView")

        def combos():
            return [c for c in view.children() if c.element_info.control_type == "ComboBox"]
        for _ in range(5):
            combos()[1].select(family); time.sleep(1.5)
            if model:
                combos()[2].select(model); time.sleep(1)
            got = [combos()[1].selected_text(), combos()[2].selected_text()]
            if got[0] == family and (not model or got[1] == model):
                break
        else:
            raise Abort(f"could not select device {device!r} (combo shows {got})")
        self.find(auto="CreateButton").invoke()
        end = time.time() + 180
        while time.time() < end and not self.project_open():
            time.sleep(2)
        if not self.project_open():
            raise Abort("project was not created")
        time.sleep(5)

    def tree(self):
        t = self.find(auto="SolutionTreeView")
        tv = TreeViewWrapper(t.element_info.handle)
        out = []

        def walk(it, path):
            p = path + [it.text().strip()]
            out.append(("/".join(p), it))
            for c in it.children():
                walk(c, p)
        for r in tv.roots():
            walk(r, [])
        return out

    def programs(self) -> list[str]:
        pre = "Programming/POUs/Programs/"
        return [p[len(pre):] for p, _ in self.tree() if p.startswith(pre) and "/" not in p[len(pre):]]

    def delete_program(self, name: str) -> None:
        for p, it in self.tree():
            if p == "Programming/POUs/Programs/" + name:
                it.select(); time.sleep(0.5)
                self.menu("Edit", "Delete")
                mb = self.wait_msgbox(10)
                if not mb or "delete" not in mb[0].lower():
                    raise Abort(f"unexpected prompt deleting {name}: {mb}")
                self.msgbox("Yes"); time.sleep(2)
                return

    def save(self) -> None:
        f = [d for d in self.main().descendants(control_type="MenuItem") if d.element_info.automation_id == "_File"][0]
        f.expand(); time.sleep(1.2)
        [d for d in f.descendants(control_type="MenuItem") if d.element_info.name == "Save"][0].invoke()
        time.sleep(6)

    def file_dialog(self, path: str, timeout: float = 15) -> None:
        end = time.time() + timeout
        dlg = None
        while time.time() < end and not dlg:
            found = []
            win32gui.EnumWindows(lambda h, _: found.append(h) if win32gui.GetClassName(h) == "#32770" and win32gui.IsWindowVisible(h)
                                 and win32process.GetWindowThreadProcessId(h)[1] == self.pid else None, None)
            dlg = found[0] if found else None
            time.sleep(0.3)
        if not dlg:
            raise Abort("file dialog not found")
        edits = []
        win32gui.EnumChildWindows(dlg, lambda h, _: edits.append(h) if win32gui.GetClassName(h) == "Edit" else None, None)
        target = next((h for h in edits if 1148 in (win32gui.GetDlgCtrlID(win32gui.GetParent(win32gui.GetParent(h))),
                                                     win32gui.GetDlgCtrlID(win32gui.GetParent(h))) or win32gui.GetDlgCtrlID(h) == 1152), edits[0])
        win32gui.SendMessage(target, win32con.WM_SETTEXT, 0, path)
        time.sleep(0.3)
        win32gui.SendMessage(dlg, win32con.WM_COMMAND, 1, win32gui.GetDlgItem(dlg, 1))
        time.sleep(1.5)

    # --- output / build panes ---------------------------------------------------
    def _pane(self, auto: str):
        return self.main().element_info.element.FindFirst(4, IUIA_.iuia.CreatePropertyCondition(30011, auto))

    def _container(self):
        return WALKER.GetParentElement(self._pane("buildWindowsViewWindow"))

    def _raw(self, elem, depth: int = 12):
        out = []

        def walk(e, lvl):
            try:
                out.append((lvl, e.CurrentLocalizedControlType, e.CurrentName or ""))
            except Exception:
                return
            if lvl < depth:
                c = WALKER.GetFirstChildElement(e)
                while c:
                    walk(c, lvl + 1); c = WALKER.GetNextSiblingElement(c)
        walk(elem, 0)
        return out

    def _select_tab(self, auto: str) -> None:
        import comtypes.gen.UIAutomationClient as UIA
        self._pane(auto).GetCurrentPattern(10010).QueryInterface(UIA.IUIAutomationSelectionItemPattern).Select()
        time.sleep(1)

    def log_lines(self) -> list[str]:
        # the two tab panes swap content in the UIA tree; pick the one holding the log list
        for tab in ("buildWindowsViewWindow", "outputWindowsViewWindow"):
            self._select_tab(tab)
            items = self._raw(self._container())
            if any(t == "list view" for _, t, _ in items):
                return [n for _, t, n in items if t == "text" and n and n != "Title"]
        return []

    def build_messages(self) -> dict:
        for tab in ("outputWindowsViewWindow", "buildWindowsViewWindow"):
            self._select_tab(tab)
            items = self._raw(self._container())
            if any(t == "datagrid" for _, t, _ in items):
                break
        counts = {}
        for i, (_, t, n) in enumerate(items):
            if t == "text" and n in ("Errors", "Warnings") and items[i - 1][1] == "text" and items[i - 1][2].isdigit():
                counts[n.lower()] = int(items[i - 1][2])
        rows, row, lvl = [], None, 0
        for level, t, n in items:
            if t == "dataitem":
                if row is not None:
                    rows.append(row)
                row, lvl = [], level
            elif row is not None and level > lvl and t == "text" and n:
                row.append(n)
            elif row is not None and level <= lvl:
                rows.append(row); row = None
        if row is not None:
            rows.append(row)
        messages = [{"description": r[1], "program": r[2], "location": r[3]} for r in rows if len(r) >= 4]
        return {"errors": counts.get("errors"), "warnings": counts.get("warnings"), "messages": messages}

    # --- operations ------------------------------------------------------------
    def xml_import(self, path: str) -> dict:
        self.menu("Tools", "IEC 61131-10 XML", "Import...")
        dlg = None
        for _ in range(30):
            mb = self.msgbox()
            if mb and "saved" in mb[0]:
                self.msgbox("Yes"); time.sleep(4)
            dlg = next((d for d in self.main().children() if d.element_info.name == "IEC 61131-10 XML Import"), None)
            if dlg:
                break
            time.sleep(0.5)
        if dlg is None:
            raise Abort("IEC 61131-10 XML Import dialog did not open")
        self.find(dlg, auto="FilePathArea_ShowSelectFileDialogButton").invoke()
        self.file_dialog(path)
        shown = self.find(dlg, auto="FilePathArea_FilePath").get_value()
        if Path(shown).name != Path(path).name:
            raise Abort(f"file dialog did not select {path} (shows {shown!r})")
        self.find(dlg, auto="OkButton").invoke()
        mb = self.wait_msgbox(180)
        if mb is None:
            raise Abort("import did not finish")
        text = mb[0]
        if "completed" in text or "failed" in text:
            self.msgbox("OK")
        else:
            raise Abort(f"unexpected prompt during import: {mb}")
        time.sleep(1)
        log = self.log_lines()
        start = max((i for i, s in enumerate(log) if s.startswith("IEC 61131-10 XML Import started")), default=0)
        return {"imported": "completed" in text, "message": text.replace("\r", ""), "log": log[start:]}

    def build(self) -> dict:
        self.menu("Project", "Check All Programs"); time.sleep(10)
        result = self.build_messages()
        if result["errors"] == 0:
            self.menu("Project", "Build Controller"); time.sleep(15)
            result = self.build_messages()
        result["ok"] = result["errors"] == 0
        return result

    def solution_dir(self, program: str) -> Path:
        dirs = sorted((p for p in SOLUTIONS.iterdir() if (p / f"{p.name}.oem").exists()),
                      key=lambda p: (p / f"{p.name}.oem").stat().st_mtime, reverse=True)
        tag = program_entity_pattern(program)
        for d in dirs:
            if tag.search((d / f"{d.name}.oem").read_text(encoding="utf-8-sig")):
                return d
        raise Abort(f"program {program!r} not found in any saved solution under {SOLUTIONS}")

    def read(self, program: str) -> dict:
        self.save()
        d = self.solution_dir(program)
        oem = (d / f"{d.name}.oem").read_text(encoding="utf-8-sig")
        i = program_entity_pattern(program).search(oem).start()
        nxt = re.search(r'<Entity type="(Program|Group)" subtype=', oem[i + 1:])
        seg = oem[i: i + 1 + nxt.start()] if nxt else oem[i:]
        sections = []
        for m in re.finditer(r'type="PouBody" subtype="Ladder" id="([0-9a-f-]+)" name="([^"]*)"', seg):
            sections.append({"name": m.group(2), "listing": (d / f"{m.group(1)}.xml").read_text(encoding="utf-8-sig")})
        var = re.search(r'type="Variables" subtype="Ladder" id="([0-9a-f-]+)"', seg)
        variables = (d / f"{var.group(1)}.xml").read_text(encoding="utf-8-sig") if var else ""
        return {"solution_dir": str(d), "sections": sections, "variables_text": variables}


def run(job: dict) -> dict:
    sm = Sysmac(job.get("exe") or DEFAULT_EXE)
    op = job["op"]
    if op == "import":
        created = False
        if not sm.project_open():
            sm.new_project(job.get("project_name") or job["program"], job.get("device") or "NX1P2-1040DT")
            created = True
        replaced = job["program"] in sm.programs()
        if replaced:
            sm.delete_program(job["program"])
        res = sm.xml_import(job["xml"])
        res.update({"created_project": created, "replaced_program": replaced, "programs": sm.programs()})
        if res["imported"]:
            res["build"] = sm.build()
            res.update(sm.read(job["program"]))
        res["ok"] = bool(res["imported"] and res.get("build", {}).get("ok"))
        return res
    if op == "build":
        return sm.build()
    if op == "read":
        return {"ok": True, **sm.read(job["program"])}
    raise Abort(f"unknown op {op}")


def main() -> int:
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    try:
        result = run(job)
    except Abort as e:
        result = {"ok": False, "error": str(e)}
    except Exception as e:  # report driver crashes as data for the server
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
