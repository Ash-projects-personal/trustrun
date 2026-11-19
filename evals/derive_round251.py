"""Derive run_evals_round251.py from run_evals_round250.py (seed 249)."""
src = open("run_evals_round250.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 248 seed 246, round 249 seed 247, round 250 seed 248)",
    "round 249 seed 247, round 250 seed 248, round 251 seed 249)")
rep("except seed=248", "except seed=249")
rep("run_evals_round250.py", "run_evals_round251.py")
rep("round 250:", "round 251:")
rep("reports/round250/", "reports/round251/", 4)
rep("round250/ before the run", "round251/ before the run")
rep("the round-249 script", "the round-250 script")
rep("round250", "round251", 2)
rep("SEED = 248  # diversity vs rounds 1-249 (seeds 0-247)",
    "SEED = 249  # diversity vs rounds 1-250 (seeds 0-248)")
assert "round250" not in out, "stale round250 refs remain"
assert "round249" not in out, "stale round249 refs remain"
open("run_evals_round251.py", "w").write(out)
print("derived OK")
