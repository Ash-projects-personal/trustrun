"""Derive run_evals_round247.py from run_evals_round246.py (seed 245)."""
src = open("run_evals_round246.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 244 seed 242, round 245 seed 243, round 246 seed 244)",
    "round 245 seed 243, round 246 seed 244, round 247 seed 245)")
rep("except seed=244", "except seed=245")
rep("run_evals_round246.py", "run_evals_round247.py")
rep("round 246:", "round 247:")
rep("reports/round246/", "reports/round247/", 4)
rep("round246/ before the run", "round247/ before the run")
rep("the round-245 script", "the round-246 script")
rep("round246", "round247", 2)
rep("SEED = 244  # diversity vs rounds 1-245 (seeds 0-243)",
    "SEED = 245  # diversity vs rounds 1-246 (seeds 0-244)")
assert "round246" not in out, "stale round246 refs remain"
assert "round245" not in out, "stale round245 refs remain"
open("run_evals_round247.py", "w").write(out)
print("derived OK")
