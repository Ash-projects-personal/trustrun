# Trustrun

The trust layer for AI agents. Point it at any agent, get a report that proves what it did.

I built Trustrun because agents are moving into production and nobody can prove what they actually did. Benchmark scores look great. Production tells a different story. Trustrun closes that gap. It audits an agent the way an auditor checks a financial statement. It runs the agent, watches everything, attacks it, repeats it, checks its training data, and hands you one report.

## The four modules

**Contract.** Did the agent do what was agreed. Every run gets a machine checkable contract of what the agent was supposed to do. A verifier judges the delivered output against the contract, claim by claim. Working now: `verify_delivery` supports four check kinds (exact match, contains, numeric tolerance, custom judge), returns a per claim verdict of pass, fail, or unverified with evidence attached, and never passes a claim it cannot check. Dogfooded on 32 real Pact records: 31 pass, 1 fail, and the fail is the documented translation limit case, a cheat that counting checks cannot catch.

**Stress.** Does the agent survive attack. Adversarial replay: perturbed inputs, tool failures mid run, prompt injection including invisible encoding attacks.

**Consistency.** Does the agent do it every time. One pass means little. This module scores the agent across repeated runs and flags variance, reward hacking, and grader gaming. Working now: `score_repeated_runs` runs an agent k times on one task with a seeded RNG, reports pass rate at 1 and at k, flags variance when runs disagree, and runs two documented cheating heuristics (identical outputs on variants with different expected answers, and outputs that echo the grading rubric without answering). Anything it cannot determine comes back unverified, and with k equal to 1 variance stays unmeasured. Ships with a steady demo agent and a seeded flaky demo agent.

**Data.** Was the agent trained on clean data. Audits training and fine tuning data for collapse, poisoning, and synthetic rot. Working now: `audit_dataset` takes a list of records with a text field and measures exact duplicates, near duplicates (word 5 gram Jaccard at 0.8, the same method as the Lexsi collapse gate), and template clusters (numbers and capitalized words masked across the full text). Each metric gets a pass, review, or unverified verdict with evidence attached, and anything too small to measure comes back unverified. Dogfooded on all 15,011 real dolly-15k rows: the near duplicate count on responses reproduces the gate's measured 65 exactly.

## Install

```bash
pip install -e .
```

## Quickstart

```bash
pip install -e .
```

Audit any agent with one command. The agent is a dotted path to a
callable, the task is a JSON file.

```bash
trustrun audit trustrun.consistency:steady_agent task.json \
  --tools trustrun.stress:demo_tools \
  --data train.jsonl --k 5 --seed 0
```

You get one trust report with four sections. Each section returns
READY, REVIEW, or BLOCK, with evidence attached to every claim.

In code, the same audit is one function call:

```python
from trustrun.cli import run_audit, format_report

report = run_audit(agent, task, data_path="train.jsonl", seed=0, k=5)
print(format_report(report))
```

The agent takes the task text and returns a dict with a "result" key.
Agents that also accept a tools dict get the full stress battery. The
task is a dict with "text", "expect", and optional "tools",
"variants", "rubric", and "contract". The --data file is JSONL, one
record per line, with a "text" field. Records shaped like dolly-15k
(instruction, input, output) are joined automatically.

## How the verdict works

READY means every section passed cleanly. REVIEW means something needs
a human look: a section came back unverified, the data has review level
duplication, or the agent does not take tools so the tool channel
attacks could not be measured. BLOCK means something failed: a contract
claim failed, an attack got through, runs disagreed, or a cheating
check fired. BLOCK beats REVIEW beats READY.

Three rules keep the report honest. Anything a module cannot determine
stays unverified and never becomes a pass. An agent that completes zero
runs is consistently failing, so its consistency section reports BLOCK,
not a clean pass. And skipping --data leaves the data section
unverified, so the report can never read READY without training data
to check.

## Real data

No synthetic data in the demo path. The contract module grows out of the Pact verifier battery, which judges delivered work against deal terms claim by claim over real market cases. The stress module grows out of the UnseenRecall teardown, which measured attack survival over four invisible encoding classes. The data module grows out of CollapseWatch and the Lexsi collapse gate, measured on dolly-15k with 15,011 real rows.

## Status

All four modules are live and the CLI wires them into one report. The
demo runs the consistency module's steady agent against its flaky agent
on the same task, with a 2,000 row slice of real dolly-15k as the
training data. The steady agent lands at REVIEW: contract, consistency,
and data all pass, but it takes no tools, so the tool channel attacks
are honestly unmeasured. The flaky agent lands at BLOCK: variance and
cheating flags fire with the evidence attached. Full suite 70/70 green.
