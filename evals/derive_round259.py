"""Derive run_evals_round259.py from run_evals_round258.py (seed 257)."""
src = open("run_evals_round258.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 257 seed 255, round 258 seed 256)",
    "round 258 seed 256, round 259 seed 257)")
rep("except seed=256", "except seed=257")
rep("run_evals_round258.py", "run_evals_round259.py")
rep("round 258:", "round 259:")
rep("reports/round258/", "reports/round259/", 4)
rep("round258/ before the run", "round259/ before the run")
rep("the round-257 script", "the round-258 script")
rep("round258", "round259", 2)
rep("SEED = 256  # diversity vs rounds 1-257 (seeds 0-255)",
    "SEED = 257  # diversity vs rounds 1-258 (seeds 0-256)")
assert "round258" not in out, "stale round258 refs remain"
assert "round257" not in out, "stale round257 refs remain"
open("run_evals_round259.py", "w").write(out)
print("derived OK")
