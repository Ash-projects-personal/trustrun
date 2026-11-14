"""Probe: drive the REAL Goose 1.59.1 CLI loop with the deterministic stub.

One-shot probe (not the battery): starts the stub OpenAI server on
127.0.0.1:18092 and the tool bridge on 127.0.0.1:18093, writes an
isolated Goose config (provider openai -> the stub; extension
"trustrun" -> the stdio MCP server goose_mcp_server.py), and runs
one `goose run --no-session --text <task>`.

Usage:
    ~/workspace/hackathons/trustrun/.venv/bin/python3 probe_goose.py \
        ["task text"] [--extra-flag ...]

Logs: goose-venv/goose-requests.jsonl (every stub request body,
verbatim), goose-venv/goose-toolcalls.jsonl (every bridge call).
Prints goose stdout, exit code, and a short summary of the last
stub request (message roles, tool names offered, tool result
shape). All traffic is localhost; no key, no network.
"""

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HERE = os.path.dirname(os.path.abspath(__file__))
_GOOSE = os.path.join(_HERE, "goose-venv", "goose")
_GOOSE_HOME = os.path.join(_HERE, "goose-venv", "goose-home")
_GOOSE_WORK = os.path.join(_HERE, "goose-work")
_CONFIG_PATH = os.path.join(_GOOSE_HOME, ".config", "goose", "config.yaml")
_MCP_SERVER = os.path.join(_HERE, "goose_mcp_server.py")
_REQUESTS_LOG = os.path.join(_HERE, "goose-venv", "goose-requests.jsonl")
_TOOLCALLS_LOG = os.path.join(_HERE, "goose-venv", "goose-toolcalls.jsonl")
_CLI_STDERR_LOG = os.path.join(_HERE, "goose-venv", "goose-run-stderr.log")

_STUB_PATH = os.path.normpath(os.path.join(
    _HERE, "..", "..", "..", "..", "..", "trustrun-venvs", "n8n-venv",
    "n8n-stub.py"))

STUB_PORT = 18092
BRIDGE_PORT = 18093
STUB_URL = "http://127.0.0.1:%d" % STUB_PORT
BRIDGE_URL = "http://127.0.0.1:%d" % BRIDGE_PORT

_spec = importlib.util.spec_from_file_location("goose_n8n_stub", _STUB_PATH)
_stub_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_stub_mod)
DeterministicStub = _stub_mod.DeterministicStub
decide_for_request = _stub_mod.decide_for_request

_stub_spec = importlib.util.spec_from_file_location(
    "goose_stub", os.path.join(_HERE, "goose_stub.py"))
_stub_shim = importlib.util.module_from_spec(_stub_spec)
_stub_shim.__name__ = "goose_stub"
_stub_spec.loader.exec_module(_stub_shim)
sse_chunks = _stub_shim.sse_chunks

_CURRENT = {"tools": {}, "call_id": "probe"}
_STUBS = {}
_LOCK = threading.Lock()
_LOG_LOCK = threading.Lock()


def _append_jsonl(path, row):
    with _LOG_LOCK:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")


def _content_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
            elif isinstance(block, str):
                parts.append(block)
        return "".join(parts)
    return "" if content is None else str(content)


def _unwrap_observation(raw):
    """Unwrap Goose's tool-message content to the tool result string.

    Measured in the probe (see goose-requests.jsonl): Goose sends
    the MCP tool result as a tool message. The common case is the
    MCP content array [{"type":"text","text":"<tool text>"}]; the
    n8n list shapes ([{output|response|error}]) and a bare string
    are handled too. A raising tool's error arrives as an isError
    MCP result; Goose's rendering of it is whatever the probe log
    shows -- the unwrap keeps the raw text verbatim so the stub's
    error branch sees exactly what Goose delivered.
    """
    if not isinstance(raw, str):
        return "" if raw is None else str(raw)
    text = raw.strip()
    if not text.startswith("[") and not text.startswith("{"):
        return raw
    try:
        parsed = json.loads(text)
    except ValueError:
        return raw
    if isinstance(parsed, dict):
        content = parsed.get("content")
        if isinstance(content, list) and content:
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(
                        item.get("text"), str):
                    parts.append(item["text"])
                elif isinstance(item, str):
                    parts.append(item)
            if parts:
                return "".join(parts)
        if "error" in parsed:
            err = parsed["error"]
            err = err if isinstance(err, str) else json.dumps(err)
            return "error:" + err
        return raw
    if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
        item = parsed[0]
        if isinstance(item.get("text"), str):
            return item["text"]
        for key in ("output", "response"):
            if key in item:
                out = item[key]
                return out if isinstance(out, str) else json.dumps(out)
        if "error" in item:
            err = item["error"]
            err = err if isinstance(err, str) else json.dumps(err)
            return "error:" + err
    return raw


