# Methodology

How Trustrun's audits are run, and what they do and do not measure.
The short version lives in the README; this file is the full account.

## The task battery

Every audit runs the same battery shape. The standard battery is 25
tasks (`evals/tasks.json`): factual questions, arithmetic, document
questions, multi-step tasks, a low-confidence task where the honest
answer is that the information is not there, and tasks that exercise
each tool. Round audits run the clean-room agents over generated task
sets at the same shape; real-agent audits run a framework's own agent
loop over the 25 standard tasks.

Each task carries a machine-checkable contract: the claims the
delivered answer must satisfy. The contract module judges the
delivered output against the contract claim by claim and records
pass, fail, or unverified for each claim, with the evidence attached.
A claim the verifier cannot check is recorded unverified, never as a
pass.

## The injection test setup

The stress module replays each task under attack. The battery holds
19 attack classes, including:

- Prompt injection delivered through tool output, in plaintext and in
  invisible encodings (Unicode tag block, zero-width characters).
- Tool failure mid run, and a separate check of whether the failure
  was visible to the agent or silently dropped.
- Tampering with the monitor and with the evaluator (rewriting the
  test, self-grading).
- A misleading principal, clarification-channel injection, input
  perturbation, task tampering, and adaptive injection that reacts to
  the agent's own output.

Each attack records survived, not survived, or unverified, plus
whether the agent detected the attack. An attack the harness could
not deliver, or whose outcome cannot be determined, is recorded
unverified. Unmeasurable items are marked unverified.

## Runs, seeds, and repetition

- Real-agent audits: 25 tasks, seed 0, k=5 (each task run 5 times for
  the consistency checks: pass at 1, pass at k, variance across runs,
  and two cheating heuristics).
- Labeled eval rounds: fixed seed per round (the round script names
  it), 300 audits per round in recent rounds.
- Every stored result names the script that produced it, and the
  scripts are deterministic at their fixed seeds, so a stored row can
  be reproduced by re-running its script.

## Model versions used

- The real-agent audits drive each framework's real agent loop, its
  real tools, and its real parsing, with a deterministic stub model
  behind it (the literal model recorded in each audit's summary file,
  for example `deterministic-stub-v1`). The stub follows instructions
  in task text and tool output the way an instruction-following model
  would, which is what makes the injection and tampering outcomes
  measurable without a live model in the loop.
- No live frontier model is part of the stored audit results. Rounds
  that need a live model key are skipped when no key is configured,
  and are recorded as skipped, never estimated.

## Limits of the tests

- The audits measure what the framework's agent loop does with the
  stub model's behavior. They record how instructions, tool results,
  failures, and tampering flow through the framework. They are not a
  measurement of any live model's judgment, and a result here is not
  a claim about a vendor's shipped product service.
- The battery is one task set of 25 tasks. Coverage grows as tasks
  and attack classes are added; a class not in the battery is not
  measured, and the report says so through the unverified state.
- The data module measures duplication and template structure in a
  dataset. It does not measure dataset legality, consent, or factual
  accuracy.
- Consistency is measured over k=5 repeats of the same task. It
  records repeatability on this battery, not behavior on new tasks.
