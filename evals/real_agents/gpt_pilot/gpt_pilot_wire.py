"""Wire helpers for the GPT-Pilot real-agent adapter (audit 88).

Stdlib only, so both the gpt-pilot-py driver
(evals/real_agents/gpt_pilot/gpt_pilot_driver.py) and the project-venv
tests can import it.

The tool channel (Sweep precedent, audit 83): GPT-Pilot 0.2.13's live
agent loop is plain-text `BaseLLMClient.__call__` -- the shipped
agents never pass `tools=` / `functions=` (package grep: zero hits
for "tools" as a request parameter anywhere in core/), and the
models' outputs are consumed as parsed text (JSONParser / StringParser),
not as tool calls. So the stub's tool decisions are rendered as text
lines:

    CALL <name> <json args>

The driver parses them, executes the harness tool via the bridge,
and feeds `Tool <name> returned: <text>` back as the next user
message -- the same feedback channel GPT-Pilot uses for user feedback
and for Executor command output. A CALL naming a tool the agent does
not hold is NOT dispatched: the driver returns the observation
"error: Tool '<name>' not found." (lowercase "error:" prefix, so the
stub's error branch fires -- the unregistered-tool class). A raising
tool's exception becomes the observation "error: Tool '<name>'
raised: <msg>" (lowercase "error:" prefix, so the stub's error branch
fires -- the caught class).
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


def parse_tool_result(text):
    """Parse a "Tool <name> returned: <text>" observation line.

    Returns (name, text) or None.
    """
    if not isinstance(text, str):
        return None
    match = TOOL_RESULT_RE.match(text.strip())
    if not match:
        return None
    return match.group(1), match.group(2)
