"""Agent register: an audit-derived register entry and decision record.

Trustrun audits an agent and returns a report. This module turns
that report into the two artifacts regulators are converging on:

* an agent-register entry: who the agent is, who owns it, what it
  is for, which tools it may use, and under what authority it acted;
* a tamper-evident decision record: a hash chain over the register
  entry plus the audit's verdicts, so a later edit to either the
  identity or a verdict is detectable on re-read.

Regulatory basis, all named sources:

* UK ICO call for evidence on agentic AI, opened Oct 8 2026,
  closes Nov 20 2026: asks whether firms identify or register an
  agent first with an owner and purpose, and seeks evidence on
  structured, tamper-evident logging of agent identity alongside
  actions, plus reconstruction of which agent acted, under what
  authority, what it accessed, and whether human involvement was
  meaningful.
* TC260 AI Safety Governance Framework 3.0 (Sep 14 2026): unique
  agent identities and credentials, least privilege, tool-integrity
  checks, mandatory human approval, abnormal-call blocking, runtime
  monitoring, auditable records, operation logs retained at least
  six months with periodic audits.
* China Implementation Opinions on intelligent agents, enforceable
  Jul 15 2026: the first dedicated national agent regulation,
  three authorisation tiers, mandatory filing and pre-release
  compliance testing.
* US Stop Rogue AI Act, introduced Sep 10 2026 (Gottheimer/Lawler,
  bill not law): directs NIST to develop agent security standards
  including tamper-resistant logs, agent inventories, and
  continuous verification.

Prior art, stated plainly: the register-plus-chained-record shape
itself is now a crowded space. Agent Audit (agentaudit.co.uk;
PyPI package `agentaudits`, alpha, pre-launch) issues hash-chained
cryptographic receipts for every agent action, optionally RFC 3161
timestamped. Verosek seals every request into a signed, chained
trace. Attestorian chains every action into an evidence package
with pre-execution guardrails. A braiviq playbook publishes the
same register-and-decision-record pattern as engineering examples.
What is new here is the object being registered and chained: not
the agent's live actions at runtime (those products need an SDK
on the tool-call path), but an independent audit's verdicts about
the agent, derived after the fact from a Trustrun report. No
runtime integration, no account, no key: a stranger verifies the
record with the standard library alone. The chain construction is
the same as trustrun.evidence (SHA-256 over previous hash, a
newline, and canonical JSON; genesis prev is 64 zeros), and an
anchor built here verifies with evidence.verify_anchor, which is
tested. The same honest limit applies as in the evidence module:
the chain proves the record was not edited, not that the events
are true; a chain can be regenerated from scratch by anyone
holding the report, so it catches edits, not wholesale
fabrication. An external anchor (a published head hash, a
timestamp) is what would close that hole; this module does not
claim to.

Fail-closed rules: registration requires an owner and a purpose;
a tool grant requires a name and a known risk tier; anything the
audit did not measure is recorded as "unverified", never filled
in. A register entry for an agent whose audit never recorded a
human checkpoint says so plainly: the audit itself is post-hoc
review, not in-run human involvement.
"""

import hashlib
import json
import re

from trustrun.evidence import anchor_records, verify_anchor

ANCHOR_VERSION = 1
ALGORITHM = "sha256"
GENESIS_PREV = "0" * 64

# TC260 Framework 3.0: operation logs retained at least six months.
RETENTION_MONTHS = 6

# Tool risk tiers, in plain words. A tool that only reads is the
# lowest tier; one that changes state is higher; one that destroys
# state or moves money or data out is the highest an entry may
# grant without a named human approval step.
TOOL_RISKS = ("read", "write", "destructive")

# Evidence strings that show the audited agent asked a human or
# escalated instead of acting alone. Matched case-insensitively
# against contract-claim and stress-attack evidence.
_HUMAN_MARKERS = ("ask_user", "clarification", "escalat",
                  "human review", "asked the user", "deferred to")

_ENTRY_RE = re.compile(
    r"^  #(\d+) ([0-9a-f]{64}) prev=([0-9a-f]{64}) (\{.*\})$"
)
_HEAD_RE = re.compile(
    r"^\[register\] sha256 head ([0-9a-f]{64}) \(\d+ entries\)$"
)


