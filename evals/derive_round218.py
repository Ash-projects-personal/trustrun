"""Derive run_evals_round218.py from run_evals_round217.py (seed 216)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round217.py")
DST = os.path.join(HERE, "run_evals_round218.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round217 -> round218 replace)
    ("round 217 seed 215)", "round 217 seed 215, round 218 seed 216)", 1),
    # 2. title
    ("Run Trustrun round 217:", "Run Trustrun round 218:", 1),
    # 3. usage line
    ("run_evals_round217.py", "run_evals_round218.py", 1),
    # 4. docstring seed
    ("except seed=215 for diversity", "except seed=216 for diversity", 1),
    # 5. derivation note
    ("derived from the round-216 script", "derived from the round-217 script", 1),
    # 6. SEED value
    ("SEED = 215", "SEED = 216", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-215 (seeds 0-213)",
     "# diversity vs rounds 1-216 (seeds 0-214)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round217/", "reports/round218/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round217", "round218", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round217 refs; exactly one spaced 'round 217' hit
# (the seed-history line itself).
assert text.count("round217") == 0, "stale round217 refs remain"
assert text.count("round 217") == 1, (
    "expected 1 'round 217' hit (seed history), got %d" % text.count("round 217")
)
assert "round 218 seed 216" in text
assert 'SEED = 216' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round218")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
