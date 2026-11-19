"""Derive run_evals_round211.py from run_evals_round210.py (seed 209)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round210.py")
DST = os.path.join(HERE, "run_evals_round211.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round210 -> round211 replace)
    ("round 210 seed 208)", "round 210 seed 208, round 211 seed 209)", 1),
    # 2. title
    ("Run Trustrun round 210:", "Run Trustrun round 211:", 1),
    # 3. usage line
    ("run_evals_round210.py", "run_evals_round211.py", 1),
    # 4. docstring seed
    ("except seed=208 for diversity", "except seed=209 for diversity", 1),
    # 5. derivation note
    ("derived from the round-209 script", "derived from the round-210 script", 1),
    # 6. SEED value
    ("SEED = 208", "SEED = 209", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-208 (seeds 0-206)",
     "# diversity vs rounds 1-209 (seeds 0-207)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round210/", "reports/round211/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round210", "round211", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round210 refs; exactly one spaced 'round 210' hit
# (the seed-history line itself).
assert text.count("round210") == 0, "stale round210 refs remain"
assert text.count("round 210") == 1, (
    "expected 1 'round 210' hit (seed history), got %d" % text.count("round 210")
)
assert "round 211 seed 209" in text
assert 'SEED = 209' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round211")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
