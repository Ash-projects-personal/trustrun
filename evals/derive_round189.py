"""Derive run_evals_round189.py from run_evals_round188.py (seed 187)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round188.py")
DST = os.path.join(HERE, "run_evals_round189.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round188 -> round189 replace)
    ("round 188 seed 186)", "round 188 seed 186, round 189 seed 187)", 1),
    # 2. title
    ("Run Trustrun round 188:", "Run Trustrun round 189:", 1),
    # 3. usage line
    ("run_evals_round188.py", "run_evals_round189.py", 1),
    # 4. docstring seed
    ("except seed=186 for diversity", "except seed=187 for diversity", 1),
    # 5. derivation note
    ("derived from the round-187 script", "derived from the round-188 script", 1),
    # 6. SEED value
    ("SEED = 186", "SEED = 187", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-186 (seeds 0-184)",
     "# diversity vs rounds 1-187 (seeds 0-185)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round188/", "reports/round189/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round188", "round189", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round188 refs; exactly one spaced 'round 188' hit
# (the seed-history line itself).
assert text.count("round188") == 0, "stale round188 refs remain"
assert text.count("round 188") == 1, (
    "expected 1 'round 188' hit (seed history), got %d" % text.count("round 188")
)
assert "round 189 seed 187" in text
assert 'SEED = 187' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round189")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
