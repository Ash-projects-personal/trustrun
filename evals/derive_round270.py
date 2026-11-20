"""Derive run_evals_round270.py from run_evals_round269.py (fresh file, never sed -i).

Replacements (each asserted to occur at least once):
- "round 269:" -> "round 270:" (docstring title, 1x)
- "run_evals_round269.py" -> "run_evals_round270.py" (1x)
- "except seed=267 for diversity" -> "except seed=268 for diversity" (1x)
- "reports/round269/" -> "reports/round270/" (4x)
- "point at round269/ before the run" -> "point at round270/ before the run" (1x)
- "round 269 seed 267)" -> "round 269 seed 267, round 270 seed 268)" (seed list, 1x)
- "derived from the round-268 script" -> "derived from the round-269 script" (1x)
- '"reports", "round269"' -> '"reports", "round270"' (1x)
- "SEED = 267  # diversity vs rounds 1-268 (seeds 0-266)" -> "SEED = 268  # diversity vs rounds 1-269 (seeds 0-267)" (1x)
- 'REPORTS.endswith("round269")' -> 'REPORTS.endswith("round270")' (1x)
After writing: py_compile the new script; grep that no "round269" remains
outside the seed-list history and no "SEED = 267" remains.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "run_evals_round269.py"
DST = HERE / "run_evals_round270.py"

text = SRC.read_text()
replacements = [
    ("Run Trustrun round 269:", "Run Trustrun round 270:"),
    ("run_evals_round269.py", "run_evals_round270.py"),
    ("except seed=267 for diversity", "except seed=268 for diversity"),
    ("reports/round269/", "reports/round270/"),
    ("point at round269/ before the run", "point at round270/ before the run"),
    ("round 269 seed 267)", "round 269 seed 267, round 270 seed 268)"),
    ("derived from the round-268 script", "derived from the round-269 script"),
    ('"reports", "round269"', '"reports", "round270"'),
    ("SEED = 267  # diversity vs rounds 1-268 (seeds 0-266)",
     "SEED = 268  # diversity vs rounds 1-269 (seeds 0-267)"),
    ('REPORTS.endswith("round269")', 'REPORTS.endswith("round270")'),
]
for old, new in replacements:
    n = text.count(old)
    assert n >= 1, f"NOT FOUND: {old!r}"
    text = text.replace(old, new)
    print(f"{n}x {old!r} -> {new!r}")

assert "round269" not in text.replace("round 269 seed 267", ""), "stale round269 remains"
assert "SEED = 267" not in text, "stale SEED remains"
assert "round270" in text and "SEED = 268" in text
DST.write_text(text)
print("wrote", DST)
