src = open("run_evals_round230.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 230 seed 228)", "round 230 seed 228, round 231 seed 229)")
rep("except seed=228", "except seed=229")
rep("run_evals_round230.py", "run_evals_round231.py")
rep("round 230:", "round 231:")
rep("reports/round230/", "reports/round231/", 4)
rep("round230/ before the run", "round231/ before the run")
rep("the round-229 script", "the round-230 script")
rep("round230", "round231", 2)
rep("SEED = 228  # diversity vs rounds 1-228 (seeds 0-226)", "SEED = 229  # diversity vs rounds 1-229 (seeds 0-227)")
assert "round230" not in out, "stale round230 refs remain"
assert "round229" not in out, "stale round229 refs remain"
open("run_evals_round231.py", "w").write(out)
print("derived OK")
