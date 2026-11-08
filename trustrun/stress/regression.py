"""Failure-to-regression loop.

An audit that only reports failures once is a snapshot. This module
turns a failure into a regression test: record what an audit caught,
save it, and replay it against the same agent (or a new version of
it) later. A failure is fixed only when the replay grades it
survived True; until then it stays open and gets re-checked every
run.

Prior art, stated plainly: BotGauge (closed commercial product)
ships exactly this failure-to-regression loop. What is new here is
the open-harness implementation: the loop is built from Trustrun's
own attack battery and report shape, the registry is a plain JSON
file anyone can read, and replay re-runs the recorded attack spec
through `replay_attack`, not a paraphrase of it.

Registry shape (version 1):

    {"version": 1, "failures": {key: entry, ...}}

An entry:

    {
        "key": "task text|kind|vector",
        "agent": "rag_agent",          # who first showed the failure
        "task": "What is the capital of France?",
        "kind": "injection",
        "vector": None,
        "encoding": "plaintext",
        "claim_id": None,              # set for contract-claim failures
        "attack": {...},               # the full attack spec, when known
        "evidence": "...",             # the audit's evidence string
        "first_seen": "2026-11-08",
        "last_seen": "2026-11-08",
        "count": 2,
        "status": "open",              # "open" or "fixed"
    }

Keys are per task, not per agent: the same failure class on the same
task is one entry, however many agents showed it. `count` tracks how
many audits recorded it; `first_agent` is provenance, not identity.

Contract-claim failures are recorded but not replayed: replaying
one would mean re-running the contract check, which lives outside
the stress battery. They sit in the registry as open items with
`attack` None and replay as "unverified" with that reason stated.
"""

import datetime
import json
import os

from trustrun.stress import replay_attack

REGISTRY_VERSION = 1


def new_registry():
    """Return an empty registry."""
    return {"version": REGISTRY_VERSION, "failures": {}}


def _today():
    return datetime.date.today().isoformat()


def failure_key(task_text, kind, vector=None, encoding=None, claim_id=None):
    """Build the registry key for one failure."""
    if claim_id is not None:
        return "%s|claim:%s" % (task_text, claim_id)
    parts = [task_text, kind]
    if vector is not None:
        parts.append(vector)
    elif encoding is not None:
        parts.append(encoding)
    return "|".join(parts)


def record_failure(registry, agent, task_text, kind, vector=None,
                   encoding=None, claim_id=None, attack=None,
                   evidence="", seen=None):
    """Record one failure, creating or updating its entry.

    Returns the entry key. Recording the same failure again bumps
    `count`, refreshes `last_seen` and `evidence`, and re-opens a
    "fixed" entry: a failure that shows up again is not fixed.
    """
    if not isinstance(registry, dict) or not isinstance(
            registry.get("failures"), dict):
        raise TypeError("registry must be a registry dict")
    key = failure_key(task_text, kind, vector, encoding, claim_id)
    seen = seen or _today()
    entry = registry["failures"].get(key)
    if entry is None:
        entry = {
            "key": key,
            "agent": agent,
            "task": task_text,
            "kind": kind,
            "vector": vector,
            "encoding": encoding,
            "claim_id": claim_id,
            "attack": attack,
            "evidence": evidence,
            "first_seen": seen,
            "last_seen": seen,
            "count": 1,
            "status": "open",
        }
        registry["failures"][key] = entry
        return key
    entry["count"] += 1
    entry["last_seen"] = seen
    entry["evidence"] = evidence
    if attack is not None:
        entry["attack"] = attack
    if entry.get("status") == "fixed":
        entry["status"] = "open"
    return key


def _match_attack_spec(result, attacks):
    """Find the attack spec for one stress result, by kind + vector/encoding."""
    kind = result.get("kind")
    vector = result.get("vector")
    encoding = result.get("encoding")
    for attack in attacks:
        if attack.get("kind") != kind:
            continue
        if vector is not None and attack.get("vector") != vector:
            continue
        if encoding is not None and attack.get("encoding") != encoding:
            continue
        if vector is None and encoding is None:
            return attack
        if attack.get("vector") == vector or attack.get("encoding") == encoding:
            return attack
    return None


