"""Derive run_evals_round221.py from run_evals_round220.py (seed 219)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round220.py")
DST = os.path.join(HERE, "run_evals_round221.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round220 -> round221 replace)
    ("round 220 seed 218)", "round 220 seed 218, round 221 seed 219)", 1),
    # 2. title
    ("Run Trustrun round 220:", "Run Trustrun round 221:", 1),
    # 3. usage line
    ("run_evals_round220.py", "run_evals_round221.py", 1),
    # 4. docstring seed
    ("except seed=218 for diversity", "except seed=219 for diversity", 1),
    # 5. derivation note
    ("derived from the round-219 script", "derived from the round-220 script", 1),
    # 6. SEED value
    ("SEED = 218", "SEED = 219", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-218 (seeds 0-216)",
     "# diversity vs rounds 1-219 (seeds 0-217)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round220/", "reports/round221/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round220", "round221", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round220 refs; exactly one spaced 'round 220' hit
# (the seed-history line itself).
assert text.count("round220") == 0, "stale round220 refs remain"
assert text.count("round 220") == 1, (
    "expected 1 'round 220' hit (seed history), got %d" % text.count("round 220")
)
assert "round 221 seed 219" in text
assert 'SEED = 219' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round221")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
