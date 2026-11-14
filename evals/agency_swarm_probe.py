"""Wiring probe for the Agency Swarm audit (audit 51).

Proves the deterministic stub can drive a real agency_swarm.Agent
(1.11.0, OpenAI Agents SDK under the hood) through the SDK Model
seam before the adapter is built. Run with the audit venv python
from /tmp so any framework side-effects land outside the repo:

    cd /tmp && ~/workspace/hackathons/trustrun-venvs/agency-swarm-venv/bin/python \\
        ~/workspace/hackathons/trustrun/evals/agency_swarm_probe.py

Three cases, each a fresh Agent + stub model:
  1. end-to-end tool call: stub calls search_docs, framework must
     dispatch it, return the result to the model, and the run must
     end with the model's final answer.
  2. raising tool: search_docs raises RuntimeError; record whether
     the exception propagates out of get_response, is caught and
     handed back as an observation, or is swallowed.
  3. unregistered tool: stub calls a tool name the agent does not
     hold; record whether anything executes, whether the run errors,
     and what observation (if any) the model receives next.
"""

import asyncio
import json
import os
import sys

# NAME COLLISION: this file lives in evals/, whose agents.py shadows
# the OpenAI Agents SDK package also named `agents`. Drop this
# script's own directory from sys.path before importing the SDK so
# `import agents` (here and inside agency_swarm) resolves to the
# installed openai-agents package.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path = [p for p in sys.path if os.path.abspath(p) != _HERE]

os.environ.setdefault("OPENAI_API_KEY", "dummy-audit-key")
# No network is used anywhere in this audit (stub model, tracing
# disabled), but the SDK's trace provider builds an httpx.Client at
# import/setup time and httpx parses the ambient proxy env vars: the
# runtime's NO_PROXY carries bracketed IPv6 entries ("[::1]") that
# httpx rejects as "Invalid port: ':1]'". Drop the proxy vars in this
# process before touching the SDK.
for _var in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY",
             "ALL_PROXY", "all_proxy", "no_proxy", "NO_PROXY"):
    os.environ.pop(_var, None)

from agents import function_tool, set_tracing_disabled  # noqa: E402
from agents.models.interface import ModelResponse  # noqa: E402
from agents.models.interface import Model  # noqa: E402
from agents.usage import Usage  # noqa: E402
from openai.types.responses import (  # noqa: E402
    ResponseFunctionToolCall,
    ResponseOutputMessage,
    ResponseOutputText,
)

from agency_swarm import Agent  # noqa: E402

set_tracing_disabled(True)

CALLS = []


class ProbeModel(Model):
    """Minimal stub model: first call issues the configured tool call,
    later calls answer with the latest observation (or a fixed final)."""

    def __init__(self, tool_name, tool_args, final_text="DONE"):
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.final_text = final_text
        self.n = 0
        self.calls = []  # (system_instructions, input items) per call

    def _observation(self, model_input):
        found = None
        if isinstance(model_input, str):
            return None
        for item in model_input:
            kind = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
            if kind != "function_call_output":
                continue
            if isinstance(item, dict):
                found = item.get("output")
            else:
                found = getattr(item, "output", None)
        return found

    async def get_response(self, system_instructions, input, model_settings,
                           tools, output_schema, handoffs, tracing, *,
                           previous_response_id, conversation_id, prompt):
        self.n += 1
        self.calls.append({
            "system_instructions": system_instructions,
            "input": input,
            "tools": [getattr(t, "name", str(t)) for t in (tools or [])],
        })
        usage = Usage(requests=1, input_tokens=0, output_tokens=0, total_tokens=0)
        if self.n == 1:
            output = [ResponseFunctionToolCall(
                id="call_1", call_id="call_1",
                arguments=json.dumps(self.tool_args),
                name=self.tool_name, type="function_call",
                status="completed",
            )]
        else:
            obs = self._observation(input)
            text = "OBS=%s" % (obs,)
            output = [ResponseOutputMessage(
                id="msg_%d" % self.n, type="message", role="assistant",
                status="completed",
                content=[ResponseOutputText(
                    text=text, type="output_text", annotations=[])],
            )]
        return ModelResponse(output=output, usage=usage,
                             response_id="resp_stub_%d" % self.n)

    async def stream_response(self, system_instructions, input, model_settings,
                              tools, output_schema, handoffs, tracing, *,
                              previous_response_id, conversation_id, prompt):
        from agents.stream_events import ResponseCompletedEvent
        response = await self.get_response(
            system_instructions, input, model_settings, tools,
            output_schema, handoffs, tracing,
            previous_response_id=previous_response_id,
            conversation_id=conversation_id, prompt=prompt)
        yield ResponseCompletedEvent(response=response)


def _make_agent(model, tools):
    return Agent(
        name="probe_agent",
        instructions="You are a helpful agent. Use your tools.",
        tools=tools,
        model=model,
    )


def _run_case(label, tool_name, tool_args, tools):
    print("=== %s ===" % label)
    model = ProbeModel(tool_name, tool_args)
    agent = _make_agent(model, tools)
    try:
        result = asyncio.run(agent.get_response("What is the capital of France?"))
        final = result.final_output
        print("final_output: %r" % (final,))
        print("model calls: %d" % model.n)
        for i, call in enumerate(model.calls):
            print("  call %d: system_instructions=%r" % (
                i + 1, (call["system_instructions"] or "")[:200]))
            print("  call %d: tools seen by model=%s" % (i + 1, call["tools"]))
            print("  call %d: input items=%s" % (
                i + 1, json.dumps(call["input"], default=str)[:800]))
    except Exception as exc:  # noqa: BLE001 - probe records, does not die
        import traceback
        print("EXCEPTION out of get_response: %s: %s" % (type(exc).__name__, exc))
        traceback.print_exc(limit=3)
        print("model calls before exception: %d" % model.n)
    print("tool executions: %s" % (CALLS,))
    CALLS.clear()
    print()


@function_tool
def search_docs(query: str) -> str:
    """Search the document corpus for the query."""
    CALLS.append(("search_docs", query))
    return "Paris is the capital of France."


@function_tool(name_override="search_docs")
def raising_docs(query: str) -> str:
    """Search the document corpus for the query."""
    CALLS.append(("search_docs", query))
    raise RuntimeError("injected tool failure in 'search_docs'")


def main():
    _run_case("1 end-to-end tool call", "search_docs",
              {"query": "capital France"}, [search_docs])
    _run_case("2 raising tool", "search_docs",
              {"query": "capital France"}, [raising_docs])
    _run_case("3 unregistered tool name", "nonexistent_tool",
              {"query": "x"}, [search_docs])
    print("probe marker file /tmp/probe.txt exists:",
          os.path.exists("/tmp/probe.txt"))


if __name__ == "__main__":
    main()
