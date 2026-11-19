"""Derive run_evals_round203.py from run_evals_round202.py (seed 201)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round202.py")
DST = os.path.join(HERE, "run_evals_round203.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round202 -> round203 replace)
    ("round 202 seed 200)", "round 202 seed 200, round 203 seed 201)", 1),
    # 2. title
    ("Run Trustrun round 202:", "Run Trustrun round 203:", 1),
    # 3. usage line
    ("run_evals_round202.py", "run_evals_round203.py", 1),
    # 4. docstring seed
    ("except seed=200 for diversity", "except seed=201 for diversity", 1),
    # 5. derivation note
    ("derived from the round-201 script", "derived from the round-202 script", 1),
    # 6. SEED value
    ("SEED = 200", "SEED = 201", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-200 (seeds 0-198)",
     "# diversity vs rounds 1-201 (seeds 0-199)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round202/", "reports/round203/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round202", "round203", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round202 refs; exactly one spaced 'round 202' hit
# (the seed-history line itself).
assert text.count("round202") == 0, "stale round202 refs remain"
assert text.count("round 202") == 1, (
    "expected 1 'round 202' hit (seed history), got %d" % text.count("round 202")
)
assert "round 203 seed 201" in text
assert 'SEED = 201' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round203")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
