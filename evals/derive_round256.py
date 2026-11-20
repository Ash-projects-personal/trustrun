"""Derive run_evals_round256.py from run_evals_round255.py (seed 254)."""
src = open("run_evals_round255.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 254 seed 252, round 255 seed 253)",
    "round 255 seed 253, round 256 seed 254)")
rep("except seed=253", "except seed=254")
rep("run_evals_round255.py", "run_evals_round256.py")
rep("round 255:", "round 256:")
rep("reports/round255/", "reports/round256/", 4)
rep("round255/ before the run", "round256/ before the run")
rep("the round-254 script", "the round-255 script")
rep("round255", "round256", 2)
rep("SEED = 253  # diversity vs rounds 1-254 (seeds 0-252)",
    "SEED = 254  # diversity vs rounds 1-255 (seeds 0-253)")
assert "round255" not in out, "stale round255 refs remain"
assert "round254" not in out, "stale round254 refs remain"
open("run_evals_round256.py", "w").write(out)
print("derived OK")
