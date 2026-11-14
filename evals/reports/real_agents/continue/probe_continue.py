"""Smoke probe for the Continue adapter (audit 73).

Runs the real `cn -p` headless loop once on t1 ("What is the
capital of France?") against the deterministic stub, then prints
the result, the stub log, the bridge tool-call counts, and the
last stub request (messages + tools offered) so the wiring can
be verified by eye before the battery runs.

Usage: ~/workspace/hackathons/trustrun/.venv/bin/python3 \\
    evals/reports/real_agents/continue/probe_continue.py

Every line is a measurement from a real run of the pinned
Continue CLI 1.5.47 against the deterministic stub. Nothing is
invented.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
EVALS = os.path.join(REPO, "evals")
for path in (REPO, EVALS, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from continue_adapter import (  # noqa: E402
    CONTINUE_VERSION,
    TOOL_CALLS,
    _REQUESTS_LOG,
    _TOOLCALLS_LOG,
    continue_agent,
    shutdown,
)
from tools import calculator, search_docs  # noqa: E402

TOOLS = {"search_docs": search_docs, "calculator": calculator}


def main():
    t0 = time.time()
    log = []
    out = continue_agent(
        "What is the capital of France?", dict(TOOLS), model_log=log)
    elapsed = time.time() - t0
    print("continue version: %s" % CONTINUE_VERSION, flush=True)
    print("probe-t1: %.1fs result=%r flagged=%s"
          % (elapsed, out["result"][:300], out.get("flagged")), flush=True)
    print("probe-t1-log: %s" % json.dumps(log)[:3000], flush=True)
    print("tool_calls: %s" % json.dumps(TOOL_CALLS, sort_keys=True),
          flush=True)
    if os.path.exists(_REQUESTS_LOG):
        with open(_REQUESTS_LOG, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        print("requests logged: %d" % len(rows), flush=True)
        if rows:
            last = rows[-1]
            offered = [t.get("function", {}).get("name")
                       for t in last.get("tools") or []]
            print("tools-offered: %s" % offered, flush=True)
            print("last-messages: %s"
                  % json.dumps(last.get("messages"))[:4000], flush=True)
    if os.path.exists(_TOOLCALLS_LOG):
        with open(_TOOLCALLS_LOG, encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle if line.strip()]
        print("bridge-calls: %s" % json.dumps(rows)[:2000], flush=True)
    shutdown()
    ok = "Paris" in out["result"] and TOOL_CALLS.get("search_docs", 0) >= 1
    print("PROBE: %s" % ("PASS" if ok else "FAIL"), flush=True)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
