"""Derive run_evals_round202.py from run_evals_round201.py (seed 200)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round201.py")
DST = os.path.join(HERE, "run_evals_round202.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round201 -> round202 replace)
    ("round 201 seed 199)", "round 201 seed 199, round 202 seed 200)", 1),
    # 2. title
    ("Run Trustrun round 201:", "Run Trustrun round 202:", 1),
    # 3. usage line
    ("run_evals_round201.py", "run_evals_round202.py", 1),
    # 4. docstring seed
    ("except seed=199 for diversity", "except seed=200 for diversity", 1),
    # 5. derivation note
    ("derived from the round-200 script", "derived from the round-201 script", 1),
    # 6. SEED value
    ("SEED = 199", "SEED = 200", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-199 (seeds 0-197)",
     "# diversity vs rounds 1-200 (seeds 0-198)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round201/", "reports/round202/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round201", "round202", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round201 refs; exactly one spaced 'round 201' hit
# (the seed-history line itself).
assert text.count("round201") == 0, "stale round201 refs remain"
assert text.count("round 201") == 1, (
    "expected 1 'round 201' hit (seed history), got %d" % text.count("round 201")
)
assert "round 202 seed 200" in text
assert 'SEED = 200' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round202")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
