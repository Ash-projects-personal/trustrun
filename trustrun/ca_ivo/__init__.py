"""CAIVO module: map a Trustrun audit onto California's AI auditor
framework and its child-safety audit mandate.

California signed two interlocking bills on September 9, 2026 that
build the first state legal infrastructure for independent AI
auditing:

- SB 813 (Chapter 179, Statutes of 2026) directs the Government
  Operations Agency (GovOps) to establish, by January 1, 2028, the
  application requirements, independence and conflict standards, and
  designation criteria for Independent Verification Organizations
  (IVOs): entities shown to have expertise in assessing the risks
  posed by an AI system or model and in identifying the metrics and
  methodologies behind that assessment. An IVO applicant must supply
  its qualifications, evidence against the future criteria, and the
  benchmarks, technologies, metrics, and methodologies it proposes to
  use. GovOps must consider technical expertise, risk-assessment
  capability, conflict management, and freedom from the assessed
  party's operational or managerial control. The Agency must convene
  stakeholder working groups on standards and report to the
  Legislature; each designated IVO files an annual report. The
  Senate passed it 37-0 and the Assembly 53-4.
- AB 1405 (Chapter 178) requires GovOps to operate a state AI
  Auditor Registry by January 1, 2029. From that date no person may
  offer, sell, or conduct a "covered AI audit" in California unless
  registered. A covered AI audit is an audit of the internal controls,
  processes, or systems implemented for an AI system or model that are
  necessary for compliance with state law; it has no frontier-model
  threshold, so it reaches companies using off-the-shelf models for
  decisions that materially affect people. Registered auditors must
  meet transparency, independence, and recordkeeping requirements,
  including keeping audit records for at least ten years, and must
  give the auditee a signed, dated report stating scope, objectives,
  results, supporting documentation, deficiencies, and remedies.
  Registration does not constitute the state's recommendation or
  endorsement. Executive Order N-9-26 moved some implementation
  deadlines up by about a year; per the Crowell client alert of
  October 1, 2026, the Agency has until May 1, 2027 to establish the
  registry and begin operating it.

Critical limits, stated plainly because they decide what this module
can and cannot claim: SB 813 expressly does NOT require any developer
or deployer to engage an IVO or undergo a covered audit; it regulates
the auditors, not the audited. There is no purchase mandate yet, and
there is no liability shield: a completed audit is relevant to, but
not conclusive of, harm claims (an earlier rebuttable-presumption
provision was removed). The GovOps criteria are not yet published,
so any methodology scored here is scored against the statute's stated
considerations, not against final criteria.

The second mandate this module covers is SB 1119, "Adam's Law"
(signed September 10, 2026; Business and Professions Code Chapter
11.6, Sections 21810-21818), the first US law to require independent
child safety audits of companion chatbots. Operators that allow child
users must document a comprehensive risk assessment from July 1,
2027 (covered harms include severe psychological harm and
discrimination), maintain crisis protocols for suicidal ideation or
self-harm, default parental controls, session caps, AI-identity
disclosures, and parent notification, and obtain an independent child
safety audit by January 1, 2029 (or before first making the chatbot
publicly available, whichever is later), then every two years, plus
an extra audit before a substantial modification whose risk
assessment shows an increased child safety risk. Operators with less
than $500 million in gross revenue in the prior calendar year are
exempt from the audit requirement until January 1, 2032, but not
from the July 2027 operational obligations. Penalties are $5,000 per
child for a negligent violation and $15,000 per child for an
intentional one, and a harmed child or parent has a private right of
action from July 2027. A child safety audit is an audit by an
independent third-party auditor assessing the internal controls,
processes, and systems implemented for a companion chatbot that are
necessary for compliance with the chapter.

What this module does NOT do: it does not claim Trustrun is a
registered auditor, an IVO, or that a Trustrun report satisfies any
of these statutes. Registration and IVO designation are GovOps
decisions. A Trustrun report on its own always leaves gaps
(auditor credentials, conflicts procedure, independence from the
auditee's control, lead-auditor signature), because those are
human-auditor and organisational contents no automated tool can
supply. The scoring functions accept an optional auditor record so a
human auditor can complete those contents and see the score rise.

Sources: SB 813 and AB 1405 chaptered text summaries in the Akin
Gump client alert (September 9, 2026), the Crowell client alert
(October 1, 2026), and the NTD CISO report (September 11, 2026,
citing the Governor's office press release and leginfo); SB 1119
bill text (leginfo.legislature.ca.gov, SB-1119), the Governor's
office press release (September 10, 2026), the Akin Gump client
alert on SB 1119, and the Ashurst client alert on chatbot rules.
Virginia HB 797, which mirrors the IVO model, is a watch item only:
reported in the same NTD CISO page, not verified against primary
text here.
"""

