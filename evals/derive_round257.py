"""Derive run_evals_round257.py from run_evals_round256.py (seed 255)."""
src = open("run_evals_round256.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 255 seed 253, round 256 seed 254)",
    "round 256 seed 254, round 257 seed 255)")
rep("except seed=254", "except seed=255")
rep("run_evals_round256.py", "run_evals_round257.py")
rep("round 256:", "round 257:")
rep("reports/round256/", "reports/round257/", 4)
rep("round256/ before the run", "round257/ before the run")
rep("the round-255 script", "the round-256 script")
rep("round256", "round257", 2)
rep("SEED = 254  # diversity vs rounds 1-255 (seeds 0-253)",
    "SEED = 255  # diversity vs rounds 1-256 (seeds 0-254)")
assert "round256" not in out, "stale round256 refs remain"
assert "round255" not in out, "stale round255 refs remain"
open("run_evals_round257.py", "w").write(out)
print("derived OK")
