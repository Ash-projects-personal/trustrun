"""Run Trustrun's judge-bias instrument and report the measurements.

Usage: python3 run_judge_bias_scenarios.py

Measures, over the reconstruction set in judge_bias_scenarios.py:
- the Bias Sensitivity Rate (BSR, JudgeBiasBench eq. 4) per bias type
  for both stand-in judges (surface_signal_judge, strict_judge);
- the same BSR for the two BiasExtend extension probes (13 filename,
  14 demographic label);
- the agentic DAG-judge alignment with and without ground truth
  (AgentJudgeBench-style, per tier and overall).

Writes reports/judgebias/summary.json (machine readable) and
reports/judgebias/summary.txt (human readable). Every number in
those files comes from a real run of the clean-room harness. The
paper's reference numbers (JudgeBiasBench Table 4 BSRs,
AgentJudgeBench 77-82% hard-tier ceiling) are cited in the text
summary for comparison only; they are not Trustrun measurements.
"""

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)

from judge_bias_scenarios import (  # noqa: E402
    AGENTIC_CASES,
    BIAS_TYPES,
    EXTENDED_BIAS_TYPES,
    dag_judge_with_gt,
    dag_judge_without_gt,
    measure_agentic_alignment,
    measure_bias_profile,
    measure_extended_profile,
    strict_judge,
    surface_signal_judge,
)

OUT_DIR = os.path.join(HERE, "reports", "judgebias")


