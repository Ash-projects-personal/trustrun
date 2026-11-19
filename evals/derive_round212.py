"""Derive run_evals_round212.py from run_evals_round211.py (seed 210)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round211.py")
DST = os.path.join(HERE, "run_evals_round212.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round211 -> round212 replace)
    ("round 211 seed 209)", "round 211 seed 209, round 212 seed 210)", 1),
    # 2. title
    ("Run Trustrun round 211:", "Run Trustrun round 212:", 1),
    # 3. usage line
    ("run_evals_round211.py", "run_evals_round212.py", 1),
    # 4. docstring seed
    ("except seed=209 for diversity", "except seed=210 for diversity", 1),
    # 5. derivation note
    ("derived from the round-210 script", "derived from the round-211 script", 1),
    # 6. SEED value
    ("SEED = 209", "SEED = 210", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-209 (seeds 0-207)",
     "# diversity vs rounds 1-210 (seeds 0-208)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round211/", "reports/round212/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round211", "round212", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round211 refs; exactly one spaced 'round 211' hit
# (the seed-history line itself).
assert text.count("round211") == 0, "stale round211 refs remain"
assert text.count("round 211") == 1, (
    "expected 1 'round 211' hit (seed history), got %d" % text.count("round 211")
)
assert "round 212 seed 210" in text
assert 'SEED = 210' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round212")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
