src = open("run_evals_round231.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 231 seed 229)", "round 231 seed 229, round 232 seed 230)")
rep("except seed=229", "except seed=230")
rep("run_evals_round231.py", "run_evals_round232.py")
rep("round 231:", "round 232:")
rep("reports/round231/", "reports/round232/", 4)
rep("round231/ before the run", "round232/ before the run")
rep("the round-230 script", "the round-231 script")
rep("round231", "round232", 2)
rep("SEED = 229  # diversity vs rounds 1-229 (seeds 0-227)", "SEED = 230  # diversity vs rounds 1-230 (seeds 0-228)")
assert "round231" not in out, "stale round231 refs remain"
assert "round230" not in out, "stale round230 refs remain"
open("run_evals_round232.py", "w").write(out)
print("derived OK")
