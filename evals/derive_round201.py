"""Derive run_evals_round201.py from run_evals_round200.py (seed 199)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round200.py")
DST = os.path.join(HERE, "run_evals_round201.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round200 -> round201 replace)
    ("round 200 seed 198)", "round 200 seed 198, round 201 seed 199)", 1),
    # 2. title
    ("Run Trustrun round 200:", "Run Trustrun round 201:", 1),
    # 3. usage line
    ("run_evals_round200.py", "run_evals_round201.py", 1),
    # 4. docstring seed
    ("except seed=198 for diversity", "except seed=199 for diversity", 1),
    # 5. derivation note
    ("derived from the round-199 script", "derived from the round-200 script", 1),
    # 6. SEED value
    ("SEED = 198", "SEED = 199", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-198 (seeds 0-196)",
     "# diversity vs rounds 1-199 (seeds 0-197)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round200/", "reports/round201/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round200", "round201", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round200 refs; exactly one spaced 'round 200' hit
# (the seed-history line itself).
assert text.count("round200") == 0, "stale round200 refs remain"
assert text.count("round 200") == 1, (
    "expected 1 'round 200' hit (seed history), got %d" % text.count("round 200")
)
assert "round 201 seed 199" in text
assert 'SEED = 199' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round201")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