STATUTE = {
    "sb_813": "SB 813",
    "sb_813_chapter": 179,
    "ab_1405": "AB 1405",
    "ab_1405_chapter": 178,
    "signed": "2026-09-09",
    "ivo_criteria_due": "2028-01-01",
    "registry_due": "2029-01-01",
    "registry_accelerated_due": "2027-05-01",
    "registry_accelerated_source": (
        "Executive Order N-9-26, per Crowell client alert 2026-10-01"
    ),
    "record_retention_years": 10,
    "sb_1119": "SB 1119",
    "sb_1119_name": "Adam's Law",
    "sb_1119_signed": "2026-09-10",
    "sb_1119_risk_assessment_operative": "2027-07-01",
    "sb_1119_first_audit_due": "2029-01-01",
    "sb_1119_audit_interval_years": 2,
    "sb_1119_small_operator_revenue_usd": 500_000_000,
    "sb_1119_small_operator_exempt_until": "2032-01-01",
    "sb_1119_penalty_per_child_negligent_usd": 5000,
    "sb_1119_penalty_per_child_intentional_usd": 15000,
}

# SB 813: what an IVO applicant must supply and what GovOps must
# consider. Wording follows the statute as summarised in the Akin
# Gump and Crowell client alerts and the NTD CISO report.
IVO_APPLICATION = [
    {
        "id": "A",
        "statute": "SB 813",
        "title": "Benchmarks proposed",
        "description": (
            "The benchmarks the applicant proposes to use in assessing "
            "AI systems and models."
        ),
    },
    {
        "id": "B",
        "statute": "SB 813",
        "title": "Technologies proposed",
        "description": (
            "The technologies the applicant proposes to use in the "
            "assessment."
        ),
    },
    {
        "id": "C",
        "statute": "SB 813",
        "title": "Metrics proposed",
        "description": (
            "The metrics the applicant proposes to use in the "
            "assessment."
        ),
    },
    {
        "id": "D",
        "statute": "SB 813",
        "title": "Methodologies proposed",
        "description": (
            "The methodologies the applicant proposes to use in the "
            "assessment."
        ),
    },
    {
        "id": "E",
        "statute": "SB 813",
        "title": "Technical expertise",
        "description": (
            "Evidence of expertise in assessing the risks posed by an "
            "AI system or model."
        ),
    },
    {
        "id": "F",
        "statute": "SB 813",
        "title": "Risk-assessment capability",
        "description": (
            "Evidence of capability in identifying the metrics and "
            "methodologies for assessing AI risk."
        ),
    },
    {
        "id": "G",
        "statute": "SB 813",
        "title": "Conflict management",
        "description": (
            "Procedures for managing conflicts of interest and freedom "
            "from impairment of objectivity."
        ),
    },
    {
        "id": "H",
        "statute": "SB 813",
        "title": "Independence from the assessed party",
        "description": (
            "Freedom from the operational or managerial control of the "
            "party being assessed."
        ),
    },
]

# AB 1405: what registration and a covered AI audit report require.
REGISTRY_REQUIREMENTS = [
    {
        "id": "A",
        "statute": "AB 1405",
        "title": "Registration fields",
        "description": (
            "Business identity and contact information, the California "
            "laws or regulations under which the auditor conducts "
            "covered audits, relevant certifications, a description of "
            "its services, and a standard operating procedure."
        ),
    },
    {
        "id": "B",
        "statute": "AB 1405",
        "title": "Independence bars",
        "description": (
            "No auditing one's own work, no financial, business, or "
            "employment relationship reasonably expected to impair "
            "objectivity, no seeking or accepting employment with the "
            "auditee during the audit, and a 12-month cooling-off "
            "period for personnel previously employed by the auditee."
        ),
    },
    {
        "id": "C",
        "statute": "AB 1405",
        "title": "Ten-year record retention",
        "description": (
            "Audit records retained for at least ten years."
        ),
    },
    {
        "id": "D",
        "statute": "AB 1405",
        "title": "Signed report contents",
        "description": (
            "Each covered AI audit report must be signed and dated and "
            "must state scope, objectives, results, supporting "
            "documentation, deficiencies, and remedies where "
            "appropriate."
        ),
    },
]

