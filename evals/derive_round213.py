"""Derive run_evals_round213.py from run_evals_round212.py (seed 211)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round212.py")
DST = os.path.join(HERE, "run_evals_round213.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round212 -> round213 replace)
    ("round 212 seed 210)", "round 212 seed 210, round 213 seed 211)", 1),
    # 2. title
    ("Run Trustrun round 212:", "Run Trustrun round 213:", 1),
    # 3. usage line
    ("run_evals_round212.py", "run_evals_round213.py", 1),
    # 4. docstring seed
    ("except seed=210 for diversity", "except seed=211 for diversity", 1),
    # 5. derivation note
    ("derived from the round-211 script", "derived from the round-212 script", 1),
    # 6. SEED value
    ("SEED = 210", "SEED = 211", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-210 (seeds 0-208)",
     "# diversity vs rounds 1-211 (seeds 0-209)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round212/", "reports/round213/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round212", "round213", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round212 refs; exactly one spaced 'round 212' hit
# (the seed-history line itself).
assert text.count("round212") == 0, "stale round212 refs remain"
assert text.count("round 212") == 1, (
    "expected 1 'round 212' hit (seed history), got %d" % text.count("round 212")
)
assert "round 213 seed 211" in text
assert 'SEED = 211' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round213")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
