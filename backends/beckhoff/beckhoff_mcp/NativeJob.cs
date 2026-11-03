using System;
using System.IO;
using System.Collections.Generic;
using Process = System.Diagnostics.Process;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text.RegularExpressions;
using System.Threading;
using System.Web.Script.Serialization;
using EnvDTE;
using EnvDTE80;
using TCatSysManagerLib;

// Compiled locally against the operator's installed public SDK. No vendor binary is bundled.
internal static class NativeJob
{
    private static string assemblies;
    private static readonly JavaScriptSerializer Json = new JavaScriptSerializer();
    [DllImport("user32.dll")] private static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);

    [STAThread]
    private static int Main(string[] args)
    {
        Console.OutputEncoding = new System.Text.UTF8Encoding(false);
        var job = Json.Deserialize<Dictionary<string, object>>(File.ReadAllText(args[0]));
        assemblies = (string)job["public_assemblies"];
        AppDomain.CurrentDomain.AssemblyResolve += Resolve;
        return Run(job);
    }

    private static int Run(Dictionary<string, object> job)
    {
        var result = new Dictionary<string, object> { {"ok", false}, {"online_operations", 0} };
        DTE2 dte = null;
        Process ownedHost = null;
        System.Threading.Timer deadline = null;
        bool timedOut = false;
        try
        {
            var before = new HashSet<int>();
            foreach (Process process in Process.GetProcesses()) { before.Add(process.Id); process.Dispose(); }
            dte = (DTE2)Activator.CreateInstance(Type.GetTypeFromProgID("TcXaeShell.DTE.17.0", true));
            DateTime end = DateTime.UtcNow.AddSeconds(45);
            IntPtr hwnd;
            while (true)
            {
                try { hwnd = dte.MainWindow.HWnd; break; }
                catch (COMException) { if (DateTime.UtcNow >= end) throw; System.Threading.Thread.Sleep(100); }
            }
            uint pid; GetWindowThreadProcessId(hwnd, out pid);
            if (before.Contains((int)pid)) { dte = null; throw new InvalidOperationException("COM did not create a fresh host; refusing to attach"); }
            ownedHost = Process.GetProcessById((int)pid);
            IntPtr heldHandle = ownedHost.Handle;
            result["host"] = new Dictionary<string, object> {
                {"pid", pid}, {"hwnd", hwnd.ToInt64()}, {"start_time_utc", ownedHost.StartTime.ToUniversalTime().ToString("o")},
                {"executable", ownedHost.MainModule.FileName}, {"progid", "TcXaeShell.DTE.17.0"}
            };
            deadline = new System.Threading.Timer(delegate {
                timedOut = true;
                try { if (!ownedHost.HasExited) ownedHost.Kill(); } catch (InvalidOperationException) { }
            }, null, 150000, System.Threading.Timeout.Infinite);
            dte.SuppressUI = true;
            dte.UserControl = false;
            dte.MainWindow.Visible = true;
            if (dte.Solution.IsOpen) throw new InvalidOperationException("Fresh host unexpectedly has an open solution");
            Execute(dte, job, result);
        }
        catch (Exception error)
        {
            result["ok"] = false;
            result["error"] = error.GetType().Name + ": " + error.Message;
            result["hresult"] = "0x" + error.HResult.ToString("X8");
        }
        finally
        {
            if (deadline != null) deadline.Dispose();
            if (dte != null)
            {
                try { dte.Quit(); result["quit_returned"] = true; }
                catch (Exception error) { result["close_error"] = error.Message; result["ok"] = false; }
                Marshal.FinalReleaseComObject(dte);
                dte = null;
            }
            GC.Collect(); GC.WaitForPendingFinalizers();
            if (ownedHost != null)
            {
                bool exited = ownedHost.WaitForExit(10000);
                result["owned_host_exited"] = exited;
                if (!exited) { result["ok"] = false; result["cleanup_error"] = "Owned native host did not exit after Quit"; }
                ownedHost.Dispose();
            }
            result["timed_out"] = timedOut;
            if (timedOut) result["ok"] = false;
            string output = Json.Serialize(result);
            if (job != null) File.WriteAllText((string)job["result_path"], output);
        }
        return (bool)result["ok"] ? 0 : 1;
    }

    private static Assembly Resolve(object sender, ResolveEventArgs args)
    {
        string name = new AssemblyName(args.Name).Name;
        if (name != "EnvDTE" && name != "EnvDTE80" && name != "Microsoft.VisualStudio.Interop") return null;
        return Assembly.LoadFrom(Path.Combine(assemblies, name + ".dll"));
    }

    private static bool RemoveMain(ITcSmTreeItem parent)
    {
        int childCount = parent.ChildCount;
        for (int i = 1; i <= childCount; i++)
        {
            ITcSmTreeItem child = parent.Child[i];
            if (child.ItemType == 602 && child.Name == "MAIN") { parent.DeleteChild(child.Name); return true; }
            if (child.ItemType == 601 && RemoveMain(child)) return true;
        }
        return false;
    }

    private static void Execute(DTE2 dte, Dictionary<string, object> job, Dictionary<string, object> result)
    {
        string operation = (string)job["op"];
        if (operation != "write" && operation != "build" && operation != "export") throw new ArgumentException("Unsupported offline operation");
        string solution = (string)job["solution"];
        result["solution"] = solution;
        Project engineering;
        if (operation == "write")
        {
            if (File.Exists(solution)) throw new IOException("Native writer requires a fresh destination");
            dte.Solution.Create(Path.GetDirectoryName(solution), Path.GetFileNameWithoutExtension(solution));
            engineering = dte.Solution.AddFromTemplate((string)job["template"], Path.Combine(Path.GetDirectoryName(solution), "Engineering"), "Engineering");
            ITcSysManager created = (ITcSysManager)engineering.Object;
            created.LookupTreeItem("TIPC").CreateChild("AgentPLC", 0, "", "Standard PLC Template");
            ((ITcSysManager7)created).ConfigurationManager.ActiveTargetPlatform = "TwinCAT RT (x64)";
            ITcSmTreeItem iec = created.LookupTreeItem("TIPC^AgentPLC^AgentPLC Project");
            if (!RemoveMain(iec)) throw new InvalidOperationException("Native standard template has no MAIN to replace");
            ((ITcPlcOpenImportExport)iec).PlcOpenImport((string)job["xml_path"], (int)PLCIMPORTOPTIONS.PLCIMPORTOPTIONS_REPLACE, "", true);
            engineering.Save();
            dte.Solution.SaveAs(solution);
            dte.Solution.Close(true);
            dte.Solution.Open(solution);
            result["saved_closed_reopened"] = true;
        }
        else dte.Solution.Open(solution);
        engineering = dte.Solution.Projects.Item(1);
        ITcSysManager manager = (ITcSysManager)engineering.Object;
        var configuration = ((ITcSysManager7)manager).ConfigurationManager;
        result["previous_platform"] = configuration.ActiveTargetPlatform;
        configuration.ActiveTargetPlatform = "TwinCAT RT (x64)";
        string selectedPlatform = configuration.ActiveTargetPlatform;
        result["platform"] = selectedPlatform;
        if (selectedPlatform != "TwinCAT RT (x64)") throw new InvalidOperationException("Owned solution uses an unverified target platform: " + selectedPlatform);
        ITcSmTreeItem project = manager.LookupTreeItem("TIPC^AgentPLC^AgentPLC Project");
        string export = (string)job["export_path"];
        ((ITcPlcOpenImportExport)project).PlcOpenExport(export, "");
        result["export_xml"] = File.ReadAllText(export);
        if (operation == "export") { result["ok"] = true; return; }
        try { ((ITcPlcProject)manager.LookupTreeItem("TIPC^AgentPLC")).CompileProject(); }
        catch (Exception error) { result["plc_compile_error"] = error.Message; }
        SolutionBuild engine = dte.Solution.SolutionBuild;
        engine.Build(true);
        vsBuildState state = engine.BuildState;
        int failedProjects = engine.LastBuildInfo;
        result["build_state"] = state.ToString();
        result["failed_projects"] = failedProjects;
        var diagnostics = new List<object>();
        ErrorItems items = dte.ToolWindows.ErrorList.ErrorItems;
        for (int i = 1; i <= items.Count; i++)
        {
            ErrorItem item = items.Item(i);
            diagnostics.Add(new Dictionary<string, object> { {"level", item.ErrorLevel.ToString()}, {"description", item.Description}, {"file", item.FileName}, {"line", item.Line} });
        }
        result["diagnostics"] = diagnostics;
        string build = "";
        foreach (OutputWindowPane pane in dte.ToolWindows.OutputWindow.OutputWindowPanes)
        {
            if (pane.Name != "Build") continue;
            TextDocument document = pane.TextDocument;
            build = document.StartPoint.CreateEditPoint().GetText(document.EndPoint);
        }
        result["native_build_output"] = build;
        Match counts = Regex.Match(build, @"Build complete -- (\d+) errors, (\d+) warnings");
        int? errors = counts.Success ? (int?)Int32.Parse(counts.Groups[1].Value) : null;
        int? warnings = counts.Success ? (int?)Int32.Parse(counts.Groups[2].Value) : null;
        result["errors"] = errors;
        result["warnings"] = warnings;
        bool platform = build.Contains("TwinCAT RT (x64)");
        result["platform_matches"] = platform;
        result["ok"] = errors == 0
            && failedProjects == 0
            && state == vsBuildState.vsBuildStateDone
            && !result.ContainsKey("plc_compile_error") && platform;
    }
}