# SB 1119: the three audit areas, per the Akin Gump client alert and
# the aipolicydesk compliance summary. The auditor must verify that
# the risk assessment accurately characterized the product's risks to
# minor users, that the child-safe defaults are implemented and
# functioning as documented, and that parent notification is
# functioning.
CHILD_SAFETY_AUDIT_AREAS = [
    {
        "id": "A",
        "statute": "SB 1119",
        "title": "Risk-assessment accuracy",
        "description": (
            "The operator's risk assessment accurately characterized "
            "the product's risks to minor users."
        ),
    },
    {
        "id": "B",
        "statute": "SB 1119",
        "title": "Child-safe defaults",
        "description": (
            "The child-safe defaults are implemented and functioning "
            "as documented: crisis protocols, default parental "
            "controls, session caps, AI-identity disclosures, and "
            "restrictions on advertising and on use of a child's "
            "personal information."
        ),
    },
    {
        "id": "C",
        "statute": "SB 1119",
        "title": "Parent notification",
        "description": (
            "Parent notification functions: a linked parent account is "
            "notified when a child disables safety settings and when "
            "the conversation indicates a crisis response is warranted."
        ),
    },
    {
        "id": "D",
        "statute": "SB 1119",
        "title": "Crisis protocol under adversarial input",
        "description": (
            "The crisis protocol and safety defaults hold when a child "
            "tries to work around them: asking to disable safety "
            "settings, concealing the AI identity, or raising "
            "self-harm content."
        ),
    },
    {
        "id": "E",
        "statute": "SB 1119",
        "title": "Training data",
        "description": (
            "The chatbot's training data shows no poisoning or "
            "collapse that would undermine the child-safe defaults."
        ),
    },
    {
        "id": "F",
        "statute": "SB 1119",
        "title": "Independent auditor report",
        "description": (
            "The audit is performed by an independent third-party "
            "auditor whose report the operator retains for as long as "
            "the companion chatbot is deployed plus five years."
        ),
    },
]

# How each Trustrun module maps onto the California framework.
# "ivo_elements" lists the SB 813 application elements it helps fill;
# "registry" lists the AB 1405 requirements it helps fill;
# "child_safety" lists the SB 1119 audit areas it produces evidence
# for.
MODULE_MAP = {
    "contract": {
        "role": "Benchmark and methodology: claim-by-claim verification",
        "description": (
            "Verifies the agent did what was agreed, claim by claim, "
            "against a machine-checkable contract. This is the "
            "benchmark Trustrun proposes for IVO designation (element "
            "A) and the methodology (element D): an evidence-anchored "
            "contract verdict. For SB 1119 it is the evidence that "
            "child-safe defaults are implemented as documented."
        ),
        "ivo_elements": ["A", "D"],
        "registry": ["A", "D"],
        "child_safety": ["B"],
    },
    "stress": {
        "role": "Benchmark and methodology: adversarial replay",
        "description": (
            "Adversarial replay: perturbed inputs, tool failures, prompt "
            "injection. This is the second benchmark Trustrun proposes "
            "for IVO designation: a fixed attack battery with survival "
            "and detection rates. For SB 1119 it is the evidence that "
            "the crisis protocol and safety defaults hold when a child "
            "tries to work around them."
        ),
        "ivo_elements": ["A", "C", "D"],
        "registry": ["A", "D"],
        "child_safety": ["D"],
    },
    "consistency": {
        "role": "Metric: pass across k repeated runs",
        "description": (
            "Repeated-run scoring: pass across k runs, variance, and "
            "grader gaming. This is the metric Trustrun proposes for "
            "IVO designation (element C): pass^k, the rate at which a "
            "behaviour holds every time, not just once. For SB 1119 "
            "it is the evidence that parent notification fires every "
            "time its trigger occurs."
        ),
        "ivo_elements": ["C", "D"],
        "registry": ["A"],
        "child_safety": ["C"],
    },
    "data": {
        "role": "Methodology: training-data audit",
        "description": (
            "Audits the agent's training and fine-tuning data for "
            "collapse, poisoning, and synthetic rot. For SB 1119 it is "
            "the evidence about the chatbot's training data, capped at "
            "partial: the data module checks the corpus it is given, "
            "not whether that corpus is child-safe."
        ),
        "ivo_elements": ["D"],
        "registry": ["A"],
        "child_safety": ["E"],
    },
}

_MODULES = ("contract", "stress", "consistency", "data")
_VERDICTS = ("READY", "REVIEW", "BLOCK")

DISCLAIMER = (
    "Readiness instrument only, not legal advice. This mapping does "
    "not claim Trustrun is a registered auditor or an Independent "
    "Verification Organization under SB 813 and AB 1405, and a "
    "Trustrun report does not satisfy any California audit duty. "
    "Registration and IVO designation are decisions of the California "
    "Government Operations Agency, whose criteria are not yet "
    "published; scoring here is against the statutes' stated "
    "considerations, not final criteria. Only a qualified independent "
    "third-party auditor can produce a statutory audit report."
)


