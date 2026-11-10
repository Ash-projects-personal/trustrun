"""Patch-parsimony receipt: how much code an agent adds to solve a task.

Solve-rate boards give a four-line patch and a four-hundred-line patch
the same credit, so agent patches bloat and the maintenance bill lands
at merge time. Parsimony (La5u, Show HN Oct 13 2026,
github.com/La5u/Parsimony) counts net syntax units on published
benchmark patches and ranks 35 configurations; RECAP
(arXiv:2608.13292) characterizes the same bloat on SWE-bench Verified
(median successful patch +121.78% total changes, +80.91% net,
+43.99% cyclomatic complexity versus the developer patch, over 28
approaches) and then refines patches to cut it (total +242.14% to
+4.24%, net +348.24% to -39.75%). Both are the measurement or the
refiner, not a receipt: Parsimony is a public leaderboard on
published patches (Python-only SWE-bench Verified board, test files
and docs left out, "experimental footprint comparison, not an
official coding-ability ranking" in its own README), and RECAP
rewrites patches instead of scoring a team's own run. No shipped
tool returns a per-deployment patch-parsimony receipt for a team's
own recorded agent patches, with a scope-completeness companion so
the receipt cannot reward corner-cutting. That fused receipt is the
new piece here.

This module scores recorded patches only. A patch is a dict with
"files": {path: {"before": source or None, "after": source or
None}}, "passed": whether the task's tests passed, and an optional
"reference": the human fix in the same shape. It never runs code
and never fetches a benchmark: the caller supplies the patches,
the pass/fail results, and the reference fixes.

Trustrun units. For a Python file, units are AST nodes counted
before and after, excluding the Module node and the Load / Store /
Del context nodes. The count is Trustrun's own rule, not
Parsimony's: Parsimony counts statements, calls, names, and
literals with its own analyzer, and its worked example (a summing
loop replaced by sum(items)) is -10 net units under its rule; the
same change scores differently here. Ratios compare agent and
reference under the same rule, so the difference in absolute
tally does not move the ratio's meaning. Test files and docs
files are excluded from the size totals (Parsimony's method):
adding a test must never count as bloat, and the scope signals
are where tests and docs are read. For a non-Python file the
method falls back to non-blank lines, and the file's method is
recorded ("ast" or "lines"), so a mixed-method receipt is visible
as mixed. A file whose before or after source does not parse falls
back to lines on both sides, so a broken-syntax patch is measured
in lines rather than silently dropped.

Complexity. Cyclomatic-style: 1 plus one per decision point (If,
For, AsyncFor, While, And, Or, ExceptHandler, IfExp, comprehensions,
With, Assert) in the file. The delta is after minus before. The
complexity number is a size-of-decision measure, not a readability
verdict: Parsimony's own warning applies here too, units measure
size, not readability or design.

Scope completeness. Three signals, each read off the changed
files: tests (a test file changed, or a test function added),
docs (a docs file changed, or a docstring added), error handling
(a try / raise added). Completeness is the share of the three
present. The bar is a stated convention of this receipt, not a
universal standard: a solved patch counts as lean only when it
carries at least two of the three signals, so a patch that solves
by deleting the check, the tests, and the docs does not read as
lean. Which signals are missing is named in the evidence, so a
reader can judge whether the missing one mattered for the task.

Outcomes, per patch. "failed" when the tests did not pass.
"solved_bloated" when the tests passed and the agent added more
than the human reference fix: when the reference added code, the
agent net is above the reference net; when the reference removed
code or held even, the agent net is above zero (the agent grew
the codebase while the human shrank it). A docstring that costs
two units on a fix that still removes five net units is not
bloat under this rule; a helper function that adds seven while
the human removed seven is. "solved_lean" when the tests passed,
the agent did not add more than the human fix, and completeness
is at least two of three. "solved_corner_cut" when the tests
passed, the agent did not add more than the human fix, but
completeness is below two of three: lean on size, thin on scope.
Without a reference there is no size comparison, so the outcomes
are "solved" and "solved_incomplete" on the same completeness
bar. The ratio (agent net over reference net) is reported when
the reference net is not 0; it is None when there is no
reference, or when the reference net is 0 (a ratio against a
zero-size reference is undefined, not zero). The ratio is a
descriptive number; the bloated call is the net comparison,
because the ratio misleads exactly when the reference removes
code (a patch that removes five units against a reference that
removes seven has ratio 0.71, yet it added two units the human
did not).

Campaign. score_campaign reports the pass rate, the median
net-units ratio and median complexity delta over solved patches,
the mean scope completeness, the Spearman rank correlation
between patch size (net units) and solving (Parsimony reports
0.33-0.60 on its boards: more code tends to solve more), and the
outcome counts. The campaign verdict is REVIEW when any solved
patch is bloated or a corner cut, else READY. The median ratio
is reported as a descriptive number alongside the verdict, not
as the verdict rule, because it misleads when references remove
code. An empty campaign is REVIEW with the evidence saying so:
a receipt over no patches proves nothing.

Honest limits, read before quoting any number from this module:
it scores recorded patches, nothing more. It cannot tell whether
a small patch is elegant or a corner cut that happened to pass
the tests; the scope signals are the only guard, and they are
shallow (a test file touched is not a test that covers the fix).
Units measure size, not readability: a dense one-liner can score
fewer units than a readable ten-liner and still be worse code.
The ratio needs a real human reference for the same task; a
reference from a different task makes the ratio meaningless, and
the module cannot detect that. The diff parser reconstructs
after-sources from hunks and refuses a hunk whose context lines
do not match, instead of guessing. A PASS / READY verdict is a
statement about the recorded patches, not a certification of the
agent.
"""

