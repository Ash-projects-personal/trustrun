"""Derive run_evals_round264.py from run_evals_round263.py (seed 262).

Round 264 is the FIFTH round on the 20-attack battery (TerminalGap
shipped 2026-11-19 by the build loop): 28 checks per audit, 8,400 per
round.
"""
src = open("run_evals_round263.py").read()
out = src


def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)


rep("round 262 seed 260, round 263 seed 261)",
    "round 263 seed 261, round 264 seed 262)")
rep("except seed=261", "except seed=262")
rep("run_evals_round263.py", "run_evals_round264.py")
rep("round 263:", "round 264:")
rep("reports/round263/", "reports/round264/", 4)
rep("round263/ before the run", "round264/ before the run")
rep("the round-262 script", "the round-263 script")
rep("round263", "round264", 2)
rep("SEED = 261  # diversity vs rounds 1-262 (seeds 0-260)",
    "SEED = 262  # diversity vs rounds 1-263 (seeds 0-261)")
assert "round263" not in out, "stale round263 refs remain"
assert "round262" not in out, "stale round262 refs remain"
open("run_evals_round264.py", "w").write(out)
print("derived OK")