def _canonical(record):
    """Deterministic JSON for a record: sorted keys, tight separators."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def _entry_hash(prev, record):
    """SHA-256 over the previous hash, a newline, and the record.

    Same construction as trustrun.evidence, so an anchor built here
    verifies with evidence.verify_anchor.
    """
    payload = (prev + "\n" + _canonical(record)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _blank(value):
    return not isinstance(value, str) or not value.strip()


def _checked_tools(tools):
    """Validate tool grants. Returns a normalised list of dicts."""
    if tools is None:
        return []
    if not isinstance(tools, list):
        raise ValueError("tools must be a list of {name, risk} dicts")
    checked = []
    for grant in tools:
        if not isinstance(grant, dict):
            raise ValueError("each tool grant must be a dict")
        name = grant.get("name")
        if _blank(name):
            raise ValueError("each tool grant needs a non-blank name")
        risk = grant.get("risk", "read")
        if risk not in TOOL_RISKS:
            raise ValueError(
                "tool %r has unknown risk %r; want one of %s"
                % (name, risk, ", ".join(TOOL_RISKS)))
        checked.append({"name": name.strip(), "risk": risk})
    return checked


def register_agent(agent_id, name, owner, purpose, tools=None,
                   model=None, version=None):
    """Register an agent. Fail-closed: owner and purpose are required.

    agent_id: stable identifier for the register (not a secret).
    name: human-readable name. owner: named person or team. purpose:
    what the agent is for, in plain words. tools: optional list of
    {"name": ..., "risk": "read"|"write"|"destructive"} grants.
    model/version: optional deployment facts, recorded as given.
    """
    if _blank(agent_id):
        raise ValueError("registration needs a non-blank agent_id")
    if _blank(name):
        raise ValueError("registration needs a non-blank name")
    if _blank(owner):
        raise ValueError(
            "registration needs a named owner; an agent with no "
            "owner cannot be registered")
    if _blank(purpose):
        raise ValueError(
            "registration needs a purpose; an agent with no stated "
            "purpose cannot be registered")
    registration = {
        "agent_id": agent_id.strip(),
        "name": name.strip(),
        "owner": owner.strip(),
        "purpose": purpose.strip(),
        "tools": _checked_tools(tools),
    }
    if model is not None:
        registration["model"] = model
    if version is not None:
        registration["version"] = version
    return registration


def _evidence_strings(report):
    """All evidence strings in a report, for the human marker scan."""
    strings = []
    sections = report.get("sections") or {}
    contract = sections.get("contract") or {}
    for claim in contract.get("claims") or []:
        evidence = claim.get("evidence")
        if isinstance(evidence, str):
            strings.append(evidence)
    stress = sections.get("stress") or {}
    for attack in stress.get("attacks") or []:
        evidence = attack.get("evidence")
        if isinstance(evidence, str):
            strings.append(evidence)
    return strings


def assess_human_involvement(report, human_checkpoints=None):
    """Judge whether human involvement in the audited run was meaningful.

    The ICO's reconstruction question is whether any human
    involvement was meaningful, not whether a human existed
    somewhere in the org chart. Three sources, in order:

    * named checkpoints supplied by the caller (for example an
      operator reviewed the output before it was sent): meaningful.
    * evidence in the report that the agent asked the user, sought
      clarification, or escalated: meaningful, with that evidence
      quoted.
    * otherwise: not meaningful. The audit itself is post-hoc
      review, not in-run involvement, and this function says so
      instead of letting the register imply a human was in the loop.
    """
    if not isinstance(report, dict):
        raise TypeError("report must be a dict")
    if human_checkpoints:
        if not isinstance(human_checkpoints, list) or not all(
                isinstance(item, str) and item.strip()
                for item in human_checkpoints):
            raise ValueError(
                "human_checkpoints must be a list of non-blank strings")
        return {
            "meaningful": True,
            "evidence": "named human checkpoint(s): "
                        + "; ".join(item.strip()
                                    for item in human_checkpoints),
            "basis": ["named_checkpoint"],
        }
    for text in _evidence_strings(report):
        lowered = text.lower()
        for marker in _HUMAN_MARKERS:
            if marker in lowered:
                return {
                    "meaningful": True,
                    "evidence": "audit evidence shows the agent "
                                "involved a human: %s" % text[:200],
                    "basis": ["agent_escalated"],
                }
    return {
        "meaningful": False,
        "evidence": "the audited run had no human checkpoint; the "
                    "audit itself is post-hoc review, not in-run "
                    "human involvement",
        "basis": ["no_checkpoint_in_audit"],
    }


def reconstruction_answers(entry):
    """Answer the ICO's four reconstruction questions from an entry.

    Returns a dict keyed by the question in plain words. Any
    question the entry cannot answer says "unverified" with the
    reason, never a filled-in guess.
    """
    registration = entry["registration"]
    audit = entry["audit"]
    human = entry["human_involvement"]
    tools = audit.get("tools_observed")
    if tools == "unverified" or tools is None:
        accessed = ("unverified: the audit report does not record "
                    "which tools the agent called; do not assume "
                    "the registered grants are what ran")
    elif not tools:
        accessed = "no tool calls were observed in the audited run"
    else:
        accessed = ("tools observed in the audited run: "
                    + ", ".join(sorted(tools)))
    return {
        "which_agent": "%s (%s), owned by %s, purpose: %s"
                       % (registration["name"],
                          registration["agent_id"],
                          registration["owner"],
                          registration["purpose"]),
        "under_what_authority": audit.get("authority")
                                or "unverified: no task text in the "
                                "audit report",
        "what_it_accessed": accessed,
        "was_human_involvement_meaningful":
            ("yes: " + human["evidence"]
             if human["meaningful"]
             else "no: " + human["evidence"]),
    }


def build_register_entry(report, registration, tools_observed=None,
                         human_checkpoints=None):
    """Build a register entry from an audit report and a registration.

    report: a run_audit report dict. registration: the dict from
    register_agent. tools_observed: optional list of tool names the
    audit actually saw called; when omitted the entry records
    "unverified" instead of assuming the registered grants ran.
    human_checkpoints: optional named human checkpoints.
    """
    if not isinstance(report, dict):
        raise TypeError("report must be a dict")
    if not isinstance(registration, dict):
        raise TypeError("registration must be a dict")
    sections = report.get("sections") or {}
    contract = sections.get("contract") or {}
    stress = sections.get("stress") or {}
    consistency = sections.get("consistency") or {}
    data = sections.get("data") or {}
    if tools_observed is None:
        observed = "unverified"
    else:
        if not isinstance(tools_observed, list) or not all(
                isinstance(item, str) for item in tools_observed):
            raise ValueError("tools_observed must be a list of strings")
        observed = sorted(set(tools_observed))
    entry = {
        "registration": registration,
        "audit": {
            "agent": report.get("agent"),
            "task": report.get("task"),
            "k": report.get("k"),
            "seed": report.get("seed"),
            "verdict": report.get("verdict"),
            "contract": contract.get("verdict"),
            "stress": stress.get("verdict"),
            "consistency": consistency.get("verdict"),
            "data": data.get("verdict"),
            "authority": report.get("task"),
            "tools_observed": observed,
        },
        "human_involvement": assess_human_involvement(
            report, human_checkpoints),
        # TC260: operation logs retained at least six months. This
        # is the retention the entry must be kept under, not a
        # computed expiry date: no dates are stored in chained
        # records, so the entry stays deterministic.
        "retention_months": RETENTION_MONTHS,
    }
    entry["reconstruction"] = reconstruction_answers(entry)
    return entry


def decision_records(report, entry):
    """The records a decision record chains, in order.

    Three register records first (identity, authority, human
    involvement), then the audit's verdict records from
    trustrun.evidence.anchor_records, so one chain covers both the
    register entry and the verdicts it stands on. Every record is
    JSON-safe; anything the audit could not determine stays in its
    verdict instead of being dropped.
    """
    if not isinstance(report, dict):
        raise TypeError("report must be a dict")
    if not isinstance(entry, dict):
        raise TypeError("entry must be a dict")
    registration = entry["registration"]
    audit = entry["audit"]
    human = entry["human_involvement"]
    records = [
        {
            "record": "register",
            "agent_id": registration.get("agent_id"),
            "name": registration.get("name"),
            "owner": registration.get("owner"),
            "purpose": registration.get("purpose"),
            "tools": registration.get("tools") or [],
            "model": registration.get("model"),
            "version": registration.get("version"),
        },
        {
            "record": "authority",
            "task": audit.get("authority"),
            "tools_observed": audit.get("tools_observed"),
        },
        {
            "record": "human_involvement",
            "meaningful": human.get("meaningful"),
            "evidence": human.get("evidence"),
            "basis": list(human.get("basis") or []),
        },
    ]
    records.extend(anchor_records(report))
    return records


def build_decision_record(report, entry):
    """Chain the decision records. Deterministic: the same inputs
    always yield the same head. The returned dict has the same
    shape as a trustrun.evidence anchor, so evidence.verify_anchor
    verifies it."""
    records = decision_records(report, entry)
    entries = []
    prev = GENESIS_PREV
    for index, record in enumerate(records):
        entry_hash = _entry_hash(prev, record)
        entries.append({
            "index": index,
            "prev": prev,
            "hash": entry_hash,
            "record": record,
        })
        prev = entry_hash
    return {
        "version": ANCHOR_VERSION,
        "algorithm": ALGORITHM,
        "entries": entries,
        "head": prev,
    }


def verify_decision_record(record):
    """Recompute a decision record's chain. Returns {"valid",
    "bad_index", "reason"}; a malformed or tampered record is
    invalid, never a pass. Delegates to evidence.verify_anchor:
    the schemes are the same by construction, and a test proves
    the delegation agrees."""
    if not isinstance(record, dict):
        raise TypeError("decision record must be a dict")
    return verify_anchor(record)


def format_decision_record(entry, anchor):
    """Render a register entry plus its decision record as text."""
    registration = entry["registration"]
    audit = entry["audit"]
    human = entry["human_involvement"]
    lines = [
        "Trustrun agent register entry",
        "Agent: %s (%s)" % (registration["name"],
                            registration["agent_id"]),
        "Owner: %s" % registration["owner"],
        "Purpose: %s" % registration["purpose"],
        "Tools granted: %s" % (
            ", ".join("%s (%s)" % (grant["name"], grant["risk"])
                      for grant in registration["tools"])
            or "none"),
        "Audit verdict: %s (contract %s, stress %s, consistency %s, "
        "data %s)" % (audit.get("verdict"), audit.get("contract"),
                      audit.get("stress"), audit.get("consistency"),
                      audit.get("data")),
        "Human involvement meaningful: %s" % human["meaningful"],
        "Retention: keep at least %d months (TC260 minimum)"
        % entry["retention_months"],
        "",
        "[register] %s head %s (%d entries)"
        % (anchor["algorithm"], anchor["head"],
           len(anchor["entries"])),
    ]
    for item in anchor["entries"]:
        lines.append(
            "  #%d %s prev=%s %s"
            % (item["index"], item["hash"], item["prev"],
               _canonical(item["record"]))
        )
    return lines


def verify_register_text(text):
    """Verify the decision record carried inside rendered text.

    Returns {"valid", "bad_index", "reason", "head"}; head is the
    last entry hash when the chain parses, else None. Text with no
    register block is invalid: an unanchored entry is not a
    verified one.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    entries = []
    head_line = None
    for line in text.splitlines():
        match = _ENTRY_RE.match(line)
        if match:
            index = int(match.group(1))
            try:
                record = json.loads(match.group(4))
            except json.JSONDecodeError:
                return {"valid": False, "bad_index": index,
                        "reason": "entry record is not valid JSON",
                        "head": None}
            entries.append({
                "index": index,
                "prev": match.group(3),
                "hash": match.group(2),
                "record": record,
            })
            continue
        head_match = _HEAD_RE.match(line)
        if head_match:
            head_line = head_match.group(1)
    if not entries:
        return {"valid": False, "bad_index": None,
                "reason": "no register block found in text",
                "head": None}
    anchor = {
        "version": ANCHOR_VERSION,
        "algorithm": ALGORITHM,
        "entries": entries,
        "head": entries[-1]["hash"],
    }
    result = verify_anchor(anchor)
    result["head"] = entries[-1]["hash"] if result["valid"] else None
    if result["valid"] and head_line is not None \
            and head_line != entries[-1]["hash"]:
        return {"valid": False, "bad_index": None,
                "reason": "register head line does not match the "
                          "last entry hash",
                "head": None}
    if result["valid"]:
        result["head"] = entries[-1]["hash"]
    return result
