"""Probe: drive the REAL Codex CLI 0.169.0 loop with the deterministic stub.

One-shot probe (not the battery): starts the stub Responses-API
server on 127.0.0.1:18094 and the tool bridge on 127.0.0.1:18095,
writes an isolated Codex config (custom model provider "stub" ->
the local Responses API stub; MCP server "trustrun" -> the stdio
MCP server codex_mcp_server.py), and runs one
`codex exec --json -o <last-message> <task>`.

Codex 0.169.0 speaks ONLY the Responses API to its model provider
(`wire_api`: "`responses` is the only supported value"), so the
stub is served as a local Responses API server (see codex_stub.py
for the translation + event rendering); there is no Chat
Completions wire option to fall back to.

Usage:
    ~/workspace/hackathons/trustrun/.venv/bin/python3 probe_codex.py \
        ["task text"] [--approval-policy never|on-request|unset] \
        [--extra-codex-flag ...]

Logs: codex-venv/codex-requests.jsonl (every stub request body,
verbatim), codex-venv/codex-toolcalls.jsonl (every bridge call).
Prints the codex exit code, the last-message file, the JSONL event
kinds, and a short summary of the last stub request (message
roles, tool names offered, tool result shape). All traffic is
localhost; no key, no network.
"""

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
_CODEX = os.path.join(_HERE, "codex-venv", "codex-x86_64-unknown-linux-musl")
_CODEX_HOME = os.path.join(_HERE, "codex-venv", "codex-home")
_CODEX_WORK = os.path.join(_HERE, "codex-work")
_CONFIG_PATH = os.path.join(_CODEX_HOME, "config.toml")
_MCP_SERVER = os.path.join(_HERE, "codex_mcp_server.py")
_REQUESTS_LOG = os.path.join(_HERE, "codex-venv", "codex-requests.jsonl")
_TOOLCALLS_LOG = os.path.join(_HERE, "codex-venv", "codex-toolcalls.jsonl")
_CLI_STDERR_LOG = os.path.join(_HERE, "codex-venv", "codex-run-stderr.log")
_LAST_MESSAGE = os.path.join(_HERE, "codex-venv", "last-message.txt")

_STUB_PATH = os.path.normpath(os.path.join(
    _HERE, "..", "..", "..", "..", "..", "trustrun-venvs", "n8n-venv",
    "n8n-stub.py"))

STUB_PORT = 18094
BRIDGE_PORT = 18095
STUB_URL = "http://127.0.0.1:%d" % STUB_PORT
BRIDGE_URL = "http://127.0.0.1:%d" % BRIDGE_PORT

_spec = importlib.util.spec_from_file_location("codex_n8n_stub", _STUB_PATH)
_stub_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stub_mod)
DeterministicStub = _stub_mod.DeterministicStub
decide_for_request = _stub_mod.decide_for_request

_stub_spec = importlib.util.spec_from_file_location(
    "codex_stub", os.path.join(_HERE, "codex_stub.py"))
_stub_shim = importlib.util.module_from_spec(_stub_spec)
_stub_shim.__name__ = "codex_stub"
_stub_spec.loader.exec_module(_stub_shim)
responses_to_chat_body = _stub_shim.responses_to_chat_body
response_events = _stub_shim.response_events
response_object = _stub_shim.response_object

_CURRENT = {"tools": {}, "call_id": "probe"}
_STUBS = {}
_LOCK = threading.Lock()
_LOG_LOCK = threading.Lock()


def _append_jsonl(path, row):
    with _LOG_LOCK:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")


def _as_text(out):
    if isinstance(out, dict) and "content" in out:
        return str(out["content"])
    if isinstance(out, dict):
        return json.dumps(out)
    if out is None:
        return "ok"
    return str(out)


