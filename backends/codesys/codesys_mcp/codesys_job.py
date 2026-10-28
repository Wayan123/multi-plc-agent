# -*- coding: utf-8 -*-
"""Runs inside CODESYS (ScriptEngine, IronPython 2.7):

    CODESYS.exe --profile="CODESYS V3.5 SP21" --noUI --runscript=codesys_job.py

Reads the job from %CODESYS_MCP_JOB% (a JSON file), writes the result to
<job>.result.json. Ops:
  write   - create (or replace) <project>, add device + Standard library,
            import the PLCopen XML POU, bind it to MainTask, save, build,
            export the POU back
  build   - open <project>, build its Application, report messages
  export  - open <project>, export one POU as PLCopen XML
Only offline engineering: nothing here logs in to or downloads to a PLC.
"""
from __future__ import print_function
import json
import os
import traceback

JOB = os.environ["CODESYS_MCP_JOB"]


def messages():
    found = []
    for cat in system.get_message_categories():
        desc = system.get_message_category_description(cat)
        for m in system.get_message_objects(cat):
            found.append({"category": desc, "severity": str(m.severity), "text": m.text})
    return found


def summary(msgs):
    errors = sum(1 for m in msgs if m["category"] == "Build" and m["severity"] in ("Error", "FatalError"))
    warnings = sum(1 for m in msgs if m["category"] == "Build" and m["severity"] == "Warning")
    done = [m["text"] for m in msgs if m["category"] == "Build" and "Compile complete" in m["text"]]
    return errors, warnings, done


def application(proj):
    apps = proj.find("Application", True)
    if not apps:
        raise RuntimeError("project has no Application object")
    return apps[0]


def build(proj, result):
    # each job runs in a fresh CODESYS process, so the message store holds only this build
    application(proj).build()
    msgs = messages()
    errors, warnings, done = summary(msgs)
    result.update({"error_count": errors, "warning_count": warnings, "compile_line": done[-1] if done else None,
                   "messages": [m for m in msgs if m["category"] in ("Build", "Additional code checks")]})
    result["ok"] = bool(done) and errors == 0


def export(proj, pou, result):
    found = application(proj).find(pou, False)
    if not found:
        raise RuntimeError("POU %s not found" % pou)
    xml = proj.export_xml(objects=found, declarations_as_plaintext=True)
    result["export_xml"] = xml


def run(job):
    result = {"ok": False, "op": job["op"], "project": job["project"]}
    path = job["project"]
    if job["op"] == "write":
        if os.path.exists(path):
            os.remove(path)  # caller made the backup and holds the overwrite decision
        proj = projects.create(path, True)
        dev = job["device"]
        proj.add("Device", int(dev["type"]), dev["id"], dev["version"])
        app = application(proj)
        lm = proj.find("Library Manager", True)[0]
        lm.add_placeholder("Standard", "Standard, * (System)")
        app.import_xml(job["xml_path"])
        if not app.find(job["pou"], False):
            raise RuntimeError("PLCopen import created no POU %s" % job["pou"])
        tc = app.create_task_configuration()
        task = tc.create_task("MainTask")
        task.pous.add(job["pou"])
        proj.save()
        build(proj, result)
        export(proj, job["pou"], result)
        proj.save()
        proj.close()
    elif job["op"] in ("build", "export"):
        proj = projects.open(path)
        if job["op"] == "build":
            build(proj, result)
        else:
            export(proj, job["pou"], result)
            result["ok"] = True
        proj.close()
    else:
        raise RuntimeError("unknown op %s" % job["op"])
    return result


try:
    with open(JOB) as f:
        job = json.load(f)
    out = run(job)
except Exception:
    out = {"ok": False, "error": traceback.format_exc()}
with open(JOB + ".result.json", "w") as f:
    json.dump(out, f)
