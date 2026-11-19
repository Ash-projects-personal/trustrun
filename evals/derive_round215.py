"""Derive run_evals_round215.py from run_evals_round214.py (seed 213)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round214.py")
DST = os.path.join(HERE, "run_evals_round215.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round214 -> round215 replace)
    ("round 214 seed 212)", "round 214 seed 212, round 215 seed 213)", 1),
    # 2. title
    ("Run Trustrun round 214:", "Run Trustrun round 215:", 1),
    # 3. usage line
    ("run_evals_round214.py", "run_evals_round215.py", 1),
    # 4. docstring seed
    ("except seed=212 for diversity", "except seed=213 for diversity", 1),
    # 5. derivation note
    ("derived from the round-213 script", "derived from the round-214 script", 1),
    # 6. SEED value
    ("SEED = 212", "SEED = 213", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-212 (seeds 0-210)",
     "# diversity vs rounds 1-213 (seeds 0-211)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round214/", "reports/round215/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round214", "round215", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round214 refs; exactly one spaced 'round 214' hit
# (the seed-history line itself).
assert text.count("round214") == 0, "stale round214 refs remain"
assert text.count("round 214") == 1, (
    "expected 1 'round 214' hit (seed history), got %d" % text.count("round 214")
)
assert "round 215 seed 213" in text
assert 'SEED = 213' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round215")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
