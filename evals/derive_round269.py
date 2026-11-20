"""Derive run_evals_round269.py from run_evals_round268.py (fresh file, never sed -i).

Replacements (each asserted to occur at least once):
- "round 268:" -> "round 269:" (docstring title, 1x)
- "run_evals_round268.py" -> "run_evals_round269.py" (1x)
- "except seed=266 for diversity" -> "except seed=267 for diversity" (1x)
- "reports/round268/" -> "reports/round269/" (4x)
- "point at round268/ before the run" -> "point at round269/ before the run" (1x)
- "round 268 seed 266)" -> "round 268 seed 266, round 269 seed 267)" (seed list, 1x)
- "derived from the round-267 script" -> "derived from the round-268 script" (1x)
- '"reports", "round268"' -> '"reports", "round269"' (1x)
- "SEED = 266  # diversity vs rounds 1-267 (seeds 0-265)" -> "SEED = 267  # diversity vs rounds 1-268 (seeds 0-266)" (1x)
- 'REPORTS.endswith("round268")' -> 'REPORTS.endswith("round269")' (1x)
After writing: py_compile the new script; grep that no "round268" remains
outside the seed-list history and no "SEED = 266" remains.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "run_evals_round268.py"
DST = HERE / "run_evals_round269.py"

text = SRC.read_text()
replacements = [
    ("Run Trustrun round 268:", "Run Trustrun round 269:"),
    ("run_evals_round268.py", "run_evals_round269.py"),
    ("except seed=266 for diversity", "except seed=267 for diversity"),
    ("reports/round268/", "reports/round269/"),
    ("point at round268/ before the run", "point at round269/ before the run"),
    ("round 268 seed 266)", "round 268 seed 266, round 269 seed 267)"),
    ("derived from the round-267 script", "derived from the round-268 script"),
    ('"reports", "round268"', '"reports", "round269"'),
    ("SEED = 266  # diversity vs rounds 1-267 (seeds 0-265)",
     "SEED = 267  # diversity vs rounds 1-268 (seeds 0-266)"),
    ('REPORTS.endswith("round268")', 'REPORTS.endswith("round269")'),
]
for old, new in replacements:
    n = text.count(old)
    assert n >= 1, f"NOT FOUND: {old!r}"
    text = text.replace(old, new)
    print(f"{n}x {old!r} -> {new!r}")

assert "round268" not in text.replace("round 268 seed 266", ""), "stale round268 remains"
assert "SEED = 266" not in text, "stale SEED remains"
assert "round269" in text and "SEED = 267" in text
DST.write_text(text)
print("wrote", DST)
