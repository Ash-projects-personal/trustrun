"""MKA eval target (TRUSTRUN-MKA-Target): Google DeepMind's Multimodal
Knowledge Agent benchmark as a Trustrun consistency/contract eval target.

MKA (Google DeepMind + Artificial Analysis, Nov 10, 2026) is a 200-task
benchmark for agents doing real multimodal knowledge work (decks,
spreadsheets, reports) across 10 industries / 83 occupations, each task
taking a human expert 3-8 hours and scored on ~70 yes/no checks weighted
75% factual accuracy / 25% visual design. The 200-task set stays private
(anti-leakage); this module adopts the 10 public showcase tasks from
Hugging Face (google/multimodal-knowledge-agent, Apache 2.0), vendored
in evals/mka/tasks.json. Sources: Google DeepMind blog Nov 10, 2026
and the dataset card, both read in full before building.

Scope (decided before writing code, per the queue brief): MKA tasks
demand real multimodal deliverables (.xlsx/.pptx/.docx) built from
load-bearing visual inputs (CAD, rasters, maps), while Trustrun's
agents are stub-LLM/text shaped. So this target runs contract +
consistency only, on a textual deliverable surrogate: the agent gets
the task prompt plus the input-file inventory as text and returns the
deliverable as text. No file tools are provided; the input files
themselves are not vendored and are recorded as unprocessed.

Each rubric criterion becomes one contract claim, classified by a
deterministic parser:

- numeric: the description states an acceptable range ("Acceptable
  range: 7,462 - 7,466" or "acceptable frequency 11.83 to 12.23 GHz").
  Pass when the deliverable reports a number inside every stated
  range; fail when it reports numbers but none in range, or reports
  no number at all for a figure the criterion requires. The check is
  text-checkable and the deliverable text is the full evidence, so
  absence is a failed check, not an unverifiable one.
- entity: the description states a value after " as " ("States the
  study area as City of Nottingham (B)"). Pass when the deliverable
  contains that value (case-insensitive, whitespace-normalized); any
  long digit run (an ID such as a UPRN) named before the " as " must
  also appear. Fail otherwise.
- visual: the description requires a rendered visual (map, chart,
  graph, figure, diagram, image, plot, slide). A text-only pipeline
  cannot see rendered visuals, so the judge abstains: unverified,
  reason judge_abstained. This is the UnableToVerify third state
  doing its job, and it is why the unverifiable share is high here.
- format: two exact, safe text-format checks ("Contains zero asterisk
  characters"; "Uses a hyphen as the bullet marker"). Anything else
  the parser cannot reduce to a check is unverified with the reason
  naming that no deterministic checker exists for the criterion text.

The runner scores each agent k times per task (default 5, seeded),
builds the contract report per run with trustrun.contract, and
computes per-criterion pass@k with trustrun.consistency.pass_at_k.
Autorater-vs-judge agreement (the queue experiment plan's third
metric) is NOT measured here: MKA's autorater runs inside the
Stirrup harness and is not available as a callable in this VM; the
96% human-vs-autorater agreement is MKA's own number, not one this
run can reproduce. The report says so instead of inventing it.

The honest limit: stub agents with no file tools score near zero on
these tasks, and the deterministic ones repeat identically across
runs, so pass@k equals pass@1 for them. The numbers are a floor for
a real-model agent with file tools, not a capability claim. One
measured artifact to read with the numbers: the two format checks on
the RF-IC task ("zero asterisk characters", "hyphen bullet markers")
pass on ANY refusal text, so they are satisfied by an agent that did
nothing; they are not evidence of capability and are reported as
such, not hidden.
"""

import re

from trustrun.consistency import pass_at_k
from trustrun.contract import verify_delivery

SOURCE = "https://huggingface.co/datasets/google/multimodal-knowledge-agent"
REVISION = "46bce7ab8768f661750bd1016ec8cbdc517740b5"

AGENT_ERROR_MARKER = "AGENT-ERROR"

_VISUAL_WORDS = (
    "map", "chart", "graph", "figure", "diagram", "image", "picture",
    "plot", "slide", "visual", "colour", "color",
)

