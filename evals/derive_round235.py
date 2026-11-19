src = open("run_evals_round234.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 234 seed 232)", "round 234 seed 232, round 235 seed 233)")
rep("except seed=232", "except seed=233")
rep("run_evals_round234.py", "run_evals_round235.py")
rep("round 234:", "round 235:")
rep("reports/round234/", "reports/round235/", 4)
rep("round234/ before the run", "round235/ before the run")
rep("the round-233 script", "the round-234 script")
rep("round234", "round235", 2)
rep("SEED = 232  # diversity vs rounds 1-232 (seeds 0-230)", "SEED = 233  # diversity vs rounds 1-233 (seeds 0-231)")
assert "round234" not in out, "stale round234 refs remain"
assert "round233" not in out, "stale round233 refs remain"
open("run_evals_round235.py", "w").write(out)
print("derived OK")
