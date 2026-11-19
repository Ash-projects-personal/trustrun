"""Derive run_evals_round217.py from run_evals_round216.py (seed 215)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round216.py")
DST = os.path.join(HERE, "run_evals_round217.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round216 -> round217 replace)
    ("round 216 seed 214)", "round 216 seed 214, round 217 seed 215)", 1),
    # 2. title
    ("Run Trustrun round 216:", "Run Trustrun round 217:", 1),
    # 3. usage line
    ("run_evals_round216.py", "run_evals_round217.py", 1),
    # 4. docstring seed
    ("except seed=214 for diversity", "except seed=215 for diversity", 1),
    # 5. derivation note
    ("derived from the round-215 script", "derived from the round-216 script", 1),
    # 6. SEED value
    ("SEED = 214", "SEED = 215", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-214 (seeds 0-212)",
     "# diversity vs rounds 1-215 (seeds 0-213)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round216/", "reports/round217/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round216", "round217", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round216 refs; exactly one spaced 'round 216' hit
# (the seed-history line itself).
assert text.count("round216") == 0, "stale round216 refs remain"
assert text.count("round 216") == 1, (
    "expected 1 'round 216' hit (seed history), got %d" % text.count("round 216")
)
assert "round 217 seed 215" in text
assert 'SEED = 215' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round217")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
