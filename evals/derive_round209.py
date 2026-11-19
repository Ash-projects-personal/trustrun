"""Derive run_evals_round209.py from run_evals_round208.py (seed 207)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round208.py")
DST = os.path.join(HERE, "run_evals_round209.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round208 -> round209 replace)
    ("round 208 seed 206)", "round 208 seed 206, round 209 seed 207)", 1),
    # 2. title
    ("Run Trustrun round 208:", "Run Trustrun round 209:", 1),
    # 3. usage line
    ("run_evals_round208.py", "run_evals_round209.py", 1),
    # 4. docstring seed
    ("except seed=206 for diversity", "except seed=207 for diversity", 1),
    # 5. derivation note
    ("derived from the round-207 script", "derived from the round-208 script", 1),
    # 6. SEED value
    ("SEED = 206", "SEED = 207", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-206 (seeds 0-204)",
     "# diversity vs rounds 1-207 (seeds 0-205)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round208/", "reports/round209/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round208", "round209", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round208 refs; exactly one spaced 'round 208' hit
# (the seed-history line itself).
assert text.count("round208") == 0, "stale round208 refs remain"
assert text.count("round 208") == 1, (
    "expected 1 'round 208' hit (seed history), got %d" % text.count("round 208")
)
assert "round 209 seed 207" in text
assert 'SEED = 207' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round209")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