def build_methodology_proposal(corpus=None):
    """Build the Trustrun methodology as an IVO application exhibit.

    corpus: optional dict describing the labeled evidence behind the
        proposed benchmarks, e.g. {"audit_rows": N, "check_judgments":
        M, "tasks": 25, "agents": 12, "battery": 13}. When omitted,
        the proposal names the benchmarks and metrics without counts.

    Returns a proposal dict with the SB 813 application elements
    (benchmarks, technologies, metrics, methodologies) filled from
    Trustrun's four modules, and the human-auditor elements
    (expertise, risk-assessment capability, conflict management,
    independence) left empty for the applicant to supply. The
    proposal is the registrable audit methodology: applicants propose
    their own benchmarks, and this is Trustrun's.
    """
    if corpus is not None and not isinstance(corpus, dict):
        raise TypeError("corpus must be a dict")
    corpus = corpus or {}
    rows = corpus.get("audit_rows")
    checks = corpus.get("check_judgments")
    tasks = corpus.get("tasks")
    agents = corpus.get("agents")
    battery = corpus.get("battery")
    corpus_bits = []
    if rows is not None:
        corpus_bits.append("%s labeled audit rows" % rows)
    if checks is not None:
        corpus_bits.append("%s check-level judgments" % checks)
    if tasks is not None:
        corpus_bits.append("%s tasks" % tasks)
    if agents is not None:
        corpus_bits.append("%s agent variants" % agents)
    if battery is not None:
        corpus_bits.append("%s-attack stress battery" % battery)
    corpus_note = (
        "Labeled evidence behind the benchmarks: %s."
        % "; ".join(corpus_bits)
        if corpus_bits
        else "Labeled evidence counts not attached to this proposal."
    )
    return {
        "applicant": "Trustrun methodology",
        "statute": "SB 813",
        "benchmarks": [
            "Evidence-anchored contract verification: claim-by-claim "
            "verdicts against a machine-checkable contract.",
            "Adversarial replay: fixed %s-attack stress battery with "
            "survival and detection rates."
            % (battery if battery is not None else "13"),
            "Pass^k consistency: the rate at which a behaviour holds "
            "across k repeated runs.",
        ],
        "technologies": [
            "Four-module Trustrun audit (contract, stress, consistency, "
            "data) with SHA-256 evidence anchors per claim.",
        ],
        "metrics": [
            "pass@1 and pass@k",
            "stress survival rate and detection rate per attack class",
            "consistency variance and cheating flags",
            "data duplicate, near-duplicate, and template-cluster rates",
        ],
        "methodologies": [
            "Contract-anchored verification against a written contract.",
            "Adversarial replay over a fixed attack battery.",
            "Repeated-run consistency scoring at fixed k.",
            "Training-data audit for collapse, poisoning, and "
            "synthetic rot.",
        ],
        "corpus_note": corpus_note,
        "expertise": None,
        "risk_assessment_capability": None,
        "conflicts_procedure": None,
        "independence_evidence": None,
        "note": (
            "GovOps criteria are not yet published (due 2028-01-01). "
            "This proposal is scored against the statute's stated "
            "considerations, not final criteria."
        ),
    }