_PAIR_RE = re.compile(
    r"([+-]?[\d,]+\.?\d*)\s*(?:-|to)\s*([+-]?[\d,]+\.?\d*)"
)
_NUMBER_RE = re.compile(r"[+-]?[\d,]+\.?\d*")
_DIGITS_RE = re.compile(r"\d{6,}")
_AS_RE = re.compile(r"\bas\s+(.+?)\.?\s*$", re.IGNORECASE | re.DOTALL)


def _to_float(text):
    return float(text.replace(",", ""))


def _find_ranges(text):
    """Acceptable ranges stated in a criterion description.

    Only text after an "acceptable" marker is scanned, so year pairs
    elsewhere in the description ("from 2006 to 2016") are never read
    as ranges. A description may state several ranges after one
    marker ("acceptable ranges -2.5 to -1.3 and -1.9 to -0.7").
    """
    ranges = []
    parts = re.split(r"acceptable", text, flags=re.IGNORECASE)
    for part in parts[1:]:
        for low, high in _PAIR_RE.findall(part):
            ranges.append((_to_float(low), _to_float(high)))
    return ranges


def _normalize_minus(text):
    """Rubric text uses U+2212 minus in places; fold it to ASCII."""
    return (text or "").replace("\u2212", "-")


def _numbers_in(text):
    """All numbers in a text as floats, commas stripped."""
    found = []
    for match in _NUMBER_RE.finditer(_normalize_minus(text)):
        try:
            found.append(_to_float(match.group(0)))
        except ValueError:
            continue
    return found


def _normalize(text):
    return " ".join(str(text).lower().split())


def _judge_numeric(ranges):
    """Judge for a numeric criterion: every stated range needs a hit."""

    def judge(value, claim, output):
        numbers = _numbers_in(value)
        missing = []
        hits = []
        for low, high in ranges:
            inside = [n for n in numbers if low <= n <= high]
            if inside:
                hits.append((low, high, inside[0]))
            else:
                missing.append((low, high))
        if not missing:
            return True, "numbers in every stated range: %s" % (hits,)
        if not numbers:
            return False, (
                "deliverable reports no number; ranges needed: %s"
                % ([(low, high) for low, high in ranges],)
            )
        return False, (
            "no number in range %s; numbers reported: %s"
            % (missing, numbers[:10])
        )

    return judge


def _judge_entity(value_text, digit_tokens):
    """Judge for an entity criterion: value plus any ID tokens."""

    def judge(value, claim, output):
        haystack = _normalize(value)
        if _normalize(value_text) not in haystack:
            return False, "deliverable does not state %r" % value_text
        for token in digit_tokens:
            if token not in haystack:
                return False, "deliverable does not state ID %s" % token
        return True, "deliverable states %r" % value_text

    return judge


def _judge_abstain(reason):
    """Judge that cannot decide from text alone: unverified, never pass."""

    def judge(value, claim, output):
        return None, reason

    return judge


def _judge_zero_asterisk(value, claim, output):
    if "*" in str(value):
        return False, "deliverable contains asterisk characters"
    return True, "deliverable contains zero asterisk characters"


def _judge_hyphen_bullets(value, claim, output):
    bad = []
    for line in str(value).splitlines():
        match = re.match(r"^\s*([*+\-])\s", line)
        if match and match.group(1) != "-":
            bad.append(line.strip()[:60])
    if bad:
        return False, "non-hyphen bullet markers used: %s" % (bad[:3],)
    return True, "every list item uses a hyphen bullet marker"


def classify_criterion(description):
    """Classify one rubric criterion description into a checkable kind.

    Returns a dict: kind plus the parsed data the judge needs.
    Kinds: "numeric", "entity", "visual", "format", "unparsed".
    """
    text = _normalize_minus(description or "")
    lowered = text.lower()
    ranges = _find_ranges(text)
    if ranges:
        return {"kind": "numeric", "ranges": ranges}
    if any(word in lowered for word in _VISUAL_WORDS):
        return {
            "kind": "visual",
            "reason": (
                "criterion requires a rendered visual (%r); a text-only "
                "pipeline cannot verify it" % description[:120]
            ),
        }
    if "zero asterisk" in lowered:
        return {"kind": "format", "check": "zero_asterisk"}
    if "hyphen as the bullet" in lowered:
        return {"kind": "format", "check": "hyphen_bullets"}
    match = _AS_RE.search(text)
    if match:
        value_text = match.group(1).strip()
        before = text[: match.start()]
        digit_tokens = _DIGITS_RE.findall(before)
        if len(value_text) <= 80:
            return {
                "kind": "entity",
                "value": value_text,
                "digits": digit_tokens,
            }
        if digit_tokens:
            return {
                "kind": "entity",
                "value": None,
                "digits": digit_tokens,
            }
    return {
        "kind": "unparsed",
        "reason": (
            "no deterministic checker for this criterion text: %r"
            % description[:120]
        ),
    }


