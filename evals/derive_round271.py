"""Derive run_evals_round271.py from run_evals_round270.py (fresh file, never sed -i).

Replacements (each asserted to occur at least once):
- "round 270:" -> "round 271:" (docstring title, 1x)
- "run_evals_round270.py" -> "run_evals_round271.py" (1x)
- "except seed=268 for diversity" -> "except seed=269 for diversity" (1x)
- "reports/round270/" -> "reports/round271/" (4x)
- "point at round270/ before the run" -> "point at round271/ before the run" (1x)
- "round 270 seed 268)" -> "round 270 seed 268, round 271 seed 269)" (seed list, 1x)
- "derived from the round-269 script" -> "derived from the round-270 script" (1x)
- '"reports", "round270"' -> '"reports", "round271"' (1x)
- "SEED = 268  # diversity vs rounds 1-269 (seeds 0-267)" -> "SEED = 269  # diversity vs rounds 1-270 (seeds 0-268)" (1x)
- 'REPORTS.endswith("round270")' -> 'REPORTS.endswith("round271")' (1x)
After writing: py_compile the new script; grep that no "round270" remains
outside the seed-list history and no "SEED = 268" remains.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "run_evals_round270.py"
DST = HERE / "run_evals_round271.py"

text = SRC.read_text()
replacements = [
    ("Run Trustrun round 270:", "Run Trustrun round 271:"),
    ("run_evals_round270.py", "run_evals_round271.py"),
    ("except seed=268 for diversity", "except seed=269 for diversity"),
    ("reports/round270/", "reports/round271/"),
    ("point at round270/ before the run", "point at round271/ before the run"),
    ("round 270 seed 268)", "round 270 seed 268, round 271 seed 269)"),
    ("derived from the round-269 script", "derived from the round-270 script"),
    ('"reports", "round270"', '"reports", "round271"'),
    ("SEED = 268  # diversity vs rounds 1-269 (seeds 0-267)",
     "SEED = 269  # diversity vs rounds 1-270 (seeds 0-268)"),
    ('REPORTS.endswith("round270")', 'REPORTS.endswith("round271")'),
]
for old, new in replacements:
    n = text.count(old)
    assert n >= 1, f"NOT FOUND: {old!r}"
    text = text.replace(old, new)
    print(f"{n}x {old!r} -> {new!r}")

assert "round270" not in text.replace("round 270 seed 268", ""), "stale round270 remains"
assert "SEED = 268" not in text, "stale SEED remains"
assert "round271" in text and "SEED = 269" in text
DST.write_text(text)
print("wrote", DST)
