src = open("fold_round230.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("Fold round 230 into DATASET.md Totals.", "Fold round 231 into DATASET.md Totals.")
rep("Round 230 is the ninth round on the 18-attack battery: 26 checks per\naudit, 7,800 per round. Aggregate-identical to rounds 222-229 expected",
    "Round 231 is the tenth round on the 18-attack battery: 26 checks per\naudit, 7,800 per round. Aggregate-identical to rounds 222-230 expected")
rep("for n in range(2, 231):", "for n in range(2, 232):")
rep('assert disk == 64392, "disk rows rounds 2-230: %d (expected 64392)" % disk',
    'assert disk == 64692, "disk rows rounds 2-231: %d (expected 64692)" % disk')
rep('assert disk + 15 == 64407, "rounds 1-230 audits"',
    'assert disk + 15 == 64707, "rounds 1-231 audits"')
rep("#    is the only 24-check round, rounds 222-230 are 26-check rounds)",
    "#    is the only 24-check round, rounds 222-231 are 26-check rounds)")
rep("    + 9 * 300 * 26", "    + 10 * 300 * 26")
rep('assert checks == 1408719, "round check math: %d" % checks',
    'assert checks == 1416519, "round check math: %d" % checks')
rep('assert (a_old, c_old) == (66773, 1501491), (',
    'assert (a_old, c_old) == (67073, 1509291), (')
rep('("| Labeled eval rounds 1-229 (`reports/round*/summary.json`) | 64,107 | 1,400,919 |",\n     "| Labeled eval rounds 1-230 (`reports/round*/summary.json`) | 64,407 | 1,408,719 |", 1),',
    '("| Labeled eval rounds 1-230 (`reports/round*/summary.json`) | 64,407 | 1,408,719 |",\n     "| Labeled eval rounds 1-231 (`reports/round*/summary.json`) | 64,707 | 1,416,519 |", 1),')
rep('("| **Total** | **66,773** | **1,501,491** |",\n     "| **Total** | **67,073** | **1,509,291** |", 1),',
    '("| **Total** | **67,073** | **1,509,291** |",\n     "| **Total** | **67,373** | **1,517,091** |", 1),')
rep('("Round-audit detail: 64,092 audits sit in the round2-229 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-229: 300 each); the 64,107 total",\n     "Round-audit detail: 64,392 audits sit in the round2-230 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-230: 300 each); the 64,407 total", 1),',
    '("Round-audit detail: 64,392 audits sit in the round2-230 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-230: 300 each); the 64,407 total",\n     "Round-audit detail: 64,692 audits sit in the round2-231 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-231: 300 each); the 64,707 total", 1),')
rep('("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 8x300x26 = 1,400,919.",\n     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 9x300x26 = 1,408,719.", 1),',
    '("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 9x300x26 = 1,408,719.",\n     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 10x300x26 = 1,416,519.", 1),')
rep('("round 229: 1,501,491, 501,491 past target.)",\n     "round 229: 1,501,491, 501,491 past target; "\n     "round 230: 1,509,291, 509,291 past target.)", 1),',
    '("round 230: 1,509,291, 509,291 past target.)",\n     "round 230: 1,509,291, 509,291 past target; "\n     "round 231: 1,517,091, 517,091 past target.)", 1),')
rep('assert (a_new, c_new) == (67073, 1509291), (',
    'assert (a_new, c_new) == (67373, 1517091), (')
rep('print("folded round 230: Totals now 67,073 / 1,509,291")',
    'print("folded round 231: Totals now 67,373 / 1,517,091")')
assert "fold_round230" not in out
assert out.count("round 230") == 2, "unexpected round 230 refs: %d" % out.count("round 230")
open("fold_round231.py", "w").write(out)
print("derived OK")