def criterion_claim(task_id, criterion):
    """Build one contract claim from one rubric criterion."""
    parsed = classify_criterion(criterion["description"])
    claim_id = "%s_%s" % (task_id, criterion["id"].replace(" ", "_"))
    claim = {
        "id": claim_id,
        "statement": criterion["description"],
        "kind": "judge",
        "field": "deliverable",
    }
    kind = parsed["kind"]
    if kind == "numeric":
        claim["judge"] = _judge_numeric(parsed["ranges"])
    elif kind == "entity":
        if parsed["value"] is None:
            claim["judge"] = _judge_entity("", parsed["digits"])
            # Value was a sentence, not a token: only the ID tokens
            # are checkable; the judge reports that in its evidence.
            original = claim["judge"]

            def judge(value, claim, output, _orig=original):
                decision, evidence = _orig(value, claim, output)
                return decision, "value is a sentence, checked ID tokens only; " + evidence

            claim["judge"] = judge
        else:
            claim["judge"] = _judge_entity(parsed["value"], parsed["digits"])
    elif kind == "visual":
        claim["judge"] = _judge_abstain(parsed["reason"])
    elif kind == "format":
        if parsed["check"] == "zero_asterisk":
            claim["judge"] = _judge_zero_asterisk
        else:
            claim["judge"] = _judge_hyphen_bullets
    else:
        claim["judge"] = _judge_abstain(parsed["reason"])
    claim["_mka_kind"] = kind
    claim["_mka_weight"] = criterion.get("weight", 1)
    return claim


def task_contract(task):
    """Build the contract for one MKA task from its rubric criteria."""
    claims = [criterion_claim(task["task_id"], c) for c in task["criteria"]]
    return {"task": task["task_id"], "claims": claims}


def task_prompt(task):
    """The text the agent under test receives for one MKA task."""
    return (
        "%s\n\nRole: %s (%s, %s).\nInput files: %s.\n"
        "Return the full deliverable as text."
        % (
            task["prompt"],
            task["role"],
            task["domain"],
            task["vertical"],
            task["input_files"],
        )
    )


def _call_agent(agent, text):
    """Run the agent once. Returns (deliverable, agent_error)."""
    try:
        output = agent(text, {})
    except Exception as exc:
        return "%s: %s" % (AGENT_ERROR_MARKER, exc), True
    if not isinstance(output, dict):
        return "%s: agent returned a non dict" % AGENT_ERROR_MARKER, True
    result = output.get("result")
    if result is None:
        return "%s: agent returned no result" % AGENT_ERROR_MARKER, True
    return str(result), False


