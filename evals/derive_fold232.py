src = open("fold_round231.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("Fold round 231 into DATASET.md Totals.", "Fold round 232 into DATASET.md Totals.")
rep("Round 231 is the tenth round on the 18-attack battery: 26 checks per\naudit, 7,800 per round. Aggregate-identical to rounds 222-230 expected",
    "Round 232 is the eleventh round on the 18-attack battery: 26 checks per\naudit, 7,800 per round. Aggregate-identical to rounds 222-231 expected")
rep("for n in range(2, 232):", "for n in range(2, 233):")
rep('assert disk == 64692, "disk rows rounds 2-231: %d (expected 64692)" % disk',
    'assert disk == 64992, "disk rows rounds 2-232: %d (expected 64992)" % disk')
rep('assert disk + 15 == 64707, "rounds 1-231 audits"',
    'assert disk + 15 == 65007, "rounds 1-232 audits"')
rep("#    is the only 24-check round, rounds 222-231 are 26-check rounds)",
    "#    is the only 24-check round, rounds 222-232 are 26-check rounds)")
rep("    + 10 * 300 * 26", "    + 11 * 300 * 26")
rep('assert checks == 1416519, "round check math: %d" % checks',
    'assert checks == 1424319, "round check math: %d" % checks')
rep('assert (a_old, c_old) == (67073, 1509291), (',
    'assert (a_old, c_old) == (67373, 1517091), (')
rep('("| Labeled eval rounds 1-230 (`reports/round*/summary.json`) | 64,407 | 1,408,719 |",\n     "| Labeled eval rounds 1-231 (`reports/round*/summary.json`) | 64,707 | 1,416,519 |", 1),',
    '("| Labeled eval rounds 1-231 (`reports/round*/summary.json`) | 64,707 | 1,416,519 |",\n     "| Labeled eval rounds 1-232 (`reports/round*/summary.json`) | 65,007 | 1,424,319 |", 1),')
rep('("| **Total** | **67,073** | **1,509,291** |",\n     "| **Total** | **67,373** | **1,517,091** |", 1),',
    '("| **Total** | **67,373** | **1,517,091** |",\n     "| **Total** | **67,673** | **1,524,891** |", 1),')
rep('("Round-audit detail: 64,392 audits sit in the round2-230 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-230: 300 each); the 64,407 total",\n     "Round-audit detail: 64,692 audits sit in the round2-231 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-231: 300 each); the 64,707 total", 1),',
    '("Round-audit detail: 64,692 audits sit in the round2-231 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-231: 300 each); the 64,707 total",\n     "Round-audit detail: 64,992 audits sit in the round2-232 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-232: 300 each); the 65,007 total", 1),')
rep('("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 9x300x26 = 1,408,719.",\n     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 10x300x26 = 1,416,519.", 1),',
    '("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 10x300x26 = 1,416,519.",\n     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 11x300x26 = 1,424,319.", 1),')
rep('("round 230: 1,509,291, 509,291 past target.)",\n     "round 230: 1,509,291, 509,291 past target; "\n     "round 231: 1,517,091, 517,091 past target.)", 1),',
    '("round 231: 1,517,091, 517,091 past target.)",\n     "round 231: 1,517,091, 517,091 past target; "\n     "round 232: 1,524,891, 524,891 past target.)", 1),')
rep('assert (a_new, c_new) == (67373, 1517091), (',
    'assert (a_new, c_new) == (67673, 1524891), (')
rep('print("folded round 231: Totals now 67,373 / 1,517,091")',
    'print("folded round 232: Totals now 67,673 / 1,524,891")')
assert "fold_round231" not in out
assert out.count("round 231") == 2, "unexpected round 231 refs: %d" % out.count("round 231")
open("fold_round232.py", "w").write(out)
print("derived OK")
