"""Derive run_evals_round224.py from run_evals_round223.py (seed 222).

Round 224 runs the same 18-attack battery as rounds 222-223
(task_tamper 16th, ci_harness_inject 17th, prompt_adware 18th): 26
checks per audit, 7,800 per round. Round 223 was aggregate-identical
to round 222 (summary.json md5 e42d092a506d8a6faddb4c7a5cee4470).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round223.py")
DST = os.path.join(HERE, "run_evals_round224.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round223 -> round224 replace)
    ("round 223 seed 221)", "round 223 seed 221, round 224 seed 222)", 1),
    # 2. title
    ("Run Trustrun round 223:", "Run Trustrun round 224:", 1),
    # 3. usage line
    ("run_evals_round223.py", "run_evals_round224.py", 1),
    # 4. docstring seed
    ("except seed=221 for diversity", "except seed=222 for diversity", 1),
    # 5. derivation note
    ("derived from the round-222 script", "derived from the round-223 script", 1),
    # 6. SEED value
    ("SEED = 221", "SEED = 222", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-221 (seeds 0-219)",
     "# diversity vs rounds 1-222 (seeds 0-220)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round223/", "reports/round224/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round223", "round224", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round223 refs; exactly one spaced 'round 223' hit
# (the seed-history line itself).
assert text.count("round223") == 0, "stale round223 refs remain"
assert text.count("round 223") == 1, (
    "expected 1 'round 223' hit (seed history), got %d" % text.count("round 223")
)
assert "round 224 seed 222" in text
assert 'SEED = 222' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round224")' in text
assert "18-attack battery" in text
assert "26 per audit" in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