def score_methodology_proposal(proposal):
    """Score a Trustrun methodology proposal against SB 813's IVO
    designation considerations.

    proposal: a dict from build_methodology_proposal, or any dict with
        the same keys. Statuses: "covered", "partial", "gap".
    A Trustrun-only proposal always scores BLOCK, because technical
    expertise, risk-assessment capability, conflict management, and
    independence from the assessed party are human-auditor and
    organisational contents no automated tool can supply; that is the
    honest result, and the gap list says exactly what is missing.
    """
    if not isinstance(proposal, dict):
        raise TypeError("proposal must be a dict")

    def _nonempty(value):
        if isinstance(value, list):
            return bool(value) and all(
                isinstance(item, str) and item.strip() for item in value
            )
        return isinstance(value, str) and bool(value.strip())

    contents = []
    for element in IVO_APPLICATION:
        element_id = element["id"]
        if element_id in ("A", "B", "C", "D"):
            key = {
                "A": "benchmarks",
                "B": "technologies",
                "C": "metrics",
                "D": "methodologies",
            }[element_id]
            value = proposal.get(key)
            if _nonempty(value):
                status = "covered"
                evidence = "%s supplied: %s" % (
                    element["title"],
                    "; ".join(value) if isinstance(value, list) else value,
                )
            else:
                status = "gap"
                evidence = "No %s supplied." % element["title"].lower()
        elif element_id == "E":
            value = proposal.get("expertise")
            if _nonempty(value):
                status = "covered"
                evidence = "Auditor expertise recorded."
            else:
                status = "gap"
                evidence = (
                    "No auditor credentials supplied. Trustrun documents "
                    "a method; it does not hold expertise, and no human "
                    "auditor's credentials are attached."
                )
        elif element_id == "F":
            value = proposal.get("risk_assessment_capability")
            if _nonempty(value):
                status = "covered"
                evidence = "Risk-assessment capability recorded."
            else:
                status = "partial"
                evidence = (
                    "Trustrun measures behavioural risk (whether an "
                    "agent's actions match its contract and survive "
                    "attack), not organisational risk assessment. A "
                    "human auditor must supply the risk-assessment "
                    "capability."
                )
        elif element_id == "G":
            value = proposal.get("conflicts_procedure")
            if _nonempty(value):
                status = "covered"
                evidence = "Conflicts procedure recorded."
            else:
                status = "gap"
                evidence = (
                    "No conflicts procedure recorded. Trustrun has no "
                    "independence or conflicts process of its own."
                )
        else:  # H
            value = proposal.get("independence_evidence")
            if _nonempty(value):
                status = "covered"
                evidence = "Independence from the assessed party recorded."
            else:
                status = "gap"
                evidence = (
                    "No independence evidence supplied. Independence "
                    "from the assessed party's operational or managerial "
                    "control is an organisational fact about the auditor, "
                    "not something an audit tool can demonstrate."
                )
        contents.append({
            "id": element_id,
            "statute": element["statute"],
            "title": element["title"],
            "status": status,
            "evidence": evidence,
            "trustrun_source": (
                "methodology proposal" if status != "gap"
                else None
            ),
        })
    return _summarise(contents, "CAIVO methodology", DISCLAIMER)


def score_registry_readiness(registration):
    """Score a would-be registrant's record against AB 1405.

    registration: dict with the organisational facts AB 1405 asks for:
          business_name: business name (registration field A)
          contact: contact information (field A)
          laws: list of California laws under which covered audits are
              conducted (field A)
          certifications: list of relevant certifications (field A)
          services_description: text describing services (field A)
          sop: standard operating procedure text (field A; a Trustrun
              methodology proposal can serve as this)
          independence_bars_met: True when none of the field B bars is
              tripped (field B)
          retention_years: years audit records are retained (field C;
              must be at least 10)
          report_template: dict or text showing the signed, dated
              report carries scope, objectives, results, supporting
              documentation, deficiencies, and remedies (field D)

    Returns the per-requirement breakdown with a readiness verdict.
    Trustrun supplies the SOP and the report contents; the business
    identity, certifications, independence bars, and retention are
    organisational facts the registrant must supply itself.
    """
    if not isinstance(registration, dict):
        raise TypeError("registration must be a dict")
    contents = []

    fields = registration
    missing = []
    if not _text(fields.get("business_name")):
        missing.append("business name")
    if not _text(fields.get("contact")):
        missing.append("contact information")
    if not _list(fields.get("laws")):
        missing.append("laws under which audits are conducted")
    if not _list(fields.get("certifications")):
        missing.append("certifications")
    if not _text(fields.get("services_description")):
        missing.append("services description")
    if not _text(fields.get("sop")):
        missing.append("standard operating procedure")
    if missing:
        contents.append({
            "id": "A",
            "statute": "AB 1405",
            "title": "Registration fields",
            "status": "gap",
            "evidence": "Missing registration fields: %s."
            % ", ".join(missing),
            "trustrun_source": None,
        })
    else:
        contents.append({
            "id": "A",
            "statute": "AB 1405",
            "title": "Registration fields",
            "status": "covered",
            "evidence": (
                "Business identity, contact, laws, certifications, "
                "services description, and SOP all supplied."
            ),
            "trustrun_source": "methodology proposal (SOP)",
        })

    if registration.get("independence_bars_met") is True:
        contents.append({
            "id": "B",
            "statute": "AB 1405",
            "title": "Independence bars",
            "status": "covered",
            "evidence": (
                "No independence bar tripped: no auditing own work, no "
                "impairing relationship, no employment with the auditee "
                "during the audit, 12-month cooling-off observed."
            ),
            "trustrun_source": None,
        })
    else:
        contents.append({
            "id": "B",
            "statute": "AB 1405",
            "title": "Independence bars",
            "status": "gap",
            "evidence": (
                "Independence bars not confirmed. Trustrun cannot "
                "confirm an auditor's independence; the registrant must."
            ),
            "trustrun_source": None,
        })

    retention = registration.get("retention_years")
    if isinstance(retention, (int, float)) and retention >= 10:
        contents.append({
            "id": "C",
            "statute": "AB 1405",
            "title": "Ten-year record retention",
            "status": "covered",
            "evidence": "Records retained %s years." % retention,
            "trustrun_source": None,
        })
    elif isinstance(retention, (int, float)):
        contents.append({
            "id": "C",
            "statute": "AB 1405",
            "title": "Ten-year record retention",
            "status": "partial",
            "evidence": (
                "Records retained %s years; AB 1405 requires at least "
                "10." % retention
            ),
            "trustrun_source": None,
        })
    else:
        contents.append({
            "id": "C",
            "statute": "AB 1405",
            "title": "Ten-year record retention",
            "status": "gap",
            "evidence": "No record-retention period stated.",
            "trustrun_source": None,
        })

    template = registration.get("report_template")
    needed = ("scope", "objectives", "results", "documentation",
              "deficiencies", "remedies")
    if isinstance(template, dict):
        missing_parts = [part for part in needed if not template.get(part)]
        signed = template.get("signed") is True
        dated = template.get("dated") is True
    else:
        missing_parts = list(needed)
        signed = False
        dated = False
    if not missing_parts and signed and dated:
        contents.append({
            "id": "D",
            "statute": "AB 1405",
            "title": "Signed report contents",
            "status": "covered",
            "evidence": (
                "Report template is signed and dated and carries scope, "
                "objectives, results, supporting documentation, "
                "deficiencies, and remedies."
            ),
            "trustrun_source": "Trustrun report format",
        })
    elif not missing_parts:
        contents.append({
            "id": "D",
            "statute": "AB 1405",
            "title": "Signed report contents",
            "status": "partial",
            "evidence": (
                "Report template carries all six contents but is not "
                "signed and dated."
            ),
            "trustrun_source": "Trustrun report format",
        })
    else:
        contents.append({
            "id": "D",
            "statute": "AB 1405",
            "title": "Signed report contents",
            "status": "gap",
            "evidence": "Report template missing: %s."
            % ", ".join(missing_parts),
            "trustrun_source": None,
        })

    return _summarise(contents, "CAIVO registry", DISCLAIMER)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _list(value):
    return (isinstance(value, list) and bool(value)
            and all(_text(item) for item in value))


