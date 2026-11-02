"""Trustrun command line interface.

Usage:
    trustrun audit <agent> <task>

Runs the four module audit and prints the trust report skeleton. Each
section returns READY, REVIEW, or BLOCK with evidence fields. Module
verdicts stay PENDING until that module is implemented.
"""

import argparse

from trustrun import __version__

SECTIONS = ("contract", "stress", "consistency", "data")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="trustrun",
        description="The trust layer for AI agents.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="audit an agent on a task")
    audit.add_argument("agent", help="agent under test")
    audit.add_argument("task", help="task to audit the agent on")
    return parser


def cmd_audit(args):
    lines = []
    lines.append("Trustrun audit report")
    lines.append("Agent: {}".format(args.agent))
    lines.append("Task: {}".format(args.task))
    lines.append("")
    for section in SECTIONS:
        lines.append("[{}]".format(section))
        lines.append("  verdict: PENDING (module not implemented yet)")
        lines.append("  evidence: none yet")
        lines.append("")
    lines.append("Overall: PENDING")
    print("\n".join(lines))


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "audit":
        cmd_audit(args)


if __name__ == "__main__":
    main()
