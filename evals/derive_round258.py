"""Derive run_evals_round258.py from run_evals_round257.py (seed 256)."""
src = open("run_evals_round257.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 256 seed 254, round 257 seed 255)",
    "round 257 seed 255, round 258 seed 256)")
rep("except seed=255", "except seed=256")
rep("run_evals_round257.py", "run_evals_round258.py")
rep("round 257:", "round 258:")
rep("reports/round257/", "reports/round258/", 4)
rep("round257/ before the run", "round258/ before the run")
rep("the round-256 script", "the round-257 script")
rep("round257", "round258", 2)
rep("SEED = 255  # diversity vs rounds 1-256 (seeds 0-254)",
    "SEED = 256  # diversity vs rounds 1-257 (seeds 0-255)")
assert "round257" not in out, "stale round257 refs remain"
assert "round256" not in out, "stale round256 refs remain"
open("run_evals_round258.py", "w").write(out)
print("derived OK")
