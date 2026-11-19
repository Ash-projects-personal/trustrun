src = open("run_evals_round242.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 240 seed 238, round 241 seed 239, round 242 seed 240)", "round 241 seed 239, round 242 seed 240, round 243 seed 241)")
rep("except seed=240", "except seed=241")
rep("run_evals_round242.py", "run_evals_round243.py")
rep("round 242:", "round 243:")
rep("reports/round242/", "reports/round243/", 4)
rep("round242/ before the run", "round243/ before the run")
rep("the round-241 script", "the round-242 script")
rep("round242", "round243", 2)
rep("SEED = 240  # diversity vs rounds 1-241 (seeds 0-239)", "SEED = 241  # diversity vs rounds 1-242 (seeds 0-240)")
assert "round242" not in out, "stale round242 refs remain"
assert "round241" not in out, "stale round241 refs remain"
open("run_evals_round243.py", "w").write(out)
print("derived OK")
