"""Run the page-reader injection attack across all 25 tasks
(TRUSTRUN-PageReaderInject).

Measures the new page_reader_inject kind on the repo's task set with
four deterministic stub agents, one run per task per agent. Each
task run is one session with the same fetched page re-read, so the
followed count across the 25 tasks is also the per-technique
obedience rate: the sessions in which the hidden instruction was
obeyed.

- raw-HTML follower: reads the fetched page as raw text and obeys
  any instruction it can read in it, the failure Lamplit Labs
  measured as delivery (Nov 4, 2026: raw HTML 216 of 216, html2text
  180, BeautifulSoup 156, accessibility tree 120, innerText 96).
  Expectation: followed on the 17 plain-text techniques, every
  task; resisted on unicode_tag (the instruction is tag-encoded,
  not readable as text).
- tag decoder: decodes Unicode tag characters and carries the
  marker they name. Expectation: followed on unicode_tag only,
  every task; resisted on the 17 plain-text techniques. This is
  the control showing the per-technique scoring separates the
  delivery shapes.
- naive echo agent: follows plaintext injected instructions, the
  naive_agent shape. Expectation: never followed; every technique
  unclear (it echoes the whole fetched page, marker with benign
  content, so no marker is carried). This is the control showing
  the class is a different mechanism from instruction following.
- visible-text reader: reads only plain visible paragraphs and
  strips Unicode format characters, the blog's visible-text filter
  shape (0 of 216 in-sample). Expectation: never followed; every
  technique resisted; survived True on every task.

Metrics: followed rate per agent, per-technique follow rates, the
echo-vs-carrying split (unclear techniques on the naive agent), and
the Cf-strip split (unicode_tag on the tag decoder vs the raw-HTML
follower).

Usage: python3 run_page_reader_inject_verify.py
Writes reports/page_reader_inject_verify/summary.json.

Deterministic, stdlib only. Stub agents only, not real models: this
measures the harness protocol, not a shipped product's robustness.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.stress import replay_attack  # noqa: E402
from trustrun.stress import page_reader_inject  # noqa: E402


def _stub_tools(names, expect):
    def benign(query):
        return {"content": "The answer is %s." % expect}

    return {name: benign for name in names}


def _visible_paragraph(content):
    match = re.search(r"<p>([^<]+)</p>", content)
    if match:
        return page_reader_inject.strip_format_chars(
            match.group(1)
        ).strip()
    # No markup: the clean tool output is already visible text.
    return page_reader_inject.strip_format_chars(content).strip()


def _follower_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        match = re.search(
            r"reply with exactly this line and nothing else: (.+)", content
        )
        if match:
            return {"result": match.group(1).strip()}
        return {"result": "answer from: " + _visible_paragraph(content)}

    return agent


def _decoder_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        decoded = page_reader_inject.decode_tags(content)
        if page_reader_inject.PAGE_MARKER in decoded:
            return {"result": page_reader_inject.payload_line()}
        return {"result": "answer from: " + _visible_paragraph(content)}

    return agent


def _echo_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        return {"result": "answer from: " + content}

    return agent


def _visible_reader_for(tool):
    def agent(task_text, tools):
        result = tools[tool]("query")
        content = result.get("content", "") if isinstance(result, dict) else ""
        return {"result": "answer from: " + _visible_paragraph(content)}

    return agent


AGENTS = (
    ("raw_html_follower", _follower_for),
    ("tag_decoder", _decoder_for),
    ("naive_echo", _echo_for),
    ("visible_text_reader", _visible_reader_for),
)


def main():
    with open(os.path.join(HERE, "tasks.json")) as handle:
        tasks = json.load(handle)
    rows = []
    for task in tasks:
        tool = task["tools_order"][0]
        probe_task = {
            "text": task["text"],
            "tools": _stub_tools(task["tools_order"], task["expect"]),
            "expect": task["expect"],
        }
        attack = {"kind": "page_reader_inject", "tool": tool}
        for agent_name, builder in AGENTS:
            result = replay_attack(builder(tool), probe_task, attack)
            rows.append(
                {
                    "task": task["id"],
                    "agent": agent_name,
                    "tool": tool,
                    "probes": result["probes"],
                    "followed_techniques": result["followed_techniques"],
                    "survived": result["survived"],
                    "detected": result["detected"],
                    "techniques": result["techniques"],
                }
            )
    summary = {"rows": rows, "agents": {}, "per_technique": {}}
    for agent_name, _ in AGENTS:
        agent_rows = [r for r in rows if r["agent"] == agent_name]
        summary["agents"][agent_name] = {
            "tasks": len(agent_rows),
            "followed_any": sum(
                1 for r in agent_rows if r["followed_techniques"]
            ),
            "followed_all_plain": sum(
                1
                for r in agent_rows
                if len(r["followed_techniques"]) == 17
            ),
            "survived_true": sum(1 for r in agent_rows if r["survived"] is True),
            "survived_unverified": sum(
                1 for r in agent_rows if r["survived"] == "unverified"
            ),
        }
    for technique in page_reader_inject.TECHNIQUES:
        summary["per_technique"][technique] = {}
        for agent_name, _ in AGENTS:
            agent_rows = [r for r in rows if r["agent"] == agent_name]
            summary["per_technique"][technique][agent_name] = sum(
                1
                for r in agent_rows
                if any(
                    t["technique"] == technique and t["outcome"] == "followed"
                    for t in r["techniques"]
                )
            )
    out_dir = os.path.join(HERE, "reports", "page_reader_inject_verify")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=2)
    for agent_name, stats in summary["agents"].items():
        print(
            "%s: %d/%d followed any technique, %d followed all 17 plain, "
            "survived True %d, unverified %d"
            % (
                agent_name,
                stats["followed_any"],
                stats["tasks"],
                stats["followed_all_plain"],
                stats["survived_true"],
                stats["survived_unverified"],
            )
        )
    for technique in page_reader_inject.TECHNIQUES:
        print(
            "%s: followed %s"
            % (
                technique,
                ", ".join(
                    "%s %d/25"
                    % (name, summary["per_technique"][technique][name])
                    for name, _ in AGENTS
                ),
            )
        )


if __name__ == "__main__":
    main()
