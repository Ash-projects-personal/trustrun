"""Derive run_evals_round186.py from run_evals_round185.py (seed 184)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round185.py")
DST = os.path.join(HERE, "run_evals_round186.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round185 -> round186 replace)
    ("round 185 seed 183)", "round 185 seed 183, round 186 seed 184)", 1),
    # 2. title
    ("Run Trustrun round 185:", "Run Trustrun round 186:", 1),
    # 3. usage line
    ("run_evals_round185.py", "run_evals_round186.py", 1),
    # 4. docstring seed (round-185 script carried stale seed=182; round 186 uses 184)
    ("except seed=182 for diversity", "except seed=184 for diversity", 1),
    # 5. derivation note
    ("derived from the round-184 script", "derived from the round-185 script", 1),
    # 6. SEED value
    ("SEED = 183", "SEED = 184", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-183 (seeds 0-181)",
     "# diversity vs rounds 1-184 (seeds 0-182)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round185/", "reports/round186/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round185", "round186", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round185 refs; exactly one spaced 'round 185' hit
# (the seed-history line itself).
assert text.count("round185") == 0, "stale round185 refs remain"
assert text.count("round 185") == 1, (
    "expected 1 'round 185' hit (seed history), got %d" % text.count("round 185")
)
assert "round 186 seed 184" in text
assert 'SEED = 184' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round186")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