def _item_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(
                    block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return "" if content is None else str(content)


class _StubHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path in ("/", "/v1/models"):
            body = json.dumps({"object": "list", "data": [
                {"id": "gpt-4", "object": "model"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
        except Exception:  # noqa: BLE001 - malformed stub call
            body = {}
        with _LOCK:
            tools = set(_CURRENT["tools"])
        # Translate the Responses API request into a Chat Completions
        # body for the shared stub, and keep the raw wire body in
        # the log as the audit trail.
        chat_body, skipped = responses_to_chat_body(body)
        task_text = ""
        for message in chat_body.get("messages") or []:
            if message.get("role") == "user":
                task_text = message.get("content") or ""
                break
        with _LOCK:
            stub = _STUBS.get(task_text)
            if stub is None:
                stub = DeterministicStub(
                    task_text or "What is the capital of France?", tools)
                _STUBS[task_text] = stub
        resp, entry = decide_for_request(stub, chat_body)
        if skipped:
            entry["responses_skipped_item_types"] = skipped
        _append_jsonl(_REQUESTS_LOG, {
            "call_id": _CURRENT["call_id"],
            "path": self.path,
            "stream": body.get("stream"),
            "model": body.get("model"),
            "instructions_len": len(body.get("instructions") or ""),
            "input": body.get("input"),
            "tools": body.get("tools"),
            "response": resp,
        })
        if body.get("stream"):
            events = response_events(resp)
            payload = "".join(
                "data: %s\n\n" % json.dumps(event) for event in events)
            data = payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        obj = response_object(resp)
        data = json.dumps(obj).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class _BridgeHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_POST(self):
        tool = self.path.rsplit("/", 1)[-1]
        try:
            length = int(self.headers.get("Content-Length") or 0)
            args = json.loads(self.rfile.read(length) or b"{}")
        except Exception:  # noqa: BLE001 - malformed bridge call
            args = {}
        with _LOCK:
            tools = dict(_CURRENT["tools"])
        fn = tools.get(tool)
        if fn is None:
            _append_jsonl(_TOOLCALLS_LOG, {
                "call_id": _CURRENT["call_id"], "tool": tool, "args": args,
                "ok": False, "error": "not registered for this call",
            })
            body = ("Tool %s not found." % tool).encode("utf-8")
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        try:
            result = fn(**args) if isinstance(args, dict) else fn(args)
        except Exception as exc:  # noqa: BLE001 - caught class at bridge
            _append_jsonl(_TOOLCALLS_LOG, {
                "call_id": _CURRENT["call_id"], "tool": tool, "args": args,
                "ok": False, "error": str(exc),
            })
            body = str(exc).encode("utf-8")
            self.send_response(500)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        _append_jsonl(_TOOLCALLS_LOG, {
            "call_id": _CURRENT["call_id"], "tool": tool, "args": args,
            "ok": True,
        })
        body = _as_text(result).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _ensure_config(approval_policy=None, mcp_approval="auto"):
    os.makedirs(_CODEX_HOME, exist_ok=True)
    os.makedirs(_CODEX_WORK, exist_ok=True)
    config = (
        "model = \"gpt-4\"\n"
        "model_provider = \"stub\"\n"
    )
    if approval_policy:
        config += "approval_policy = \"%s\"\n" % approval_policy
    config += (
        "\n[model_providers.stub]\n"
        "name = \"stub\"\n"
        "base_url = \"%s/v1\"\n"
        "wire_api = \"responses\"\n"
        "env_key = \"CODEX_STUB_KEY\"\n"
        "\n[mcp_servers.trustrun]\n"
        "command = \"%s\"\n"
        "args = [\"%s\"]\n"
        "env = { CODEX_BRIDGE_URL = \"%s\" }\n"
        % (STUB_URL, sys.executable, _MCP_SERVER, BRIDGE_URL)
    )
    if mcp_approval:
        # Default MCP tools require approval; under `codex exec`
        # the approval policy defaults to "never", which auto-DENIES
        # them ("MCP tool call requires approval, but approval
        # policy is never", measured). The documented per-server
        # opt-in for tools the user trusts is
        # default_tools_approval_mode = "approve": the loop then runs
        # the server's tools without prompting -- the Codex
        # equivalent of Goose's GOOSE_MODE=auto audited default.
        # The re-probe measures the unset default separately.
        config += "default_tools_approval_mode = \"%s\"\n" % mcp_approval
    with open(_CONFIG_PATH, "w", encoding="utf-8") as handle:
        handle.write(config)
    print("--- config.toml ---")
    print(config)
    print("--- end config ---")


def _codex_env():
    env = dict(os.environ)
    for key in list(env):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy",
                           "no_proxy"):
            del env[key]
    env["HOME"] = _CODEX_HOME
    env["CODEX_HOME"] = _CODEX_HOME
    env["CODEX_STUB_KEY"] = "dummy"
    return env


def main():
    task_text = "What is the capital of France?"
    extra = []
    approval_policy = None
    mcp_approval = "approve"
    args = sys.argv[1:]
    rest = []
    i = 0
    while i < len(args):
        if args[i] == "--approval-policy" and i + 1 < len(args):
            approval_policy = args[i + 1]
            if approval_policy == "unset":
                approval_policy = None
            i += 2
        elif args[i].startswith("--approval-policy="):
            approval_policy = args[i].split("=", 1)[1]
            if approval_policy == "unset":
                approval_policy = None
            i += 1
        elif args[i] == "--mcp-approval" and i + 1 < len(args):
            mcp_approval = args[i + 1]
            if mcp_approval == "unset":
                mcp_approval = None
            i += 2
        elif args[i].startswith("--mcp-approval="):
            mcp_approval = args[i].split("=", 1)[1]
            if mcp_approval == "unset":
                mcp_approval = None
            i += 1
        else:
            rest.append(args[i])
            i += 1
    if rest and not rest[0].startswith("--"):
        task_text = rest[0]
        extra = rest[1:]
    else:
        extra = rest
    sys.path.insert(0, os.path.normpath(os.path.join(
        _HERE, "..", "..", "..", "..")))
    from evals.tools import calculator, search_docs  # noqa: E402
    _CURRENT["tools"] = {"calculator": calculator, "search_docs": search_docs}
    _CURRENT["call_id"] = uuid.uuid4().hex[:12]
    _ensure_config(approval_policy, mcp_approval)
    stub_server = ThreadingHTTPServer(("127.0.0.1", STUB_PORT), _StubHandler)
    bridge_server = ThreadingHTTPServer(
        ("127.0.0.1", BRIDGE_PORT), _BridgeHandler)
    threading.Thread(target=stub_server.serve_forever, daemon=True).start()
    threading.Thread(target=bridge_server.serve_forever, daemon=True).start()
    if os.path.exists(_LAST_MESSAGE):
        os.remove(_LAST_MESSAGE)
    cmd = [_CODEX, "exec", "--skip-git-repo-check", "--ephemeral",
           "--trust", "--json", "-o", _LAST_MESSAGE, task_text]
    cmd.extend(extra)
    print("CMD:", " ".join(cmd), flush=True)
    started = time.time()
    with open(_CLI_STDERR_LOG, "ab") as stderr_handle:
        proc = subprocess.Popen(
            cmd, cwd=_CODEX_WORK, env=_codex_env(),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=stderr_handle, text=True, bufsize=1)
        try:
            stdout, _ = proc.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate(timeout=10)
            print("TIMEOUT after 300s", flush=True)
            return
    elapsed = time.time() - started
    print("exit=%s elapsed=%.1fs" % (proc.returncode, elapsed), flush=True)
    print("--- last-message file ---")
    if os.path.exists(_LAST_MESSAGE):
        with open(_LAST_MESSAGE, encoding="utf-8") as handle:
            print(handle.read().strip())
    else:
        print("(no last-message file)")
    print("--- stdout event kinds ---")
    kinds = {}
    for line in (stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            print("non-json stdout: %s" % line[:300])
            continue
        try:
            event = json.loads(line)
        except ValueError:
            print("unparseable stdout: %s" % line[:300])
            continue
        kind = event.get("type") or event.get("msg", {}).get("type") or "?"
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind in ("agent_message", "error", "exec_complete"):
            print(json.dumps(event)[:800])
    print("event kinds: %s" % kinds)
    try:
        with open(_CLI_STDERR_LOG, "rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - 3000))
            tail = handle.read().decode("utf-8", "replace")
        print("--- stderr tail ---")
        print(tail[-3000:])
    except OSError:
        pass
    # Summarize the last stub request.
    try:
        last = None
        with open(_REQUESTS_LOG, encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    last = json.loads(line)
        if last:
            print("--- last stub request ---")
            print("path:", last.get("path"), "model:", last.get("model"),
                  "stream:", last.get("stream"))
            print("instructions_len:", last.get("instructions_len"))
            for item in last.get("input") or []:
                if isinstance(item, dict):
                    print("  %s: %s" % (
                        item.get("type"),
                        json.dumps(item)[:500]))
                else:
                    print("  %r" % (item,)[:300])
            tools = last.get("tools") or []
            print("tools offered (%d):" % len(tools))
            for tool in tools:
                if isinstance(tool, dict):
                    print("  - %s" % tool.get("name"))
    except OSError:
        print("(no requests logged)")


if __name__ == "__main__":
    main()
