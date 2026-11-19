"""Derive run_evals_round254.py from run_evals_round253.py (seed 252)."""
src = open("run_evals_round253.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 252 seed 250, round 253 seed 251)",
    "round 253 seed 251, round 254 seed 252)")
rep("except seed=251", "except seed=252")
rep("run_evals_round253.py", "run_evals_round254.py")
rep("round 253:", "round 254:")
rep("reports/round253/", "reports/round254/", 4)
rep("round253/ before the run", "round254/ before the run")
rep("the round-252 script", "the round-253 script")
rep("round253", "round254", 2)
rep("SEED = 251  # diversity vs rounds 1-252 (seeds 0-250)",
    "SEED = 252  # diversity vs rounds 1-253 (seeds 0-251)")
assert "round253" not in out, "stale round253 refs remain"
assert "round252" not in out, "stale round252 refs remain"
open("run_evals_round254.py", "w").write(out)
print("derived OK")
