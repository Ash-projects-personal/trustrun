src = open("run_evals_round241.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("round 240 seed 238, round 241 seed 239)", "round 240 seed 238, round 241 seed 239, round 242 seed 240)")
rep("except seed=238", "except seed=240")
rep("run_evals_round241.py", "run_evals_round242.py")
rep("round 241:", "round 242:")
rep("reports/round241/", "reports/round242/", 4)
rep("round241/ before the run", "round242/ before the run")
rep("the round-240 script", "the round-241 script")
rep("round241", "round242", 2)
rep("SEED = 239  # diversity vs rounds 1-240 (seeds 0-238)", "SEED = 240  # diversity vs rounds 1-241 (seeds 0-239)")
# Battery grew: PageReaderInject shipped 2026-11-18 as the 19th attack.
rep("Expected\nyield: 300 audits, ~7,800 check-level judgments (26 per audit at the\n18-attack battery: 1 contract claim + 18 stress outcomes + 4\nconsistency + 3 data checks).",
    "Expected\nyield: 300 audits, ~8,100 check-level judgments (27 per audit at the\n19-attack battery: 1 contract claim + 19 stress outcomes + 4\nconsistency + 3 data checks).")
rep("as the 17th; prompt_adware shipped 2026-11-17 as the 18th).",
    "as the 17th; prompt_adware shipped 2026-11-17 as the 18th;\npage_reader_inject shipped 2026-11-18 as the 19th).")
rep("Battery note: the default battery is 18 attacks (clarification-",
    "Battery note: the default battery is 19 attacks (clarification-")
assert "round241" not in out, "stale round241 refs remain"
assert "round240" not in out, "stale round240 refs remain"
assert "18-attack" not in out, "stale 18-attack refs remain"
open("run_evals_round242.py", "w").write(out)
print("derived OK")
