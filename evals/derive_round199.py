"""Derive run_evals_round199.py from run_evals_round198.py (seed 197)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round198.py")
DST = os.path.join(HERE, "run_evals_round199.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round198 -> round199 replace)
    ("round 198 seed 196)", "round 198 seed 196, round 199 seed 197)", 1),
    # 2. title
    ("Run Trustrun round 198:", "Run Trustrun round 199:", 1),
    # 3. usage line
    ("run_evals_round198.py", "run_evals_round199.py", 1),
    # 4. docstring seed
    ("except seed=196 for diversity", "except seed=197 for diversity", 1),
    # 5. derivation note
    ("derived from the round-197 script", "derived from the round-198 script", 1),
    # 6. SEED value
    ("SEED = 196", "SEED = 197", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-196 (seeds 0-194)",
     "# diversity vs rounds 1-197 (seeds 0-195)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round198/", "reports/round199/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round198", "round199", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round198 refs; exactly one spaced 'round 198' hit
# (the seed-history line itself).
assert text.count("round198") == 0, "stale round198 refs remain"
assert text.count("round 198") == 1, (
    "expected 1 'round 198' hit (seed history), got %d" % text.count("round 198")
)
assert "round 199 seed 197" in text
assert 'SEED = 197' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round199")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
