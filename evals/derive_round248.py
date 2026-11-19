"""Derive run_evals_round248.py from run_evals_round247.py (seed 246)."""
src = open("run_evals_round247.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 245 seed 243, round 246 seed 244, round 247 seed 245)",
    "round 246 seed 244, round 247 seed 245, round 248 seed 246)")
rep("except seed=245", "except seed=246")
rep("run_evals_round247.py", "run_evals_round248.py")
rep("round 247:", "round 248:")
rep("reports/round247/", "reports/round248/", 4)
rep("round247/ before the run", "round248/ before the run")
rep("the round-246 script", "the round-247 script")
rep("round247", "round248", 2)
rep("SEED = 245  # diversity vs rounds 1-246 (seeds 0-244)",
    "SEED = 246  # diversity vs rounds 1-247 (seeds 0-245)")
assert "round247" not in out, "stale round247 refs remain"
assert "round246" not in out, "stale round246 refs remain"
open("run_evals_round248.py", "w").write(out)
print("derived OK")
