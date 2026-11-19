# How the numbers are counted

Every public number about Trustrun comes from the stored results in
this repository. Nothing is estimated. Recompute all of them with:

```bash
python3 scripts/count_stats.py
```

The script prints the counts as JSON and exits nonzero if the dataset
accounting table does not re-sum exactly to its own printed total.

## Definitions

**Audit.** One full `run_audit` over one agent on one task, or one
calibration or validation run of the same shape. Each audit is a
labeled row in the Totals table of `evals/DATASET.md`, and each row
names the stored summary file it was counted from.

**Labeled check (check-level labeled judgment).** One labeled verdict
at check granularity inside an audit. A full audit contributes 8 base
checks (contract claim verdicts, the consistency checks, and the data
checks) plus one judgment per attack in the stress battery, recorded
as survived, not survived, or unverified. Anything a check cannot
determine is recorded as unverified and is never counted as a pass.

**Checks per audit.** The battery grew as new attack classes landed,
so the per-audit count depends on when the audit ran:

| Rounds | Attacks in battery | Checks per audit |
| --- | --- | --- |
| 1-3 | 9 | 17 |
| 4-8 | 11 | 19 |
| 9-93 | 13 | 21 |
| 94-205 | 14 | 22 |
| 206-220 | 15 | 23 |
| 221 | 16 | 24 |
| 222-241 | 18 | 26 |
| 242 and later | 19 | 27 |

Single-purpose rows (one probe-case verdict, one tenet verdict) count
as 1 labeled check each, as recorded in the Totals table.

**Framework audited.** One real-agent audit row in the Totals table:
one named agent implementation driven through the standard 25-task
battery (seed 0, k=5) with its verdicts and evidence stored under
`evals/reports/real_agents/<name>/`. A framework that contributes
more than one agent class (for example a second agent from the same
package) counts once per audited agent. Audits still in progress,
whose slices have not been folded into the Totals table, are not
counted.

## Current counts

Counted 2026-11-19 from this checkout with `scripts/count_stats.py`:

- Audits: 74,817
- Labeled checks: 1,714,868
- Frameworks audited (real-agent audit rows): 77
- Test suite (Python 3.12, this checkout): 1,701 passed, 212 skipped,
  0 failed, run with `python -m pytest tests/ -q`. Test counts change
  as tests are added; the suite result for a given checkout is
  whatever that command prints.

The dataset keeps growing as new eval rounds and real-agent audits
land, so these counts are a snapshot. The script always reports the
counts for the checkout it runs in.

## Which runs are automated and which are manual

Automated:

- The labeled eval rounds (`evals/run_evals_round*.py`) run on a
  schedule against the clean-room agents in the battery, at fixed
  seeds, and write one summary file per round.
- The test suite runs in CI on every push and pull request, on
  Python 3.9, 3.11, and 3.12.

Manual:

- Each real-agent audit is set up by hand: the framework is pinned to
  a release, its agent loop is wired to the battery through an
  adapter in `evals/real_agents/`, the run is watched, and the stored
  results are re-counted from the summary file before the audit is
  folded into `evals/DATASET.md`.
- The counting in this file and in the README is refreshed by running
  `scripts/count_stats.py` and copying its output, never by editing a
  number by hand.
