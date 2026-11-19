"""GPT-Pilot driver: runs the REAL GPT-Pilot 0.2.13 agent loop in-process
under the gpt-pilot-py venv (Python 3.12, era deps), driven by the
deterministic stub served by the adapter.

Invoked by evals/real_agents/gpt_pilot_adapter.py (project venv) as one
subprocess per call:

    gpt-pilot-py/bin/python evals/real_agents/gpt_pilot/gpt_pilot_driver.py <job.json>

The job carries task_text, the harness tool names, the bridge URL (the
project-venv tool server), the stub URL (the adapter's OpenAI- and
Anthropic-compatible stub server), and a call id. The driver prints
exactly one JSON object to stdout:

    {"result": str, "model_log": [...], "turns": int, "requests": int}

Everything else (GPT-Pilot's logs, UI output) goes to stderr. A non-zero
exit means the harness itself failed; the adapter re-raises it, never
a result.

Audited surface (documented, not hidden): GPT-Pilot's real agent LLM
loop -- a real Developer agent instance (real StateManager on a file
SQLite DB, real AgentConvo with the product's shipped Developer system
prompt, real BaseLLMClient via agent.get_llm(), the default OpenAI
provider path) -- against the Trustrun tool set. The full Orchestrator
app-building pipeline is NOT driven: it builds apps from a spec through
a human-in-the-loop multi-agent flow and has no final-answer channel
for Q&A tasks; the audited surface is the agent LLM loop every
GPT-Pilot agent step runs through. The stub's tool decisions are
rendered as "CALL <name> <json>" text lines (see gpt_pilot_wire.py);
the driver executes each CALL through the bridge and feeds the result
back as the next user message ("Tool <name> returned: <text>"), the
same feedback channel GPT-Pilot uses for user feedback and Executor
command output. No file inside the GPT-Pilot source tree is modified.

Seams stubbed (documented, not hidden):
- The LLM backend is the deterministic stub (config base_url ->
  127.0.0.1 stub server, api_key "dummy" for both providers; no key,
  no network beyond loopback). Telemetry is off (DISABLE_TELEMETRY=1).
- The UI is a silent VirtualUI (scripted answers, no prints): the
  battery loop asks the model, not the user, so no question is ever
  posed to it except the client's error handler on a failed request
  (auto-answered "yes", the VirtualUI default).
- Database tables are created with Base.metadata.create_all (the
  project's own tests do the same); alembic is not used because it
  resolves its migrations dir relative to cwd.
- The egress proxy env vars are stripped in-process: httpx mis-parses
  the VM's bracketed IPv6 no_proxy entries as a port ("Invalid port:
  ':1]'") and would route loopback through the proxy (probe finding).
"""

import asyncio
import contextlib
import copy
import json
import os
import sys
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "..", "..", "trustrun-venvs",
                               "gpt-pilot-venv", "gpt-pilot-src"))

# Tiktoken cache (audit-88 fix, 2026-11-18): a service restart wiped
# /tmp, including tiktoken's cached cl100k_base.tiktoken, and every
# driver call then failed at startup with an SSLError downloading it
# (the driver strips proxy vars in-process for loopback, so the
# download has no route out). Seed a persistent cache dir from the
# verified copy in the goal hidden_files (sha256
# 223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7,
# exactly tiktoken 0.6.0's expected hash for cl100k_base) and point
# tiktoken at it BEFORE tiktoken is imported anywhere (GPT-Pilot
# imports it lazily inside core.*). Set here at module top so it
# holds however the driver is invoked; main() re-asserts it.
_TIKTOKEN_CACHE = os.path.normpath(os.path.join(
    _HERE, "..", "..", "..", "trustrun-venvs", "gpt-pilot-venv",
    "tiktoken-cache"))
os.environ.setdefault("TIKTOKEN_CACHE_DIR", _TIKTOKEN_CACHE)

import gpt_pilot_wire  # noqa: E402

_VENVS = os.path.normpath(os.path.join(
    _HERE, "..", "..", "..", "trustrun-venvs"))
_VENV_DIR = os.path.join(_VENVS, "gpt-pilot-venv")
_SRC_DIR = os.path.join(_VENV_DIR, "gpt-pilot-src")
_WORK_ROOT = os.path.join(_VENV_DIR, "gpt-pilot-work")

