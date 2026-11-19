src = open("fold_round233.py").read()
out = src
def rep(old, new, count=1):
    global out
    assert out.count(old) == count, f"expected {count}x {old!r}, got {out.count(old)}"
    out = out.replace(old, new)
rep("Fold round 233 into DATASET.md Totals.", "Fold round 234 into DATASET.md Totals.")
rep("Round 233 is the twelfth round on the 18-attack battery: 26 checks per\naudit, 7,800 per round. Aggregate-identical to rounds 222-232 expected",
    "Round 234 is the thirteenth round on the 18-attack battery: 26 checks per\naudit, 7,800 per round. Aggregate-identical to rounds 222-233 expected")
rep("for n in range(2, 234):", "for n in range(2, 235):")
rep('assert disk == 65292, "disk rows rounds 2-233: %d (expected 65292)" % disk',
    'assert disk == 65592, "disk rows rounds 2-234: %d (expected 65592)" % disk')
rep('assert disk + 15 == 65307, "rounds 1-233 audits"',
    'assert disk + 15 == 65607, "rounds 1-234 audits"')
rep("#    is the only 24-check round, rounds 222-233 are 26-check rounds)",
    "#    is the only 24-check round, rounds 222-234 are 26-check rounds)")
rep("    + 12 * 300 * 26", "    + 13 * 300 * 26")
rep('assert checks == 1432119, "round check math: %d" % checks',
    'assert checks == 1439919, "round check math: %d" % checks')
rep('assert (a_old, c_old) == (67673, 1524891), (',
    'assert (a_old, c_old) == (67973, 1532691), (')
rep('("| Labeled eval rounds 1-232 (`reports/round*/summary.json`) | 65,007 | 1,424,319 |",\n     "| Labeled eval rounds 1-233 (`reports/round*/summary.json`) | 65,307 | 1,432,119 |", 1),',
    '("| Labeled eval rounds 1-233 (`reports/round*/summary.json`) | 65,307 | 1,432,119 |",\n     "| Labeled eval rounds 1-234 (`reports/round*/summary.json`) | 65,607 | 1,439,919 |", 1),')
rep('("| **Total** | **67,673** | **1,524,891** |",\n     "| **Total** | **67,973** | **1,532,691** |", 1),',
    '("| **Total** | **67,973** | **1,532,691** |",\n     "| **Total** | **68,273** | **1,540,491** |", 1),')
rep('("Round-audit detail: 64,992 audits sit in the round2-232 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-232: 300 each); the 65,007 total",\n     "Round-audit detail: 65,292 audits sit in the round2-233 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-233: 300 each); the 65,307 total", 1),',
    '("Round-audit detail: 65,292 audits sit in the round2-233 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-233: 300 each); the 65,307 total",\n     "Round-audit detail: 65,592 audits sit in the round2-234 summary files\\n"\n     "(round 2: 24; rounds 3-18: 48 each; rounds 19-234: 300 each); the 65,607 total", 1),')
rep('("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 11x300x26 = 1,424,319.",\n     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 12x300x26 = 1,432,119.", 1),',
    '("15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 12x300x26 = 1,432,119.",\n     "15x17 + 24x17 + 48x17 + 5x48x19 + 10x48x21 + 75x300x21 + 112x300x22 + 15x300x23 + 1x300x24 + 13x300x26 = 1,439,919.", 1),')
rep('("round 232: 1,524,891, 524,891 past target.)",\n     "round 232: 1,524,891, 524,891 past target; "\n     "round 233: 1,532,691, 532,691 past target.)", 1),',
    '("round 233: 1,532,691, 532,691 past target.)",\n     "round 233: 1,532,691, 532,691 past target; "\n     "round 234: 1,540,491, 540,491 past target.)", 1),')
rep('assert (a_new, c_new) == (67973, 1532691), (',
    'assert (a_new, c_new) == (68273, 1540491), (')
rep('print("folded round 233: Totals now 67,973 / 1,532,691")',
    'print("folded round 234: Totals now 68,273 / 1,540,491")')
assert "fold_round232" not in out
assert out.count("round 233") == 2, "unexpected round 233 refs: %d" % out.count("round 233")
open("fold_round234.py", "w").write(out)
print("derived OK")