def run_mka_task(agent, task, k=5, seed=0):
    """Run one agent over one MKA task k times and score it.

    agent: callable taking (task_text, tools) and returning a dict
      with a "result" string (the Trustrun agent shape). It is called
      with an empty tool set: no file tools exist in this harness.
    k: repeated runs per task. seed: accepted for interface parity
      with the consistency module; the stub agents are deterministic,
      so the seed does not change their outputs.

    Returns a dict with the per-run contract reports, per-criterion
    pass@k, and the task aggregates. Anything the pipeline cannot
    determine is "unverified", never a pass.
    """
    if not callable(agent):
        raise TypeError("agent must be a callable")
    if isinstance(k, bool) or not isinstance(k, int) or k < 1:
        raise TypeError("k must be a positive integer")
    contract = task_contract(task)
    text = task_prompt(task)
    runs = []
    full_reports = []
    for i in range(k):
        deliverable, agent_error = _call_agent(agent, text)
        report = verify_delivery(contract, {"deliverable": deliverable})
        full_reports.append(report)
        runs.append(
            {
                "run": i + 1,
                "agent_error": agent_error,
                "deliverable": deliverable[:500],
                "passed": report["passed"],
                "failed": report["failed"],
                "unverified": report["unverified"],
                "pass_rate_verifiable": report["pass_rate_verifiable"],
                "unverifiable_share": report["unverifiable_share"],
                "verdict": report["verdict"],
            }
        )
    criteria = task["criteria"]
    per_criterion = []
    for index, criterion in enumerate(criteria):
        claim = contract["claims"][index]
        outcomes = []
        for report in full_reports:
            entry = report["claims"][index]
            if entry["verdict"] == "pass":
                outcomes.append(True)
            elif entry["verdict"] == "fail":
                outcomes.append(False)
            else:
                outcomes.append("unverified")
        judged = [o for o in outcomes if o is True or o is False]
        per_criterion.append(
            {
                "id": claim["id"],
                "kind": claim["_mka_kind"],
                "weight": claim["_mka_weight"],
                "outcomes": outcomes,
                "pass_at_1": (
                    1.0
                    if outcomes[0] is True
                    else 0.0
                    if outcomes[0] is False
                    else "unverified"
                ),
                "pass_at_k": pass_at_k(outcomes, k),
                "judged_runs": len(judged),
            }
        )
    verifiable = [c for c in per_criterion if c["judged_runs"] > 0]
    pass_1_values = [
        c["pass_at_1"] for c in verifiable if c["pass_at_1"] != "unverified"
    ]
    mean_pass_1 = (
        sum(pass_1_values) / len(pass_1_values) if pass_1_values else "unverified"
    )
    pass_k_values = [
        c["pass_at_k"] for c in verifiable if c["pass_at_k"] != "unverified"
    ]
    mean_pass_k = (
        sum(pass_k_values) / len(pass_k_values) if pass_k_values else "unverified"
    )
    first = runs[0]
    first_claims = full_reports[0]["claims"]
    passed_weights = sum(
        c["weight"]
        for c, entry in zip(per_criterion, first_claims)
        if entry["verdict"] == "pass"
    )
    verifiable_weights = sum(
        c["weight"]
        for c, entry in zip(per_criterion, first_claims)
        if entry["verdict"] in ("pass", "fail")
    )
    return {
        "task": task["task_id"],
        "vertical": task["vertical"],
        "domain": task["domain"],
        "criteria": len(criteria),
        "k": k,
        "seed": seed,
        "runs": runs,
        "per_criterion": per_criterion,
        "passed_run1": first["passed"],
        "failed_run1": first["failed"],
        "unverified_run1": first["unverified"],
        "pass_rate_verifiable_run1": first["pass_rate_verifiable"],
        "unverifiable_share_run1": first["unverifiable_share"],
        "weighted_pass_rate_verifiable_run1": (
            passed_weights / verifiable_weights if verifiable_weights else None
        ),
        "mean_pass_at_1": mean_pass_1,
        "mean_pass_at_k": mean_pass_k,
        "verifiable_criteria": len(verifiable),
    }


def run_mka_target(agent, tasks, k=5, seed=0):
    """Run one agent over all MKA tasks. Returns the full target report."""
    task_reports = [run_mka_task(agent, task, k=k, seed=seed) for task in tasks]
    total_criteria = sum(t["criteria"] for t in task_reports)
    total_verifiable = sum(t["verifiable_criteria"] for t in task_reports)
    mean_pass_1 = [
        t["mean_pass_at_1"] for t in task_reports if t["mean_pass_at_1"] != "unverified"
    ]
    mean_pass_k = [
        t["mean_pass_at_k"] for t in task_reports if t["mean_pass_at_k"] != "unverified"
    ]
    return {
        "tasks": task_reports,
        "task_count": len(task_reports),
        "total_criteria": total_criteria,
        "verifiable_criteria": total_verifiable,
        "mean_pass_at_1": (
            sum(mean_pass_1) / len(mean_pass_1) if mean_pass_1 else "unverified"
        ),
        "mean_pass_at_k": (
            sum(mean_pass_k) / len(mean_pass_k) if mean_pass_k else "unverified"
        ),
        "check_level_judgments": sum(
            t["criteria"] * t["k"] for t in task_reports
        ),
    }