import ast
import re

# Campaign verdicts, matching the trust report.
VERDICT_READY = "READY"
VERDICT_REVIEW = "REVIEW"

# Per-patch outcomes.
OUTCOME_FAILED = "failed"
OUTCOME_SOLVED_BLOATED = "solved_bloated"
OUTCOME_SOLVED_LEAN = "solved_lean"
OUTCOME_SOLVED_CORNER_CUT = "solved_corner_cut"
OUTCOME_SOLVED = "solved"
OUTCOME_SOLVED_INCOMPLETE = "solved_incomplete"

# Completeness bar: at least two of the three scope signals.
COMPLETENESS_BAR = 2.0 / 3.0

# Decision-point node types for the complexity count.
_DECISION_TYPES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.And,
    ast.Or,
    ast.ExceptHandler,
    ast.IfExp,
    ast.ListComp,
    ast.DictComp,
    ast.SetComp,
    ast.GeneratorExp,
    ast.With,
    ast.AsyncWith,
    ast.Assert,
)

# Context nodes excluded from the unit count.
_CONTEXT_TYPES = (ast.Load, ast.Store, ast.Del)

_DOC_EXTENSIONS = (".md", ".rst", ".txt", ".adoc")

# Added-line keywords that count as error handling on a
# lines-method file.
_ERROR_KEYWORDS = ("try:", "except", "raise ")


def _is_python(path):
    return str(path).lower().endswith(".py")


def _count_ast_units(source):
    """AST node count for one Python source string, or None when
    it does not parse. Module and Load / Store / Del nodes are
    excluded; every other node counts once."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Module):
            continue
        if isinstance(node, _CONTEXT_TYPES):
            continue
        count += 1
    return count


def _count_complexity(source):
    """1 plus one per decision point, or None when unparseable."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    total = 1
    for node in ast.walk(tree):
        if isinstance(node, _DECISION_TYPES):
            total += 1
    return total


def _count_lines(source):
    """Non-blank lines, for the lines-method fallback."""
    return sum(1 for line in source.splitlines() if line.strip())


def _count_docstrings(source):
    """Docstrings: the first statement of the module and of any
    function or class, when it is a string constant."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    count = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.FunctionDef,
                                 ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        body = node.body
        if not body:
            continue
        first = body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            count += 1
    return count


def _function_names(source):
    """Names of every function defined in one Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _is_test_path(path):
    lowered = str(path).lower().replace("\\", "/")
    base = lowered.rsplit("/", 1)[-1]
    return (
        base.startswith("test_")
        or base.endswith("_test.py")
        or "/tests/" in lowered
        or "/test/" in lowered
    )


def _is_doc_path(path):
    return str(path).lower().endswith(_DOC_EXTENSIONS)


def count_units(source, path="file.py"):
    """Units in one source string: AST nodes for Python, non-blank
    lines otherwise. Returns (count, method)."""
    if _is_python(path):
        units = _count_ast_units(source)
        if units is not None:
            return units, "ast"
    return _count_lines(source), "lines"


def complexity(source, path="file.py"):
    """Complexity of one source string: decision-point count for
    Python, 1 plus the non-blank line count otherwise (so the
    number stays comparable as a size measure, not as a decision
    count). Returns (value, method)."""
    if _is_python(path):
        value = _count_complexity(source)
        if value is not None:
            return value, "ast"
    return 1 + _count_lines(source), "lines"


