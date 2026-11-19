src = open("run_evals_round243.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 241 seed 239, round 242 seed 240, round 243 seed 241)", "round 242 seed 240, round 243 seed 241, round 244 seed 242)")
rep("except seed=241", "except seed=242")
rep("run_evals_round243.py", "run_evals_round244.py")
rep("round 243:", "round 244:")
rep("reports/round243/", "reports/round244/", 4)
rep("round243/ before the run", "round244/ before the run")
rep("the round-242 script", "the round-243 script")
rep("round243", "round244", 2)
rep("SEED = 241  # diversity vs rounds 1-242 (seeds 0-240)", "SEED = 242  # diversity vs rounds 1-243 (seeds 0-241)")
assert "round243" not in out, "stale round243 refs remain"
assert "round242" not in out, "stale round242 refs remain"
open("run_evals_round244.py", "w").write(out)
print("derived OK")
