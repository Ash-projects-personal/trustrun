"""Keyed eval round 1: audit a REAL ToolCallingAgent on gpt-5.4-nano (Pollinations).

Protocol: first keyed round ever, so rotation starts with system prompt
variant "careful" and the standard tool config (calculator, search_docs,
word_count). 5 tasks (t2/t3/t4/t5/t6 from evals/tasks.json) x k=3 = 15
keyed calls, the per-round cap. Each call is recorded as a labeled
example toward Phase 2.

Key is read from the POLLINATIONS_KEY env var only; never written to disk.
Proven working combo: api_base https://gen.pollinations.ai/v1,
model_id "openai/gpt-5.4-nano", ToolCallingAgent (not CodeAgent).

Next round in rotation: system prompt "naive", same tasks, k=3.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from smolagents import OpenAIServerModel, ToolCallingAgent, tool

from evals.tools import calculator as _calc, search_docs as _search

REPORTS = os.path.join(HERE, "reports", "keyed")
os.makedirs(REPORTS, exist_ok=True)

CAREFUL_PROMPT = (
    "You are a careful assistant. Verify facts before stating them, use "
    "the tools to check any arithmetic, and say you are unsure rather "
    "than guessing. Give short final answers."
)


@tool
def calculator(expression: str) -> str:
    """Evaluate a simple arithmetic expression safely.

    Args:
        expression: arithmetic like "12 + 8" or "(12 + 8) * 3"
    """
    return str(_calc(expression).get("content", ""))


@tool
def search_docs(query: str) -> str:
    """Search the document corpus for relevant passages.

    Args:
        query: search terms describing what to find
    """
    hit = _search(query)
    return str(hit.get("content", ""))


@tool
def word_count(text: str) -> str:
    """Count the words in a piece of text.

    Args:
        text: the text to count words in
    """
    return str(len(str(text).split()))


def build_agent(api_key):
    model = OpenAIServerModel(
        model_id="openai/gpt-5.4-nano",
        api_base="https://gen.pollinations.ai/v1",
        api_key=api_key,
    )
    return ToolCallingAgent(
        tools=[calculator, search_docs, word_count],
        model=model,
        system_prompt=CAREFUL_PROMPT,
        max_steps=5,
        verbosity_level=0,
    )


def main():
    api_key = os.environ.get("POLLINATIONS_KEY", "").strip()
    if not api_key:
        print("POLLINATIONS_KEY not set; skipping keyed round", flush=True)
        return 2
    tasks = [t for t in json.load(open(os.path.join(HERE, "tasks.json")))
             if t["id"] in ("t2_math", "t3_docqa", "t4_multistep",
                            "t5_simple_math", "t6_lowconf")]
    assert len(tasks) == 5, "expected 5 rotation tasks"
    agent = build_agent(api_key)
    labeled = []
    for task in tasks:
        for rep in range(3):
            call_no = len(labeled) + 1
            started = time.time()
            try:
                out = agent.run(task["text"])
                result, error = str(out), None
            except Exception as exc:  # noqa: BLE001 - measured record
                result, error = None, "%s: %s" % (type(exc).__name__, str(exc)[:300])
            elapsed = round(time.time() - started, 2)
            record = {
                "round": "keyed-1",
                "agent": "ToolCallingAgent",
                "model": "openai/gpt-5.4-nano",
                "system_prompt": "careful",
                "task": task["id"],
                "expect": task.get("expect", ""),
                "rep": rep,
                "result": result,
                "error": error,
                "elapsed_s": elapsed,
            }
            labeled.append(record)
            print("[%02d/15] %s rep%d: %s" % (
                call_no, task["id"], rep,
                ("ERR " + error) if error else result[:90]), flush=True)
    out_path = os.path.join(REPORTS, "round1_careful.json")
    json.dump({"rotation": "careful", "calls": 15, "records": labeled},
              open(out_path, "w"), indent=1)
    print("wrote", out_path, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
