"""Derive run_evals_round193.py from run_evals_round192.py (seed 191)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round192.py")
DST = os.path.join(HERE, "run_evals_round193.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round192 -> round193 replace)
    ("round 192 seed 190)", "round 192 seed 190, round 193 seed 191)", 1),
    # 2. title
    ("Run Trustrun round 192:", "Run Trustrun round 193:", 1),
    # 3. usage line
    ("run_evals_round192.py", "run_evals_round193.py", 1),
    # 4. docstring seed
    ("except seed=190 for diversity", "except seed=191 for diversity", 1),
    # 5. derivation note
    ("derived from the round-191 script", "derived from the round-192 script", 1),
    # 6. SEED value
    ("SEED = 190", "SEED = 191", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-190 (seeds 0-188)",
     "# diversity vs rounds 1-191 (seeds 0-189)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round192/", "reports/round193/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round192", "round193", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round192 refs; exactly one spaced 'round 192' hit
# (the seed-history line itself).
assert text.count("round192") == 0, "stale round192 refs remain"
assert text.count("round 192") == 1, (
    "expected 1 'round 192' hit (seed history), got %d" % text.count("round 192")
)
assert "round 193 seed 191" in text
assert 'SEED = 191' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round193")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
