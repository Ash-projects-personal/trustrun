"""Derive run_evals_round255.py from run_evals_round254.py (seed 253)."""
src = open("run_evals_round254.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 253 seed 251, round 254 seed 252)",
    "round 254 seed 252, round 255 seed 253)")
rep("except seed=252", "except seed=253")
rep("run_evals_round254.py", "run_evals_round255.py")
rep("round 254:", "round 255:")
rep("reports/round254/", "reports/round255/", 4)
rep("round254/ before the run", "round255/ before the run")
rep("the round-253 script", "the round-254 script")
rep("round254", "round255", 2)
rep("SEED = 252  # diversity vs rounds 1-253 (seeds 0-251)",
    "SEED = 253  # diversity vs rounds 1-254 (seeds 0-252)")
assert "round254" not in out, "stale round254 refs remain"
assert "round253" not in out, "stale round253 refs remain"
open("run_evals_round255.py", "w").write(out)
print("derived OK")
