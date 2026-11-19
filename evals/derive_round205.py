"""Derive run_evals_round205.py from run_evals_round204.py (seed 203)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round204.py")
DST = os.path.join(HERE, "run_evals_round205.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round204 -> round205 replace)
    ("round 204 seed 202)", "round 204 seed 202, round 205 seed 203)", 1),
    # 2. title
    ("Run Trustrun round 204:", "Run Trustrun round 205:", 1),
    # 3. usage line
    ("run_evals_round204.py", "run_evals_round205.py", 1),
    # 4. docstring seed
    ("except seed=202 for diversity", "except seed=203 for diversity", 1),
    # 5. derivation note
    ("derived from the round-203 script", "derived from the round-204 script", 1),
    # 6. SEED value
    ("SEED = 202", "SEED = 203", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-202 (seeds 0-200)",
     "# diversity vs rounds 1-203 (seeds 0-201)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round204/", "reports/round205/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round204", "round205", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round204 refs; exactly one spaced 'round 204' hit
# (the seed-history line itself).
assert text.count("round204") == 0, "stale round204 refs remain"
assert text.count("round 204") == 1, (
    "expected 1 'round 204' hit (seed history), got %d" % text.count("round 204")
)
assert "round 205 seed 203" in text
assert 'SEED = 203' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round205")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
