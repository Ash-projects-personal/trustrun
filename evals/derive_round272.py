"""Derive run_evals_round272.py from run_evals_round271.py (fresh file, never sed -i).

Replacements (each asserted to occur at least once):
- "round 271:" -> "round 272:" (docstring title, 1x)
- "run_evals_round271.py" -> "run_evals_round272.py" (1x)
- "except seed=269 for diversity" -> "except seed=270 for diversity" (1x)
- "reports/round271/" -> "reports/round272/" (4x)
- "point at round271/ before the run" -> "point at round272/ before the run" (1x)
- "round 271 seed 269)" -> "round 271 seed 269, round 272 seed 270)" (seed list, 1x)
- "derived from the round-270 script" -> "derived from the round-271 script" (1x)
- '"reports", "round271"' -> '"reports", "round272"' (1x)
- "SEED = 269  # diversity vs rounds 1-270 (seeds 0-268)" -> "SEED = 270  # diversity vs rounds 1-271 (seeds 0-269)" (1x)
- 'REPORTS.endswith("round271")' -> 'REPORTS.endswith("round272")' (1x)
After writing: py_compile the new script; grep that no "round271" remains
outside the seed-list history and no "SEED = 269" remains.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "run_evals_round271.py"
DST = HERE / "run_evals_round272.py"

text = SRC.read_text()
replacements = [
    ("Run Trustrun round 271:", "Run Trustrun round 272:"),
    ("run_evals_round271.py", "run_evals_round272.py"),
    ("except seed=269 for diversity", "except seed=270 for diversity"),
    ("reports/round271/", "reports/round272/"),
    ("point at round271/ before the run", "point at round272/ before the run"),
    ("round 271 seed 269)", "round 271 seed 269, round 272 seed 270)"),
    ("derived from the round-270 script", "derived from the round-271 script"),
    ('"reports", "round271"', '"reports", "round272"'),
    ("SEED = 269  # diversity vs rounds 1-270 (seeds 0-268)",
     "SEED = 270  # diversity vs rounds 1-271 (seeds 0-269)"),
    ('REPORTS.endswith("round271")', 'REPORTS.endswith("round272")'),
]
for old, new in replacements:
    n = text.count(old)
    assert n >= 1, f"NOT FOUND: {old!r}"
    text = text.replace(old, new)
    print(f"{n}x {old!r} -> {new!r}")

assert "round271" not in text.replace("round 270 seed 268, round 271 seed 269", ""), "stale round271 remains"
assert "SEED = 269" not in text, "stale SEED remains"
assert "round272" in text and "SEED = 270" in text
DST.write_text(text)
print("wrote", DST)
