"""Derive run_evals_round190.py from run_evals_round189.py (seed 188)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round189.py")
DST = os.path.join(HERE, "run_evals_round190.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round189 -> round190 replace)
    ("round 189 seed 187)", "round 189 seed 187, round 190 seed 188)", 1),
    # 2. title
    ("Run Trustrun round 189:", "Run Trustrun round 190:", 1),
    # 3. usage line
    ("run_evals_round189.py", "run_evals_round190.py", 1),
    # 4. docstring seed
    ("except seed=187 for diversity", "except seed=188 for diversity", 1),
    # 5. derivation note
    ("derived from the round-188 script", "derived from the round-189 script", 1),
    # 6. SEED value
    ("SEED = 187", "SEED = 188", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-187 (seeds 0-185)",
     "# diversity vs rounds 1-188 (seeds 0-186)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round189/", "reports/round190/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round189", "round190", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round189 refs; exactly one spaced 'round 189' hit
# (the seed-history line itself).
assert text.count("round189") == 0, "stale round189 refs remain"
assert text.count("round 189") == 1, (
    "expected 1 'round 189' hit (seed history), got %d" % text.count("round 189")
)
assert "round 190 seed 188" in text
assert 'SEED = 188' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round190")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
