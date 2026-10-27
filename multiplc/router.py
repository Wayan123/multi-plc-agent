"""MCP stdio router that exposes several vendor PLC servers as one server."""
from __future__ import annotations

import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, TextIO

from . import __version__
from .backend import Backend, BackendError, BackendRPCError, BackendSpec

PROTOCOL_VERSION = "2025-06-18"
LIST_TOOL = "list_plc_backends"

INSTRUCTIONS = (
    "multi-plc-agent routes to one MCP server per PLC engineering tool. Tool names start with the "
    "vendor prefix (mitsubishi_, siemens_, omron_). Call list_plc_backends first to see which "
    "backends started, their software and how many tools each exposes. Each backend keeps its own "
    "safety rules and approval flow; its instructions apply to its tools. Tools that act on a live "
    "PLC or delete project content are not exposed. Generated logic is not a substitute for "
    "hardware safety functions and must be reviewed and tested before use on equipment."
)


class Router:
    def __init__(self, specs: list[BackendSpec]):
        self.backends = [Backend(spec) for spec in specs]
        self._routes: dict[str, tuple[Backend, str]] = {}
        self._tools: list[dict[str, Any]] = []

    # -- lifecycle -------------------------------------------------------
    def start(self, client_info: dict[str, Any]) -> None:
        def launch(backend: Backend) -> None:
            try:
                backend.start(PROTOCOL_VERSION, client_info)
            except BackendError as error:
                backend.error = str(error)
                backend.stop()
        with ThreadPoolExecutor(max_workers=max(1, len(self.backends))) as pool:
            list(pool.map(launch, self.backends))
        self._index()

    def stop(self) -> None:
        for backend in self.backends:
            backend.stop()

    def _index(self) -> None:
        routes: dict[str, tuple[Backend, str]] = {}
        tools: list[dict[str, Any]] = [{
            "name": LIST_TOOL,
            "description": "List configured PLC backends: vendor, software, start status, server identity and exposed tool count.",
            "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
        }]
        for backend in self.backends:
            if backend.error:
                continue
            for tool in backend.tools:
                original = tool["name"]
                if original in backend.spec.deny:
                    continue
                name = backend.spec.prefix + original
                routes[name] = (backend, original)
                exposed = dict(tool)
                exposed["name"] = name
                exposed["description"] = f"[{backend.spec.vendor} · {backend.spec.software or backend.spec.name}] " + str(tool.get("description", ""))
                tools.append(exposed)
        self._routes, self._tools = routes, tools

    # -- MCP methods -----------------------------------------------------
    def list_tools(self) -> dict[str, Any]:
        return {"tools": self._tools}

    def backend_status(self) -> dict[str, Any]:
        rows = []
        for backend in self.backends:
            exposed = sum(1 for _, (owner, _) in self._routes.items() if owner is backend)
            rows.append({
                "name": backend.spec.name,
                "vendor": backend.spec.vendor,
                "software": backend.spec.software,
                "prefix": backend.spec.prefix,
                "status": "error" if backend.error else ("running" if backend.running else "stopped"),
                "error": backend.error,
                "server_info": backend.server_info,
                "tools_exposed": exposed,
                "tools_denied": sorted(backend.spec.deny & {t["name"] for t in backend.tools}),
                "stderr_tail": backend.stderr_tail()[-5:] if backend.error else [],
            })
        return {"backends": rows}

    def call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == LIST_TOOL:
            return _text_result(self.backend_status())
        route = self._routes.get(name)
        if route is None:
            return _text_result({"error": f"unknown tool {name!r}; call {LIST_TOOL}"}, is_error=True)
        backend, original = route
        if original in backend.spec.proxy_tools:
            inner = arguments.get("name")
            if inner in backend.spec.deny:
                return _text_result({"error": f"{inner!r} is not exposed through multi-plc-agent"}, is_error=True)
        try:
            return backend.request("tools/call", {"name": original, "arguments": arguments})
        except BackendRPCError:
            raise
        except BackendError as error:
            return _text_result({"error": str(error), "backend": backend.spec.name,
                                 "stderr_tail": backend.stderr_tail()[-5:]}, is_error=True)


def _text_result(payload: Any, is_error: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}]}
    if is_error:
        result["isError"] = True
    return result


class StdioServer:
    """Line-delimited JSON-RPC over stdin/stdout, one thread per tool call."""

    def __init__(self, router: Router, stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout):
        self.router = router
        self.stdin = stdin
        self.stdout = stdout
        self._write_lock = threading.Lock()
        self._started = False

    def write(self, message: dict[str, Any]) -> None:
        with self._write_lock:
            self.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
            self.stdout.flush()

    def serve(self) -> None:
        workers: list[threading.Thread] = []
        try:
            for line in self.stdin:
                line = line.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except ValueError:
                    self.write({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}})
                    continue
                if "id" not in message:
                    continue  # notifications (initialized, cancelled) need no reply
                if message.get("method") == "tools/call":
                    worker = threading.Thread(target=self._handle, args=(message,), daemon=True)
                    worker.start()
                    workers = [w for w in workers if w.is_alive()] + [worker]
                else:
                    self._handle(message)
            # stdin closed: let in-flight calls reply before backends stop.
            for worker in workers:
                worker.join()
        finally:
            self.router.stop()

    def _handle(self, message: dict[str, Any]) -> None:
        request_id = message["id"]
        method = message.get("method")
        params = message.get("params") or {}
        try:
            if method == "initialize":
                if not self._started:
                    self.router.start({"name": "multi-plc-agent", "version": __version__})
                    self._started = True
                result: dict[str, Any] = {
                    "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "multi-plc-agent", "version": __version__},
                    "instructions": INSTRUCTIONS,
                }
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = self.router.list_tools()
            elif method == "tools/call":
                result = self.router.call_tool(params)
            else:
                self.write({"jsonrpc": "2.0", "id": request_id,
                            "error": {"code": -32601, "message": f"method not found: {method}"}})
                return
            self.write({"jsonrpc": "2.0", "id": request_id, "result": result})
        except BackendRPCError as error:
            self.write({"jsonrpc": "2.0", "id": request_id, "error": error.rpc_error})
        except Exception as error:  # report, never crash the stdio loop
            self.write({"jsonrpc": "2.0", "id": request_id,
                        "error": {"code": -32603, "message": f"{type(error).__name__}: {error}"}})
