"""Derive run_evals_round216.py from run_evals_round215.py (seed 214)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round215.py")
DST = os.path.join(HERE, "run_evals_round216.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round215 -> round216 replace)
    ("round 215 seed 213)", "round 215 seed 213, round 216 seed 214)", 1),
    # 2. title
    ("Run Trustrun round 215:", "Run Trustrun round 216:", 1),
    # 3. usage line
    ("run_evals_round215.py", "run_evals_round216.py", 1),
    # 4. docstring seed
    ("except seed=213 for diversity", "except seed=214 for diversity", 1),
    # 5. derivation note
    ("derived from the round-214 script", "derived from the round-215 script", 1),
    # 6. SEED value
    ("SEED = 213", "SEED = 214", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-213 (seeds 0-211)",
     "# diversity vs rounds 1-214 (seeds 0-212)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round215/", "reports/round216/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round215", "round216", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round215 refs; exactly one spaced 'round 215' hit
# (the seed-history line itself).
assert text.count("round215") == 0, "stale round215 refs remain"
assert text.count("round 215") == 1, (
    "expected 1 'round 215' hit (seed history), got %d" % text.count("round 215")
)
assert "round 216 seed 214" in text
assert 'SEED = 214' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round216")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
