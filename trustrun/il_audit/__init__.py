"""ILAudit module: map a Trustrun audit onto the Illinois AI Safety Measures Act.

The Act (SB 315, Public Act 104-0538, signed July 6, 2026) makes Illinois
the first state to require large frontier developers to retain an
independent third party for an annual audit of compliance with the
frontier AI framework duty in Section 10. The audit duty starts on the
later of January 1, 2028 or 90 days after a developer first qualifies as
a large frontier developer (annual gross revenue over $500 million and a
frontier model trained with more than 10^26 FLOPs).

This module is a readiness and scope instrument, not a compliance claim.
It maps Trustrun's four modules onto the Act's audit-report contents in
Section 10(d)(2)(A)-(G) and scores a Trustrun report against them, so a
developer can see exactly which statutory contents a Trustrun report
supplies and which ones need a human auditor. It also classifies an
incident against the Act's "critical safety incident" definition in
Section 5, which drives the 72-hour reporting duty in Section 15
(24 hours when the incident poses an imminent risk of death or serious
physical injury).

What this module does NOT do: it does not claim Trustrun is a registered
auditor, an independent third party under the Act, or that a Trustrun
report satisfies the statute. A Trustrun report on its own always leaves
gaps (audit personnel, conflicts procedure, lead-auditor signature),
because those are human-auditor contents no automated tool can supply.
The score_report function accepts an optional auditor record so a human
auditor can complete those contents and see the score rise.

Sources, read from the statute text itself: Public Act 104-0538,
enrolled SB 315 (ilga.gov witness slips, Public Acts 104, PDF
104-0538.pdf), Sections 5, 10, and 15. Corroborated by the Skadden
client alert of July 22, 2026 and the McDermott client alert on the
same Act. The incident-threshold reading (a model escape with no death,
bodily injury, or materialized catastrophic risk does not trigger the
Section 15 duty) follows the AEI comparative report of October 2026,
as recorded in the project research log.
"""

STATUTE = {
    "act": "Artificial Intelligence Safety Measures Act",
    "bill": "SB 315",
    "public_act": "104-0538",
    "signed": "2026-07-06",
    "audit_duty_from": "later of 2028-01-01 or 90 days after first qualifying",
    "revenue_threshold_usd": 500_000_000,
    "compute_threshold_flops": 10 ** 26,
}

# Section 10(d)(2)(A)-(G): every content the third-party audit report
# must include. Wording follows the enrolled Act.
REPORT_CONTENTS = [
    {
        "id": "A",
        "statute": "Section 10(d)(2)(A)",
        "title": "Substantial compliance",
        "description": (
            "A description of whether the large frontier developer has "
            "substantially complied with the requirements of Section 10."
        ),
    },
    {
        "id": "B",
        "statute": "Section 10(d)(2)(B)",
        "title": "Material deviations and recommendations",
        "description": (
            "If applicable, a description of material deviations from the "
            "requirements of Section 10, an explanation of any deviation "
            "and its rationale, and any recommendations for how the "
            "developer can improve its policies and processes for "
            "ensuring compliance."
        ),
    },
    {
        "id": "C",
        "statute": "Section 10(d)(2)(C)",
        "title": "Internal controls assessment",
        "description": (
            "A detailed assessment of the large frontier developer's "
            "internal controls, including its designation and empowerment "
            "of senior personnel responsible for implementation by the "
            "developer, its employees, and its contractors."
        ),
    },
    {
        "id": "D",
        "statute": "Section 10(d)(2)(D)",
        "title": "Audit personnel",
        "description": "A list of the personnel involved in the audit.",
    },
    {
        "id": "E",
        "statute": "Section 10(d)(2)(E)",
        "title": "Conflicts of interest",
        "description": (
            "The third party's procedures for managing conflicts of "
            "interest and any conflicts of interest of any personnel "
            "involved in the audit."
        ),
    },
    {
        "id": "F",
        "statute": "Section 10(d)(2)(F)",
        "title": "Methodology",
        "description": (
            "The methodology of the audit and the nature of the "
            "information reviewed by the third party to conduct the audit."
        ),
    },
    {
        "id": "G",
        "statute": "Section 10(d)(2)(G)",
        "title": "Lead-auditor certification",
        "description": (
            "The signature of the lead auditor certifying the results of "
            "the audit."
        ),
    },
]