def _fmt_bsr(value):
    if value is None:
        return "n/a"
    return "%.3f" % value


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    surface = measure_bias_profile(surface_signal_judge)
    strict = measure_bias_profile(strict_judge)
    surface_ext = measure_extended_profile(surface_signal_judge)
    strict_ext = measure_extended_profile(strict_judge)
    with_gt = measure_agentic_alignment(dag_judge_with_gt)
    without_gt = measure_agentic_alignment(dag_judge_without_gt)

    summary = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "base_pairs": 8,
        "bias_types": len(BIAS_TYPES),
        "extended_bias_probes": len(EXTENDED_BIAS_TYPES),
        "agentic_cases": len(AGENTIC_CASES),
        "agentic_traces": sum(len(c["traces"]) for c in AGENTIC_CASES),
        "bias_profiles": {"surface_signal_judge": surface, "strict_judge": strict},
        "extended_bias_profiles": {
            "surface_signal_judge": surface_ext,
            "strict_judge": strict_ext,
        },
        "agentic_alignment": {
            "with_ground_truth": with_gt,
            "without_ground_truth": without_gt,
        },
        "references": {
            "judgebiasbench_bsr": (
                "Zhou et al., arXiv:2603.08091, Table 4: overall BSR "
                "Claude-3.7-Sonnet 10.2%, GPT-3.5-Turbo 35.2%, "
                "Auto-J-13B 38.5% (291-500 instances per type)."
            ),
            "agentjudgebench_ceiling": (
                "Verma et al., arXiv:2608.26623: on hard queries without "
                "ground truth all six judges converge to a 77-82% "
                "alignment band; 3,808 instances, three tiers."
            ),
            "filename_bias": (
                "Popov, arXiv:2611.01829: three frontier LLMs score the "
                "same document differently when only the filename "
                "changes; person-related label scores higher than no "
                "label; 4 documents x 5 filename conditions, 10,944 "
                "marks."
            ),
            "demographic_label_bias": (
                "Amin, Salminen & Jansen, arXiv:2611.02692: 8 models, "
                "240 narratives, 30,720 judgments; explicit candidate "
                "gender labels +1.05-1.73pp Yes-vote vs unspecified; "
                "2.5-3.3% decisions reversed; DLMs 1.18% reversals vs "
                "LaJ 3.38% under direct substitution."
            ),
        },
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)

    lines = []
    lines.append("Trustrun judge-bias instrument (TRUSTRUN-JudgeBenchAdopt)")
    lines.append("Generated %s" % summary["generated_at"])
    lines.append("")
    lines.append(
        "Bias Sensitivity Rate (BSR, JudgeBiasBench eq. 4) per bias type, "
        "8 base pairs per type. BSR = originally-correct judgments that "
        "become incorrect after bias injection, over originally-correct "
        "judgments."
    )
    lines.append("")
    lines.append(
        "%-22s %8s %8s %8s %8s"
        % ("bias type", "surface", "surf n", "strict", "str n")
    )
    for surf_row, strict_row in zip(
        surface["per_type"], strict["per_type"]
    ):
        lines.append(
            "%-22s %8s %4d/%d %8s %4d/%d"
            % (
                surf_row["bias_type"],
                _fmt_bsr(surf_row["bsr"]),
                surf_row["orig_correct"],
                surf_row["n"],
                _fmt_bsr(strict_row["bsr"]),
                strict_row["orig_correct"],
                strict_row["n"],
            )
        )
    lines.append(
        "%-22s %8s %8s %8s %8s"
        % (
            "OVERALL (mean)",
            _fmt_bsr(surface["overall_bsr"]),
            "",
            _fmt_bsr(strict["overall_bsr"]),
            "",
        )
    )
    lines.append("")
    lines.append(
        "Reference (paper, not Trustrun): JudgeBiasBench Table 4 overall "
        "BSR 10.2% (Claude-3.7-Sonnet) to 38.5% (Auto-J-13B). The "
        "surface-signal stand-in is the instrument's ceiling case, the "
        "strict judge its floor case; real LLM judges sit between them."
    )
    lines.append("")
    lines.append(
        "BiasExtend probes 13-14 (BSR, JudgeBiasBench eq. 4), 8 base "
        "pairs per probe:"
    )
    lines.append(
        "%-22s %8s %8s %8s %8s"
        % ("extension probe", "surface", "surf n", "strict", "str n")
    )
    for surf_row, strict_row in zip(
        surface_ext["per_type"], strict_ext["per_type"]
    ):
        lines.append(
            "%-22s %8s %4d/%d %8s %4d/%d"
            % (
                surf_row["bias_type"],
                _fmt_bsr(surf_row["bsr"]),
                surf_row["orig_correct"],
                surf_row["n"],
                _fmt_bsr(strict_row["bsr"]),
                strict_row["orig_correct"],
                strict_row["n"],
            )
        )
    lines.append(
        "%-22s %8s %8s %8s %8s"
        % (
            "OVERALL (mean)",
            _fmt_bsr(surface_ext["overall_bsr"]),
            "",
            _fmt_bsr(strict_ext["overall_bsr"]),
            "",
        )
    )
    lines.append("")
    lines.append(
        "Reference (papers, not Trustrun): Popov arXiv:2611.01829 "
        "(filename changes move scores; person label beats no label); "
        "Amin et al. arXiv:2611.02692 (explicit candidate gender labels "
        "+1.05-1.73pp Yes-vote vs unspecified; 2.5-3.3% reversals). "
        "DLM-vs-LaJ note from the same paper: decision language models "
        "reversed 1.18% of decisions vs 3.38% for LLM-as-a-judge models "
        "under direct substitution, so binary verdicts belong to a "
        "decision-model judge, which is how Trustrun's contract judge "
        "already works."
    )
    lines.append("")
    lines.append("Agentic DAG-judge alignment (6 cases, 12 traces):")
    for label, result in (
        ("with ground truth   ", with_gt),
        ("without ground truth", without_gt),
    ):
        lines.append(
            "  %s: %d/%d = %.3f"
            % (label, result["aligned"], result["total"], result["overall"])
        )
        for tier in ("easy", "medium", "hard"):
            tier_row = result["per_tier"][tier]
            lines.append(
                "    %-6s: %d/%d = %.3f"
                % (
                    tier,
                    tier_row["aligned"],
                    tier_row["total"],
                    tier_row["aligned"] / tier_row["total"],
                )
            )
    lines.append("")
    lines.append(
        "Reference (paper, not Trustrun): AgentJudgeBench hard queries "
        "without ground truth, all six judges converge to a 77-82% "
        "alignment band. Trustrun's reconstruction is 12 toy verdicts, "
        "not comparable in scale; the comparison is directional only."
    )
    text = "\n".join(lines) + "\n"
    with open(os.path.join(OUT_DIR, "summary.txt"), "w") as fh:
        fh.write(text)
    print(text, flush=True)
    print(
        "done: surface overall BSR %s, strict overall BSR %s, "
        "extended surface BSR %s, extended strict BSR %s, "
        "agentic with-GT %.3f, without-GT %.3f"
        % (
            _fmt_bsr(surface["overall_bsr"]),
            _fmt_bsr(strict["overall_bsr"]),
            _fmt_bsr(surface_ext["overall_bsr"]),
            _fmt_bsr(strict_ext["overall_bsr"]),
            with_gt["overall"],
            without_gt["overall"],
        )
    )


if __name__ == "__main__":
    main()
