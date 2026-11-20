"""Derive run_evals_round273.py from run_evals_round272.py (fresh file, never sed -i).

Replacements (each asserted to occur at least once):
- "round 272:" -> "round 273:" (docstring title, 1x)
- "run_evals_round272.py" -> "run_evals_round273.py" (1x)
- "except seed=270 for diversity" -> "except seed=271 for diversity" (1x)
- "reports/round272/" -> "reports/round273/" (4x)
- "point at round272/ before the run" -> "point at round273/ before the run" (1x)
- "round 272 seed 270)" -> "round 272 seed 270, round 273 seed 271)" (seed list, 1x)
- "derived from the round-271 script" -> "derived from the round-272 script" (1x)
- '"reports", "round272"' -> '"reports", "round273"' (1x)
- "SEED = 270  # diversity vs rounds 1-271 (seeds 0-269)" -> "SEED = 271  # diversity vs rounds 1-272 (seeds 0-270)" (1x)
- 'REPORTS.endswith("round272")' -> 'REPORTS.endswith("round273")' (1x)
After writing: py_compile the new script; grep that no "round272" remains
outside the seed-list history and no "SEED = 270" remains.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "run_evals_round272.py"
DST = HERE / "run_evals_round273.py"

text = SRC.read_text()
replacements = [
    ("Run Trustrun round 272:", "Run Trustrun round 273:"),
    ("run_evals_round272.py", "run_evals_round273.py"),
    ("except seed=270 for diversity", "except seed=271 for diversity"),
    ("reports/round272/", "reports/round273/"),
    ("point at round272/ before the run", "point at round273/ before the run"),
    ("round 272 seed 270)", "round 272 seed 270, round 273 seed 271)"),
    ("derived from the round-271 script", "derived from the round-272 script"),
    ('"reports", "round272"', '"reports", "round273"'),
    ("SEED = 270  # diversity vs rounds 1-271 (seeds 0-269)",
     "SEED = 271  # diversity vs rounds 1-272 (seeds 0-270)"),
    ('REPORTS.endswith("round272")', 'REPORTS.endswith("round273")'),
]
for old, new in replacements:
    n = text.count(old)
    assert n >= 1, f"NOT FOUND: {old!r}"
    text = text.replace(old, new)
    print(f"{n}x {old!r} -> {new!r}")

assert "round272" not in text.replace("round 271 seed 269, round 272 seed 270", ""), "stale round272 remains"
assert "SEED = 270" not in text, "stale SEED remains"
assert "round273" in text and "SEED = 271" in text
DST.write_text(text)
print("wrote", DST)
