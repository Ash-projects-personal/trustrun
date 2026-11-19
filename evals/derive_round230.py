src = open("run_evals_round229.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 229 seed 227)", "round 229 seed 227, round 230 seed 228)")
rep("run_evals_round229.py", "run_evals_round230.py")
rep("round 229:", "round 230:")
rep("reports/round229/", "reports/round230/", 4)
rep("round229/ before the run", "round230/ before the run")
rep("the round-228 script", "the round-229 script")
rep("round229", "round230", 2)
rep("SEED = 227  # diversity vs rounds 1-227 (seeds 0-225)", "SEED = 228  # diversity vs rounds 1-228 (seeds 0-226)")
assert "round229" not in out, "stale round229 refs remain"
assert "round228" not in out, "stale round228 refs remain"
open("run_evals_round230.py", "w").write(out)
print("derived OK")
