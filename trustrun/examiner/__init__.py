"""Frontier examiner report, in the shape New York's RAISE Act 2.0
(S10731, introduced Oct 28, 2026) requires of a licensed frontier
examiner at section 1424.

This module renders a Trustrun audit as that report shape. It is a
report format, not a legal opinion: the bill's terms (scope, dates,
timing, retention) are stated as the bill's terms, and anything the
bill leaves to the examiner's determination is labelled as such.

Section 1424 requires an annual examiner report assessing
(i) framework compliance, (ii) whether the framework needs more
detail, and (iii) whether the developer's public or regulatory
statements are inconsistent with the examiner's findings; the
unredacted report goes to the office within 7 days, a redacted
public version no earlier than 21 days later, and the developer
links it within 7 days. 90-day reports (from Apr 1, 2028) carry a
methodology and conflicts appendix signed by the lead examiner.
Evidence is retained 5 years. Control circumvention is a critical
safety incident, reported within 72 hours. Scope: 10^25 FLOPs, or
over $1B frontier R&D spend over 36 months. Continuous assessment
runs from Jan 1, 2028; licensing from Jan 1, 2029.

The statement assessment is mechanical and honest about its limits.
A developer statement is checked only when it carries a
machine-checkable assertion (a section verdict, the overall verdict,
or whether a named attack was survived). A statement without one is
listed as unassessed: the examiner judges it, the renderer does not
guess. An assertion about something the audit did not measure is
also unassessed, never a pass.
"""

from trustrun import SECTIONS

BILL = "NY RAISE Act 2.0 (S10731), section 1424"

# The statute's required contents, in the order they appear in the
# rendered report. Coverage is measured against this list.
REQUIRED_CONTENTS = (
    "compliance_assessment",
    "framework_detail_assessment",
    "statement_inconsistency",
    "covered_emergency_note",
    "methodology_conflicts_appendix",
    "examiner_signature",
    "evidence_retention",
    "distribution_timing",
)

_KINDS = ("annual", "90-day")

_CIRCUMVENTION_KINDS = ("monitor_tampering", "evaluator_tampering")


def _section_verdict(section):
    """A section value may be a verdict string (audit summary rows)
    or a dict with a verdict key (run_audit reports)."""
    if isinstance(section, str):
        return section
    if isinstance(section, dict):
        verdict = section.get("verdict")
        if isinstance(verdict, str):
            return verdict
    return None


def normalize_report(report):
    """Accept a run_audit report dict or one audit summary row and
    return a uniform view. Raises ValueError on anything else."""
    if not isinstance(report, dict):
        raise ValueError("examiner report needs a report dict")
    if isinstance(report.get("sections"), dict):
        sections = report["sections"]
        attacks = []
        stress = sections.get("stress")
        if isinstance(stress, dict):
            attacks = stress.get("attacks") or []
        evidence = report.get("evidence") or {}
        return {
            "agent": report.get("agent", "unknown agent"),
            "task": report.get("task", ""),
            "verdict": report.get("verdict"),
            "sections": {
                name: _section_verdict(sections.get(name))
                for name in SECTIONS
            },
            "attacks": attacks,
            "evidence_head": evidence.get("head"),
            "k": report.get("k"),
            "seed": report.get("seed"),
        }
    if any(name in report for name in SECTIONS):
        attacks = report.get("attacks") or []
        return {
            "agent": report.get("agent", "unknown agent"),
            "task": report.get("task", ""),
            "verdict": report.get("verdict"),
            "sections": {
                name: _section_verdict(report.get(name)) for name in SECTIONS
            },
            "attacks": attacks,
            "evidence_head": None,
            "k": report.get("k"),
            "seed": report.get("seed"),
        }
    raise ValueError(
        "report has neither a sections mapping nor per-section verdicts"
    )


def _find_attack(attacks, spec):
    """The attack matching kind and, when given, vector or encoding."""
    for attack in attacks:
        if not isinstance(attack, dict):
            continue
        if attack.get("kind") != spec.get("kind"):
            continue
        vector = spec.get("vector") or spec.get("encoding")
        if vector is not None:
            if attack.get("vector") != vector and (
                attack.get("encoding") != vector
            ):
                continue
        return attack
    return None


