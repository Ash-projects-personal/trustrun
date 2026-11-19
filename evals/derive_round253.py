"""Derive run_evals_round253.py from run_evals_round252.py (seed 251)."""
src = open("run_evals_round252.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 250 seed 248, round 251 seed 249, round 252 seed 250)",
    "round 251 seed 249, round 252 seed 250, round 253 seed 251)")
rep("except seed=250", "except seed=251")
rep("run_evals_round252.py", "run_evals_round253.py")
rep("round 252:", "round 253:")
rep("reports/round252/", "reports/round253/", 4)
rep("round252/ before the run", "round253/ before the run")
rep("the round-251 script", "the round-252 script")
rep("round252", "round253", 2)
rep("SEED = 250  # diversity vs rounds 1-251 (seeds 0-249)",
    "SEED = 251  # diversity vs rounds 1-252 (seeds 0-250)")
assert "round252" not in out, "stale round252 refs remain"
assert "round251" not in out, "stale round251 refs remain"
open("run_evals_round253.py", "w").write(out)
print("derived OK")