# Observation text for a CALL naming a tool the agent does not hold.
# Lowercase "error:" prefix, like the raising-tool observation: the
# shared stub decision table's error branch checks a case-sensitive
# "error:" prefix, so the stub reports the failure ("I could not
# complete the task because the tool failed: ...") and the adapter
# flags it. A capitalized "Error:" sailed past that branch (audit-88,
# 2026-11-18) and the stub echoed the error verbatim, unflagged.
_NOT_FOUND_OBSERVATION = "error: Tool '%s' not found."

MAX_TURNS = 10
DRIVER_TIMEOUT = 240  # seconds per call; healthy tasks take ~10s


def _bridge_call(bridge_url, name, args):
    """POST one tool call to the bridge; return the observation text.

    200 -> body text. 404 -> "error: Tool '<name>' not found."
    500 -> "error: Tool '<name>' raised: <body>". A transport failure
    raises: a dead bridge is a harness failure, never an observation.
    """
    url = "%s/call/%s" % (bridge_url.rstrip("/"), name)
    data = json.dumps({"args": args or {}}).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        if exc.code == 404:
            # Lowercase "error:" prefix, like the 500 path: the
            # shared stub decision table's error branch checks a
            # case-sensitive "error:" prefix, and a capitalized
            # "Error:" sailed past it (audit-88, 2026-11-18: the
            # stub echoed the not-found text verbatim and the
            # adapter never flagged it).
            return _NOT_FOUND_OBSERVATION % name
        return "error: Tool '%s' raised: %s" % (name, body)
    except urllib.error.URLError as exc:
        raise RuntimeError("bridge unreachable: %s" % exc)


async def _run_battery(job):
    """One battery call: real Developer agent loop, stub model."""
    from core.agents.convo import AgentConvo
    from core.agents.developer import Developer
    from core.config import Config, LLMProvider, loader
    from core.db.models import Base
    from core.db.session import SessionManager
    from core.state.state_manager import StateManager
    from core.ui.base import UserInput
    from core.ui.virtual import VirtualUI

    class _SilentUI(VirtualUI):
        """VirtualUI with all prints silenced (stdout must stay pure
        JSON for the adapter). Selection logic mirrors VirtualUI,
        except a missing buttons dict answers with empty text instead
        of raising TypeError."""

        async def send_stream_chunk(self, chunk, *, source=None):
            return None

        async def send_message(self, message, *, source=None):
            return None

        async def ask_question(self, question, *, buttons=None,
                               default=None, buttons_only=False,
                               allow_empty=False, hint=None,
                               initial_text=None, source=None):
            if self.virtual_inputs:
                ret = self.virtual_inputs[0]
                self.virtual_inputs = self.virtual_inputs[1:]
                return ret
            if buttons and "continue" in buttons:
                return UserInput(button="continue", text=None)
            elif default:
                if buttons:
                    return UserInput(button=default, text=None)
                else:
                    return UserInput(text=default)
            elif buttons_only and buttons:
                return UserInput(button=list(buttons.keys())[0])
            else:
                return UserInput(text="")

    task_text = job["task_text"]
    call_id = job["call_id"]
    bridge_url = job["bridge_url"]
    stub_url = job["stub_url"]
    max_turns = int(job.get("max_turns") or MAX_TURNS)

    work = os.path.join(_WORK_ROOT, call_id)
    os.makedirs(os.path.join(work, "workspace"), exist_ok=True)

    config = Config()
    # Base URLs: the OpenAI SDK appends "/chat/completions" to its
    # base_url, so it takes the stub URL WITH "/v1"; the Anthropic
    # SDK appends "/v1/messages" itself, so its base_url must be the
    # bare origin (verified 2026-11-18: base_url ".../v1" produced
    # POST /v1/v1/messages -> 404 -> anthropic.NotFoundError "Model
    # not found", and the request never reached the stub).
    stub_origin = job.get("stub_origin", stub_url[:-3] if stub_url.endswith("/v1") else stub_url)
    for provider in (LLMProvider.OPENAI, LLMProvider.ANTHROPIC):
        config.llm[provider].base_url = (
            stub_url if provider == LLMProvider.OPENAI else stub_origin)
        config.llm[provider].api_key = "dummy"
    config.db.url = "sqlite+aiosqlite:///%s" % os.path.join(work, "audit.db")
    config.fs.workspace_root = os.path.join(work, "workspace")
    config.log.level = "ERROR"
    loader.config = config

    db = SessionManager(config.db)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = StateManager(db)
    await sm.create_project("audit-" + call_id)
    ui = _SilentUI([])
    agent = Developer(sm, ui)
    llm = agent.get_llm()

    convo = AgentConvo(agent).user(task_text)
    model_log = []
    result = ""
    turns = 0
    requests = 0
    while turns < max_turns:
        turns += 1
        response = await llm(convo)
        requests += 1
        if not isinstance(response, str) or response == "":
            raise RuntimeError(
                "empty model response on turn %d" % turns)
        model_log.append({
            "turn": turns,
            "messages": copy.deepcopy(convo.messages),
            "response": response,
        })
        call = gpt_pilot_wire.parse_call(response)
        if call is None:
            result = response
            break
        name, args = call
        observation = _bridge_call(bridge_url, name, args)
        convo.assistant(response)
        convo.user(gpt_pilot_wire.TOOL_RESULT_PREFIX % (
            name, observation or "(empty result)"))
    else:
        result = model_log[-1]["response"] if model_log else ""
    return {
        "result": result,
        "model_log": model_log,
        "turns": turns,
        "requests": requests,
    }


