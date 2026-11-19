"""Derive run_evals_round226.py from run_evals_round225.py (seed 224).

Round 226 runs the same 18-attack battery as rounds 222-225
(task_tamper 16th, ci_harness_inject 17th, prompt_adware 18th): 26
checks per audit, 7,800 per round. Round 225 was aggregate-identical
to rounds 221-224 (summary.json md5 e42d092a506d8a6faddb4c7a5cee4470).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round225.py")
DST = os.path.join(HERE, "run_evals_round226.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round225 -> round226 replace)
    ("round 225 seed 223)", "round 225 seed 223, round 226 seed 224)", 1),
    # 2. title
    ("Run Trustrun round 225:", "Run Trustrun round 226:", 1),
    # 3. usage line
    ("run_evals_round225.py", "run_evals_round226.py", 1),
    # 4. docstring seed
    ("except seed=223 for diversity", "except seed=224 for diversity", 1),
    # 5. derivation note
    ("derived from the round-224 script", "derived from the round-225 script", 1),
    # 6. SEED value
    ("SEED = 223", "SEED = 224", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-223 (seeds 0-221)",
     "# diversity vs rounds 1-224 (seeds 0-222)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round225/", "reports/round226/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round225", "round226", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round225 refs; exactly one spaced 'round 225' hit
# (the seed-history line itself).
assert text.count("round225") == 0, "stale round225 refs remain"
assert text.count("round 225") == 1, (
    "expected 1 'round 225' hit (seed history), got %d" % text.count("round 225")
)
assert "round 226 seed 224" in text
assert 'SEED = 224' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round226")' in text
assert "18-attack battery" in text
assert "26 per audit" in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("derived run_evals_round226.py from run_evals_round225.py")