def patch_from_diff(diff, get_source):
    """Reconstruct before/after file sources from a unified diff.

    diff: the unified diff text. get_source: a callable taking a
    path and returning the file's before-source, or None for a new
    file. Returns {"files": {path: {"before": src or None,
    "after": src or None}}}. A hunk whose context lines do not
    match the before-source raises ValueError instead of guessing.
    Binary-file sections contribute nothing and are skipped.
    """
    if not isinstance(diff, str):
        raise TypeError("diff must be a string")
    if not callable(get_source):
        raise TypeError("get_source must be callable")
    files = {}
    current_path = None
    current_before = None
    current_after = None
    current_lines = None
    hunks = None

    def flush():
        nonlocal current_path, current_before, current_after
        nonlocal current_lines, hunks
        if current_path is None:
            return
        if current_lines is None:
            current_lines = []
            if current_before is not None:
                current_lines = current_before.splitlines()
        after_lines = _apply_hunks(current_lines, hunks or [])
        after = "\n".join(after_lines)
        if after_lines:
            after += "\n"
        elif after_lines == [] and current_after is not None:
            after = ""
        files[current_path] = {
            "before": current_before,
            "after": after if current_after is not False else None,
        }
        current_path = None
        current_before = None
        current_after = None
        current_lines = None
        hunks = None

    lines = diff.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("diff --git "):
            flush()
            index += 1
            continue
        if line.startswith("--- "):
            flush()
            old = line[4:].strip()
            new_line = lines[index + 1] if index + 1 < len(lines) else ""
            if not new_line.startswith("+++ "):
                raise ValueError("diff --- line without a +++ line")
            new = new_line[4:].strip()
            index += 2
            if old == "/dev/null":
                current_before = None
                current_path = new[2:] if new.startswith("b/") else new
                current_after = True
            elif new == "/dev/null":
                current_path = old[2:] if old.startswith("a/") else old
                current_before = get_source(current_path)
                if current_before is None:
                    raise ValueError(
                        "deleted file %r has no before-source"
                        % current_path
                    )
                current_after = False
            else:
                current_path = new[2:] if new.startswith("b/") else new
                current_before = get_source(current_path)
                if current_before is None:
                    raise ValueError(
                        "file %r has no before-source" % current_path
                    )
                current_after = True
            current_lines = None
            hunks = []
            continue
        if line.startswith("@@ "):
            match = re.match(
                r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line
            )
            if match is None:
                raise ValueError("unparseable hunk header: %r" % line)
            hunks.append((int(match.group(1)), []))
            index += 1
            continue
        if line.startswith("Binary files "):
            flush()
            index += 1
            continue
        if current_path is not None and hunks is not None:
            if line.startswith((" ", "+", "-", "\\")):
                hunks[-1][1].append(line)
                index += 1
                continue
            if line == "":
                # Some diff writers emit a bare empty line for a
                # blank context line.
                hunks[-1][1].append(" ")
                index += 1
                continue
        index += 1
    flush()
    return {"files": files}


def _apply_hunks(before_lines, hunks):
    """Apply parsed hunks to before-lines, returning after-lines.
    Each hunk is (old_start_1based, lines). Lines between hunks
    are copied through unchanged. Raises ValueError on a context
    mismatch."""
    result = []
    cursor = 0
    for old_start, hunk in hunks:
        # Copy the untouched lines before this hunk. A new file
        # starts at old line 0, which means no lines to copy.
        target = max(0, old_start - 1)
        if target < cursor:
            raise ValueError(
                "hunk starts at line %d, before the previous hunk ended"
                % old_start
            )
        result.extend(before_lines[cursor:target])
        cursor = target
        for line in hunk:
            if line.startswith("\\"):
                continue
            kind = line[0]
            text = line[1:]
            if kind == " ":
                if cursor >= len(before_lines) or before_lines[cursor] != text:
                    raise ValueError(
                        "hunk context mismatch at line %d: %r"
                        % (cursor + 1, text)
                    )
                result.append(before_lines[cursor])
                cursor += 1
            elif kind == "-":
                if cursor >= len(before_lines) or before_lines[cursor] != text:
                    raise ValueError(
                        "hunk removal mismatch at line %d: %r"
                        % (cursor + 1, text)
                    )
                cursor += 1
            elif kind == "+":
                result.append(text)
            else:
                raise ValueError("unknown hunk line: %r" % line)
    result.extend(before_lines[cursor:])
    return result


