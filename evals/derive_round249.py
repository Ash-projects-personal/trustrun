"""Derive run_evals_round249.py from run_evals_round248.py (seed 247)."""
src = open("run_evals_round248.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 246 seed 244, round 247 seed 245, round 248 seed 246)",
    "round 247 seed 245, round 248 seed 246, round 249 seed 247)")
rep("except seed=246", "except seed=247")
rep("run_evals_round248.py", "run_evals_round249.py")
rep("round 248:", "round 249:")
rep("reports/round248/", "reports/round249/", 4)
rep("round248/ before the run", "round249/ before the run")
rep("the round-247 script", "the round-248 script")
rep("round248", "round249", 2)
rep("SEED = 246  # diversity vs rounds 1-247 (seeds 0-245)",
    "SEED = 247  # diversity vs rounds 1-248 (seeds 0-246)")
assert "round248" not in out, "stale round248 refs remain"
assert "round247" not in out, "stale round247 refs remain"
open("run_evals_round249.py", "w").write(out)
print("derived OK")
