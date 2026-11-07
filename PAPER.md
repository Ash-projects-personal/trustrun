# Trustrun: Auditing What AI Agents Actually Did

## 1. The reliability gap

Agents score high on benchmarks and fail in production. The 2026 record shows the pattern clearly: strong benchmark numbers, then dropped accuracy once the agent faces real tasks, tool failures, and messy inputs. Capability is no longer the constraint. Verification is. This section measures the gap on public agent benchmarks and production incident reports, and names exactly where benchmark scores stop predicting real outcomes.

## 2. Contract anchored verification

Every agent run gets a machine checkable contract of what the agent was supposed to do. A verifier judges the delivered output against the contract, claim by claim, with evidence attached to every verdict. This section describes the method and reports results from the Pact verifier battery: real deliveries judged against real deal terms, with check level accuracy measured on the full battery.

A bound on what the verifier itself can claim: LLM judges are not reliable arbiters on hard agentic work. AgentJudgeBench (Verma et al., arXiv:2608.26623, EMNLP 2026) measures all six tested judges converging to a 77-82% alignment band on hard tool-calling queries without ground truth, regardless of scale, and ground truth can hurt through over-anchoring. Trustrun does not claim its contract judge beats ~80% agreement on hard agentic workflows without ground truth. The judge's own bias is measured, not assumed away: JudgeBiasBench (Zhou et al., arXiv:2603.08091) supplies the 12-type bias taxonomy and the Bias Sensitivity Rate, and Trustrun runs that instrument over its own reconstruction set — a surface-signal stand-in judge flips on every injected bias (BSR 1.000) while a fact-only control judge flips on none (BSR 0.000), with real LLM judges measured in the paper at 10-38% overall BSR between the two.

## 3. Adversarial replay

The agent is replayed under attack: perturbed inputs, tool failures mid run, and prompt injection including invisible encoding classes. This section defines the attack classes, describes the replay harness, and reports survival rates per class. The baseline comes from the UnseenRecall teardown, which measured how invisible encodings defeat a plaintext filter.

## 4. Consistency scoring

One pass means little. The agent runs the same task k times. The report scores pass across the k runs and flags variance, reward hacking, and grader gaming. This section defines the consistency metrics and shows how they catch failures that single run benchmarks miss, including agents that game the grader instead of doing the work.

## 5. Data auditing

The agent's training and fine tuning data is audited for collapse, poisoning, and synthetic rot before the agent is trusted with real work. This section describes the collapse metrics and reports them on real datasets, starting with dolly-15k and its 15,011 measured rows.

## 6. The fused report

Four slices beat one. This section shows why: ablations that drop each module in turn and measure what the report misses without it. The fused report returns READY, REVIEW, or BLOCK per section with evidence attached, so a deployment decision rests on proof, not on a benchmark number.