def record_from_result(registry, report, task=None, seen=None):
    """Record every failure in one audit report.

    Stress attacks graded survived False and contract claims graded
    "fail" are recorded. When `task` is given (the same task dict the
    audit ran on), each failed stress result is matched to its full
    attack spec from the default battery, so the entry can be
    replayed later. Without `task`, the entry keeps kind/vector/
    encoding only and replays as unverified. Returns the list of
    keys recorded.
    """
    if not isinstance(report, dict):
        raise TypeError("report must be a dict")
    agent = report.get("agent", "?")
    task_text = report.get("task", "")
    attacks = None
    if task is not None:
        # Imported here so this module does not depend on cli at
        # import time; the default battery is the same one the
        # stress section runs.
        from trustrun.cli import _default_attacks
        tools = task.get("tools") or {}
        attacks = _default_attacks(tools, task.get("misleading_suggestion"))
    recorded = []
    sections = report.get("sections") or {}
    stress = sections.get("stress") or {}
    for result in stress.get("attacks") or []:
        if result.get("survived") is not False:
            continue
        attack = None
        if attacks is not None:
            attack = _match_attack_spec(result, attacks)
        recorded.append(record_failure(
            registry, agent, task_text, result.get("kind"),
            vector=result.get("vector"),
            encoding=result.get("encoding"),
            attack=attack,
            evidence=result.get("evidence", ""),
            seen=seen,
        ))
    contract = sections.get("contract") or {}
    for claim in contract.get("claims") or []:
        if claim.get("verdict") != "fail":
            continue
        recorded.append(record_failure(
            registry, agent, task_text, "contract",
            claim_id=claim.get("id"),
            evidence=claim.get("evidence", ""),
            seen=seen,
        ))
    return recorded


def save_registry(registry, path):
    """Write a registry to a JSON file, creating parent dirs."""
    if not isinstance(registry, dict) or not isinstance(
            registry.get("failures"), dict):
        raise TypeError("registry must be a registry dict")
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(registry, handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_registry(path):
    """Read a registry from a JSON file.

    A missing file returns a fresh empty registry (the loop starts
    empty). A present file must be a registry dict, else ValueError.
    """
    if not os.path.exists(path):
        return new_registry()
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict) or not isinstance(
            data.get("failures"), dict):
        raise ValueError("not a Trustrun regression registry: %s" % path)
    return data


def replay_regression(agent, task, registry, seed=0, tools_capable=True):
    """Replay every open failure recorded for this task.

    `task` is the task dict the audit ran on (text, tools, expect).
    For each open entry whose task text matches, the recorded attack
    spec is re-run through `replay_attack` against this agent:
    survived True means fixed, False means still failing,
    "unverified" stays unverified. Entries without an attack spec
    (contract-claim failures) replay as unverified: the reason is
    stated, not hidden. Fixed entries have their status updated in
    the registry; still-failing ones stay open. Returns a summary
    dict with the key lists.
    """
    if not isinstance(registry, dict) or not isinstance(
            registry.get("failures"), dict):
        raise TypeError("registry must be a registry dict")
    if not isinstance(task, dict):
        raise TypeError("task must be a dict")
    if tools_capable:
        replay_agent = agent
    else:
        def replay_agent(task_text, task_tools):
            return agent(task_text)

    task_text = task.get("text", "")
    tools = task.get("tools") or {}
    replay_task = {"text": task_text, "tools": tools,
                   "expect": task.get("expect", "")}
    still_failing = []
    fixed = []
    unverified = []
    replayed = 0
    for key, entry in sorted(registry["failures"].items()):
        if entry.get("status") != "open":
            continue
        if entry.get("task") != task_text:
            continue
        replayed += 1
        attack = entry.get("attack")
        if not isinstance(attack, dict):
            unverified.append(key)
            continue
        attack = dict(attack)
        if attack.get("kind") == "perturbation":
            attack["seed"] = seed
        result = replay_attack(replay_agent, replay_task, attack)
        survived = result.get("survived")
        if survived is True:
            entry["status"] = "fixed"
            fixed.append(key)
        elif survived is False:
            still_failing.append(key)
        else:
            unverified.append(key)
    return {
        "replayed": replayed,
        "still_failing": still_failing,
        "fixed": fixed,
        "unverified": unverified,
    }
