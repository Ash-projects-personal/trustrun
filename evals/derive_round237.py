src = open("run_evals_round236.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 235 seed 233, round 236 seed 234)", "round 235 seed 233, round 236 seed 234, round 237 seed 235)")
rep("except seed=234", "except seed=235")
rep("run_evals_round236.py", "run_evals_round237.py")
rep("round 236:", "round 237:")
rep("reports/round236/", "reports/round237/", 4)
rep("round236/ before the run", "round237/ before the run")
rep("the round-235 script", "the round-236 script")
rep("round236", "round237", 2)
rep("SEED = 234  # diversity vs rounds 1-234 (seeds 0-232)", "SEED = 235  # diversity vs rounds 1-235 (seeds 0-233)")
assert "round236" not in out, "stale round236 refs remain"
assert "round235" not in out, "stale round235 refs remain"
open("run_evals_round237.py", "w").write(out)
print("derived OK")