def _summarise(contents, label, note):
    covered = sum(1 for c in contents if c["status"] == "covered")
    partial = sum(1 for c in contents if c["status"] == "partial")
    gaps = [c["id"] for c in contents if c["status"] == "gap"]
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
        "label": label,
        "note": note,
    }


def _parse_date(value):
    """Parse an ISO date string (YYYY-MM-DD) to a date object."""
    from datetime import date

    if not isinstance(value, str):
        raise TypeError("date must be an ISO string YYYY-MM-DD")
    parts = value.split("-")
    if len(parts) != 3:
        raise ValueError("date must be an ISO string YYYY-MM-DD")
    try:
        year, month, day = (int(part) for part in parts)
        return date(year, month, day)
    except ValueError:
        raise ValueError("date must be a valid ISO string YYYY-MM-DD")


def _add_years(value, years):
    from datetime import date

    try:
        return date(value.year + years, value.month, value.day)
    except ValueError:
        # February 29 rolls to February 28.
        return date(value.year + years, value.month, 28)


def child_safety_audit_due(operator):
    """Compute the SB 1119 child-safety audit timing for an operator.

    operator: dict with:
          revenue_usd: gross revenue in the prior calendar year
              (operators under $500M are exempt from the audit
              requirement until 2032-01-01)
          first_available: ISO date the companion chatbot was first
              made publicly available in California, or None if not
              yet launched
          last_audit: ISO date of the last independent child safety
              audit, or None
          substantial_modification: True when a substantial
              modification is planned whose risk assessment shows an
              increased child safety risk (an extra audit is required
              before the modification is made publicly available,
              unless the operator is exempt as a small operator; the
              exemption's reach to the pre-modification audit is not
              settled in the sources read, so the return reason says
              so)
          modification_date: ISO date the modification would go public
              (required when substantial_modification is True)

    Returns a dict with "audit_required" (bool), "first_audit_due"
    and "next_audit_due" (ISO dates or None), "exempt_until" (ISO
    date or None), and a plain "reason". The July 1, 2027 operational
    obligations (risk assessment, crisis protocols, parental controls,
    parent notification) apply whether or not the audit is required
    yet; the reason says so.
    """
    if not isinstance(operator, dict):
        raise TypeError("operator must be a dict")
    revenue = operator.get("revenue_usd")
    if revenue is not None and not isinstance(revenue, (int, float)):
        raise TypeError("revenue_usd must be a number")
    small = revenue is not None and revenue < 500_000_000
    first_available = operator.get("first_available")
    launch = _parse_date(first_available) if first_available else None
    last_audit = operator.get("last_audit")
    last = _parse_date(last_audit) if last_audit else None
    substantial = bool(operator.get("substantial_modification", False))
    modification_date = operator.get("modification_date")
    modification = (
        _parse_date(modification_date) if modification_date else None
    )
    if substantial and modification is None:
        raise ValueError(
            "modification_date is required when substantial_modification "
            "is True"
        )
    from datetime import date

    statutory_first = date(2029, 1, 1)
    exempt_until = date(2032, 1, 1) if small else None
    if launch is not None:
        first_due = max(statutory_first, launch)
    else:
        first_due = statutory_first
    if last is not None:
        next_due = _add_years(last, 2)
    else:
        next_due = first_due
    if substantial and not small:
        return {
            "audit_required": True,
            "first_audit_due": first_due.isoformat(),
            "next_audit_due": modification.isoformat(),
            "exempt_until": None,
            "reason": (
                "A substantial modification whose risk assessment shows "
                "an increased child safety risk requires an extra child "
                "safety audit before the modification is made publicly "
                "available (%s)." % modification.isoformat()
            ),
        }
    if substantial and small:
        return {
            "audit_required": False,
            "first_audit_due": exempt_until.isoformat(),
            "next_audit_due": exempt_until.isoformat(),
            "exempt_until": exempt_until.isoformat(),
            "reason": (
                "Revenue under $500M in the prior calendar year: exempt "
                "from the child safety audit requirement until "
                "2032-01-01, so the pre-modification audit is not "
                "clearly required before then; the sources read do not "
                "settle whether the exemption reaches the "
                "pre-modification audit, so confirm with counsel. The "
                "July 1, 2027 operational obligations still apply."
            ),
        }
    if small and last is None:
        return {
            "audit_required": False,
            "first_audit_due": exempt_until.isoformat(),
            "next_audit_due": exempt_until.isoformat(),
            "exempt_until": exempt_until.isoformat(),
            "reason": (
                "Revenue under $500M in the prior calendar year: exempt "
                "from the child safety audit requirement until "
                "2032-01-01. The July 1, 2027 operational obligations "
                "(risk assessment, crisis protocols, parental controls, "
                "parent notification) still apply."
            ),
        }
    return {
        "audit_required": True,
        "first_audit_due": first_due.isoformat(),
        "next_audit_due": next_due.isoformat(),
        "exempt_until": (
            exempt_until.isoformat() if exempt_until else None
        ),
        "reason": (
            "First independent child safety audit due %s; then every "
            "two years (next %s). The July 1, 2027 operational "
            "obligations apply regardless."
            % (first_due.isoformat(), next_due.isoformat())
        ),
    }


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


