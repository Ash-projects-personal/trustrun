"""Derive run_evals_round250.py from run_evals_round249.py (seed 248)."""
src = open("run_evals_round249.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 247 seed 245, round 248 seed 246, round 249 seed 247)",
    "round 248 seed 246, round 249 seed 247, round 250 seed 248)")
rep("except seed=247", "except seed=248")
rep("run_evals_round249.py", "run_evals_round250.py")
rep("round 249:", "round 250:")
rep("reports/round249/", "reports/round250/", 4)
rep("round249/ before the run", "round250/ before the run")
rep("the round-248 script", "the round-249 script")
rep("round249", "round250", 2)
rep("SEED = 247  # diversity vs rounds 1-248 (seeds 0-246)",
    "SEED = 248  # diversity vs rounds 1-249 (seeds 0-247)")
assert "round249" not in out, "stale round249 refs remain"
assert "round248" not in out, "stale round248 refs remain"
open("run_evals_round250.py", "w").write(out)
print("derived OK")
