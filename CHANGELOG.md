# Changelog

All notable changes to Trustrun are recorded here. The format
follows Keep a Changelog, and the project uses semantic versioning
for tagged releases.

## [0.1.0] - 2026-11-19

First tagged public release.

### Added

- Four module audit (contract, stress, consistency, data) behind
  one CLI report, with READY, REVIEW, and BLOCK verdicts and a
  SHA-256 evidence hash chain over the verdicts.
- Stress battery of 19 attack classes, including plaintext and
  invisible encoding prompt injection, tool failure and tool
  failure visibility, monitor and evaluator tampering, misleading
  principal, clarification injection, task tampering, CI harness
  injection, prompt adware, and page reader injection.
- RAISE Act style examiner report renderer (a report format, not
  legal advice).
- Labeled audit dataset in `evals/`: 74,817 audits and 1,714,868
  labeled checks as of this release, including audits of 77 agent
  frameworks driven through the standard 25 task battery. Counting
  definitions in STATS.md; recompute with scripts/count_stats.py.
- STATS.md and METHODOLOGY.md documenting how every public number
  is counted, the task battery, the injection test setup, the
  seeds, and the limits of the tests.
- Sample reports for all three verdicts in docs/sample-report.md.
- CI on Python 3.9, 3.11, and 3.12.

### Changed

- README claims audited against the stored results. Every number
  in the README now names the file or script that reproduces it,
  and wording was softened from proof language to evidence
  language throughout.

### Removed

- The claim of 228 poisoned observations delivered verbatim. The
  keyed real-model result files behind it were never stored in
  this repo, so the number cannot be reproduced and is no longer
  published.
- The stale test count (70/70) and the stale Pact dogfood count
  (32 records). Both were replaced by re-run numbers.
