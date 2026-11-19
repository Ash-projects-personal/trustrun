"""Derive run_evals_round204.py from run_evals_round203.py (seed 202)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round203.py")
DST = os.path.join(HERE, "run_evals_round204.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round203 -> round204 replace)
    ("round 203 seed 201)", "round 203 seed 201, round 204 seed 202)", 1),
    # 2. title
    ("Run Trustrun round 203:", "Run Trustrun round 204:", 1),
    # 3. usage line
    ("run_evals_round203.py", "run_evals_round204.py", 1),
    # 4. docstring seed
    ("except seed=201 for diversity", "except seed=202 for diversity", 1),
    # 5. derivation note
    ("derived from the round-202 script", "derived from the round-203 script", 1),
    # 6. SEED value
    ("SEED = 201", "SEED = 202", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-201 (seeds 0-199)",
     "# diversity vs rounds 1-202 (seeds 0-200)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round203/", "reports/round204/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round203", "round204", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round203 refs; exactly one spaced 'round 203' hit
# (the seed-history line itself).
assert text.count("round203") == 0, "stale round203 refs remain"
assert text.count("round 203") == 1, (
    "expected 1 'round 203' hit (seed history), got %d" % text.count("round 203")
)
assert "round 204 seed 202" in text
assert 'SEED = 202' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round204")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
