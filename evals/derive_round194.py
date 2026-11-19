"""Derive run_evals_round194.py from run_evals_round193.py (seed 192)."""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round193.py")
DST = os.path.join(HERE, "run_evals_round194.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round193 -> round194 replace)
    ("round 193 seed 191)", "round 193 seed 191, round 194 seed 192)", 1),
    # 2. title
    ("Run Trustrun round 193:", "Run Trustrun round 194:", 1),
    # 3. usage line
    ("run_evals_round193.py", "run_evals_round194.py", 1),
    # 4. docstring seed
    ("except seed=191 for diversity", "except seed=192 for diversity", 1),
    # 5. derivation note
    ("derived from the round-192 script", "derived from the round-193 script", 1),
    # 6. SEED value
    ("SEED = 191", "SEED = 192", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-191 (seeds 0-189)",
     "# diversity vs rounds 1-192 (seeds 0-190)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round193/", "reports/round194/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round193", "round194", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round193 refs; exactly one spaced 'round 193' hit
# (the seed-history line itself).
assert text.count("round193") == 0, "stale round193 refs remain"
assert text.count("round 193") == 1, (
    "expected 1 'round 193' hit (seed history), got %d" % text.count("round 193")
)
assert "round 194 seed 192" in text
assert 'SEED = 192' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round194")' in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