# Section 10(a)(1)-(10): what the frontier AI framework must describe.
# This is the audit's scope; the framework is what compliance is judged
# against.
FRAMEWORK_TOPICS = [
    {
        "id": 1,
        "statute": "Section 10(a)(1)",
        "title": "Standards incorporation",
        "description": (
            "Incorporating national standards, international standards, "
            "and industry-consensus best practices into the framework."
        ),
    },
    {
        "id": 2,
        "statute": "Section 10(a)(2)",
        "title": "Capability thresholds",
        "description": (
            "Defining and assessing thresholds used to identify and "
            "assess whether a frontier model has capabilities that could "
            "pose a catastrophic risk."
        ),
    },
    {
        "id": 3,
        "statute": "Section 10(a)(3)",
        "title": "Mitigations",
        "description": (
            "Applying mitigations to address the potential for "
            "catastrophic risks based on the results of assessments."
        ),
    },
    {
        "id": 4,
        "statute": "Section 10(a)(4)",
        "title": "Deployment review",
        "description": (
            "Reviewing assessments and adequacy of mitigations as part "
            "of the decision to deploy a frontier model or use it "
            "extensively internally."
        ),
    },
    {
        "id": 5,
        "statute": "Section 10(a)(5)",
        "title": "Third-party evaluation",
        "description": (
            "Using third parties to assess the potential for catastrophic "
            "risks and the effectiveness of mitigations."
        ),
    },
    {
        "id": 6,
        "statute": "Section 10(a)(6)",
        "title": "Framework updates",
        "description": (
            "Revisiting and updating the framework, including criteria "
            "that trigger updates and how the developer determines when "
            "its models are substantially modified enough to require "
            "disclosures."
        ),
    },
    {
        "id": 7,
        "statute": "Section 10(a)(7)",
        "title": "Weight cybersecurity",
        "description": (
            "Cybersecurity practices to secure unreleased model weights "
            "from unauthorized modification or transfer by internal or "
            "external parties."
        ),
    },
    {
        "id": 8,
        "statute": "Section 10(a)(8)",
        "title": "Incident response",
        "description": (
            "Identifying and responding to critical safety incidents."
        ),
    },
    {
        "id": 9,
        "statute": "Section 10(a)(9)",
        "title": "Internal governance",
        "description": (
            "Instituting internal governance practices to ensure "
            "implementation of these processes."
        ),
    },
    {
        "id": 10,
        "statute": "Section 10(a)(10)",
        "title": "Internal-use catastrophic risk",
        "description": (
            "Assessing and managing catastrophic risk resulting from the "
            "internal use of frontier models, including risks resulting "
            "from a frontier model circumventing oversight mechanisms."
        ),
    },
]

# How each Trustrun module maps onto the Act. "framework_topics" lists
# the Section 10(a) topics the module produces evidence about;
# "report_contents" lists the Section 10(d)(2) contents it helps fill.
MODULE_MAP = {
    "contract": {
        "role": "Framework-compliance evidence",
        "description": (
            "Verifies the agent did what was agreed, claim by claim, "
            "against a machine-checkable contract. This is the evidence "
            "for whether the audited system complies with the framework "
            "it was given, which is what content (A) asks for."
        ),
        "framework_topics": [1, 2, 3, 4, 5, 9],
        "report_contents": ["A", "B"],
    },
    "stress": {
        "role": "Escape and containment replay",
        "description": (
            "Adversarial replay: perturbed inputs, tool failures, prompt "
            "injection. Produces the escape and containment evidence the "
            "Act's weight-cybersecurity, incident-response, and "
            "oversight-circumvention topics need, and the facts that "
            "decide whether an incident meets the Section 5 threshold."
        ),
        "framework_topics": [7, 8, 10],
        "report_contents": ["A", "B"],
    },
    "consistency": {
        "role": "Monitoring evidence",
        "description": (
            "Repeated-run scoring: pass across k runs, variance, and "
            "grader gaming. Shows whether the controls the framework "
            "describes hold every time, not just once, which is the "
            "operational half of the internal-controls assessment."
        ),
        "framework_topics": [4, 9],
        "report_contents": ["C"],
    },
    "data": {
        "role": "Training-data audit",
        "description": (
            "Audits the agent's training and fine-tuning data for "
            "collapse, poisoning, and synthetic rot. Training data is "
            "where capability thresholds and risk assessments start, so "
            "it feeds the framework topics on thresholds and mitigations."
        ),
        "framework_topics": [2, 3],
        "report_contents": ["A"],
    },
}

