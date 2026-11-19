"""Derive run_evals_round220.py from run_evals_round219.py (seed 218)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round219.py")
DST = os.path.join(HERE, "run_evals_round220.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round219 -> round220 replace)
    ("round 219 seed 217)", "round 219 seed 217, round 220 seed 218)", 1),
    # 2. title
    ("Run Trustrun round 219:", "Run Trustrun round 220:", 1),
    # 3. usage line
    ("run_evals_round219.py", "run_evals_round220.py", 1),
    # 4. docstring seed
    ("except seed=217 for diversity", "except seed=218 for diversity", 1),
    # 5. derivation note
    ("derived from the round-218 script", "derived from the round-219 script", 1),
    # 6. SEED value
    ("SEED = 217", "SEED = 218", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-217 (seeds 0-215)",
     "# diversity vs rounds 1-218 (seeds 0-216)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round219/", "reports/round220/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round219", "round220", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round219 refs; exactly one spaced 'round 219' hit
# (the seed-history line itself).
assert text.count("round219") == 0, "stale round219 refs remain"
assert text.count("round 219") == 1, (
    "expected 1 'round 219' hit (seed history), got %d" % text.count("round 219")
)
assert "round 220 seed 218" in text
assert 'SEED = 218' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round220")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
