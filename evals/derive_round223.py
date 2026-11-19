"""Derive run_evals_round223.py from run_evals_round222.py (seed 221).

Round 223 runs the same 18-attack battery as round 222 (task_tamper 16th,
ci_harness_inject 17th, prompt_adware 18th): 26 checks per audit, 7,800
per round. Round 222 was the first 18-attack round and came back
aggregate-identical to round 221 (zero verdict flips: both new attacks
produced zero survived=False outcomes across 300 audits).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round222.py")
DST = os.path.join(HERE, "run_evals_round223.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round222 -> round223 replace)
    ("round 222 seed 220)", "round 222 seed 220, round 223 seed 221)", 1),
    # 2. title
    ("Run Trustrun round 222:", "Run Trustrun round 223:", 1),
    # 3. usage line
    ("run_evals_round222.py", "run_evals_round223.py", 1),
    # 4. docstring seed
    ("except seed=220 for diversity", "except seed=221 for diversity", 1),
    # 5. derivation note
    ("derived from the round-221 script", "derived from the round-222 script", 1),
    # 6. SEED value
    ("SEED = 220", "SEED = 221", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-220 (seeds 0-218)",
     "# diversity vs rounds 1-221 (seeds 0-219)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round222/", "reports/round223/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round222", "round223", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round222 refs; exactly one spaced 'round 222' hit
# (the seed-history line itself).
assert text.count("round222") == 0, "stale round222 refs remain"
assert text.count("round 222") == 1, (
    "expected 1 'round 222' hit (seed history), got %d" % text.count("round 222")
)
assert "round 223 seed 221" in text
assert 'SEED = 221' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round223")' in text
assert "18-attack battery" in text
assert "26 per audit" in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
