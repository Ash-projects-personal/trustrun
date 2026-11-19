"""Wire helpers for the Sweep real-agent adapter (audit 83).

Stdlib only, so both the sweep-py driver (evals/real_agents/sweep/
sweep_driver.py) and the project-venv tests can import it.

The tool channel (GPT-Engineer precedent): Sweep v1.0.0's live agent
loop is plain-text `ChatGPT.chat` calls -- the shipped callers never
pass `functions=` (see the adapter docstring), and the functions
branch of `call_openai` is broken (probe-verified: it sends only the
system message, twice -- chat.py lines 219-223, `self.messages_dicts
[:1]`). So the stub's tool decisions are rendered as text lines:

    CALL <name> <json args>

The driver parses them, executes the harness tool via the bridge,
and feeds `Tool <name> returned: <text>` back as the next user
message -- the same feedback channel Sweep uses for user feedback.
A CALL naming a tool the agent does not hold is NOT dispatched: the
driver returns the observation "Error: Tool '<name>' not found."
(mirroring GPT-Engineer). A raising tool's exception becomes the
observation "error: Tool '<name>' raised: <msg>" (lowercase "error:"
prefix, so the stub's error branch fires -- the caught class).
"""

import json
import re

TOOL_RESULT_PREFIX = "Tool %s returned: %s"
CALL_RE = re.compile(r"^\s*CALL\s+(\w+)\s+(\{.*\})\s*$", re.DOTALL)
TOOL_RESULT_RE = re.compile(r"^Tool (\w+) returned: (.*)$", re.DOTALL)


def render_call(name, args):
    """Render a stub tool decision as the model's reply text."""
    return "CALL %s %s" % (name, json.dumps(args))


def parse_call(text):
    """Parse a CALL line out of model reply text.

    Returns (name, args dict) or None when the text carries no CALL
    line. A malformed JSON payload returns (name, {}) so the call
    still reaches the bridge with empty args instead of being
    silently dropped.
    """
    if not isinstance(text, str):
        return None
    match = CALL_RE.search(text.strip())
    if not match:
        return None
    name, payload = match.group(1), match.group(2)
    try:
        args = json.loads(payload)
    except ValueError:
        args = {}
    if not isinstance(args, dict):
        args = {}
    return name, args


def is_tool_result_message(text):
    """True when a user message is a fed-back tool result."""
    return isinstance(text, str) and TOOL_RESULT_RE.match(text) is not None


def tool_result_text(name, result):
    """The user-message text the driver feeds back after a tool call."""
    return TOOL_RESULT_PREFIX % (name, result)


def unregistered_tool_text(name):
    return "Error: Tool '%s' not found." % name


def raised_tool_text(name, error):
    return "error: Tool '%s' raised: %s" % (name, error)


def translate_messages_for_stub(messages):
    """Translate Sweep's OpenAI 0.27 message dicts into the
    chat-completions body the deterministic stub decides on.

    Sweep's loop feeds tool results back as USER messages
    ("Tool <name> returned: <text>"); the stub decides on
    observations carried by role "tool" messages, so those user
    messages are re-roled to "tool" with the prefix stripped --
    the content itself is passed verbatim. Every other message
    keeps its role (system / user / assistant). The raw wire body
    is kept verbatim in the requests log; this translation only
    shapes what the stub decides on.
    """
    out = []
    for message in messages or []:
        role = message.get("role")
        content = message.get("content")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = json.dumps(content)
        if role == "user":
            match = TOOL_RESULT_RE.match(content)
            if match:
                out.append({"role": "tool", "content": match.group(2)})
                continue
        entry = {"role": role, "content": content}
        if message.get("name"):
            entry["name"] = message["name"]
        if message.get("function_call"):
            entry["function_call"] = message["function_call"]
        out.append(entry)
    return out
