"""Derive run_evals_round246.py from run_evals_round245.py (seed 244)."""
src = open("run_evals_round245.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 243 seed 241, round 244 seed 242, round 245 seed 243)",
    "round 244 seed 242, round 245 seed 243, round 246 seed 244)")
rep("except seed=243", "except seed=244")
rep("run_evals_round245.py", "run_evals_round246.py")
rep("round 245:", "round 246:")
rep("reports/round245/", "reports/round246/", 4)
rep("round245/ before the run", "round246/ before the run")
rep("the round-244 script", "the round-245 script")
rep("round245", "round246", 2)
rep("SEED = 243  # diversity vs rounds 1-244 (seeds 0-242)",
    "SEED = 244  # diversity vs rounds 1-245 (seeds 0-243)")
assert "round245" not in out, "stale round245 refs remain"
assert "round244" not in out, "stale round244 refs remain"
open("run_evals_round246.py", "w").write(out)
print("derived OK")
