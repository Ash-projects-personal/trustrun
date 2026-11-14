"""Wiring probe for the ChatDev audit (audit 53).

Proves the deterministic stub can drive ChatDev 2.0's real agent
node executor (chatdev 0.1.0, PyPI `chatdev`, v2.2.0 tag) through
the ModelProvider seam before the adapter is built. Run with the
audit venv python from /tmp so any framework side-effects land
outside the repo:

    cd /tmp && ~/workspace/hackathons/trustrun-venvs/chatdev-venv/bin/python \
        ~/workspace/hackathons/trustrun/evals/chatdev_probe.py

ChatDev 2.0 runs "function" tools by loading Python functions from
a directory (MAC_FUNCTIONS_DIR) via its FunctionManager; the probe
points that dir at trustrun-venvs/chatdev-functions, whose
trustrun_tools.py delegates to a per-task registry the probe sets
per case. The stub is served as a ModelProvider subclass
registered under "deterministic-stub"; the real
AgentNodeExecutor builds the conversation, calls the provider,
dispatches tool calls through its ToolManager, and loops until
the provider returns a message with no tool calls.

Three cases, each a fresh executor + node + provider:
  1. end-to-end tool call: stub calls search_docs, framework must
     dispatch it, return the result to the model, and the run must
     end with the model's final answer.
  2. raising tool: search_docs raises RuntimeError; record whether
     the exception propagates out of execute(), is caught and handed
     back as an observation, or is swallowed.
  3. unregistered tool: stub calls a tool name the agent does not
     hold; record whether anything executes, whether the run errors,
     and what observation (if any) the model receives next.

No LLM key, no network anywhere in this probe.
"""

import json
import os
import sys

_FUNCTIONS_DIR = os.path.expanduser(
    "~/workspace/hackathons/trustrun-venvs/chatdev-functions")
os.environ["MAC_FUNCTIONS_DIR"] = _FUNCTIONS_DIR
sys.path.insert(0, _FUNCTIONS_DIR)

# ChatDev imports must come after the env var is set: FUNCTION_CALLING_DIR
# is resolved at import time in utils.function_manager.
from entity.configs.node.agent import AgentConfig  # noqa: E402
from entity.configs.node.node import Node  # noqa: E402
from entity.configs.node.tooling import ToolingConfig  # noqa: E402
from entity.enums import LogLevel  # noqa: E402
from entity.messages import Message, MessageRole, ToolCallPayload  # noqa: E402
from runtime.node.agent.providers.base import (  # noqa: E402
    ModelProvider, ProviderRegistry)
from runtime.node.agent.providers.response import ModelResponse  # noqa: E402
from runtime.node.agent.tool import ToolManager  # noqa: E402
from runtime.node.executor.agent_executor import AgentNodeExecutor  # noqa: E402
from runtime.node.executor.base import ExecutionContext  # noqa: E402
from utils.function_catalog import get_function_catalog  # noqa: E402
from utils.function_manager import (  # noqa: E402
    FUNCTION_CALLING_DIR, FunctionManager)
from utils.log_manager import LogManager  # noqa: E402
from utils.logger import WorkflowLogger  # noqa: E402
from utils.token_tracker import TokenTracker, TokenUsage  # noqa: E402
import trustrun_tool_registry as _registry  # noqa: E402

CALLS = []
PROBE_CALLS = []
PROBE_FIRST_TOOL = None


def _latest_tool_text(conversation):
    found = None
    for msg in conversation:
        if getattr(msg, "role", None) == MessageRole.TOOL:
            content = getattr(msg, "content", None)
            found = content if isinstance(content, str) else str(content)
    return found