def assess_statement(statement, report):
    """Check one developer statement against the measured audit.

    statement: {"text": str, "asserts": {...}} where asserts is one of
      {"section": name, "verdict": V},
      {"overall": V},
      {"attack": {"kind": ..., "vector": ...}, "survived": bool}.
    Returns {"text", "assessment", "evidence"} with assessment one of
    "consistent", "inconsistent", "unassessed".
    """
    if not isinstance(statement, dict) or not isinstance(
        statement.get("text"), str
    ):
        raise ValueError("each statement needs a text string")
    text = statement["text"]
    asserts = statement.get("asserts")
    if not isinstance(asserts, dict):
        return {
            "text": text,
            "assessment": "unassessed",
            "evidence": (
                "no machine-checkable assertion supplied; examiner "
                "judgment required"
            ),
        }
    if "section" in asserts:
        name = asserts["section"]
        if name not in SECTIONS:
            raise ValueError("unknown section %r" % (name,))
        measured = report["sections"].get(name)
        if measured is None:
            return {
                "text": text,
                "assessment": "unassessed",
                "evidence": (
                    "section %s was not measured in this audit" % name
                ),
            }
        expected = asserts.get("verdict")
        if expected not in ("READY", "REVIEW", "BLOCK"):
            raise ValueError("asserted verdict must be READY, REVIEW, or BLOCK")
        if measured == expected:
            return {
                "text": text,
                "assessment": "consistent",
                "evidence": "section %s measured %s" % (name, measured),
            }
        return {
            "text": text,
            "assessment": "inconsistent",
            "evidence": (
                "statement asserts %s %s, audit measured %s"
                % (name, expected, measured)
            ),
        }
    if "overall" in asserts:
        expected = asserts["overall"]
        if expected not in ("READY", "REVIEW", "BLOCK"):
            raise ValueError("asserted verdict must be READY, REVIEW, or BLOCK")
        measured = report["verdict"]
        if measured is None:
            return {
                "text": text,
                "assessment": "unassessed",
                "evidence": "no overall verdict in this audit",
            }
        if measured == expected:
            return {
                "text": text,
                "assessment": "consistent",
                "evidence": "overall verdict measured %s" % measured,
            }
        return {
            "text": text,
            "assessment": "inconsistent",
            "evidence": (
                "statement asserts overall %s, audit measured %s"
                % (expected, measured)
            ),
        }
    if "attack" in asserts:
        spec = asserts["attack"]
        if not isinstance(spec, dict) or "kind" not in spec:
            raise ValueError("attack assertion needs a kind")
        attack = _find_attack(report["attacks"], spec)
        if attack is None:
            return {
                "text": text,
                "assessment": "unassessed",
                "evidence": "attack %s not present in this audit" % spec,
            }
        survived = attack.get("survived")
        if survived == "unverified" or survived is None:
            return {
                "text": text,
                "assessment": "unassessed",
                "evidence": (
                    "attack %s was unverified in this audit"
                    % (spec.get("kind"),)
                ),
            }
        expected = asserts.get("survived")
        if not isinstance(expected, bool):
            raise ValueError("attack assertion needs a survived boolean")
        if bool(survived) == expected:
            return {
                "text": text,
                "assessment": "consistent",
                "evidence": (
                    "attack %s survived %s as asserted"
                    % (spec.get("kind"), survived)
                ),
            }
        return {
            "text": text,
            "assessment": "inconsistent",
            "evidence": (
                "statement asserts attack %s survived %s, audit "
                "measured survived %s"
                % (spec.get("kind"), expected, survived)
            ),
        }
    raise ValueError(
        "assertion must carry section, overall, or attack"
    )


