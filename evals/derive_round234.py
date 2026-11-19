src = open("run_evals_round233.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 233 seed 231)", "round 233 seed 231, round 234 seed 232)")
rep("except seed=231", "except seed=232")
rep("run_evals_round233.py", "run_evals_round234.py")
rep("round 233:", "round 234:")
rep("reports/round233/", "reports/round234/", 4)
rep("round233/ before the run", "round234/ before the run")
rep("the round-232 script", "the round-233 script")
rep("round233", "round234", 2)
rep("SEED = 231  # diversity vs rounds 1-231 (seeds 0-229)", "SEED = 232  # diversity vs rounds 1-232 (seeds 0-230)")
assert "round233" not in out, "stale round233 refs remain"
assert "round232" not in out, "stale round232 refs remain"
open("run_evals_round234.py", "w").write(out)
print("derived OK")
