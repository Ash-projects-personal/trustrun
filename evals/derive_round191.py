"""Derive run_evals_round191.py from run_evals_round190.py (seed 189)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round190.py")
DST = os.path.join(HERE, "run_evals_round191.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round190 -> round191 replace)
    ("round 190 seed 188)", "round 190 seed 188, round 191 seed 189)", 1),
    # 2. title
    ("Run Trustrun round 190:", "Run Trustrun round 191:", 1),
    # 3. usage line
    ("run_evals_round190.py", "run_evals_round191.py", 1),
    # 4. docstring seed
    ("except seed=188 for diversity", "except seed=189 for diversity", 1),
    # 5. derivation note
    ("derived from the round-189 script", "derived from the round-190 script", 1),
    # 6. SEED value
    ("SEED = 188", "SEED = 189", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-188 (seeds 0-186)",
     "# diversity vs rounds 1-189 (seeds 0-187)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round190/", "reports/round191/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round190", "round191", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round190 refs; exactly one spaced 'round 190' hit
# (the seed-history line itself).
assert text.count("round190") == 0, "stale round190 refs remain"
assert text.count("round 190") == 1, (
    "expected 1 'round 190' hit (seed history), got %d" % text.count("round 190")
)
assert "round 191 seed 189" in text
assert 'SEED = 189' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round191")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
