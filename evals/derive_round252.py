"""Derive run_evals_round252.py from run_evals_round251.py (seed 250)."""
src = open("run_evals_round251.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 249 seed 247, round 250 seed 248, round 251 seed 249)",
    "round 250 seed 248, round 251 seed 249, round 252 seed 250)")
rep("except seed=249", "except seed=250")
rep("run_evals_round251.py", "run_evals_round252.py")
rep("round 251:", "round 252:")
rep("reports/round251/", "reports/round252/", 4)
rep("round251/ before the run", "round252/ before the run")
rep("the round-250 script", "the round-251 script")
rep("round251", "round252", 2)
rep("SEED = 249  # diversity vs rounds 1-250 (seeds 0-248)",
    "SEED = 250  # diversity vs rounds 1-251 (seeds 0-249)")
assert "round251" not in out, "stale round251 refs remain"
assert "round250" not in out, "stale round250 refs remain"
open("run_evals_round252.py", "w").write(out)
print("derived OK")
