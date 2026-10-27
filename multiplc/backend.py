"""Stdio JSON-RPC client for one vendor MCP server."""
from __future__ import annotations

import collections
import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass, field
from typing import Any


class BackendError(RuntimeError):
    """The backend could not be started or did not answer a request."""


@dataclass(frozen=True)
class BackendSpec:
    name: str
    prefix: str
    vendor: str
    software: str
    command: str
    args: tuple[str, ...] = ()
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    deny: frozenset[str] = frozenset()
    # Tools that dispatch to another tool named in arguments["name"]
    # (for example TIA's CallTool). The inner name is checked against deny.
    proxy_tools: frozenset[str] = frozenset()
    timeout_s: float = 600.0
    start_timeout_s: float = 180.0


class Backend:
    """One child MCP server reached over stdio.

    Requests may be issued from several threads; responses are matched by id.
    Requests the child sends to us are answered (ping) or refused, so the
    child never waits on a reply that will not come.
    """

    def __init__(self, spec: BackendSpec):
        self.spec = spec
        self.tools: list[dict[str, Any]] = []
        self.server_info: dict[str, Any] | None = None
        self.error: str | None = None
        self._process: subprocess.Popen[bytes] | None = None
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._next_id = 0
        self._stderr: collections.deque[str] = collections.deque(maxlen=40)

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def stderr_tail(self) -> list[str]:
        return list(self._stderr)

    def start(self, protocol_version: str, client_info: dict[str, Any]) -> None:
        env = {**os.environ, **self.spec.env}
        try:
            self._process = subprocess.Popen(
                [self.spec.command, *self.spec.args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.spec.cwd or None,
                env=env,
            )
        except OSError as error:
            raise BackendError(f"cannot start {self.spec.command}: {error}") from error
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        result = self.request(
            "initialize",
            {"protocolVersion": protocol_version, "capabilities": {}, "clientInfo": client_info},
            timeout=self.spec.start_timeout_s,
        )
        self.server_info = result.get("serverInfo")
        self.notify("notifications/initialized")
        tools: list[dict[str, Any]] = []
        cursor = None
        while True:
            page = self.request("tools/list", {"cursor": cursor} if cursor else {}, timeout=self.spec.start_timeout_s)
            tools.extend(page.get("tools", []))
            cursor = page.get("nextCursor")
            if not cursor:
                break
        self.tools = tools

    def stop(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.stdin.close()
            process.wait(timeout=5)
        except Exception:
            process.kill()

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        message: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        self._send(message)

    def request(self, method: str, params: dict[str, Any], timeout: float | None = None) -> dict[str, Any]:
        """Return the result object; raise BackendError on transport failure.

        A JSON-RPC error from the child is raised as BackendRPCError so the
        router can pass the original code and message through.
        """
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            reply: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
            self._pending[request_id] = reply
        try:
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            try:
                message = reply.get(timeout=timeout or self.spec.timeout_s)
            except queue.Empty as error:
                raise BackendError(f"{self.spec.name}: {method} timed out") from error
        finally:
            with self._lock:
                self._pending.pop(request_id, None)
        if "__closed__" in message:
            raise BackendError(f"{self.spec.name}: server exited during {method}")
        if "error" in message:
            raise BackendRPCError(message["error"])
        return message.get("result", {})

    def _send(self, message: dict[str, Any]) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            raise BackendError(f"{self.spec.name}: server is not running")
        data = (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")
        with self._write_lock:
            try:
                process.stdin.write(data)
                process.stdin.flush()
            except OSError as error:
                raise BackendError(f"{self.spec.name}: write failed: {error}") from error

    def _read_stdout(self) -> None:
        process = self._process
        assert process is not None
        for line in process.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except ValueError:
                self._stderr.append("non-JSON stdout: " + line[:200].decode("utf-8", "replace"))
                continue
            if "method" in message:
                if "id" in message:
                    self._answer_child_request(message)
                continue  # notifications from the child are not forwarded
            with self._lock:
                waiter = self._pending.get(message.get("id"))
            if waiter is not None:
                waiter.put(message)
        with self._lock:
            waiters = list(self._pending.values())
        for waiter in waiters:
            waiter.put({"__closed__": True})

    def _answer_child_request(self, message: dict[str, Any]) -> None:
        if message["method"] == "ping":
            reply: dict[str, Any] = {"jsonrpc": "2.0", "id": message["id"], "result": {}}
        else:
            reply = {"jsonrpc": "2.0", "id": message["id"],
                     "error": {"code": -32601, "message": "multi-plc-agent does not serve client requests"}}
        try:
            self._send(reply)
        except BackendError:
            pass

    def _read_stderr(self) -> None:
        process = self._process
        assert process is not None
        for line in process.stderr:
            text = line.decode("utf-8", "replace").rstrip()
            if text:
                self._stderr.append(text)


class BackendRPCError(BackendError):
    def __init__(self, error: dict[str, Any]):
        super().__init__(error.get("message", "backend error"))
        self.rpc_error = error
