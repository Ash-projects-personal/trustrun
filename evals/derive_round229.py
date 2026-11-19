"""Derive run_evals_round229.py from run_evals_round228.py (seed 227).

Round 229 runs the same 18-attack battery as rounds 222-228
(task_tamper 16th, ci_harness_inject 17th, prompt_adware 18th): 26
checks per audit, 7,800 per round. Round 228 was aggregate-identical
to rounds 221-227 (summary.json md5 e42d092a506d8a6faddb4c7a5cee4470).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round228.py")
DST = os.path.join(HERE, "run_evals_round229.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round228 -> round229 replace)
    ("round 228 seed 226)", "round 228 seed 226, round 229 seed 227)", 1),
    # 2. title
    ("Run Trustrun round 228:", "Run Trustrun round 229:", 1),
    # 3. usage line
    ("run_evals_round228.py", "run_evals_round229.py", 1),
    # 4. docstring seed
    ("except seed=226 for diversity", "except seed=227 for diversity", 1),
    # 5. derivation note
    ("derived from the round-227 script", "derived from the round-228 script", 1),
    # 6. SEED value
    ("SEED = 226", "SEED = 227", 1),
    # 7. SEED comment
    ("# diversity vs rounds 1-226 (seeds 0-224)",
     "# diversity vs rounds 1-227 (seeds 0-225)", 1),
    # 8. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round228/", "reports/round229/", 4),
    # 9. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round228", "round229", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round228 refs; exactly one spaced 'round 228' hit
# (the seed-history line itself).
assert text.count("round228") == 0, "stale round228 refs remain"
assert text.count("round 228") == 1, (
    "expected 1 'round 228' hit (seed history), got %d" % text.count("round 228")
)
assert "round 229 seed 227" in text
assert 'SEED = 227' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round229")' in text
assert "18-attack battery" in text
assert "26 per audit" in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("derived run_evals_round229.py from run_evals_round228.py")
