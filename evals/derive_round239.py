src = open("run_evals_round238.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 237 seed 235, round 238 seed 236)", "round 237 seed 235, round 238 seed 236, round 239 seed 237)")
rep("except seed=236", "except seed=237")
rep("run_evals_round238.py", "run_evals_round239.py")
rep("round 238:", "round 239:")
rep("reports/round238/", "reports/round239/", 4)
rep("round238/ before the run", "round239/ before the run")
rep("the round-237 script", "the round-238 script")
rep("round238", "round239", 2)
rep("SEED = 236  # diversity vs rounds 1-236 (seeds 0-234)", "SEED = 237  # diversity vs rounds 1-237 (seeds 0-235)")
assert "round238" not in out, "stale round238 refs remain"
assert "round237" not in out, "stale round237 refs remain"
open("run_evals_round239.py", "w").write(out)
print("derived OK")