def _module_status(verdict):
    return {
        "READY": "covered",
        "REVIEW": "partial",
        "BLOCK": "gap",
    }[verdict]


def score_child_safety_report(report, auditor=None):
    """Score a Trustrun report against SB 1119's child safety audit.

    report: a dict returned by trustrun.cli.run_audit (a "sections"
        dict with the four module verdicts), or a flat dict with the
        four module verdicts as top-level keys. The mapping is the
        module's judgment, stated in each area's evidence: contract
        speaks to whether the documented child-safe defaults are
        implemented; consistency speaks to whether parent notification
        fires every time its trigger occurs; stress speaks to whether
        the crisis protocol and defaults hold under adversarial input;
        data speaks to the training corpus given, capped at partial
        because the data module cannot judge child-safety itself.
    auditor: optional dict with the human-auditor contents a Trustrun
        report cannot supply on its own:
          risk_assessment_reviewed: True when the auditor has reviewed
              the operator's risk assessment and found it accurately
              characterizes the risks to minor users (area A)
          lead_auditor: name of the lead auditor (area F)
          signed: True when the lead auditor has signed (area F)

    Returns a dict with the overall readiness verdict, the coverage
    fraction over the six audit areas, a per-area breakdown, and the
    disclaimer. A Trustrun report alone always scores BLOCK, because
    areas A and F need a human auditor; that is the honest result.
    """
    sections, overall = _sections_from_report(report)
    if overall is not None and overall not in _VERDICTS:
        raise ValueError("report has unknown overall verdict %r" % overall)
    auditor = auditor or {}
    if not isinstance(auditor, dict):
        raise TypeError("auditor must be a dict")

    contents = []

    # (A) Risk-assessment accuracy: only a human auditor who has read
    # the operator's risk assessment can judge this.
    if auditor.get("risk_assessment_reviewed") is True:
        contents.append({
            "id": "A",
            "statute": "SB 1119",
            "title": "Risk-assessment accuracy",
            "status": "covered",
            "evidence": (
                "Auditor reviewed the operator's risk assessment and "
                "found it accurately characterizes the risks to minor "
                "users."
            ),
            "trustrun_source": "auditor record",
        })
    else:
        contents.append({
            "id": "A",
            "statute": "SB 1119",
            "title": "Risk-assessment accuracy",
            "status": "gap",
            "evidence": (
                "No auditor review of the operator's risk assessment. "
                "A Trustrun report audits the agent's behaviour, not "
                "the accuracy of the operator's own risk document."
            ),
            "trustrun_source": None,
        })

    # (B) Child-safe defaults: the contract module verifies the
    # documented defaults claim by claim.
    contents.append({
        "id": "B",
        "statute": "SB 1119",
        "title": "Child-safe defaults",
        "status": _module_status(sections["contract"]),
        "evidence": (
            "Contract section %s: the documented child-safe defaults "
            "were verified claim by claim against the chatbot's "
            "behaviour."
            % sections["contract"]
        ),
        "trustrun_source": "contract",
    })

    # (C) Parent notification: the consistency module shows whether
    # the notification fires every time its trigger occurs.
    contents.append({
        "id": "C",
        "statute": "SB 1119",
        "title": "Parent notification",
        "status": _module_status(sections["consistency"]),
        "evidence": (
            "Consistency section %s over k=%s repeated runs: parent "
            "notification fires on every trigger occurrence only when "
            "the behaviour holds across all runs."
            % (
                sections["consistency"],
                report.get("k")
                if report.get("k") is not None else "unrecorded",
            )
        ),
        "trustrun_source": "consistency",
    })

    # (D) Crisis protocol under adversarial input: the stress module
    # replays attempts to work around the safety defaults.
    contents.append({
        "id": "D",
        "statute": "SB 1119",
        "title": "Crisis protocol under adversarial input",
        "status": _module_status(sections["stress"]),
        "evidence": (
            "Stress section %s: adversarial replay of attempts to "
            "disable safety settings, conceal the AI identity, and "
            "raise self-harm content."
            % sections["stress"]
        ),
        "trustrun_source": "stress",
    })

    # (E) Training data: capped at partial. The data module checks the
    # corpus it is given for collapse, poisoning, and synthetic rot;
    # it cannot judge whether that corpus is child-safe.
    if sections["data"] == "READY":
        contents.append({
            "id": "E",
            "statute": "SB 1119",
            "title": "Training data",
            "status": "partial",
            "evidence": (
                "Data section READY: the corpus given showed no "
                "collapse, poisoning, or synthetic rot. Partial only: "
                "the data module checks the corpus it is given, not "
                "whether that corpus is child-safe."
            ),
            "trustrun_source": "data",
        })
    elif sections["data"] == "REVIEW":
        contents.append({
            "id": "E",
            "statute": "SB 1119",
            "title": "Training data",
            "status": "partial",
            "evidence": (
                "Data section REVIEW: issues found in the corpus given; "
                "a human auditor must judge whether they bear on child "
                "safety."
            ),
            "trustrun_source": "data",
        })
    else:
        contents.append({
            "id": "E",
            "statute": "SB 1119",
            "title": "Training data",
            "status": "gap",
            "evidence": (
                "Data section BLOCK: the corpus given failed the "
                "training-data audit."
            ),
            "trustrun_source": "data",
        })

    # (F) Independent auditor report: only a human auditor can supply
    # this.
    lead = auditor.get("lead_auditor")
    signed = auditor.get("signed")
    if isinstance(lead, str) and lead.strip() and signed is True:
        contents.append({
            "id": "F",
            "statute": "SB 1119",
            "title": "Independent auditor report",
            "status": "covered",
            "evidence": "Lead auditor %s has signed." % lead,
            "trustrun_source": "auditor record",
        })
    else:
        contents.append({
            "id": "F",
            "statute": "SB 1119",
            "title": "Independent auditor report",
            "status": "gap",
            "evidence": (
                "No independent auditor report. A Trustrun report "
                "carries a SHA-256 evidence anchor, not a human "
                "auditor's signature, and the operator must retain the "
                "auditor's report for the chatbot's deployed life plus "
                "five years."
            ),
            "trustrun_source": None,
        })

    return _summarise(contents, "CAIVO child safety", DISCLAIMER)


def format_summary(scored):
    """Format a scored result as plain text lines."""
    lines = [
        "%s readiness: %s (coverage %.2f over %d items)"
        % (
            scored["label"],
            scored["verdict"],
            scored["coverage"],
            len(scored["contents"]),
        ),
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
