"""Evidence anchor: a hash chain over a trust report's verdicts.

A Trustrun report is a file anyone can edit, so a BLOCK flipped to
READY after the fact would otherwise be undetectable. This module
chains every verdict-bearing record in the report (the audit
identity, each contract claim, each stress attack outcome, the
consistency numbers, each data metric, the regression replay, and
the overall verdict) into a SHA-256 hash chain and renders the
chain inside the report text, so a stranger can verify the report
with the standard library alone: recompute each entry hash from
its predecessor and its record, and confirm the head matches.

Prior art, stated plainly: hash-chaining audit records is not a
Trustrun invention and is now a crowded space. Tracekit
(arXiv:2609.35659, Oct 21 2026) chains signed agent-action records
into a Merkle tree with witnesses; halo-record (Aug 2026) and soma
write hash-chained logs of agent tool calls and model calls;
AgentLedger does the same for recorded actions. What is new here
is the object being chained: not the agent's actions, but the
auditor's verdicts about the agent. Those tools answer "what did
the agent do"; this answers "was the audit report itself altered
after it was written". The chain is deliberately small and
dependency-free (hashlib + json only), and it proves integrity of
the record, not truth of the events: a chain can be regenerated
from scratch by anyone holding the report, so it catches edits,
not wholesale fabrication. An external anchor (a published head
hash, a timestamp) is what would close that hole; this module
does not claim to.
"""

import hashlib
import json
import re

ANCHOR_VERSION = 1
ALGORITHM = "sha256"
GENESIS_PREV = "0" * 64

# One entry per physical line in the rendered report:
#   "  #<index> <hash> prev=<prev> <canonical record JSON>"
_ENTRY_RE = re.compile(
    r"^  #(\d+) ([0-9a-f]{64}) prev=([0-9a-f]{64}) (\{.*\})$"
)
_HEAD_RE = re.compile(
    r"^\[evidence\] sha256 head ([0-9a-f]{64}) \(\d+ entries\)$"
)


