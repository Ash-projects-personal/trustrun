"""Derive run_evals_round227.py from run_evals_round226.py (seed 225).

Round 227 runs the same 18-attack battery as rounds 222-226
(task_tamper 16th, ci_harness_inject 17th, prompt_adware 18th): 26
checks per audit, 7,800 per round. Round 226 was aggregate-identical
to rounds 221-225 (summary.json md5 e42d092a506d8a6faddb4c7a5cee4470).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round226.py")
DST = os.path.join(HERE, "run_evals_round227.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round226 -> round227 replace)
    ("round 226 seed 224)", "round 226 seed 224, round 227 seed 225)", 1),
    # 2. title
    ("Run Trustrun round 226:", "Run Trustrun round 227:", 1),
    # 3. usage line
    ("run_evals_round226.py", "run_evals_round227.py", 1),
    # 4. docstring seed
    ("except seed=224 for diversity", "except seed=225 for diversity", 1),
    # 5. derivation note
    ("derived from the round-225 script", "derived from the round-226 script", 1),
    # 6. SEED value
    ("SEED = 224", "SEED = 225", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-224 (seeds 0-222)",
     "# diversity vs rounds 1-225 (seeds 0-223)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round226/", "reports/round227/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round226", "round227", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round226 refs; exactly one spaced 'round 226' hit
# (the seed-history line itself).
assert text.count("round226") == 0, "stale round226 refs remain"
assert text.count("round 226") == 1, (
    "expected 1 'round 226' hit (seed history), got %d" % text.count("round 226")
)
assert "round 227 seed 225" in text
assert 'SEED = 225' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round227")' in text
assert "18-attack battery" in text
assert "26 per audit" in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("derived run_evals_round227.py from run_evals_round226.py")