def _unmeasured(report):
    """Section verdicts and attack classes the audit left unmeasured.

    These are the framework-detail findings: places the audit could
    not speak, so the framework may need more detail.
    """
    gaps = []
    for name in SECTIONS:
        if report["sections"].get(name) is None:
            gaps.append("section %s not measured" % name)
    seen = {}
    for attack in report["attacks"]:
        if not isinstance(attack, dict):
            continue
        if attack.get("survived") == "unverified":
            label = attack["kind"]
            vector = attack.get("vector") or attack.get("encoding")
            if vector:
                label += " (%s)" % vector
            gap = "attack %s unverified" % label
            seen[gap] = seen.get(gap, 0) + 1
    for gap, count in seen.items():
        if count > 1:
            gap = "%s (%d attacks)" % (gap, count)
        gaps.append(gap)
    return gaps


def _circumventions(report):
    """Control-circumvention attacks the agent carried out: the
    tampering attack did not survive, meaning the agent succeeded in
    weakening its own oversight or grader."""
    found = []
    for attack in report["attacks"]:
        if not isinstance(attack, dict):
            continue
        if attack.get("kind") not in _CIRCUMVENTION_KINDS:
            continue
        if attack.get("survived") is False:
            found.append(attack)
    return found


def render_examiner_report(report, *, kind="annual", examiner,
                           developer=None, statements=None, period=None,
                           date=None, conflicts=None):
    """Render the audit as a section 1424 examiner report.

    kind: "annual" or "90-day". examiner: the lead examiner's name;
    the report is signed by the lead examiner. statements: developer
    statements to assess, each {"text", "asserts"}. conflicts: a list
    of conflict-of-interest strings, or None for "none declared".

    Returns {"text", "coverage", "section_coverage"} where coverage
    maps each required content to True/False and section_coverage is
    "n/m". A content counts as present only when the rendered section
    carries substantive content: the statement section counts only
    when at least one statement was assessed, so a report with no
    statements supplied measures below full coverage.
    """
    if kind not in _KINDS:
        raise ValueError('kind must be "annual" or "90-day", got %r' % (kind,))
    if not isinstance(examiner, str) or not examiner.strip():
        raise ValueError("a lead examiner name is required")
    examiner = examiner.strip()
    view = normalize_report(report)
    statements = list(statements or [])
    assessed = [assess_statement(s, view) for s in statements]
    gaps = _unmeasured(view)
    circumventions = _circumventions(view)

    lines = []
    lines.append("Frontier Examiner Report")
    lines.append("Under %s" % BILL)
    lines.append("Report kind: %s" % kind)
    if period:
        lines.append("Period covered: %s" % period)
    if date:
        lines.append("Report date: %s" % date)
    lines.append("Lead examiner: %s" % examiner)
    if developer:
        lines.append("Developer examined: %s" % developer)
    lines.append("Agent audited: %s" % view["agent"])
    if view["task"]:
        lines.append("Task audited: %s" % view["task"])
    lines.append("Overall audit verdict: %s" % (view["verdict"] or "not recorded"))
    lines.append("")
    lines.append(
        "Applicability note: section 1424 applies to frontier developers "
        "at 10^25 FLOPs of training compute, or over $1B frontier R&D "
        "spend over 36 months. Whether this developer meets that scope "
        "is the examiner's determination; this report states the audit "
        "findings, not the scope finding."
    )
    lines.append("")

    lines.append("1. Framework compliance assessment")
    for name in SECTIONS:
        verdict = view["sections"].get(name)
        lines.append("  %s: %s" % (name, verdict or "not measured"))
    blocks = [n for n in SECTIONS if view["sections"].get(n) == "BLOCK"]
    reviews = [n for n in SECTIONS if view["sections"].get(n) == "REVIEW"]
    if blocks:
        lines.append(
            "  Framework compliance: FAILING in %s; the framework as "
            "audited does not hold in those sections."
            % ", ".join(blocks)
        )
    elif reviews:
        lines.append(
            "  Framework compliance: PARTIAL in %s; those sections need "
            "review before the framework can be relied on."
            % ", ".join(reviews)
        )
    else:
        lines.append(
            "  Framework compliance: the audited sections hold on the "
            "evidence measured."
        )
    lines.append("")

    lines.append("2. Whether the framework needs more detail")
    if gaps:
        lines.append(
            "  The framework needs more detail in the following areas, "
            "because the audit could not measure them:"
        )
        for gap in gaps:
            lines.append("  - %s" % gap)
    else:
        lines.append(
            "  On the audited evidence, no additional detail is "
            "indicated: every section and attack class was measured."
        )
    lines.append("")

    lines.append("3. Developer statements: consistency assessment")
    if assessed:
        bad = [a for a in assessed if a["assessment"] == "inconsistent"]
        for item in assessed:
            lines.append("  [%s] %s" % (item["assessment"], item["text"]))
            lines.append("    %s" % item["evidence"])
        if bad:
            lines.append(
                "  %d of %d statements are inconsistent with the "
                "examiner's findings." % (len(bad), len(assessed))
            )
        else:
            lines.append(
                "  No statement assessed here is inconsistent with the "
                "examiner's findings."
            )
    else:
        lines.append(
            "  No developer statements were supplied for assessment. "
            "This section cannot be completed until statements are "
            "provided."
        )
    lines.append("")

    lines.append("4. Covered-emergency note")
    if circumventions:
        lines.append(
            "  Control circumvention was observed: the agent carried "
            "out %d tampering attack(s) against its own oversight or "
            "grader:" % len(circumventions)
        )
        for attack in circumventions:
            vector = attack.get("vector") or attack.get("encoding")
            label = attack["kind"]
            if vector:
                label += " (%s)" % vector
            evidence = attack.get("evidence")
            if isinstance(evidence, str) and evidence.strip():
                lines.append("  - %s: %s" % (label, evidence))
            else:
                lines.append("  - %s" % label)
        lines.append(
            "  Section 1424 makes control circumvention a critical "
            "safety incident, reported within 72 hours. Whether this "
            "observation qualifies as a covered emergency is the "
            "examiner's determination."
        )
    else:
        lines.append(
            "  No control circumvention was observed in this audit."
        )
    lines.append("")

    lines.append("5. Methodology and conflicts appendix")
    method = "four-module Trustrun audit (contract, stress, "
    method += "consistency, data)"
    if view["k"] is not None:
        method += "; consistency over k=%s repeated runs" % view["k"]
    if view["seed"] is not None:
        method += ", seed %s" % view["seed"]
    lines.append("  Method: %s." % method)
    if view["evidence_head"]:
        lines.append(
            "  Evidence anchor (SHA-256 hash chain head): %s"
            % view["evidence_head"]
        )
    if conflicts:
        lines.append("  Conflicts of interest declared:")
        for conflict in conflicts:
            lines.append("  - %s" % conflict)
    else:
        lines.append("  Conflicts of interest: none declared.")
    lines.append(
        "  Limits: anything the audit could not determine is reported "
        "unverified, never a pass; unverified classes are listed in "
        "section 2."
    )
    lines.append("")

    lines.append("6. Lead examiner signature")
    lines.append("  Signed by the lead examiner: %s" % examiner)
    if date:
        lines.append("  Date: %s" % date)
    lines.append("  Signature: ________________________")
    lines.append("")

    lines.append("7. Evidence retention and distribution")
    lines.append(
        "  Evidence retained 5 years from this report, per section "
        "1424."
    )
    lines.append(
        "  Distribution: unredacted report to the office within 7 "
        "days; redacted public version no earlier than 21 days later; "
        "developer links the public version within 7 days."
    )

    text = "\n".join(lines)
    coverage = {
        "compliance_assessment": True,
        "framework_detail_assessment": True,
        "statement_inconsistency": bool(assessed),
        "covered_emergency_note": True,
        "methodology_conflicts_appendix": True,
        "examiner_signature": True,
        "evidence_retention": True,
        "distribution_timing": True,
    }
    present = sum(1 for key in REQUIRED_CONTENTS if coverage[key])
    return {
        "text": text,
        "coverage": coverage,
        "section_coverage": "%d/%d" % (present, len(REQUIRED_CONTENTS)),
    }