def _canonical(record):
    """Deterministic JSON for a record: sorted keys, tight separators."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)


def _entry_hash(prev, record):
    """SHA-256 over the previous hash, a newline, and the record."""
    payload = (prev + "\n" + _canonical(record)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def anchor_records(report):
    """Build the verdict records a report's chain covers, in order.

    report: a run_audit report dict. Records carry only JSON-safe
    values (strings, numbers, booleans, None); anything a module
    could not determine stays in its verdict ("unverified",
    pass rates None) instead of being dropped, so the chain
    covers the gaps too.
    """
    if not isinstance(report, dict):
        raise TypeError("report must be a dict")
    sections = report.get("sections") or {}
    records = [{
        "section": "audit",
        "agent": report.get("agent"),
        "task": report.get("task"),
        "k": report.get("k"),
        "seed": report.get("seed"),
    }]
    contract = sections.get("contract") or {}
    # One record per section verdict first, so a section with no
    # items (no claims, no metrics) is still covered.
    records.append({
        "section": "contract",
        "verdict": contract.get("verdict"),
        "module_verdict": contract.get("module_verdict"),
        "passed": contract.get("passed"),
        "failed": contract.get("failed"),
        "unverified": contract.get("unverified"),
    })
    for claim in contract.get("claims") or []:
        records.append({
            "section": "contract",
            "claim": claim.get("id"),
            "statement": claim.get("statement"),
            "verdict": claim.get("verdict"),
            "evidence": claim.get("evidence"),
        })
    side = contract.get("side_effects")
    if side is not None:
        records.append({
            "section": "contract",
            "check": "side_effects",
            "verdict": side.get("verdict"),
            "evidence": side.get("evidence"),
        })
    stress = sections.get("stress") or {}
    records.append({
        "section": "stress",
        "verdict": stress.get("verdict"),
    })
    for attack in stress.get("attacks") or []:
        vector = attack.get("vector") or attack.get("encoding") or ""
        records.append({
            "section": "stress",
            "attack": attack.get("kind"),
            "vector": vector,
            "survived": attack.get("survived"),
            "detected": attack.get("detected"),
            "completed": attack.get("completed"),
            "evidence": attack.get("evidence"),
        })
    consistency = sections.get("consistency") or {}
    records.append({
        "section": "consistency",
        "verdict": consistency.get("verdict"),
        "module_verdict": consistency.get("module_verdict"),
        "pass_rate_1": consistency.get("pass_rate_1"),
        "pass_rate_k": consistency.get("pass_rate_k"),
        "variance_flag": consistency.get("variance_flag"),
        "cheating_flag": consistency.get("cheating_flag"),
    })
    data = sections.get("data") or {}
    records.append({
        "section": "data",
        "verdict": data.get("verdict"),
        "module_verdict": data.get("module_verdict"),
        "records": data.get("records"),
    })
    for name, metric in (data.get("metrics") or {}).items():
        records.append({
            "section": "data",
            "metric": name,
            "verdict": metric.get("verdict"),
            "evidence": metric.get("evidence"),
        })
    regression = report.get("regression")
    if regression is not None:
        records.append({
            "section": "regression",
            "replayed": regression.get("replayed"),
            "still_failing": list(regression.get("still_failing") or []),
            "fixed": list(regression.get("fixed") or []),
            "unverified": list(regression.get("unverified") or []),
            "recorded": list(regression.get("recorded") or []),
        })
    records.append({
        "section": "overall",
        "verdict": report.get("verdict"),
    })
    return records


def build_anchor(report):
    """Chain a report's verdict records. Deterministic: the same
    report always yields the same head."""
    records = anchor_records(report)
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


def verify_anchor(anchor):
    """Recompute a chain. Returns {"valid", "bad_index", "reason"}.

    A malformed or tampered anchor is invalid, never a pass.
    bad_index names the first entry that fails, or None when the
    failure is structural (wrong version, empty entries, a broken
    head).
    """
    if not isinstance(anchor, dict):
        raise TypeError("anchor must be a dict")
    if anchor.get("version") != ANCHOR_VERSION:
        return {"valid": False, "bad_index": None,
                "reason": "unsupported anchor version %r"
                          % (anchor.get("version"),)}
    if anchor.get("algorithm") != ALGORITHM:
        return {"valid": False, "bad_index": None,
                "reason": "unsupported anchor algorithm %r"
                          % (anchor.get("algorithm"),)}
    entries = anchor.get("entries")
    if not isinstance(entries, list) or not entries:
        return {"valid": False, "bad_index": None,
                "reason": "anchor has no entries"}
    prev = GENESIS_PREV
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            return {"valid": False, "bad_index": position,
                    "reason": "entry is not an object"}
        if entry.get("index") != position:
            return {"valid": False, "bad_index": position,
                    "reason": "entry index %r, want %d"
                              % (entry.get("index"), position)}
        if entry.get("prev") != prev:
            return {"valid": False, "bad_index": position,
                    "reason": "prev hash does not match the "
                              "previous entry hash"}
        record = entry.get("record")
        if not isinstance(record, dict):
            return {"valid": False, "bad_index": position,
                    "reason": "entry record is not an object"}
        try:
            want = _entry_hash(prev, record)
        except (TypeError, ValueError):
            return {"valid": False, "bad_index": position,
                    "reason": "entry record is not JSON-safe"}
        if entry.get("hash") != want:
            return {"valid": False, "bad_index": position,
                    "reason": "entry hash does not match its record"}
        prev = entry["hash"]
    if anchor.get("head") != prev:
        return {"valid": False, "bad_index": None,
                "reason": "head does not match the last entry hash"}
    return {"valid": True, "bad_index": None, "reason": "chain valid"}


def format_anchor_lines(anchor):
    """Render an anchor as report text lines, one entry per line."""
    lines = [
        "[evidence] %s head %s (%d entries)"
        % (anchor["algorithm"], anchor["head"], len(anchor["entries"]))
    ]
    for entry in anchor["entries"]:
        lines.append(
            "  #%d %s prev=%s %s"
            % (entry["index"], entry["hash"], entry["prev"],
               _canonical(entry["record"]))
        )
    return lines


def verify_report_text(text):
    """Verify the evidence chain carried inside a rendered report.

    Parses the [evidence] block lines out of the text and
    re-verifies them. Returns {"valid", "bad_index", "reason",
    "head"}; head is the last entry hash when the chain parses,
    else None. A report with no evidence block is invalid: an
    unanchored report is not a verified one.
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
                "reason": "no evidence anchor block found in report",
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
                "reason": "evidence head line does not match the "
                          "last entry hash",
                "head": None}
    if result["valid"]:
        result["head"] = entries[-1]["hash"]
    return result
