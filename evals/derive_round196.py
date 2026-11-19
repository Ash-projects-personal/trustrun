"""Derive run_evals_round196.py from run_evals_round195.py (seed 194)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round195.py")
DST = os.path.join(HERE, "run_evals_round196.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round195 -> round196 replace)
    ("round 195 seed 193)", "round 195 seed 193, round 196 seed 194)", 1),
    # 2. title
    ("Run Trustrun round 195:", "Run Trustrun round 196:", 1),
    # 3. usage line
    ("run_evals_round195.py", "run_evals_round196.py", 1),
    # 4. docstring seed
    ("except seed=193 for diversity", "except seed=194 for diversity", 1),
    # 5. derivation note
    ("derived from the round-194 script", "derived from the round-195 script", 1),
    # 6. SEED value
    ("SEED = 193", "SEED = 194", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-193 (seeds 0-191)",
     "# diversity vs rounds 1-194 (seeds 0-192)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round195/", "reports/round196/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round195", "round196", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round195 refs; exactly one spaced 'round 195' hit
# (the seed-history line itself).
assert text.count("round195") == 0, "stale round195 refs remain"
assert text.count("round 195") == 1, (
    "expected 1 'round 195' hit (seed history), got %d" % text.count("round 195")
)
assert "round 196 seed 194" in text
assert 'SEED = 194' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round196")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
