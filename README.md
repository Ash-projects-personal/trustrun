# Trustrun

The trust layer for AI agents. Point it at any agent, get a report that proves what it did.

I built Trustrun because agents are moving into production and nobody can prove what they actually did. Benchmark scores look great. Production tells a different story. Trustrun closes that gap. It audits an agent the way an auditor checks a financial statement. It runs the agent, watches everything, attacks it, repeats it, checks its training data, and hands you one report.

## The four modules

**Contract.** Did the agent do what was agreed. Every run gets a machine checkable contract of what the agent was supposed to do. A verifier judges the delivered output against the contract, claim by claim. Working now: `verify_delivery` supports four check kinds (exact match, contains, numeric tolerance, custom judge), returns a per claim verdict of pass, fail, or unverified with evidence attached, and never passes a claim it cannot check. Dogfooded on 32 real Pact records: 31 pass, 1 fail, and the fail is the documented translation limit case, a cheat that counting checks cannot catch.

**Stress.** Does the agent survive attack. Adversarial replay: perturbed inputs, tool failures mid run, prompt injection including invisible encoding attacks.

**Consistency.** Does the agent do it every time. One pass means little. This module scores the agent across repeated runs and flags variance, reward hacking, and grader gaming.

**Data.** Was the agent trained on clean data. Audits training and fine tuning data for collapse, poisoning, and synthetic rot.

## Install

```bash
pip install -e .
```

## Quickstart

```bash
trustrun audit <agent> <task>
```

You get one trust report with four sections. Each section returns READY, REVIEW, or BLOCK, with evidence attached to every claim.

## Real data

No synthetic data in the demo path. The contract module grows out of the Pact verifier battery, which judges delivered work against deal terms claim by claim over real market cases. The stress module grows out of the UnseenRecall teardown, which measured attack survival over four invisible encoding classes. The data module grows out of CollapseWatch and the Lexsi collapse gate, measured on dolly-15k with 15,011 real rows.

## Status

Early build. The contract module works and is dogfooded on real data (see above). The stress module works: adversarial replay over input perturbation, mid run tool failure, and injection, with two invisible encoding classes (tagblock and zerowidth) from the UnseenRecall teardown, each verified lossless and NFKC stable. Consistency and data are stubbed and the CLI prints the report skeleton. Working code lands module by module.
