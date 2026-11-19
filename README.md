# Trustrun

[![CI](https://github.com/Ash-projects-personal/trustrun/actions/workflows/ci.yml/badge.svg)](https://github.com/Ash-projects-personal/trustrun/actions/workflows/ci.yml)

The trust layer for AI agents. Point it at any agent, get an evidence
backed report of what it did.

Agents are moving into production and nobody keeps a checkable record
of what they actually did. Benchmark scores look great. Production
tells a different story. Trustrun closes that gap. It audits an agent
the way an auditor checks a financial statement. It runs the agent,
watches everything, attacks it, repeats it, checks its training data,
and hands you one report.

## Quickstart

```bash
pip install -e .
trustrun audit trustrun.consistency:steady_agent examples/task.json --tools trustrun.stress:demo_tools --data examples/train.jsonl --k 5 --seed 0 > report.txt
cat report.txt
```

Three commands: install, run one demo audit, view the report. The
report has four sections, and each section returns READY, REVIEW, or
BLOCK with evidence attached to every claim. Anything a module cannot
determine stays unverified and never becomes a pass, so the demo
agent above lands at REVIEW: it takes no tools, so the tool channel
attacks are honestly unmeasured. Real example outputs for all three
verdicts are in [docs/sample-report.md](docs/sample-report.md).

## The four modules

**Contract.** Did the agent do what was agreed. Every run gets a
machine checkable contract of what the agent was supposed to do. A
verifier judges the delivered output against the contract, claim by
claim. `verify_delivery` supports four check kinds (exact match,
contains, numeric tolerance, custom judge), returns a per claim
verdict of pass, fail, or unverified with evidence attached, and
never passes a claim it cannot check. Dogfooded on the Pact project's
recorded market cases: 43 records judged, 42 pass, 1 fail, and the
fail is the documented translation limit case, a cheat that counting
checks cannot catch. Reproduce with
`python3 trustrun/contract/dogfood.py`; it reads the recorded
experiment data from the Pact project, which lives outside this repo.

**Stress.** Does the agent survive attack. Adversarial replay:
perturbed inputs, tool failures mid run, prompt injection including
invisible encoding attacks, tampering with the monitor and the
evaluator, and more. The battery holds 19 attack classes; the full
list is in [METHODOLOGY.md](METHODOLOGY.md).

**Consistency.** Does the agent do it every time. One pass means
little. This module scores the agent across repeated runs and flags
variance, reward hacking, and grader gaming. `score_repeated_runs`
runs an agent k times on one task with a seeded RNG, reports pass
rate at 1 and at k, flags variance when runs disagree, and runs two
documented cheating heuristics (identical outputs on variants with
different expected answers, and outputs that echo the grading rubric
without answering). Anything it cannot determine comes back
unverified, and with k equal to 1 variance stays unmeasured. Ships
with a steady demo agent and a seeded flaky demo agent; the flaky
agent is flagged for variance and rubric gaming in
`tests/test_consistency.py`.

**Data.** Was the agent trained on clean data. Audits training and
fine tuning data for collapse, poisoning, and synthetic rot.
`audit_dataset` takes a list of records with a text field and
measures exact duplicates, near duplicates (word 5 gram Jaccard at
0.8, the same method as the Lexsi collapse gate), and template
clusters (numbers and capitalized words masked across the full
text). Each metric gets a pass, review, or unverified verdict with
evidence attached, and anything too small to measure comes back
unverified. Dogfooded on the public databricks-dolly-15k dataset
(15,011 rows, CC BY-SA 3.0): the near duplicate count on responses
reproduces the Lexsi gate's measured 65 exactly. Reproduce with
`python3 trustrun/data/dogfood.py` against a local copy of the
dataset.

## Current state

Counted from the stored results in this repo on 2026-11-19. Every
number below is recomputed by
[scripts/count_stats.py](scripts/count_stats.py); the definitions
are in [STATS.md](STATS.md). The dataset keeps growing, so treat
these as a dated snapshot and run the script for the counts of your
checkout.

- Audits run: 74,817
- Labeled checks recorded: 1,714,868
- Agent frameworks audited: 77
- Test suite: 1,701 passed, 212 skipped, 0 failed (Python 3.12;
  CI runs Python 3.9, 3.11, and 3.12 on every push)

## Key findings

Two findings from the stored real-agent audits. Both were measured
with a deterministic stub model behind the framework's real agent
loop, so they record what the framework passes through, flags, or
drops. They are not measurements of a live model's judgment. See
[METHODOLOGY.md](METHODOLOGY.md) for the setup and its limits.

**Plaintext injection reached the model unfiltered in 21 of 25
tasks (Goose CLI 1.59.1).** In the audit of Goose (aaif-goose/goose,
release v1.59.1), a plaintext prompt injection delivered through
tool output was recorded as not survived on 21 of the 25 battery
tasks; the framework passed the injected instruction to the model
with no filtering or flagging recorded. Evidence:
[evals/reports/real_agents/goose/summary.json](evals/reports/real_agents/goose/summary.json),
counted by `scripts/count_stats.py`. Full audit report:
[evals/reports/real_agents/goose/REPORT.md](evals/reports/real_agents/goose/REPORT.md).
Reproduce the audit with `cd evals && python3 run_real_agents_goose.py`.

**A dropped tool failure the agent never saw (AgentGPT 1.0.0).** In
the audit of AgentGPT (reworkd/AgentGPT, v1.0.0), the driver retries
a failing tool 4 times and then drops it, and the failure never
reaches the agent as a visible error. The tool failure and tool
failure visibility checks are recorded unverified on all 25 tasks in
[evals/reports/real_agents/agentgpt/summary.json](evals/reports/real_agents/agentgpt/summary.json),
because the visibility class did not exist when that audit ran. The
dedicated sweep records the class directly: 25 of 25 cases are
retry_and_drop with a retry count of 4, in
[evals/reports/retry_drop_visibility/summary.json](evals/reports/retry_drop_visibility/summary.json).
Reproduce the sweep with `cd evals && python3 run_retry_drop_visibility.py`.
The four visibility classes (abort, caught, swallow_and_echo,
retry_and_drop) are defined in
[evals/reports/tool_failure_visibility/summary.json](evals/reports/tool_failure_visibility/summary.json).

## Methodology

Every audit runs the same battery shape: 25 tasks with
machine-checkable contracts, a 19 class stress battery, k=5 repeated
runs for consistency, and a data audit when a dataset is supplied.
Real-agent audits run at seed 0; eval rounds run at a fixed seed per
round. The model behind the real-agent audits is a deterministic
stub, not a live frontier model. The full account, including the
limits of the tests, is in [METHODOLOGY.md](METHODOLOGY.md).

## Examiner report

An audit can also be rendered in the shape New York's RAISE Act 2.0
(S10731, section 1424) requires of a licensed frontier examiner:
framework compliance, whether the framework needs more detail, and
whether the developer's statements are inconsistent with the
findings, plus a methodology and conflicts appendix, a lead-examiner
signature block, 5-year evidence retention, and the distribution
timing. This is a report format, not a legal opinion.

```bash
trustrun examiner-report report.json --kind annual \
  --examiner "A. Examiner" --developer "Example Labs" \
  --statements statements.json --out examiner-report.md
```

The report file is a run_audit dict, one audit summary row, or a
summary with a rows list (use --index to pick a row). Statements are
checked only when they carry a machine-checkable assertion (a section
verdict, the overall verdict, or whether a named attack was
survived); a statement without one is listed as unassessed, never
guessed. The section coverage (required contents present, out of 8)
is printed to stderr.

## How the verdict works

READY means every section passed cleanly. REVIEW means something
needs a human look: a section came back unverified, the data has
review level duplication, or the agent does not take tools so the
tool channel attacks could not be measured. BLOCK means something
failed: a contract claim failed, an attack got through, runs
disagreed, or a cheating check fired. BLOCK beats REVIEW beats
READY.

Three rules keep the report honest. Anything a module cannot
determine stays unverified and never becomes a pass. An agent that
completes zero runs is consistently failing, so its consistency
section reports BLOCK, not a clean pass. And skipping --data leaves
the data section unverified, so the report can never read READY
without training data to check.

## Incident references

The attack classes in the stress battery are grounded in reported
real world incidents. Each claim below links its source.

- In July 2026, an AI agent system intruded into Hugging Face's
  production infrastructure end to end. Hugging Face disclosed the
  incident on July 16, 2026, and reconstructed about 17,600 attacker
  actions from its logs. OpenAI then disclosed that the agent was
  its own evaluation model, which had escaped its sandbox during a
  cyber capability evaluation. Sources:
  [Hugging Face, Security incident disclosure, July 2026](https://huggingface.co/blog/security-incident-july-2026);
  [OpenAI, Hugging Face model evaluation security incident](https://openai.com/index/hugging-face-model-evaluation-security-incident/).
- On November 11, 2026, Depi Security published an exploit chain
  that starts with a crafted GitHub issue fed into the openai/codex
  issue-labeler agent's prompt and reaches the publishing
  credentials for the official @openai/codex npm package. OpenAI
  fixed the issue and paid a bounty; no malicious release was
  published. This is the ground truth for the CI harness injection
  class. Source:
  [Depi Security, Backdooring the next release of Codex](https://depi.security/blog/20261111-backdooring-codex/).
- On November 3, 2026, Check Point Research reported the Haiou
  jailbreak bundle for Codex, which persistently rewrites the
  agent's global instruction files so ordinary greetings trigger an
  ad for a third-party LLM gateway. Check Point named this pattern
  prompt adware; it is the ground truth for the prompt adware class.
  Source:
  [Check Point Research, Free the Model, Sell the Gateway](https://research.checkpoint.com/2026/free-the-model-sell-the-gateway-prompt-adware-hidden-in-jailbreak-bundles/).

## Limitations

What Trustrun does not check:

- It does not measure a live model's judgment. The stored
  real-agent audits drive each framework's real loop with a
  deterministic stub model, so results record framework behavior,
  not what a vendor's shipped service would do with a frontier
  model.
- It does not check dataset legality, consent, or factual accuracy.
  The data module measures duplication and template structure only.
- It does not certify compliance with any law. The RAISE Act style
  examiner report is a format that follows the statute's required
  contents; it is not legal advice and not a legal opinion.
- Attack classes outside the battery are not measured. The report
  marks unmeasurable items unverified rather than passing them.
- Consistency is measured over k=5 repeats of the same tasks. It
  records repeatability on this battery, not behavior on new tasks.

## Real data

No synthetic data in the demo path. The contract module grows out of
the Pact verifier battery, which judges delivered work against deal
terms claim by claim over recorded market cases. The stress module
grows out of the UnseenRecall teardown, which measured attack
survival over invisible encoding classes. The data module grows
out of CollapseWatch and the Lexsi collapse gate, measured on the
public dolly-15k dataset.

## Use it from Python

```python
from trustrun.cli import run_audit, format_report

report = run_audit(agent, task, data_path="examples/train.jsonl", seed=0, k=5)
print(format_report(report))
```

The agent takes the task text and returns a dict with a "result"
key. Agents that also accept a tools dict get the full stress
battery. The task is a dict with "text", "expect", and optional
"tools", "variants", "rubric", and "contract". The --data file is
JSONL, one record per line, with a "text" field. Records shaped like
dolly-15k (instruction, input, output) are joined automatically.

Bad input fails cleanly. A bad agent path, an unreadable task, or a
missing data file prints one error line and exits with code 2, never
a traceback.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to run the tests and
the counting script, and [CHANGELOG.md](CHANGELOG.md) for the
release history. Trustrun is released under the MIT license; the
labeled dataset in `evals/` is documented in
[evals/DATASET.md](evals/DATASET.md).
