# Contributing

Thanks for looking at Trustrun. The project rule that matters most:
every public number must be reproducible from the stored results in
this repo. If a change adds a claim, it adds the file or script that
backs it.

## Setup

```bash
pip install -e ".[test]"
```

Trustrun supports Python 3.9, 3.11, and 3.12. CI runs the test
suite on all three on every push and pull request.

## Running the tests

```bash
python -m pytest tests/ -q
```

The suite is deterministic. Tests that need data living outside
this repo (for example the Pact experiment records used by the
contract dogfood) skip cleanly when the data is absent; a skip is
not a pass, and the suite prints the real counts either way.

## Checking the numbers

```bash
python3 scripts/count_stats.py
```

This recomputes the audit count, the labeled check count, and the
framework count from `evals/DATASET.md`, and re-counts the two key
findings from their stored summary files. It exits nonzero if the
dataset table does not re-sum to its own printed total. Run it
before changing any number in README.md or STATS.md, and copy its
output rather than editing a number by hand. The definitions are in
STATS.md and the test setup is in METHODOLOGY.md.

## Ground rules for changes

- Anything a check cannot determine is recorded as unverified and
  never becomes a pass. New modules and attacks keep that rule.
- Stored results are evidence. Do not edit a stored summary or
  report to make a number come out differently; re-run the audit
  instead, at the seed its script names.
- Real-agent audits pin the framework to a release, record the
  version and the model driver in the summary file, and state the
  stub model caveat wherever a finding is reported.
- Findings about a real shipped product are reported privately to
  the vendor's security contact. Do not publish a finding about a
  named product in an issue or a pull request.
