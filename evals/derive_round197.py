"""Derive run_evals_round197.py from run_evals_round196.py (seed 195)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round196.py")
DST = os.path.join(HERE, "run_evals_round197.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round196 -> round197 replace)
    ("round 196 seed 194)", "round 196 seed 194, round 197 seed 195)", 1),
    # 2. title
    ("Run Trustrun round 196:", "Run Trustrun round 197:", 1),
    # 3. usage line
    ("run_evals_round196.py", "run_evals_round197.py", 1),
    # 4. docstring seed
    ("except seed=194 for diversity", "except seed=195 for diversity", 1),
    # 5. derivation note
    ("derived from the round-195 script", "derived from the round-196 script", 1),
    # 6. SEED value
    ("SEED = 194", "SEED = 195", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-194 (seeds 0-192)",
     "# diversity vs rounds 1-195 (seeds 0-193)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round196/", "reports/round197/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round196", "round197", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round196 refs; exactly one spaced 'round 196' hit
# (the seed-history line itself).
assert text.count("round196") == 0, "stale round196 refs remain"
assert text.count("round 196") == 1, (
    "expected 1 'round 196' hit (seed history), got %d" % text.count("round 196")
)
assert "round 197 seed 195" in text
assert 'SEED = 195' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round197")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
