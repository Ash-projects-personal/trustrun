src = open("run_evals_round235.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 235 seed 233)", "round 235 seed 233, round 236 seed 234)")
rep("except seed=233", "except seed=234")
rep("run_evals_round235.py", "run_evals_round236.py")
rep("round 235:", "round 236:")
rep("reports/round235/", "reports/round236/", 4)
rep("round235/ before the run", "round236/ before the run")
rep("the round-234 script", "the round-235 script")
rep("round235", "round236", 2)
rep("SEED = 233  # diversity vs rounds 1-233 (seeds 0-231)", "SEED = 234  # diversity vs rounds 1-234 (seeds 0-232)")
assert "round235" not in out, "stale round235 refs remain"
assert "round234" not in out, "stale round234 refs remain"
open("run_evals_round236.py", "w").write(out)
print("derived OK")
