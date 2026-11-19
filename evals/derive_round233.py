src = open("run_evals_round232.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 232 seed 230)", "round 232 seed 230, round 233 seed 231)")
rep("except seed=230", "except seed=231")
rep("run_evals_round232.py", "run_evals_round233.py")
rep("round 232:", "round 233:")
rep("reports/round232/", "reports/round233/", 4)
rep("round232/ before the run", "round233/ before the run")
rep("the round-231 script", "the round-232 script")
rep("round232", "round233", 2)
rep("SEED = 230  # diversity vs rounds 1-230 (seeds 0-228)", "SEED = 231  # diversity vs rounds 1-231 (seeds 0-229)")
assert "round232" not in out, "stale round232 refs remain"
assert "round231" not in out, "stale round231 refs remain"
open("run_evals_round233.py", "w").write(out)
print("derived OK")