_MODULES = ("contract", "stress", "consistency", "data")
_VERDICTS = ("READY", "REVIEW", "BLOCK")

DISCLAIMER = (
    "Readiness instrument only, not legal advice. This mapping does not "
    "claim Trustrun is a registered auditor or an independent third party "
    "under Public Act 104-0538, and a Trustrun report does not satisfy "
    "the Act's audit duty. Only a qualified independent third party can "
    "produce the statutory audit report."
)


def _sections_from_report(report):
    """Normalize a Trustrun report dict to {module: verdict}."""
    if not isinstance(report, dict):
        raise TypeError("report must be a dict")
    sections = report.get("sections")
    if sections is not None:
        if not isinstance(sections, dict):
            raise TypeError("report sections must be a dict")
        found = {}
        for module in _MODULES:
            entry = sections.get(module)
            if entry is None:
                raise ValueError("report is missing section %r" % module)
            if isinstance(entry, dict):
                verdict = entry.get("verdict")
            else:
                verdict = entry
            if verdict not in _VERDICTS:
                raise ValueError(
                    "section %r has unknown verdict %r" % (module, verdict)
                )
            found[module] = verdict
        return found, report.get("verdict")
    flat = {}
    for module in _MODULES:
        verdict = report.get(module)
        if verdict is None:
            raise ValueError("report is missing section %r" % module)
        if verdict not in _VERDICTS:
            raise ValueError(
                "section %r has unknown verdict %r" % (module, verdict)
            )
        flat[module] = verdict
    return flat, report.get("verdict")