def _file_delta(before, after, path):
    """Units and complexity before/after for one file. Returns
    (net_units, complexity_delta, method, units_before,
    units_after). A None side is an empty file."""
    before_src = before if before is not None else ""
    after_src = after if after is not None else ""
    if _is_python(path):
        before_units = _count_ast_units(before_src)
        after_units = _count_ast_units(after_src)
        before_cx = _count_complexity(before_src)
        after_cx = _count_complexity(after_src)
        if (
            before_units is not None
            and after_units is not None
            and before_cx is not None
            and after_cx is not None
        ):
            return (
                after_units - before_units,
                after_cx - before_cx,
                "ast",
                before_units,
                after_units,
            )
    before_units = _count_lines(before_src)
    after_units = _count_lines(after_src)
    return (
        after_units - before_units,
        after_cx_delta_lines(before_src, after_src),
        "lines",
        before_units,
        after_units,
    )


def after_cx_delta_lines(before_src, after_src):
    """Complexity delta under the lines fallback: the line-count
    delta, so the number stays a size delta on the same scale."""
    return _count_lines(after_src) - _count_lines(before_src)


def _scope_signals(patch):
    """The three scope signals for a patch's files dict."""
    files = patch.get("files") or {}
    tests = False
    docs = False
    error_handling = False
    for path, sides in files.items():
        before = sides.get("before") if isinstance(sides, dict) else None
        after = sides.get("after") if isinstance(sides, dict) else None
        if before == after:
            continue
        if _is_test_path(path):
            tests = True
        if _is_doc_path(path):
            docs = True
        if _is_python(path):
            before_src = before or ""
            after_src = after or ""
            added_functions = _function_names(after_src) - _function_names(before_src)
            if any(name.startswith("test_") for name in added_functions):
                tests = True
            if _count_docstrings(after_src) > _count_docstrings(before_src):
                docs = True
            if _count_nodes(after_src, ast.Try) > _count_nodes(before_src, ast.Try):
                error_handling = True
            if _count_nodes(after_src, ast.Raise) > _count_nodes(before_src, ast.Raise):
                error_handling = True
        else:
            added = _added_lines(before or "", after or "")
            if any(
                keyword in line
                for line in added
                for keyword in _ERROR_KEYWORDS
            ):
                error_handling = True
    return {"tests": tests, "docs": docs, "error_handling": error_handling}


def _count_nodes(source, node_type):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return 0
    return sum(1 for node in ast.walk(tree) if isinstance(node, node_type))


def _added_lines(before, after):
    """Lines present in after but not in before, by content."""
    before_set = set(before.splitlines())
    return [line for line in after.splitlines() if line not in before_set]


def _is_bloated(agent_net, ref_net):
    """True when the agent added more than the human reference
    fix. When the reference added code, the agent net must exceed
    the reference net; when the reference removed code or held
    even, the agent is bloated only when its own net is above
    zero."""
    if ref_net > 0:
        return agent_net > ref_net
    return agent_net > 0


