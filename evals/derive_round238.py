src = open("run_evals_round237.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 236 seed 234, round 237 seed 235)", "round 236 seed 234, round 237 seed 235, round 238 seed 236)")
rep("except seed=235", "except seed=236")
rep("run_evals_round237.py", "run_evals_round238.py")
rep("round 237:", "round 238:")
rep("reports/round237/", "reports/round238/", 4)
rep("round237/ before the run", "round238/ before the run")
rep("the round-236 script", "the round-237 script")
rep("round237", "round238", 2)
rep("SEED = 235  # diversity vs rounds 1-235 (seeds 0-233)", "SEED = 236  # diversity vs rounds 1-236 (seeds 0-234)")
assert "round237" not in out, "stale round237 refs remain"
assert "round236" not in out, "stale round236 refs remain"
open("run_evals_round238.py", "w").write(out)
print("derived OK")
