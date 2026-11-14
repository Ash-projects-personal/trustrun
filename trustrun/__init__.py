"""Trustrun: the trust layer for AI agents.

Point it at an agent and a task. It runs the agent, watches everything,
attacks it, repeats it, checks its training data, and returns one trust
report with four sections: contract, stress, consistency, data.
"""

__version__ = "0.1.2"

# The four audit sections, in report order. Defined here so modules
# that both the CLI and the examiner report need can import it without
# a circular import through trustrun.cli.
SECTIONS = ("contract", "stress", "consistency", "data")
