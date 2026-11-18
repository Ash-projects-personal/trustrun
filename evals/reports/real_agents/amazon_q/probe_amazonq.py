"""Probe: can the deterministic stub model be injected into the
Amazon Q Developer CLI (aws/amazon-q-developer-cli, v1.19.7)?

Injection shape (read from the audited tag source, v1.19.7 commit
cf39ab6297ee7654fcbeed253445d35fe5c92b07):
- The CLI reads a custom model endpoint from its settings JSON
  (~/.local/share/amazon-q/settings.json, key
  "api.codewhisperer.service" = {"endpoint": ..., "region": ...}):
  crates/chat-cli/src/api_client/endpoints.rs
  (Endpoint::configured_value). A custom endpoint also skips the
  auth-profile ARN (ApiClient::is_custom_endpoint).
- With AMAZON_Q_SIGV4 set (non-empty), chat uses the SigV4
  streaming client (amzn_qdeveloper_streaming_client) instead of
  the Bearer one: crates/chat-cli/src/api_client/mod.rs
  (ApiClient::new). The SigV4 client resolves credentials from the
  standard AWS chain, so DUMMY env credentials satisfy it; the
  local stub ignores SigV4 signatures entirely. No real AWS
  credentials are used anywhere.
- Chat startup calls list_available_models on the non-streaming
  CodeWhisperer client (Bearer token -> NoToken without login),
  but cli/chat/cli/model.rs get_available_models falls back to a
  hardcoded model list on ANY error, so startup proceeds.
- is_mcp_enabled failure defaults to MCP enabled (cli/chat/mod.rs).
- The model call is POST / with Content-Type
  application/x-amz-json-1.0 and X-Amz-Target
  AmazonQDeveloperStreamingService.SendMessage, JSON body
  (SendMessageInput: conversationState). The response is an AWS
  event stream (application/vnd.amazon.eventstream): frames carry
  :event-type AssistantResponseEvent {"content": "..."} /
  ToolUseEvent {"toolUseId","name","input","stop"}.

This probe serves that stub on 127.0.0.1:18096, logs every
request verbatim to amazonq-requests.jsonl, and answers every
SendMessage with a single AssistantResponseEvent. It does NOT
run the battery; it only proves the loop reaches the stub and
the CLI prints the stub's text.
"""

import json
import os
import struct
import subprocess
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.normpath(os.path.join(HERE, "..", "..", "..", "..",
                                     "trustrun-venvs", "amazon-q-venv"))
Q_BIN = os.path.join(VENV, "amazon-q-venv-bin", "q", "bin", "qchat")
Q_HOME = os.path.join(VENV, "q-home")
STUB_PORT = 18096
REQUESTS_LOG = os.path.join(VENV, "amazonq-requests.jsonl")
PROBE_TEXT = "PROBE-OK: Paris is the capital of France."


def _crc(data):
    return zlib.crc32(data) & 0xFFFFFFFF


