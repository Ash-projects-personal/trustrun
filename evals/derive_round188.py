"""Derive run_evals_round188.py from run_evals_round187.py (seed 186)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round187.py")
DST = os.path.join(HERE, "run_evals_round188.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round187 -> round188 replace)
    ("round 187 seed 185)", "round 187 seed 185, round 188 seed 186)", 1),
    # 2. title
    ("Run Trustrun round 187:", "Run Trustrun round 188:", 1),
    # 3. usage line
    ("run_evals_round187.py", "run_evals_round188.py", 1),
    # 4. docstring seed
    ("except seed=185 for diversity", "except seed=186 for diversity", 1),
    # 5. derivation note
    ("derived from the round-186 script", "derived from the round-187 script", 1),
    # 6. SEED value
    ("SEED = 185", "SEED = 186", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-185 (seeds 0-183)",
     "# diversity vs rounds 1-186 (seeds 0-184)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round187/", "reports/round188/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round187", "round188", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round187 refs; exactly one spaced 'round 187' hit
# (the seed-history line itself).
assert text.count("round187") == 0, "stale round187 refs remain"
assert text.count("round 187") == 1, (
    "expected 1 'round 187' hit (seed history), got %d" % text.count("round 187")
)
assert "round 188 seed 186" in text
assert 'SEED = 186' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round188")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
