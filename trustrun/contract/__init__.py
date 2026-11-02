"""Contract module: did the agent do what was agreed.

Every run gets a machine checkable contract of what the agent was supposed
to do. A verifier judges the delivered output against the contract, claim
by claim, with evidence attached to every verdict.

Method source: the Pact verifier battery, which judges delivered work
against negotiated deal terms claim by claim over real market cases
(experiments/real_cases.py in the Pact project). This module generalizes
that method to any agent task.
"""


def verify_delivery(contract, output):
    """Judge delivered output against a task contract.

    contract: mapping of claim ids to the checks each claim must pass.
    output: the agent's delivered output for the task.

    Returns a per claim verdict mapping once implemented.
    """
    raise NotImplementedError("TODO: implement claim by claim contract verification")