def event_frame(event_type, payload):
    """One AWS event-stream message frame."""
    headers = b""

    def header(name, value):
        raw = value.encode("utf-8")
        return (bytes([len(name)]) + name.encode("utf-8") + bytes([7])
                + struct.pack(">H", len(raw)) + raw)

    headers += header(":message-type", "event")
    headers += header(":event-type", event_type)
    headers += header(":content-type", "application/json")
    total = 12 + len(headers) + len(payload) + 4
    prelude = struct.pack(">II", total, len(headers))
    body = prelude + struct.pack(">I", _crc(prelude)) + headers + payload
    return body + struct.pack(">I", _crc(body))


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
        except Exception:  # noqa: BLE001 - malformed probe call
            raw = b""
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = {"_unparsed": raw.decode("utf-8", "replace")}
        with open(REQUESTS_LOG, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "path": self.path,
                "target": self.headers.get("X-Amz-Target"),
                "content_type": self.headers.get("Content-Type"),
                "auth": (self.headers.get("Authorization") or "")[:40],
                "body": body,
            }) + "\n")
        target = self.headers.get("X-Amz-Target") or ""
        if "SendMessage" in target:
            # NOTE: the :event-type value is the Smithy member name
            # in lowerCamelCase ("assistantResponseEvent"), NOT the
            # Rust variant name ("AssistantResponseEvent"): the
            # generated unmarshaller (event_stream_serde.rs) matches
            # on response_headers.smithy_type verbatim, and the
            # PascalCase form falls through to Unknown (measured:
            # first probe run reached the stub but printed nothing).
            payload = json.dumps({"content": PROBE_TEXT}).encode()
            data = event_frame("assistantResponseEvent", payload)
            self.send_response(200)
            self.send_header("Content-Type",
                             "application/vnd.amazon.eventstream")
            self.send_header("x-amzn-RequestId", "probe-1")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        # Anything else (ListAvailableModels, GetProfile, telemetry):
        # fail closed with a JSON error so the CLI takes its
        # documented fallback path; the request itself is the log.
        err = json.dumps({
            "__type": "ValidationException",
            "message": "probe stub: operation not implemented",
        }).encode()
        self.send_response(400)
        self.send_header("Content-Type", "application/x-amz-json-1.0")
        self.send_header("x-amzn-RequestId", "probe-1")
        self.send_header("Content-Length", str(len(err)))
        self.end_headers()
        self.wfile.write(err)


def _write_settings():
    data_home = os.path.join(Q_HOME, ".local", "share")
    settings_dir = os.path.join(data_home, "amazon-q")
    os.makedirs(settings_dir, exist_ok=True)
    with open(os.path.join(settings_dir, "settings.json"), "w",
              encoding="utf-8") as handle:
        json.dump({
            "api.codewhisperer.service": {
                "endpoint": "http://127.0.0.1:%d" % STUB_PORT,
                "region": "us-east-1",
            },
        }, handle, indent=2)
    return data_home


def main():
    data_home = _write_settings()
    if os.path.exists(REQUESTS_LOG):
        os.remove(REQUESTS_LOG)
    server = ThreadingHTTPServer(("127.0.0.1", STUB_PORT), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    env = dict(os.environ)
    for key in list(env):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy",
                           "no_proxy"):
            del env[key]
    env["HOME"] = Q_HOME
    env["XDG_DATA_HOME"] = data_home
    env["XDG_CONFIG_HOME"] = os.path.join(Q_HOME, ".config")
    env["XDG_CACHE_HOME"] = os.path.join(Q_HOME, ".cache")
    env["AMAZON_Q_SIGV4"] = "1"
    env["AWS_ACCESS_KEY_ID"] = "AKIAIOSFODNN7EXAMPLE"
    env["AWS_SECRET_ACCESS_KEY"] = (
        "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    env["AWS_REGION"] = "us-east-1"
    env["AWS_DEFAULT_REGION"] = "us-east-1"
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    env["Q_DISABLE_TELEMETRY"] = "1"
    task = sys.argv[1] if len(sys.argv) > 1 else (
        "What is the capital of France?")
    cmd = [Q_BIN, "chat", task, "--no-interactive",
           "--trust-all-tools"]
    print("running: %s" % " ".join(cmd), flush=True)
    started = time.time()
    proc = subprocess.Popen(
        cmd, cwd=os.path.join(VENV, "q-work") if os.path.isdir(
            os.path.join(VENV, "q-work")) else VENV,
        env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        stdout, stderr = proc.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        proc.kill()
        stdout, stderr = proc.communicate(timeout=10)
        print("TIMEOUT after 180s", flush=True)
    print("exit=%s in %.1fs" % (proc.returncode, time.time() - started))
    print("--- stdout ---")
    print(stdout[-4000:])
    print("--- stderr (last 2000) ---")
    print(stderr[-2000:])
    server.shutdown()
    print("requests logged: %s" % REQUESTS_LOG)


if __name__ == "__main__":
    main()
