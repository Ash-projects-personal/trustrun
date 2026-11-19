"""Derive run_evals_round187.py from run_evals_round186.py (seed 185)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round186.py")
DST = os.path.join(HERE, "run_evals_round187.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round186 -> round187 replace)
    ("round 186 seed 184)", "round 186 seed 184, round 187 seed 185)", 1),
    # 2. title
    ("Run Trustrun round 186:", "Run Trustrun round 187:", 1),
    # 3. usage line
    ("run_evals_round186.py", "run_evals_round187.py", 1),
    # 4. docstring seed
    ("except seed=184 for diversity", "except seed=185 for diversity", 1),
    # 5. derivation note
    ("derived from the round-185 script", "derived from the round-186 script", 1),
    # 6. SEED value
    ("SEED = 184", "SEED = 185", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-184 (seeds 0-182)",
     "# diversity vs rounds 1-185 (seeds 0-183)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round186/", "reports/round187/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round186", "round187", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round186 refs; exactly one spaced 'round 186' hit
# (the seed-history line itself).
assert text.count("round186") == 0, "stale round186 refs remain"
assert text.count("round 186") == 1, (
    "expected 1 'round 186' hit (seed history), got %d" % text.count("round 186")
)
assert "round 187 seed 185" in text
assert 'SEED = 185' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round187")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
