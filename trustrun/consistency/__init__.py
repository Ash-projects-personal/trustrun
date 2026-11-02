"""Consistency module: does the agent do it every time.

One pass means little. This module scores the agent across k repeated runs
of the same task and flags variance, reward hacking, and grader gaming.
This is the reliability gap made measurable: benchmark scores versus
production outcomes.
"""


def score_repeated_runs(agent, task, k):
    """Score an agent over k repeated runs of the same task.

    agent: callable under test.
    task: the task input.
    k: number of repeated runs.

    Returns a consistency report once implemented.
    """
    raise NotImplementedError("TODO: implement repeated run scoring")
