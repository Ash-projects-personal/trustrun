src = open("run_evals_round244.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 242 seed 240, round 243 seed 241, round 244 seed 242)", "round 243 seed 241, round 244 seed 242, round 245 seed 243)")
rep("except seed=242", "except seed=243")
rep("run_evals_round244.py", "run_evals_round245.py")
rep("round 244:", "round 245:")
rep("reports/round244/", "reports/round245/", 4)
rep("round244/ before the run", "round245/ before the run")
rep("the round-243 script", "the round-244 script")
rep("round244", "round245", 2)
rep("SEED = 242  # diversity vs rounds 1-243 (seeds 0-241)", "SEED = 243  # diversity vs rounds 1-244 (seeds 0-242)")
assert "round244" not in out, "stale round244 refs remain"
assert "round243" not in out, "stale round243 refs remain"
open("run_evals_round245.py", "w").write(out)
print("derived OK")