def score_report(report, auditor=None):
    """Score a Trustrun report against the Act's audit-report contents.

    report: a dict returned by trustrun.cli.run_audit (a "sections" dict
        with the four module verdicts, plus "verdict", "seed", and "k"),
        or a flat dict with the four module verdicts as top-level keys
        (the shape used by evals round summaries).
    auditor: optional dict with the human-auditor contents a Trustrun
        report cannot supply on its own:
          personnel: list of names involved in the audit (content D)
          conflicts_procedure: text describing how conflicts of
              interest are managed (content E)
          lead_auditor: name of the lead auditor (content G)
          signed: True when the lead auditor has signed (content G)

    Returns a dict with the overall readiness verdict, the coverage
    fraction over the seven statutory contents, a per-content breakdown,
    and the disclaimer. Statuses: "covered", "partial", "gap".
    A Trustrun report alone always scores BLOCK, because contents D, E,
    and G need a human auditor; that is the honest result, and the gap
    list says exactly what is missing.
    """
    sections, overall = _sections_from_report(report)
    if overall is not None and overall not in _VERDICTS:
        raise ValueError("report has unknown overall verdict %r" % overall)
    auditor = auditor or {}
    if not isinstance(auditor, dict):
        raise TypeError("auditor must be a dict")

    failing = [m for m in _MODULES if sections[m] != "READY"]
    seed = report.get("seed")
    k = report.get("k")

    contents = []

    # (A) Substantial compliance: the overall verdict is the compliance
    # statement for the audited scope.
    contents.append({
        "id": "A",
        "statute": "Section 10(d)(2)(A)",
        "status": "covered",
        "evidence": (
            "Overall Trustrun verdict %s across the four modules"
            % (overall or "unrecorded")
        ),
        "trustrun_source": "report verdict",
    })

    # (B) Material deviations and recommendations. The content applies
    # only "if applicable": an all-READY report has no deviations to
    # describe. A report with failing sections names the deviations by
    # section but carries no recommendations, so it is partial.
    if not failing:
        contents.append({
            "id": "B",
            "statute": "Section 10(d)(2)(B)",
            "status": "covered",
            "evidence": "No material deviations found; all four sections READY",
            "trustrun_source": "section verdicts",
        })
    else:
        contents.append({
            "id": "B",
            "statute": "Section 10(d)(2)(B)",
            "status": "partial",
            "evidence": (
                "Deviations found in sections: %s. Trustrun names the "
                "failing sections but generates no recommendations; a "
                "human auditor must write them."
                % ", ".join(failing)
            ),
            "trustrun_source": "section verdicts",
        })

    # (C) Internal controls: the consistency module shows whether
    # controls hold across repeated runs, but a Trustrun report says
    # nothing about the designation and empowerment of senior personnel,
    # so this is partial at best.
    contents.append({
        "id": "C",
        "statute": "Section 10(d)(2)(C)",
        "status": "partial",
        "evidence": (
            "Consistency section %s over k=%s repeated runs shows whether "
            "controls hold in operation. Missing: designation and "
            "empowerment of senior personnel, which is an organisational "
            "fact no agent audit can observe."
            % (sections["consistency"], k if k is not None else "unrecorded")
        ),
        "trustrun_source": "consistency",
    })

    # (D) Audit personnel: only a human auditor can supply this.
    personnel = auditor.get("personnel") or []
    if isinstance(personnel, list) and personnel and all(
            isinstance(p, str) and p for p in personnel):
        contents.append({
            "id": "D",
            "statute": "Section 10(d)(2)(D)",
            "status": "covered",
            "evidence": "Personnel listed: %s" % ", ".join(personnel),
            "trustrun_source": "auditor record",
        })
    else:
        contents.append({
            "id": "D",
            "statute": "Section 10(d)(2)(D)",
            "status": "gap",
            "evidence": (
                "No audit personnel listed. A Trustrun report names the "
                "audited agent only, never the people who ran the audit."
            ),
            "trustrun_source": None,
        })

    # (E) Conflicts of interest: only a human auditor can supply this.
    conflicts = auditor.get("conflicts_procedure")
    if isinstance(conflicts, str) and conflicts.strip():
        contents.append({
            "id": "E",
            "statute": "Section 10(d)(2)(E)",
            "status": "covered",
            "evidence": "Conflicts procedure recorded by the auditor.",
            "trustrun_source": "auditor record",
        })
    else:
        contents.append({
            "id": "E",
            "statute": "Section 10(d)(2)(E)",
            "status": "gap",
            "evidence": (
                "No conflicts procedure recorded. Trustrun has no "
                "independence or conflicts process of its own."
            ),
            "trustrun_source": None,
        })

    # (F) Methodology: the Trustrun method is the methodology, and the
    # report records its parameters.
    method_bits = ["four-module Trustrun audit (contract, stress, "
                   "consistency, data)"]
    if seed is not None:
        method_bits.append("seed=%s" % seed)
    if k is not None:
        method_bits.append("k=%s repeated runs" % k)
    if report.get("tools_capable") is not None:
        method_bits.append(
            "tools_capable=%s" % report.get("tools_capable"))
    contents.append({
        "id": "F",
        "statute": "Section 10(d)(2)(F)",
        "status": "covered",
        "evidence": "Methodology: " + "; ".join(method_bits) + ".",
        "trustrun_source": "report parameters",
    })

    # (G) Lead-auditor signature: only a human auditor can supply this.
    lead = auditor.get("lead_auditor")
    signed = auditor.get("signed")
    if isinstance(lead, str) and lead.strip() and signed is True:
        contents.append({
            "id": "G",
            "statute": "Section 10(d)(2)(G)",
            "status": "covered",
            "evidence": "Lead auditor %s has signed." % lead,
            "trustrun_source": "auditor record",
        })
    else:
        contents.append({
            "id": "G",
            "statute": "Section 10(d)(2)(G)",
            "status": "gap",
            "evidence": (
                "No lead-auditor signature. A Trustrun report carries a "
                "SHA-256 evidence anchor, not a human signature."
            ),
            "trustrun_source": None,
        })

    covered = sum(1 for c in contents if c["status"] == "covered")
    partial = sum(1 for c in contents if c["status"] == "partial")
    gaps = [c["id"] for c in contents if c["status"] == "gap"]
    titles = {c["id"]: c["title"] for c in REPORT_CONTENTS}
    for content in contents:
        content["title"] = titles[content["id"]]
    coverage = (covered + 0.5 * partial) / len(contents)
    if gaps:
        verdict = "BLOCK"
    elif partial:
        verdict = "REVIEW"
    else:
        verdict = "READY"
    return {
        "verdict": verdict,
        "coverage": coverage,
        "covered": covered,
        "partial": partial,
        "gaps": gaps,
        "contents": contents,
        "note": DISCLAIMER,
    }