class ProbeProvider(ModelProvider):
    """Minimal stub provider: first call_model issues the configured
    tool call, later calls answer with the latest tool observation."""

    def create_client(self):
        return None

    def call_model(self, client, conversation, timeline,
                   tool_specs=None, **kwargs):
        PROBE_CALLS.append({
            "n": len(PROBE_CALLS) + 1,
            "roles": [getattr(m, "role", None).value
                      if hasattr(getattr(m, "role", None), "value")
                      else str(getattr(m, "role", None))
                      for m in conversation],
            "texts": [(getattr(m, "content", None) or "")[:200]
                      if isinstance(getattr(m, "content", None), str)
                      else str(getattr(m, "content", None))[:200]
                      for m in conversation],
            "tool_specs": sorted(s.name for s in (tool_specs or [])),
        })
        observation = _latest_tool_text(conversation)
        if len(PROBE_CALLS) == 1 and PROBE_FIRST_TOOL is not None:
            name, args = PROBE_FIRST_TOOL
            return ModelResponse(message=Message(
                role=MessageRole.ASSISTANT,
                content=None,
                tool_calls=[ToolCallPayload(
                    id="call_1", function_name=name,
                    arguments=json.dumps(args))]))
        return ModelResponse(message=Message(
            role=MessageRole.ASSISTANT,
            content="OBS=%s" % (observation,)))

    def extract_token_usage(self, response):
        return TokenUsage()


ProviderRegistry.register(
    "deterministic-stub", ProbeProvider,
    label="Deterministic stub",
    summary="Probe stub provider for the Trustrun audit.")


def _plain_search_docs(query):
    CALLS.append(("search_docs", query))
    return {"content": "Paris is the capital of France."}


def _raising_search_docs(query):
    CALLS.append(("search_docs", query))
    raise RuntimeError("injected tool failure in 'search_docs'")


def _build_executor():
    context = ExecutionContext(
        tool_manager=ToolManager(),
        function_manager=FunctionManager(FUNCTION_CALLING_DIR),
        log_manager=LogManager(WorkflowLogger(
            workflow_id="chatdev-probe", log_level=LogLevel.ERROR,
            use_structured_logging=False, log_to_console=False)),
        token_tracker=TokenTracker("chatdev-probe"),
        global_state={},
    )
    return AgentNodeExecutor(context)


def _build_node(tool_names):
    agent_config = AgentConfig.from_dict(
        {"provider": "deterministic-stub",
         "base_url": "",
         "name": "deterministic-stub-v1",
         "role": "You are a helpful AI assistant. Solve tasks using your tools.",
         "input_mode": "messages",
         "tooling": [{"type": "function",
                      "config": {"tools": [{"name": name}
                                           for name in tool_names],
                                 "auto_load": True}}]},
        path="agent")
    return Node(id="probe_agent", type="agent", config=agent_config,
                path="probe_agent")


def _run_case(label, first_tool, search_fn):
    global PROBE_FIRST_TOOL
    print("=== %s ===" % label)
    PROBE_FIRST_TOOL = first_tool
    PROBE_CALLS.clear()
    CALLS.clear()
    _registry.CURRENT.clear()
    _registry.CURRENT.update({
        "search_docs": search_fn,
        "calculator": lambda expression: {"content": "4"},
    })
    executor = _build_executor()
    node = _build_node(["search_docs", "calculator"])
    inputs = [Message(role=MessageRole.USER,
                      content="What is the capital of France?")]
    try:
        outputs = executor.execute(node, inputs)
        print("execute returned %d message(s)" % len(outputs))
        for out in outputs:
            print("  role=%s text=%r" % (
                getattr(out, "role", None), out.text_content()[:300]))
    except Exception as exc:  # noqa: BLE001 - probe records, does not die
        import traceback
        print("EXCEPTION out of execute(): %s: %s"
              % (type(exc).__name__, exc))
        traceback.print_exc(limit=5)
    print("provider call_model calls: %d" % len(PROBE_CALLS))
    for call in PROBE_CALLS:
        print("  call %d tool_specs=%s" % (call["n"], call["tool_specs"]))
        for role, text in zip(call["roles"], call["texts"]):
            print("    %s: %r" % (role, text[:200]))
    print("tool executions: %s" % (CALLS,))
    print()


def main():
    print("FUNCTION_CALLING_DIR: %s" % FUNCTION_CALLING_DIR)
    print("catalog functions: %s"
          % sorted(get_function_catalog().list_function_names()))
    print()
    _run_case("1 end-to-end tool call",
              ("search_docs", {"query": "capital France"}),
              _plain_search_docs)
    _run_case("2 raising tool",
              ("search_docs", {"query": "capital France"}),
              _raising_search_docs)
    _run_case("3 unregistered tool name",
              ("nonexistent_tool", {"query": "x"}),
              _plain_search_docs)
    print("probe marker file /tmp/probe.txt exists:",
          os.path.exists("/tmp/probe.txt"))


if __name__ == "__main__":
    main()
