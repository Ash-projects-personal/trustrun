"""Derive run_evals_round219.py from run_evals_round218.py (seed 217)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round218.py")
DST = os.path.join(HERE, "run_evals_round219.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round218 -> round219 replace)
    ("round 218 seed 216)", "round 218 seed 216, round 219 seed 217)", 1),
    # 2. title
    ("Run Trustrun round 218:", "Run Trustrun round 219:", 1),
    # 3. usage line
    ("run_evals_round218.py", "run_evals_round219.py", 1),
    # 4. docstring seed
    ("except seed=216 for diversity", "except seed=217 for diversity", 1),
    # 5. derivation note
    ("derived from the round-217 script", "derived from the round-218 script", 1),
    # 6. SEED value
    ("SEED = 216", "SEED = 217", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-216 (seeds 0-214)",
     "# diversity vs rounds 1-217 (seeds 0-215)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round218/", "reports/round219/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round218", "round219", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round218 refs; exactly one spaced 'round 218' hit
# (the seed-history line itself).
assert text.count("round218") == 0, "stale round218 refs remain"
assert text.count("round 218") == 1, (
    "expected 1 'round 218' hit (seed history), got %d" % text.count("round 218")
)
assert "round 219 seed 217" in text
assert 'SEED = 217' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round219")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
