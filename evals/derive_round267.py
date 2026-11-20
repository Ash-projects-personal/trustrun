"""Derive run_evals_round267.py from run_evals_round266.py (fresh file, never sed -i).

Replacements (each asserted to occur exactly the expected number of times):
- "round 266:" -> "round 267:" (docstring title, 1x)
- "run_evals_round266.py" -> "run_evals_round267.py" (1x)
- "except seed=263" -> "except seed=265" (fixes the stale seed in the 266 docstring)
- "reports/round266/" -> "reports/round267/" (4x: lines 8, 9, 32, 37)
- "round266/ before the run" -> "round267/ before the run" (1x)
- "round 266 seed 264)" -> "round 266 seed 264, round 267 seed 265)" (seed list, 1x)
- "derived from the round-265 script" -> "derived from the round-266 script" (1x)
- '"round266"' in REPORTS -> '"round267"' (1x)
- "SEED = 264  # diversity vs rounds 1-265 (seeds 0-263)" -> "SEED = 265  # diversity vs rounds 1-266 (seeds 0-264)" (1x)
- 'REPORTS.endswith("round266")' -> 'REPORTS.endswith("round267")' (1x)
After writing: py_compile the new script; grep that no "round266" remains
outside the seed-list history and no "SEED = 264" remains.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "run_evals_round266.py"
DST = HERE / "run_evals_round267.py"

text = SRC.read_text()
replacements = [
    ("Run Trustrun round 266:", "Run Trustrun round 267:"),
    ("run_evals_round266.py", "run_evals_round267.py"),
    ("except seed=263 for diversity", "except seed=265 for diversity"),
    ("reports/round266/", "reports/round267/"),
    ("point at round266/ before the run", "point at round267/ before the run"),
    ("round 266 seed 264)", "round 266 seed 264, round 267 seed 265)"),
    ("derived from the round-265 script", "derived from the round-266 script"),
    ('"reports", "round266"', '"reports", "round267"'),
    ("SEED = 264  # diversity vs rounds 1-265 (seeds 0-263)",
     "SEED = 265  # diversity vs rounds 1-266 (seeds 0-264)"),
    ('REPORTS.endswith("round266")', 'REPORTS.endswith("round267")'),
]
for old, new in replacements:
    n = text.count(old)
    assert n >= 1, f"NOT FOUND: {old!r}"
    text = text.replace(old, new)
    print(f"{n}x {old!r} -> {new!r}")

assert "round266" not in text.replace("round 266 seed 264", ""), "stale round266 remains"
assert "SEED = 264" not in text, "stale SEED remains"
assert "round267" in text and "SEED = 265" in text
DST.write_text(text)
print("wrote", DST)