def _as_text(out):
    if isinstance(out, dict) and "content" in out:
        return str(out["content"])
    if isinstance(out, dict):
        return json.dumps(out)
    if out is None:
        return "ok"
    return str(out)


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
        wire_tool_contents = []
        for message in body.get("messages") or []:
            if message.get("role") == "tool":
                wire_tool_contents.append(
                    _content_text(message.get("content")))
        decide_body = json.loads(json.dumps(body))
        for message in decide_body.get("messages") or []:
            if message.get("role") == "tool":
                message["content"] = _unwrap_observation(
                    _content_text(message.get("content")))
        task_text = ""
        for message in body.get("messages") or []:
            if message.get("role") == "user":
                task_text = _content_text(message.get("content"))
                break
        with _LOCK:
            stub = _STUBS.get(task_text)
            if stub is None:
                stub = DeterministicStub(
                    task_text or "What is the capital of France?", tools)
                _STUBS[task_text] = stub
        resp, entry = decide_for_request(stub, decide_body)
        if wire_tool_contents:
            entry["observation_raw"] = wire_tool_contents[-1]
        _append_jsonl(_REQUESTS_LOG, {
            "call_id": _CURRENT["call_id"],
            "path": self.path,
            "messages": body.get("messages"),
            "tools": body.get("tools"),
            "response": resp,
        })
        if body.get("stream"):
            chunks = sse_chunks(resp)
            payload = "".join(
                "data: %s\n\n" % json.dumps(chunk) for chunk in chunks)
            payload += "data: [DONE]\n\n"
            data = payload.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        data = json.dumps(resp).encode("utf-8")
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


def _ensure_config():
    os.makedirs(os.path.dirname(_CONFIG_PATH), exist_ok=True)
    os.makedirs(_GOOSE_WORK, exist_ok=True)
    config = (
        "active_provider: openai\n"
        "providers:\n"
        "  openai:\n"
        "    enabled: true\n"
        "    model: gpt-4\n"
        "    configured: true\n"
        "GOOSE_MODE: auto\n"
        "GOOSE_DISABLE_KEYRING: \"true\"\n"
        "GOOSE_TELEMETRY_ENABLED: false\n"
        "extensions:\n"
        "  trustrun:\n"
        "    type: stdio\n"
        "    name: trustrun\n"
        "    enabled: true\n"
        "    cmd: %s\n"
        "    args:\n"
        "      - %s\n"
        "    envs:\n"
        "      GOOSE_BRIDGE_URL: %s\n"
        "    timeout: 300\n"
        % (sys.executable, _MCP_SERVER, BRIDGE_URL)
    )
    with open(_CONFIG_PATH, "w", encoding="utf-8") as handle:
        handle.write(config)


def _goose_env():
    env = dict(os.environ)
    for key in list(env):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy",
                           "no_proxy"):
            del env[key]
    env["HOME"] = _GOOSE_HOME
    env["XDG_CONFIG_HOME"] = os.path.join(_GOOSE_HOME, ".config")
    env["XDG_DATA_HOME"] = os.path.join(_GOOSE_HOME, ".local", "share")
    env["XDG_CACHE_HOME"] = os.path.join(_GOOSE_HOME, ".cache")
    env["GOOSE_PROVIDER"] = "openai"
    env["GOOSE_MODEL"] = "gpt-4"
    env["OPENAI_HOST"] = STUB_URL
    env["OPENAI_BASE_PATH"] = "v1/chat/completions"
    env["OPENAI_API_KEY"] = "dummy"
    env["GOOSE_DISABLE_KEYRING"] = "true"
    env["GOOSE_TELEMETRY_ENABLED"] = "false"
    return env


def main():
    task_text = "What is the capital of France?"
    extra = []
    args = sys.argv[1:]
    if args and not args[0].startswith("--"):
        task_text = args[0]
        extra = args[1:]
    else:
        extra = args
    sys.path.insert(0, os.path.normpath(os.path.join(
        _HERE, "..", "..", "..", "..")))
    from evals.tools import calculator, search_docs  # noqa: E402
    _CURRENT["tools"] = {"calculator": calculator, "search_docs": search_docs}
    _ensure_config()
    stub_server = ThreadingHTTPServer(("127.0.0.1", STUB_PORT), _StubHandler)
    bridge_server = ThreadingHTTPServer(
        ("127.0.0.1", BRIDGE_PORT), _BridgeHandler)
    threading.Thread(target=stub_server.serve_forever, daemon=True).start()
    threading.Thread(target=bridge_server.serve_forever, daemon=True).start()
    cmd = [_GOOSE, "run", "--no-session", "--text", task_text]
    cmd.extend(extra)
    print("CMD:", " ".join(cmd), flush=True)
    started = time.time()
    with open(_CLI_STDERR_LOG, "ab") as stderr_handle:
        proc = subprocess.Popen(
            cmd, cwd=_GOOSE_WORK, env=_goose_env(),
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
    print("--- stdout ---")
    print((stdout or "").strip())
    print("--- end stdout ---")
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
            print("path:", last.get("path"))
            for message in last.get("messages") or []:
                content = _content_text(message.get("content"))
                print("  %s: %s" % (message.get("role"), content[:300]))
                for call in message.get("tool_calls") or []:
                    fn = call.get("function") or {}
                    print("    [tool-call %s %s]" % (
                        fn.get("name"),
                        str(fn.get("arguments", ""))[:300]))
            tools = last.get("tools") or []
            print("tools offered (%d):" % len(tools))
            for tool in tools:
                fn = tool.get("function") or {}
                print("  - %s" % fn.get("name"))
    except OSError:
        print("(no requests logged)")


if __name__ == "__main__":
    main()
