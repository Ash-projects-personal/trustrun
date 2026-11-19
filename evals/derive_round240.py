src = open("run_evals_round239.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 237 seed 235, round 238 seed 236, round 239 seed 237)", "round 237 seed 235, round 238 seed 236, round 239 seed 237, round 240 seed 238)")
rep("except seed=237", "except seed=238")
rep("run_evals_round239.py", "run_evals_round240.py")
rep("round 239:", "round 240:")
rep("reports/round239/", "reports/round240/", 4)
rep("round239/ before the run", "round240/ before the run")
rep("the round-238 script", "the round-239 script")
rep("round239", "round240", 2)
rep("SEED = 237  # diversity vs rounds 1-237 (seeds 0-235)", "SEED = 238  # diversity vs rounds 1-238 (seeds 0-236)")
assert "round239" not in out, "stale round239 refs remain"
assert "round238" not in out, "stale round238 refs remain"
open("run_evals_round240.py", "w").write(out)
print("derived OK")