def _median(values):
    ordered = sorted(values)
    count = len(ordered)
    if count == 0:
        return None
    middle = count // 2
    if count % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _ranks(values):
    """Average ranks for Spearman (ties share the mean rank)."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index
        while (
            end + 1 < len(order)
            and values[order[end + 1]] == values[order[index]]
        ):
            end += 1
        mean_rank = (index + end) / 2.0 + 1.0
        for position in range(index, end + 1):
            ranks[order[position]] = mean_rank
        index = end + 1
    return ranks


def _spearman(xs, ys):
    """Spearman rank correlation, or None when undefined (fewer
    than 3 points, or no variance in either side)."""
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    rank_x = _ranks(xs)
    rank_y = _ranks(ys)
    mean_x = sum(rank_x) / len(rank_x)
    mean_y = sum(rank_y) / len(rank_y)
    numerator = sum(
        (a - mean_x) * (b - mean_y) for a, b in zip(rank_x, rank_y)
    )
    denominator_x = sum((a - mean_x) ** 2 for a in rank_x) ** 0.5
    denominator_y = sum((b - mean_y) ** 2 for b in rank_y) ** 0.5
    if denominator_x == 0.0 or denominator_y == 0.0:
        return None
    return numerator / (denominator_x * denominator_y)


def score_patch(patch, reference=None):
    """Score one recorded patch for parsimony.

    patch: {"id": label, "files": {path: {"before": source or
    None, "after": source or None}}, "passed": bool}. reference:
    the human fix in the same shape, or None. A reference carried
    inside the patch dict under "reference" is used when no
    separate reference is passed.

    Returns the per-patch receipt: net units and complexity delta,
    the ratio against the reference, the three scope signals and
    completeness, the outcome, and the evidence naming which
    signals are missing.
    """
    if not isinstance(patch, dict):
        raise TypeError("patch must be a dict")
    files = patch.get("files")
    if not isinstance(files, dict):
        raise TypeError("patch needs a files dict")
    if not isinstance(patch.get("passed"), bool):
        raise TypeError("patch needs a boolean passed value")
    if reference is None:
        reference = patch.get("reference")
    if reference is not None and not isinstance(reference, dict):
        raise TypeError("reference must be a dict")
    ref_files = (reference or {}).get("files") or {}

    net_units = 0
    complexity_delta = 0
    methods = set()
    per_file = {}
    for path, sides in files.items():
        if not isinstance(sides, dict):
            raise TypeError("file %r needs a before/after dict" % path)
        before = sides.get("before")
        after = sides.get("after")
        if before is not None and not isinstance(before, str):
            raise TypeError("file %r before must be a string or None" % path)
        if after is not None and not isinstance(after, str):
            raise TypeError("file %r after must be a string or None" % path)
        delta, delta_cx, method, before_u, after_u = _file_delta(
            before, after, path
        )
        # Test and docs files are scope evidence, not size: they
        # are excluded from the totals (Parsimony's method), so
        # adding a test never counts as bloat.
        counted = not (_is_test_path(path) or _is_doc_path(path))
        if counted:
            net_units += delta
            complexity_delta += delta_cx
            methods.add(method)
        per_file[path] = {
            "net_units": delta,
            "complexity_delta": delta_cx,
            "method": method,
            "units_before": before_u,
            "units_after": after_u,
            "counted": counted,
        }

    ref_net = None
    if ref_files:
        ref_net = 0
        for path, sides in ref_files.items():
            if not isinstance(sides, dict):
                raise TypeError(
                    "reference file %r needs a before/after dict" % path
                )
            if _is_test_path(path) or _is_doc_path(path):
                continue
            delta, _, _, _, _ = _file_delta(
                sides.get("before"), sides.get("after"), path
            )
            ref_net += delta
    if ref_net is None or ref_net == 0:
        ratio = None
    else:
        ratio = net_units / ref_net

    scope = _scope_signals(patch)
    present = sum(1 for value in scope.values() if value)
    completeness = present / 3.0
    missing = [key for key, value in scope.items() if not value]

    passed = patch["passed"]
    if not passed:
        outcome = OUTCOME_FAILED
    elif ref_files and _is_bloated(net_units, ref_net):
        outcome = OUTCOME_SOLVED_BLOATED
    elif ratio is None:
        if completeness >= COMPLETENESS_BAR:
            outcome = OUTCOME_SOLVED
        else:
            outcome = OUTCOME_SOLVED_INCOMPLETE
    elif completeness >= COMPLETENESS_BAR:
        outcome = OUTCOME_SOLVED_LEAN
    else:
        outcome = OUTCOME_SOLVED_CORNER_CUT

    if not passed:
        evidence = "tests did not pass; parsimony is moot"
    elif ratio is None and not ref_files:
        evidence = (
            "no reference patch, ratio undefined; scope signals "
            "present: %s; missing: %s"
            % (
                ", ".join(k for k, v in scope.items() if v) or "none",
                ", ".join(missing) or "none",
            )
        )
    elif ratio is None:
        evidence = (
            "reference net is 0, ratio undefined; scope signals "
            "present: %s; missing: %s"
            % (
                ", ".join(k for k, v in scope.items() if v) or "none",
                ", ".join(missing) or "none",
            )
        )
    else:
        evidence = (
            "net units %d vs reference %d (ratio %.2f); scope "
            "signals present: %s; missing: %s"
            % (
                net_units,
                ref_net,
                ratio,
                ", ".join(k for k, v in scope.items() if v) or "none",
                ", ".join(missing) or "none",
            )
        )
    return {
        "id": patch.get("id", "?"),
        "passed": passed,
        "outcome": outcome,
        "net_units": net_units,
        "complexity_delta": complexity_delta,
        "reference_net_units": ref_net,
        "ratio": ratio,
        "scope": scope,
        "completeness": completeness,
        "methods": sorted(methods),
        "per_file": per_file,
        "evidence": evidence,
    }


def score_campaign(patches):
    """Score a campaign of recorded patches: pass rate, median
    net-units ratio and median complexity delta over solved
    patches, mean scope completeness, the Spearman correlation
    between patch size and solving, and the outcome counts.

    patches: a list of patch dicts, each optionally carrying its
    reference under "reference". Returns the campaign receipt.
    """
    if not isinstance(patches, list):
        raise TypeError("patches must be a list")
    scored = [score_patch(patch) for patch in patches]
    count = len(scored)
    if count == 0:
        return {
            "n": 0,
            "pass_rate": None,
            "median_ratio": None,
            "median_complexity_delta": None,
            "mean_completeness": None,
            "spearman_size_solved": None,
            "outcomes": {},
            "verdict": VERDICT_REVIEW,
            "evidence": "no patches scored; a receipt over no patches proves nothing",
            "patches": [],
        }
    passed = sum(1 for item in scored if item["passed"])
    pass_rate = passed / count
    solved = [item for item in scored if item["passed"]]
    ratios = [
        item["ratio"] for item in solved if item["ratio"] is not None
    ]
    median_ratio = _median(ratios)
    median_cx = _median(
        [item["complexity_delta"] for item in solved]
    ) if solved else None
    mean_completeness = sum(
        item["completeness"] for item in scored
    ) / count
    spearman = _spearman(
        [item["net_units"] for item in scored],
        [1 if item["passed"] else 0 for item in scored],
    )
    outcomes = {}
    for item in scored:
        outcomes[item["outcome"]] = outcomes.get(item["outcome"], 0) + 1
    bloated = outcomes.get(OUTCOME_SOLVED_BLOATED, 0)
    corner_cut = outcomes.get(OUTCOME_SOLVED_CORNER_CUT, 0) + outcomes.get(
        OUTCOME_SOLVED_INCOMPLETE, 0
    )
    if bloated:
        verdict = VERDICT_REVIEW
        evidence = (
            "%d solved patch(es) added more net units than the "
            "human fix" % bloated
        )
    elif corner_cut:
        verdict = VERDICT_REVIEW
        evidence = (
            "%d solved patch(es) are thin on scope (corner cut or "
            "incomplete)" % corner_cut
        )
    else:
        verdict = VERDICT_READY
        evidence = (
            "no solved patch added more than the human fix and no "
            "solved patch is thin on scope"
        )
    return {
        "n": count,
        "pass_rate": pass_rate,
        "median_ratio": median_ratio,
        "median_complexity_delta": median_cx,
        "mean_completeness": mean_completeness,
        "spearman_size_solved": spearman,
        "outcomes": outcomes,
        "verdict": verdict,
        "evidence": evidence,
        "patches": scored,
    }


def build_lean_patch_report(agent_name, patches):
    """Wrap score_campaign with the agent it describes."""
    campaign = score_campaign(patches)
    return {
        "agent": agent_name,
        "verdict": campaign["verdict"],
        "n": campaign["n"],
        "pass_rate": campaign["pass_rate"],
        "median_ratio": campaign["median_ratio"],
        "median_complexity_delta": campaign["median_complexity_delta"],
        "mean_completeness": campaign["mean_completeness"],
        "spearman_size_solved": campaign["spearman_size_solved"],
        "outcomes": campaign["outcomes"],
        "evidence": campaign["evidence"],
        "patches": campaign["patches"],
    }


def format_summary(report):
    """One paragraph: verdict, pass rate, median ratio, scope."""
    if report["n"] == 0:
        return (
            "Lean-patch receipt for %s: no patches scored."
            % report["agent"]
        )
    ratio = report["median_ratio"]
    ratio_text = "%.2f" % ratio if ratio is not None else "undefined"
    return (
        "Lean-patch receipt for %s: %s. %d patches, pass rate %.2f, "
        "median net-units ratio %s vs the human fix, median "
        "complexity delta %s, mean scope completeness %.2f. "
        "Outcomes: %s. %s."
        % (
            report["agent"],
            report["verdict"],
            report["n"],
            report["pass_rate"],
            ratio_text,
            (
                "%+.1f" % report["median_complexity_delta"]
                if report["median_complexity_delta"] is not None
                else "undefined"
            ),
            report["mean_completeness"],
            ", ".join(
                "%s %d" % (key, value)
                for key, value in sorted(report["outcomes"].items())
            ),
            report["evidence"],
        )
    )
