"""Derive run_evals_round195.py from run_evals_round194.py (seed 193)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round194.py")
DST = os.path.join(HERE, "run_evals_round195.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round194 -> round195 replace)
    ("round 194 seed 192)", "round 194 seed 192, round 195 seed 193)", 1),
    # 2. title
    ("Run Trustrun round 194:", "Run Trustrun round 195:", 1),
    # 3. usage line
    ("run_evals_round194.py", "run_evals_round195.py", 1),
    # 4. docstring seed
    ("except seed=192 for diversity", "except seed=193 for diversity", 1),
    # 5. derivation note
    ("derived from the round-193 script", "derived from the round-194 script", 1),
    # 6. SEED value
    ("SEED = 192", "SEED = 193", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-192 (seeds 0-190)",
     "# diversity vs rounds 1-193 (seeds 0-191)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round194/", "reports/round195/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round194", "round195", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round194 refs; exactly one spaced 'round 194' hit
# (the seed-history line itself).
assert text.count("round194") == 0, "stale round194 refs remain"
assert text.count("round 194") == 1, (
    "expected 1 'round 194' hit (seed history), got %d" % text.count("round 194")
)
assert "round 195 seed 193" in text
assert 'SEED = 193' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round195")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
