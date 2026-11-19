"""Derive run_evals_round228.py from run_evals_round227.py (seed 226).

Round 228 runs the same 18-attack battery as rounds 222-227
(task_tamper 16th, ci_harness_inject 17th, prompt_adware 18th): 26
checks per audit, 7,800 per round. Round 227 was aggregate-identical
to rounds 221-226 (summary.json md5 e42d092a506d8a6faddb4c7a5cee4470).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round227.py")
DST = os.path.join(HERE, "run_evals_round228.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round227 -> round228 replace)
    ("round 227 seed 225)", "round 227 seed 225, round 228 seed 226)", 1),
    # 2. title
    ("Run Trustrun round 227:", "Run Trustrun round 228:", 1),
    # 3. usage line
    ("run_evals_round227.py", "run_evals_round228.py", 1),
    # 4. docstring seed
    ("except seed=225 for diversity", "except seed=226 for diversity", 1),
    # 5. derivation note
    ("derived from the round-226 script", "derived from the round-227 script", 1),
    # 6. SEED value
    ("SEED = 225", "SEED = 226", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-225 (seeds 0-223)",
     "# diversity vs rounds 1-226 (seeds 0-224)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round227/", "reports/round228/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round227", "round228", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round227 refs; exactly one spaced 'round 227' hit
# (the seed-history line itself).
assert text.count("round227") == 0, "stale round227 refs remain"
assert text.count("round 227") == 1, (
    "expected 1 'round 227' hit (seed history), got %d" % text.count("round 227")
)
assert "round 228 seed 226" in text
assert 'SEED = 226' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round228")' in text
assert "18-attack battery" in text
assert "26 per audit" in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("derived run_evals_round228.py from run_evals_round227.py")
