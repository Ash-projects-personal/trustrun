"""Derive run_evals_round222.py from run_evals_round221.py (seed 220).

Round 222 is the first 18-attack round (task_tamper 16th, ci_harness_inject
17th, prompt_adware 18th, all shipped 2026-11-16/17): 26 checks per audit,
7,800 per round. The round-221 script's docstring was stale (it still said
15 attacks / 23 checks although round 221 ran 16 / 24); this derive corrects
the battery text to 18 / 26.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "run_evals_round221.py")
DST = os.path.join(HERE, "run_evals_round222.py")

with open(SRC, encoding="utf-8") as h:
    text = h.read()

# Specific-first ordering: seed history, then title, then derivation note,
# then SEED, then paths. Each replacement asserts its exact count.
REPLACEMENTS = [
    # 1. seed history append (must precede any round221 -> round222 replace)
    ("round 221 seed 219)", "round 221 seed 219, round 222 seed 220)", 1),
    # 2. title
    ("Run Trustrun round 221:", "Run Trustrun round 222:", 1),
    # 3. usage line
    ("run_evals_round221.py", "run_evals_round222.py", 1),
    # 4. docstring seed
    ("except seed=219 for diversity", "except seed=220 for diversity", 1),
    # 5. yield: 6,900 -> 7,800 checks (23 -> 26 per audit)
    ("~6,900 check-level judgments (23 per audit at the",
     "~7,800 check-level judgments (26 per audit at the", 1),
    # 6. battery size in the yield line
    ("15-attack battery: 1 contract claim + 15 stress outcomes + 4",
     "18-attack battery: 1 contract claim + 18 stress outcomes + 4", 1),
    # 7. battery note: 15 attacks -> 18, with the three new kinds
    ("Battery note: the default battery is 15 attacks (clarification-\n"
     "injection shipped 2026-11-05, two vectors; tool_failure_visibility\n"
     "shipped 2026-11-12, one vector; adaptive_injection shipped\n"
     "2026-11-16, one attack with a 4-query budget).",
     "Battery note: the default battery is 18 attacks (clarification-\n"
     "injection shipped 2026-11-05, two vectors; tool_failure_visibility\n"
     "shipped 2026-11-12, one vector; adaptive_injection shipped\n"
     "2026-11-16, one attack with a 4-query budget; task_tamper shipped\n"
     "2026-11-16 as the 16th attack; ci_harness_inject shipped 2026-11-17\n"
     "as the 17th; prompt_adware shipped 2026-11-17 as the 18th).", 1),
    # 8. derivation note
    ("derived from the round-220 script", "derived from the round-221 script", 1),
    # 9. SEED value
    ("SEED = 219", "SEED = 220", 1),
    # 10. SEED comment
    ("# diversity vs rounds 1-219 (seeds 0-217)",
     "# diversity vs rounds 1-220 (seeds 0-218)", 1),
    # 11. report paths (docstring x4: per-pair txt, summary.json, probe, escape)
    ("reports/round221/", "reports/round222/", 4),
    # 12. REPORTS constant + endswith assert + derivation-note ref (3 bare refs)
    ("round221", "round222", 3),
]

for old, new, expected in REPLACEMENTS:
    count = text.count(old)
    assert count == expected, (
        "replace %r: expected %d occurrences, found %d" % (old, expected, count)
    )
    text = text.replace(old, new)

# Final guards: no stale round221 refs; exactly one spaced 'round 221' hit
# (the seed-history line itself).
assert text.count("round221") == 0, "stale round221 refs remain"
assert text.count("round 221") == 1, (
    "expected 1 'round 221' hit (seed history), got %d" % text.count("round 221")
)
assert "round 222 seed 220" in text
assert 'SEED = 220' in text
assert 'REPORTS = os.path.join(HERE, "reports", "round222")' in text
assert "18-attack battery" in text
assert "26 per audit" in text

with open(DST, "w", encoding="utf-8") as h:
    h.write(text)
print("wrote", DST)
