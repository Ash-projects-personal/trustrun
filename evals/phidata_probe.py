"""Wiring probe for the Phidata audit (audit 52).

Proves the deterministic stub can drive a real phi.agent.Agent
(phidata 2.7.10, PyPI `phidata`) through the phi.model.base.Model
seam before the adapter is built. Run with the audit venv python
from /tmp so any framework side-effects land outside the repo:

    cd /tmp && ~/workspace/hackathons/trustrun-venvs/phidata-venv/bin/python \\
        ~/workspace/hackathons/trustrun/evals/phidata_probe.py

Three cases, each a fresh Agent + stub model:
  1. end-to-end tool call: stub calls search_docs, framework must
     dispatch it, return the result to the model, and the run must
     end with the model's final answer.
  2. raising tool: search_docs raises RuntimeError; record whether
     the exception propagates out of run(), is caught and handed back
     as an observation, or is swallowed.
  3. unregistered tool: stub calls a tool name the agent does not
     hold; record whether anything executes, whether the run errors,
     and what observation (if any) the model receives next.

The stub model subclasses phi.model.base.Model and implements
response(messages) with the same mechanics the adapter will use:
the stub decision is rendered as an assistant Message carrying
tool_calls, the framework's own run_function_calls executes it,
and the result comes back as a tool-role Message that response()
is called with again (the same recursion OpenAIChat.response
performs via handle_post_tool_call_messages). No LLM key, no
network anywhere in this probe.
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..")))

from pydantic import PrivateAttr  # noqa: E402
from phi.agent import Agent  # noqa: E402
from phi.model.base import Model  # noqa: E402
from phi.model.message import Message  # noqa: E402
from phi.model.response import ModelResponse  # noqa: E402
from phi.utils.tools import get_function_call_for_tool_call  # noqa: E402

CALLS = []


def _msg_text(msg):
    """Best-effort text of a phi Message: str, dict-with-content,
    or list content all collapse to a string."""
    content = getattr(msg, "content", None)
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        if "content" in content:
            return str(content["content"])
        return json.dumps(content)
    if isinstance(content, list):
        return json.dumps(content)
    return str(content)


def _latest_observation(messages):
    """Text of the latest tool-role message, or None."""
    found = None
    for msg in messages:
        if getattr(msg, "role", None) == "tool":
            found = _msg_text(msg)
    return found


class ProbeModel(Model):
    """Minimal stub model: first response() issues the configured
    tool call, later calls answer with the latest observation."""

    _first_tool: object = PrivateAttr(default=None)
    _n: int = PrivateAttr(default=0)
    _calls: object = PrivateAttr(default=None)

    def __init__(self, first_tool=None, **kwargs):
        super().__init__(model="probe-stub", **kwargs)
        self._first_tool = first_tool
        self._calls = []

    def response(self, messages):
        self._n += 1
        self._calls.append({
            "n": self._n,
            "messages": [
                {
                    "role": getattr(m, "role", None),
                    "content": _msg_text(m)[:400],
                    "tool_calls": getattr(m, "tool_calls", None),
                }
                for m in messages
            ],
        })
        observation = _latest_observation(messages)
        if self._n == 1 and self._first_tool is not None:
            name, args = self._first_tool
            tool_call = {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": name,
                    "arguments": json.dumps(args),
                },
            }
            assistant = Message(
                role="assistant", content=None, tool_calls=[tool_call])
            messages.append(assistant)
            model_response = ModelResponse(content="")
            function_call_results = []
            function_calls_to_run = []
            fc = get_function_call_for_tool_call(
                tool_call, self.functions)
            if fc is None:
                messages.append(Message(
                    role="tool", tool_call_id="call_1",
                    content="Could not find function to call."))
            elif fc.error is not None:
                messages.append(Message(
                    role="tool", tool_call_id="call_1",
                    content=fc.error))
            else:
                function_calls_to_run.append(fc)
                for _ in self.run_function_calls(
                        function_calls=function_calls_to_run,
                        function_call_results=function_call_results,
                        tool_role="tool"):
                    pass
                messages.extend(function_call_results)
            # Same recursion the real models do after tool calls.
            follow = self.response(messages)
            if follow.content:
                model_response.content += follow.content
            return model_response
        return ModelResponse(
            content="OBS=%s" % (observation,))


def _wrap(name, fn):
    """String-returning wrapper: harness tools return {"content": ...}
    dicts, and phi's tool Message content must be str/list, so unwrap
    here (same wrapper the adapter will use)."""
    def wrapped(*args, **kwargs):
        CALLS.append((name, args, kwargs))
        out = fn(*args, **kwargs)
        if isinstance(out, dict) and "content" in out:
            return str(out["content"])
        if out is None:
            return "ok"
        return str(out)
    wrapped.__name__ = name
    wrapped.__doc__ = "Wrapped harness tool %s." % name
    return wrapped


def _plain_search_docs(query):
    return {"content": "Paris is the capital of France."}


def _raising_search_docs(query):
    raise RuntimeError("injected tool failure in 'search_docs'")


def _run_case(label, first_tool, tools):
    print("=== %s ===" % label)
    model = ProbeModel(first_tool=first_tool)
    agent = Agent(
        name="probe_agent",
        instructions="You are a helpful agent. Use your tools.",
        tools=tools,
        model=model,
    )
    try:
        result = agent.run("What is the capital of France?")
        print("run returned: %s" % type(result).__name__)
        print("content: %r" % (getattr(result, "content", None),))
        print("model response() calls: %d" % model._n)
        for call in model._calls:
            print("  call %d messages:" % call["n"])
            for m in call["messages"]:
                print("    %s: %r tool_calls=%s" % (
                    m["role"], m["content"][:200],
                    json.dumps(m["tool_calls"])[:300]
                    if m["tool_calls"] else None))
    except Exception as exc:  # noqa: BLE001 - probe records, does not die
        import traceback
        print("EXCEPTION out of run(): %s: %s" % (type(exc).__name__, exc))
        traceback.print_exc(limit=5)
        print("model response() calls before exception: %d" % model._n)
    print("tool executions: %s" % (CALLS,))
    CALLS.clear()
    print()


def main():
    _run_case("1 end-to-end tool call",
              ("search_docs", {"query": "capital France"}),
              [_wrap("search_docs", _plain_search_docs)])
    _run_case("2 raising tool",
              ("search_docs", {"query": "capital France"}),
              [_wrap("search_docs", _raising_search_docs)])
    _run_case("3 unregistered tool name",
              ("nonexistent_tool", {"query": "x"}),
              [_wrap("search_docs", _plain_search_docs)])
    print("probe marker file /tmp/probe.txt exists:",
          os.path.exists("/tmp/probe.txt"))


if __name__ == "__main__":
    main()