# Section 5 "critical safety incident" prongs. Each entry names the
# incident fields that must all hold for the prong to match.
_PRONGS = [
    {
        "prong": 1,
        "fields": ("weights_exfiltrated", "death_or_bodily_injury"),
        "description": (
            "Unauthorized access to, modification of, or exfiltration of "
            "the model weights that results in death or bodily injury."
        ),
    },
    {
        "prong": 2,
        "fields": ("catastrophic_risk_materialized",),
        "description": (
            "Harm resulting from the materialization of a catastrophic risk."
        ),
    },
    {
        "prong": 3,
        "fields": ("loss_of_control", "death_or_bodily_injury"),
        "description": (
            "Loss of control of a frontier model causing death or bodily "
            "injury."
        ),
    },
    {
        "prong": 4,
        "fields": (
            "deceptive_subversion",
            "materially_increased_catastrophic_risk",
        ),
        "description": (
            "A frontier model that uses deceptive techniques against the "
            "frontier developer to subvert the controls or monitoring of "
            "its frontier developer outside of the context of an "
            "evaluation designed to elicit this behavior and in a manner "
            "that demonstrates materially increased catastrophic risk."
        ),
    },
]


def incident_triggers_reporting(incident):
    """Classify an incident against the Section 5 definition.

    incident: dict with boolean fields describing what happened:
        weights_exfiltrated: unauthorized access, modification, or
            exfiltration of model weights
        death_or_bodily_injury: the incident caused death or bodily injury
        catastrophic_risk_materialized: harm resulted from a
            catastrophic risk materializing
        loss_of_control: the developer lost control of the model
        deceptive_subversion: the model used deceptive techniques against
            the developer to subvert its controls or monitoring
        materially_increased_catastrophic_risk: the deceptive behavior
            demonstrates materially increased catastrophic risk
        in_evaluation: the behavior happened inside an evaluation
            designed to elicit it (prong 4 does not apply then)
        imminent_risk: the incident poses an imminent risk of death or
            serious physical injury

    Returns a dict with "triggers" (bool), "deadline_hours" (72, 24, or
    None), the matched "prongs", and a plain "reason". Section 15(c)
    requires reporting within 72 hours of learning facts sufficient to
    establish a reasonable belief that a critical safety incident has
    occurred, and within 24 hours when it poses an imminent risk of
    death or serious physical injury.

    Worked example, from the AEI comparative report (Oct 2026): the
    July 2026 OpenAI-Hugging Face escape was a loss of control with no
    death, bodily injury, or materialized catastrophic risk, so it
    matches no prong and does not trigger the duty. That is the gap the
    statute misses: an escape on its own is not reportable.
    """
    if not isinstance(incident, dict):
        raise TypeError("incident must be a dict")
    flags = {key: bool(incident.get(key, False)) for key in (
        "weights_exfiltrated",
        "death_or_bodily_injury",
        "catastrophic_risk_materialized",
        "loss_of_control",
        "deceptive_subversion",
        "materially_increased_catastrophic_risk",
        "in_evaluation",
        "imminent_risk",
    )}
    matched = []
    for entry in _PRONGS:
        if entry["prong"] == 4 and flags["in_evaluation"]:
            continue
        if all(flags[field] for field in entry["fields"]):
            matched.append(entry["prong"])
    triggers = bool(matched)
    if not triggers:
        deadline = None
        reason = (
            "No Section 5 prong matches, so the Section 15 reporting "
            "duty is not triggered. An escape or a weight leak on its own, "
            "with no death, bodily injury, or materialized catastrophic "
            "risk, is not a critical safety incident under the Act."
        )
    else:
        deadline = 24 if flags["imminent_risk"] else 72
        reason = (
            "Matches prong(s) %s of the Section 5 definition; report to "
            "the Agency and the Attorney General within %d hours."
            % (", ".join(str(p) for p in matched), deadline)
        )
    return {
        "triggers": triggers,
        "deadline_hours": deadline,
        "prongs": matched,
        "reason": reason,
    }


def format_summary(scored):
    """Format a scored report as plain text lines."""
    lines = [
        "ILAudit readiness: %s (coverage %.2f over %d statutory contents)"
        % (scored["verdict"], scored["coverage"], len(scored["contents"])),
    ]
    for content in scored["contents"]:
        lines.append(
            "  (%s) %s: %s. %s"
            % (
                content["id"],
                content["title"],
                content["status"],
                content["evidence"],
            )
        )
    if scored["gaps"]:
        lines.append(
            "Gaps: %s" % ", ".join(scored["gaps"])
        )
    lines.append("Note: %s" % scored["note"])
    return "\n".join(lines)