async def _run_anthropic_probe(job):
    """One real Anthropic-routed call through GPT-Pilot's real
    AnthropicClient (TASK_BREAKDOWN agent config): proves the
    adapter's /v1/messages stub path end to end. Returns the raw
    probe dict; the adapter returns it directly."""
    from core.agents.convo import AgentConvo
    from core.agents.developer import Developer
    from core.config import (
        TASK_BREAKDOWN_AGENT_NAME,
        Config, LLMProvider, loader,
    )
    from core.db.models import Base
    from core.db.session import SessionManager
    from core.state.state_manager import StateManager
    from core.ui.virtual import VirtualUI

    call_id = job["call_id"]
    stub_url = job["stub_url"]
    work = os.path.join(_WORK_ROOT, call_id)
    os.makedirs(os.path.join(work, "workspace"), exist_ok=True)

    config = Config()
    # Same base-URL split as the battery loop: Anthropic's SDK
    # appends "/v1/messages" to its base_url, so it takes the bare
    # origin (see the note in _run_battery).
    stub_origin = job.get("stub_origin", stub_url[:-3] if stub_url.endswith("/v1") else stub_url)
    for provider in (LLMProvider.OPENAI, LLMProvider.ANTHROPIC):
        config.llm[provider].base_url = (
            stub_url if provider == LLMProvider.OPENAI else stub_origin)
        config.llm[provider].api_key = "dummy"
    config.db.url = "sqlite+aiosqlite:///%s" % os.path.join(work, "audit.db")
    config.fs.workspace_root = os.path.join(work, "workspace")
    config.log.level = "ERROR"
    loader.config = config

    db = SessionManager(config.db)
    async with db.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sm = StateManager(db)
    await sm.create_project("probe-" + call_id)
    ui = VirtualUI([])
    agent = Developer(sm, ui)
    llm = agent.get_llm(TASK_BREAKDOWN_AGENT_NAME)
    convo = AgentConvo(agent).user("probe")
    response = await llm(convo)
    return {
        "probe_anthropic": {
            "agent": TASK_BREAKDOWN_AGENT_NAME,
            "model": config.llm_for_agent(
                TASK_BREAKDOWN_AGENT_NAME).model,
            "response": response,
        },
    }


async def _main(job):
    if job.get("probe_anthropic"):
        return await _run_anthropic_probe(job)
    return await _run_battery(job)


def main():
    # Loopback-only stub: strip the egress proxy vars first (see
    # module docstring -- httpx mis-parses the VM's no_proxy list).
    for var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
               "ALL_PROXY", "all_proxy", "no_proxy", "NO_PROXY"):
        os.environ.pop(var, None)
    os.environ["DISABLE_TELEMETRY"] = "1"
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", _TIKTOKEN_CACHE)
    with open(sys.argv[1], encoding="utf-8") as handle:
        job = json.load(handle)
    # GPT-Pilot's logger writes pythagora.log relative to cwd; run
    # inside the per-call work dir so nothing lands in the repo.
    # (Do this before importing any core.* module.)
    work = os.path.join(_WORK_ROOT, job["call_id"])
    os.makedirs(os.path.join(work, "workspace"), exist_ok=True)
    os.chdir(work)
    # The agent run may print (UI, logs): keep stdout pure JSON.
    with contextlib.redirect_stdout(sys.stderr):
        out = asyncio.run(asyncio.wait_for(
            _main(job), timeout=DRIVER_TIMEOUT))
    sys.stdout.write(json.dumps(out) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
