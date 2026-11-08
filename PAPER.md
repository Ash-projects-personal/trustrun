# Trustrun: Auditing What AI Agents Actually Did

## 1. The reliability gap

Agents score high on benchmarks and fail in production. The 2026 record shows the pattern clearly: strong benchmark numbers, then dropped accuracy once the agent faces real tasks, tool failures, and messy inputs. Capability is no longer the constraint. Verification is. This section measures the gap on public agent benchmarks and production incident reports, and names exactly where benchmark scores stop predicting real outcomes.

## 2. Contract anchored verification

Every agent run gets a machine checkable contract of what the agent was supposed to do. A verifier judges the delivered output against the contract, claim by claim, with evidence attached to every verdict. This section describes the method and reports results from the Pact verifier battery: real deliveries judged against real deal terms, with check level accuracy measured on the full battery.

A bound on what the verifier itself can claim: LLM judges are not reliable arbiters on hard agentic work. AgentJudgeBench (Verma et al., arXiv:2608.26623, EMNLP 2026) measures all six tested judges converging to a 77-82% alignment band on hard tool-calling queries without ground truth, regardless of scale, and ground truth can hurt through over-anchoring. Trustrun does not claim its contract judge beats ~80% agreement on hard agentic workflows without ground truth. The judge's own bias is measured, not assumed away: JudgeBiasBench (Zhou et al., arXiv:2603.08091) supplies the 12-type bias taxonomy and the Bias Sensitivity Rate, and Trustrun runs that instrument over its own reconstruction set — a surface-signal stand-in judge flips on every injected bias (BSR 1.000) while a fact-only control judge flips on none (BSR 0.000), with real LLM judges measured in the paper at 10-38% overall BSR between the two.

Single-trial verdicts are not treated as verified. Yagubyan (arXiv:2606.13685) measured pairwise judge preferences flipping 13.6% of the time on average, so Trustrun's contract judge runs judge-kind claims over at least 11 repeated trials with position randomization and majority vote, and reports the flip rate and Fleiss' kappa across claims next to raw agreement; a tie is unverified, never a pass. Binary-verifiable claims (exact, contains, numeric) are judged once, deterministically, and the report states their share. Judges never deliberate with each other: Carro et al. (arXiv:2610.28539) found debate gives weaker LLM judges no comparable gains and can reduce accuracy.

Task success is not enough, so the contract also scores what the agent did, not only what it said. SABench (Huang et al., arXiv:2610.34167) measured 15.2% of 2,211 model-task pairs incurring collateral damage — the agent completing the requested work while taking an unauthorized side-effecting action — and 12.8% of goal-satisfied runs still producing unauthorized writes, with ambiguity traps violating at 38.8% against 8.4% for non-ambiguous traps. Trustrun's side-effect oracle scores the recorded tool-call trace judge-free against a per-task authorization set the task author writes: a delivery that meets its claims while doing unauthorized damage fails the contract. The oracle is a closed world — an effect the authorization set does not list is unauthorized, and an effect with no recorded kind is unverified, never authorized — so it can only catch what the task author listed, and the report states that bound. CAREFUL-Bench (Kovalenko, arXiv:2611.02978 v2) supplies the effect accounting the oracle reports alongside the verdict: unrequested destructive calls, duplicate writes, redundant reads, and surplus steps against a reference trajectory, with confirmed versus unconfirmed destructive calls counted separately — CAREFUL-Bench measured 322 of 734 reference turns acting destructively without confirmation, and no model completing more than 6 of 712 conversations with every destructive call confirmed. The same claim-by-claim-against-recorded-evidence principle catches the dominant failure mode in agent-written research as well: Into the Unknown (Kim et al., arXiv:2610.19159) found 114 of 135 agent-written follow-up papers failing integrity, most often claims of work never done or numbers contradicting the recorded evidence.

## 3. Adversarial replay

The agent is replayed under attack: perturbed inputs, tool failures mid run, and prompt injection including invisible encoding classes. This section defines the attack classes, describes the replay harness, and reports survival rates per class. The baseline comes from the UnseenRecall teardown, which measured how invisible encodings defeat a plaintext filter.

## 4. Consistency scoring

One pass means little. The agent runs the same task k times. The report scores pass across the k runs and flags variance, reward hacking, and grader gaming. This section defines the consistency metrics and shows how they catch failures that single run benchmarks miss, including agents that game the grader instead of doing the work.

## 5. Data auditing

The agent's training and fine tuning data is audited for collapse, poisoning, and synthetic rot before the agent is trusted with real work. This section describes the collapse metrics and reports them on real datasets, starting with dolly-15k and its 15,011 measured rows.

## 6. The fused report

Four slices beat one. This section shows why: ablations that drop each module in turn and measure what the report misses without it. The fused report returns READY, REVIEW, or BLOCK per section with evidence attached, so a deployment decision rests on proof, not on a benchmark number.
