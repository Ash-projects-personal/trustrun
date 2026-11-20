"""Derive run_evals_round268.py from run_evals_round267.py (fresh file, never sed -i).

Replacements (each asserted to occur at least once):
- "round 267:" -> "round 268:" (docstring title, 1x)
- "run_evals_round267.py" -> "run_evals_round268.py" (1x)
- "except seed=265 for diversity" -> "except seed=266 for diversity" (1x)
- "reports/round267/" -> "reports/round268/" (4x)
- "point at round267/ before the run" -> "point at round268/ before the run" (1x)
- "round 267 seed 265)" -> "round 267 seed 265, round 268 seed 266)" (seed list, 1x)
- "derived from the round-266 script" -> "derived from the round-267 script" (1x)
- '"reports", "round267"' -> '"reports", "round268"' (1x)
- "SEED = 265  # diversity vs rounds 1-266 (seeds 0-264)" -> "SEED = 266  # diversity vs rounds 1-267 (seeds 0-265)" (1x)
- 'REPORTS.endswith("round267")' -> 'REPORTS.endswith("round268")' (1x)
After writing: py_compile the new script; grep that no "round267" remains
outside the seed-list history and no "SEED = 265" remains.
"""
import pathlib

HERE = pathlib.Path(__file__).parent
SRC = HERE / "run_evals_round267.py"
DST = HERE / "run_evals_round268.py"

text = SRC.read_text()
replacements = [
    ("Run Trustrun round 267:", "Run Trustrun round 268:"),
    ("run_evals_round267.py", "run_evals_round268.py"),
    ("except seed=265 for diversity", "except seed=266 for diversity"),
    ("reports/round267/", "reports/round268/"),
    ("point at round267/ before the run", "point at round268/ before the run"),
    ("round 267 seed 265)", "round 267 seed 265, round 268 seed 266)"),
    ("derived from the round-266 script", "derived from the round-267 script"),
    ('"reports", "round267"', '"reports", "round268"'),
    ("SEED = 265  # diversity vs rounds 1-266 (seeds 0-264)",
     "SEED = 266  # diversity vs rounds 1-267 (seeds 0-265)"),
    ('REPORTS.endswith("round267")', 'REPORTS.endswith("round268")'),
]
for old, new in replacements:
    n = text.count(old)
    assert n >= 1, f"NOT FOUND: {old!r}"
    text = text.replace(old, new)
    print(f"{n}x {old!r} -> {new!r}")

assert "round267" not in text.replace("round 267 seed 265", ""), "stale round267 remains"
assert "SEED = 265" not in text, "stale SEED remains"
assert "round268" in text and "SEED = 266" in text
DST.write_text(text)
print("wrote", DST)
