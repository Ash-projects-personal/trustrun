"""Stress module: does the agent survive attack.

Adversarial replay of an agent run: perturbed inputs, tool failures mid
run, and prompt injection including invisible encoding attack classes.
Each replay records whether the agent completed the task honestly or
broke, cheated, or leaked.

Method source: the UnseenRecall teardown, which measured attack survival
over four invisible encoding classes on a plaintext filter baseline.
"""


def replay_attack(agent, task, attack):
    """Replay one agent task under one adversarial attack.

    agent: callable under test.
    task: the task input.
    attack: description of the attack to apply (input perturbation,
        mid run tool failure, or injection class).

    Returns an attack survival record once implemented.
    """
    raise NotImplementedError("TODO: implement adversarial replay")
