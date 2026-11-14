"""Allow-rule audit: secrets and over-broad rules in agent permission files.

Claude Code's "Yes, and don't ask again" answer saves the approved
command verbatim as an allow rule in `.claude/settings.local.json`.
When the command carries a credential, the credential is saved
into the file in plain text, and the file is protected only by the
developer's global git ignore list, which does not travel with the
repository. Apiiro (Shmulik Cohen and Matan Giladi, published Nov
5 2026; numbers confirmed this run from the ByteHerald, AgentBeam,
enjoy.dev, and Medium write-ups of the research) downloaded every
public copy of the file it could find on GitHub between Nov 1 and
3 2026: 104,185 copies in 103,617 repositories, of which 1,122
(about 1.1%) hold a real secret, 1,379 distinct secrets in total
(636 provider keys and 743 passwords or tokens for public hosts,
including 379 database passwords, 122 Supabase service-role keys,
43 SSH logins, 42 GitHub/GitLab/npm tokens, and 23 AWS keys). The
wider count, adding git history, the shared settings file, and
saved agent transcripts, is 2,539 distinct secrets across 1,994
repositories, belonging to at least 63 organizations. The median
exposed file had sat on its repository's default branch for 217
days, and in 118 repositories for more than a year. In 539 of
1,105 repositories traced through history, a Claude-co-authored
commit touched the file. The shared `.claude/settings.json`, which
teams commit on purpose, holds secrets in 298 of 76,011 copies.

The standard scanners miss the shape that matters most here.
Apiiro ran gitleaks and TruffleHog over all 104,185 files: of the
1,122 files with a real secret, gitleaks flagged 564 and
TruffleHog flagged 643, and neither flagged 215, about one in
five. The missed ones are passwords typed into commands, which
have no key format to match: `PGPASSWORD=<value>`, `sshpass -p`,
`mysql -p`, bearer tokens in curl headers, and passwords in URL
userinfo. The allowlist is also over-broad on its own: 5% of the
files allow any shell command (`Bash(*)`), and 43% carry
interpreter rules like `Bash(python:*)`.

GitGuardian's follow-up (blog.gitguardian.com, read this run)
found a larger public count, 31,088 distinct secrets across
23,276 repositories with 5,343 valid when detected, and 613
secrets in public Docker Hub images, but that is continuous
monitoring of public commits, a service, not a local auditor a
team can run on its own files before committing. The ssdnodes
write-up (read this run) publishes a five-command manual git
audit and a blunt shell pre-commit snippet that refuses the
personal settings file and greps `.claude/` files for password
words: advice and a grep, not a scored auditor. Anthropic's
Claude Code lead (Boris Cherny, on Hacker News Nov 7, as
reported by iTnews) says the team is "looking into" fixes
including basic secret scanning: announced intent, not a shipped
fix. No shipped tool found that parses allow rules command-aware,
scores over-broad rules, and emits a repo-hygiene receipt for a
team's own agent permission files. That is the new piece here,
inside Trustrun's trust report: the command-aware allow-rule
auditor plus the repo-hygiene receipt, scored on recorded
settings files.

A settings file is a dict as parsed from `.claude/settings.local.json`
(or the shared `.claude/settings.json`, or another agent's
permission file in the same shape): "permissions" with "allow",
"deny", and "ask" lists of rule strings, and an optional "env"
dict of name to value. A rule looks like "Bash(npm test)",
"Bash(PGPASSWORD=hunter2 psql -h db -U app)", "Read(~/.zshrc)",
or "WebFetch(domain:example.com)".

Rule findings, in priority order (a rule carries one primary
finding, the first kind that matches):

- "secret_in_header": an Authorization / X-Api-Key / Api-Key /
  X-Auth-Token header carrying a literal value, as in a curl
  call. A "$VAR" reference is a reference, not a value, and is
  clean.
- "secret_in_url": a password in URL userinfo, as in
  "https://user:pass@host".
- "secret_in_command": a credential carried as a command
  argument: a VAR=value prefix where VAR names a credential
  (PASSWORD, PASSWD, _PWD, TOKEN, SECRET, API_KEY, PRIVATE_KEY),
  "sshpass -p <value>", "mysql -p<value>" or "--password=<value>".
  "ssh -p 2222" is a port, not a password, and is clean: the -p
  flag only counts for sshpass, mysql, and mariadb.
- "known_format_secret": a value in a recognized provider format
  (sk-, ghp_, gho_, github_pat_, AKIA, xoxb/xoxp/xoxa/xoxr/xoxs,
  sbp_, a private-key header). This is the class the general
  scanners already catch; the receipt reports it separately so
  the missed-by-scanners count is honest.
- "unrestricted_shell": "Bash(*)", any shell command allowed.
- "interpreter_wildcard": "Bash(python:*)" and the same shape for
  python3, node, sh, bash, zsh, ruby, perl, php, deno, bun.
- "unrestricted_fetch": "WebFetch(*)".
- "broad_prefix": "Bash(<command> *)", any invocation of one
  command allowed.
- "clean": no finding.

A "$VAR" reference is never a secret: the rule stores the name,
not the value, which is the safe shape GitGuardian recommends.
Placeholder values ("***", "xxx", "redacted", "<...>", "changeme")
are not secrets either. A rule carrying two secrets counts once,
under its primary finding: the receipt flags the rule, not each
secret inside it.

File findings. The "env" block is audited the same way: a literal
value in a known provider format, or a literal value under a
credential-named variable, is "secret_in_env"; a "$VAR" reference
is clean. Hygiene findings apply to the personal local file
only, "settings.local.json": "tracked_local_file" when the file
is tracked in git (the global gitignore does not travel, so a
tracked local file leaks on every machine), and
"not_ignored_in_repo" when the repository's own .gitignore does
not cover it. The shared "settings.json" is committed on purpose,
so being tracked is normal for it and carries no hygiene finding.
A deny rule does not clear a secret finding: deny stops the
command running, but the secret is still in the file, and a
committed file leaks regardless of whether the command runs.

Verdicts. A file is BLOCK when it carries any secret finding, in
a rule or in env. It is REVIEW when it carries no secret but an
over-broad rule or a hygiene finding. It is PASS otherwise. The
repo verdict is the worst file verdict. The receipt also reports
"missed_by_general_scanners": the count of secret rules whose
shape is a password in a command, a URL userinfo password, or a
header value, the shapes Apiiro measured as missed by both
gitleaks and TruffleHog in 215 of 1,122 files. That count is a
shape classification, not a live run of either scanner, and the
receipt says so.

Honest limits, read before quoting any number from this module:
it scores recorded settings files, nothing more. It does not run
gitleaks or TruffleHog, so the missed-by-scanners count is a
shape claim against Apiiro's published measurement, not a
re-measurement. Substring and pattern matching needs the secret
to sit in one of the listed shapes: a password passed through an
unlisted flag, a base64 blob with no provider prefix, or a secret
split across shell quoting is missed. Tools with no declared
rule shape are unscored, not passed: Read and Edit globs are not
scored for breadth in this version. A PASS is about the recorded
files, not a certification that the repository is clean, and
this module never validates a credential by trying it.
"""

import re

FINDING_SECRET_IN_HEADER = "secret_in_header"
FINDING_SECRET_IN_URL = "secret_in_url"
FINDING_SECRET_IN_COMMAND = "secret_in_command"
FINDING_KNOWN_FORMAT = "known_format_secret"
FINDING_UNRESTRICTED_SHELL = "unrestricted_shell"
FINDING_INTERPRETER_WILDCARD = "interpreter_wildcard"
FINDING_UNRESTRICTED_FETCH = "unrestricted_fetch"
FINDING_BROAD_PREFIX = "broad_prefix"
FINDING_CLEAN = "clean"
FINDING_UNSCORED = "unscored"

FINDING_SECRET_IN_ENV = "secret_in_env"
FINDING_TRACKED_LOCAL = "tracked_local_file"
FINDING_NOT_IGNORED = "not_ignored_in_repo"

VERDICT_BLOCK = "BLOCK"
VERDICT_REVIEW = "REVIEW"
VERDICT_PASS = "PASS"

# Secret kinds, in priority order. A rule's primary finding is the
# first kind that matches.
SECRET_KINDS = (
    FINDING_SECRET_IN_HEADER,
    FINDING_SECRET_IN_URL,
    FINDING_SECRET_IN_COMMAND,
    FINDING_KNOWN_FORMAT,
)

OVER_BROAD_KINDS = (
    FINDING_UNRESTRICTED_SHELL,
    FINDING_INTERPRETER_WILDCARD,
    FINDING_UNRESTRICTED_FETCH,
    FINDING_BROAD_PREFIX,
)

SEVERITY = {
    FINDING_SECRET_IN_HEADER: "high",
    FINDING_SECRET_IN_URL: "high",
    FINDING_SECRET_IN_COMMAND: "high",
    FINDING_KNOWN_FORMAT: "high",
    FINDING_SECRET_IN_ENV: "high",
    FINDING_UNRESTRICTED_SHELL: "medium",
    FINDING_INTERPRETER_WILDCARD: "medium",
    FINDING_UNRESTRICTED_FETCH: "medium",
    FINDING_BROAD_PREFIX: "medium",
    FINDING_TRACKED_LOCAL: "low",
    FINDING_NOT_IGNORED: "low",
}

# A credential variable name: PASSWORD, PASSWD, a _PWD suffix
# (MYSQL_PWD; bare PWD is the shell working-directory variable
# and is excluded on purpose), TOKEN, SECRET, API_KEY, PRIVATE_KEY.
_CREDENTIAL_NAME_RE = re.compile(
    r"(PASSWORD|PASSWD|_PWD|TOKEN|SECRET|API[_-]?KEY|PRIVATE[_-]?KEY)",
    re.IGNORECASE)

# VAR=value assignments. The name is checked separately against
# _CREDENTIAL_NAME_RE, so API_KEY, MY_API_KEY, DB_PASSWORD, and
# AWS_SECRET_ACCESS_KEY all match: a single regex cannot anchor
# the credential word at the end of the name without missing
# the API_KEY shape.
_VAR_ASSIGN_RE = re.compile(
    r"(?:^|[\s;&|(\"])([A-Za-z_][A-Za-z0-9_]*)\s*=\s*([^\s;&|\"']+)",
    re.IGNORECASE)

# Header carrying a literal credential value.
_HEADER_RE = re.compile(
    r"\b(?:Authorization|Proxy-Authorization|X-Api-Key|Api-Key|X-Auth-Token)"
    r"\s*:\s*(?:Bearer\s+|Token\s+)?([^\s\"',;]+)",
    re.IGNORECASE)

# Password in URL userinfo: scheme://user:pass@host.
_URL_USERINFO_RE = re.compile(r"://[^/\s:@]+:([^/\s@\"']+)@")

# Values in a recognized provider format. This is the class the
# general-purpose scanners already catch.
_KNOWN_FORMAT_RE = re.compile(
    r"(?:sk-[A-Za-z0-9-]{8,}|ghp_[A-Za-z0-9]{20,}|gho_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|sbp_[A-Za-z0-9]{20,}|"
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)")

# Password flags. "-p" is a password only for sshpass, mysql, and
# mariadb: "ssh -p 2222" and "psql -p 5432" are ports. The value
# must not be another flag.
_PASSWORD_FLAG_RES = (
    re.compile(r"\bsshpass\s+-p\s+([^\s;&|\"']+)", re.IGNORECASE),
    re.compile(r"\b(?:mysql|mariadb)\b[^;|]*?-p\s*=?\s*([^\s;&|\"']+)",
               re.IGNORECASE),
    re.compile(r"--password(?:\s*=\s*|\s+)([^\s;&|\"']+)", re.IGNORECASE),
)

_BASH_RE = re.compile(r"^Bash\((.*)\)$", re.DOTALL)
_UNRESTRICTED_SHELL_RE = re.compile(r"^Bash\(\s*\*\s*\)$")
_INTERPRETER_RE = re.compile(
    r"^Bash\(\s*(python3?|node|sh|bash|zsh|ruby|perl|php|deno|bun)"
    r":\s*\*\s*\)$")
_UNRESTRICTED_FETCH_RE = re.compile(r"^WebFetch\(\s*\*\s*\)$")
_BROAD_PREFIX_RE = re.compile(r"^Bash\(\s*[A-Za-z0-9_./-]+\s+[^)]*\*\s*\)$")

_PLACEHOLDERS = {"xxx", "xxxx", "redacted", "changeme", "example", "test",
                 "password", "none", "null"}


def _is_reference(value):
    """True when the value is a $VAR reference, not a literal."""
    return isinstance(value, str) and value.startswith("$")


def _is_placeholder(value):
    """True when the value is a redaction marker, not a secret."""
    if not isinstance(value, str) or not value:
        return True
    lowered = value.lower()
    if lowered in _PLACEHOLDERS:
        return True
    if lowered.startswith("<") and lowered.endswith(">"):
        return True
    # A run of filler characters ("xxx", "****") is a marker. A
    # single character is not: a one-character password is weak
    # but real, and flagging it costs nothing when it is not.
    return len(value) >= 2 and set(value) <= {"*", "x", "X"}


def _is_literal_secret(value):
    """True when the value is a real literal, not a reference or marker."""
    return (isinstance(value, str) and value
            and not _is_reference(value) and not _is_placeholder(value))


def _command_text(rule):
    """The command inside a Bash rule, else the whole rule string."""
    match = _BASH_RE.match(rule.strip())
    if match:
        return match.group(1)
    return rule.strip()


def _first_command_word(command):
    words = command.strip().split(None, 1)
    return words[0].lower() if words else ""


def _secret_kinds(command):
    """All secret kinds present in the command text, in priority order."""
    kinds = []
    header = _HEADER_RE.search(command)
    if header and _is_literal_secret(header.group(1)):
        kinds.append(FINDING_SECRET_IN_HEADER)
    userinfo = _URL_USERINFO_RE.search(command)
    if userinfo and _is_literal_secret(userinfo.group(1)):
        kinds.append(FINDING_SECRET_IN_URL)
    var_assign = _VAR_ASSIGN_RE.search(command)
    if var_assign and _CREDENTIAL_NAME_RE.search(var_assign.group(1)) \
            and _is_literal_secret(var_assign.group(2)):
        kinds.append(FINDING_SECRET_IN_COMMAND)
    else:
        first = _first_command_word(command)
        if first in ("sshpass", "mysql", "mariadb"):
            for pattern in _PASSWORD_FLAG_RES:
                flag = pattern.search(command)
                if flag and _is_literal_secret(flag.group(1)) \
                        and not flag.group(1).startswith("-"):
                    kinds.append(FINDING_SECRET_IN_COMMAND)
                    break
        else:
            flag = _PASSWORD_FLAG_RES[2].search(command)
            if flag and _is_literal_secret(flag.group(1)) \
                    and not flag.group(1).startswith("-"):
                kinds.append(FINDING_SECRET_IN_COMMAND)
    if _KNOWN_FORMAT_RE.search(command):
        kinds.append(FINDING_KNOWN_FORMAT)
    return kinds


def _over_broad_kind(rule):
    """The over-broad kind of the rule, or None."""
    text = rule.strip()
    if _UNRESTRICTED_SHELL_RE.match(text):
        return FINDING_UNRESTRICTED_SHELL
    if _INTERPRETER_RE.match(text):
        return FINDING_INTERPRETER_WILDCARD
    if _UNRESTRICTED_FETCH_RE.match(text):
        return FINDING_UNRESTRICTED_FETCH
    if _BROAD_PREFIX_RE.match(text):
        return FINDING_BROAD_PREFIX
    return None


def audit_rule(rule):
    """Audit one allow rule string.

    Returns a dict with "rule", "finding" (the primary kind, or
    "clean", or "unscored" for a non-string rule), "kinds" (every
    secret kind present, in priority order), "severity", and
    "evidence". A rule with a secret outranks an over-broad one:
    the secret is the finding, and the breadth is still listed in
    "kinds" only when it is itself a secret kind, never mixed in.
    """
    if not isinstance(rule, str) or not rule.strip():
        return {
            "rule": rule,
            "finding": FINDING_UNSCORED,
            "kinds": [],
            "severity": None,
            "evidence": "no rule text to audit, so the rule is "
            "unscored, never passed",
        }
    text = rule.strip()
    command = _command_text(text)
    kinds = _secret_kinds(command)
    if kinds:
        finding = kinds[0]
        return {
            "rule": text,
            "finding": finding,
            "kinds": kinds,
            "severity": SEVERITY[finding],
            "evidence": "rule carries a secret of kind %s" % finding,
        }
    broad = _over_broad_kind(text)
    if broad:
        return {
            "rule": text,
            "finding": broad,
            "kinds": [],
            "severity": SEVERITY[broad],
            "evidence": "rule is over-broad: %s" % broad,
        }
    return {
        "rule": text,
        "finding": FINDING_CLEAN,
        "kinds": [],
        "severity": None,
        "evidence": "no secret shape and no over-broad pattern found",
    }


def _audit_env(env):
    """Audit an env block: list of (name, finding) for secret values."""
    found = []
    if not isinstance(env, dict):
        return found
    for name, value in env.items():
        if not _is_literal_secret(value):
            continue
        if _KNOWN_FORMAT_RE.search(value):
            found.append((name, FINDING_SECRET_IN_ENV))
        elif isinstance(name, str) and _CREDENTIAL_NAME_RE.search(name):
            found.append((name, FINDING_SECRET_IN_ENV))
    return found


def _is_local_file(filename):
    return isinstance(filename, str) and \
        filename.endswith("settings.local.json")


def audit_settings(settings, tracked=False, gitignore_covers=True,
                    filename=".claude/settings.local.json"):
    """Audit one recorded settings file.

    settings is the parsed JSON dict. tracked says whether the file
    is tracked in git; gitignore_covers says whether the repo's own
    .gitignore covers it. Returns a dict with the filename, the
    verdict, the per-rule findings, the env findings, the hygiene
    findings, and the counts. A non-dict settings record is REVIEW:
    the audit cannot prove it clean.
    """
    if not isinstance(settings, dict):
        return {
            "filename": filename,
            "verdict": VERDICT_REVIEW,
            "rule_findings": [],
            "env_findings": [],
            "hygiene_findings": [],
            "counts": {
                "total_rules": 0,
                "secret_rules": 0,
                "over_broad_rules": 0,
                "clean_rules": 0,
                "unscored_rules": 0,
                "env_secrets": 0,
                "missed_by_general_scanners": 0,
            },
            "secret_kinds": {},
            "evidence": "settings record is not a JSON object, so "
            "the audit cannot prove it clean",
        }
    permissions = settings.get("permissions")
    allow = permissions.get("allow") if isinstance(permissions, dict) else None
    if not isinstance(allow, list):
        allow = []
    rule_findings = [audit_rule(rule) for rule in allow]
    env_findings = _audit_env(settings.get("env"))

    hygiene = []
    if _is_local_file(filename):
        if tracked:
            hygiene.append({
                "finding": FINDING_TRACKED_LOCAL,
                "severity": SEVERITY[FINDING_TRACKED_LOCAL],
                "evidence": "a personal local settings file is tracked "
                "in git, so the global gitignore does not protect it",
            })
        if not gitignore_covers:
            hygiene.append({
                "finding": FINDING_NOT_IGNORED,
                "severity": SEVERITY[FINDING_NOT_IGNORED],
                "evidence": "the repository's own .gitignore does not "
                "cover the local settings file",
            })

    counts = {
        "total_rules": len(rule_findings),
        "secret_rules": 0,
        "over_broad_rules": 0,
        "clean_rules": 0,
        "unscored_rules": 0,
        "env_secrets": len(env_findings),
        "missed_by_general_scanners": 0,
    }
    secret_kinds = {}
    for item in rule_findings:
        finding = item["finding"]
        if finding in SECRET_KINDS:
            counts["secret_rules"] += 1
            secret_kinds[finding] = secret_kinds.get(finding, 0) + 1
            if finding != FINDING_KNOWN_FORMAT:
                counts["missed_by_general_scanners"] += 1
        elif finding in OVER_BROAD_KINDS:
            counts["over_broad_rules"] += 1
        elif finding == FINDING_CLEAN:
            counts["clean_rules"] += 1
        else:
            counts["unscored_rules"] += 1

    if counts["secret_rules"] or counts["env_secrets"]:
        verdict = VERDICT_BLOCK
        evidence = "%d secret rule(s) and %d env secret(s)" % (
            counts["secret_rules"], counts["env_secrets"])
    elif counts["over_broad_rules"] or hygiene:
        verdict = VERDICT_REVIEW
        evidence = "%d over-broad rule(s) and %d hygiene finding(s)" % (
            counts["over_broad_rules"], len(hygiene))
    else:
        verdict = VERDICT_PASS
        evidence = "no secret, over-broad rule, or hygiene finding"
    return {
        "filename": filename,
        "verdict": verdict,
        "rule_findings": rule_findings,
        "env_findings": [
            {"name": name, "finding": kind,
             "severity": SEVERITY[kind],
             "evidence": "env value for %s is a literal secret" % name}
            for name, kind in env_findings
        ],
        "hygiene_findings": hygiene,
        "counts": counts,
        "secret_kinds": secret_kinds,
        "evidence": evidence,
    }


def score_campaign(files):
    """Score a recorded set of settings files as one repo audit.

    files is a list of dicts with "filename", "settings", and the
    optional "tracked" and "gitignore_covers" flags. Returns the
    per-file results, the aggregate counts, and the repo verdict,
    which is the worst file verdict. An empty file list is REVIEW:
    a receipt over no files proves nothing.
    """
    files = list(files or [])
    results = []
    totals = {
        "files": len(files),
        "total_rules": 0,
        "secret_rules": 0,
        "env_secrets": 0,
        "missed_by_general_scanners": 0,
        "over_broad_rules": 0,
        "clean_rules": 0,
        "tracked_local_files": 0,
        "not_ignored_in_repo": 0,
    }
    verdicts = {VERDICT_BLOCK: 0, VERDICT_REVIEW: 0, VERDICT_PASS: 0}
    secret_kinds = {}
    for entry in files:
        entry = entry if isinstance(entry, dict) else {}
        result = audit_settings(
            entry.get("settings"),
            tracked=entry.get("tracked", False),
            gitignore_covers=entry.get("gitignore_covers", True),
            filename=entry.get("filename", ".claude/settings.local.json"),
        )
        results.append(result)
        verdicts[result["verdict"]] += 1
        counts = result["counts"]
        totals["total_rules"] += counts["total_rules"]
        totals["secret_rules"] += counts["secret_rules"]
        totals["env_secrets"] += counts["env_secrets"]
        totals["missed_by_general_scanners"] += counts[
            "missed_by_general_scanners"]
        totals["over_broad_rules"] += counts["over_broad_rules"]
        totals["clean_rules"] += counts["clean_rules"]
        for item in result["hygiene_findings"]:
            if item["finding"] == FINDING_TRACKED_LOCAL:
                totals["tracked_local_files"] += 1
            elif item["finding"] == FINDING_NOT_IGNORED:
                totals["not_ignored_in_repo"] += 1
        for kind, count in result["secret_kinds"].items():
            secret_kinds[kind] = secret_kinds.get(kind, 0) + count

    if not files:
        verdict = VERDICT_REVIEW
        evidence = "no files to audit"
    elif verdicts[VERDICT_BLOCK]:
        verdict = VERDICT_BLOCK
        evidence = "%d of %d files carry a secret" % (
            verdicts[VERDICT_BLOCK], len(files))
    elif verdicts[VERDICT_REVIEW]:
        verdict = VERDICT_REVIEW
        evidence = "%d of %d files need review, none carries a secret" % (
            verdicts[VERDICT_REVIEW], len(files))
    else:
        verdict = VERDICT_PASS
        evidence = "all %d files clean" % len(files)
    return {
        "files": results,
        "verdicts": verdicts,
        "totals": totals,
        "secret_kinds": secret_kinds,
        "verdict": verdict,
        "verdict_evidence": evidence,
    }


def format_summary(campaign):
    """One-paragraph human-readable summary of a repo audit."""
    totals = campaign["totals"]
    verdicts = campaign["verdicts"]
    return (
        "AllowRuleAudit: %d files audited; %d BLOCK, %d REVIEW, %d "
        "PASS; %d secret rules (%s) and %d env secret(s), %d of the "
        "secret rules in the shape general scanners miss; %d "
        "over-broad rules; %d clean rules; %d tracked local file(s); "
        "%d file(s) not ignored in the repo; verdict %s (%s)."
        % (
            totals["files"],
            verdicts[VERDICT_BLOCK], verdicts[VERDICT_REVIEW],
            verdicts[VERDICT_PASS],
            totals["secret_rules"],
            ", ".join("%s %d" % (kind, count) for kind, count in
                      sorted(campaign["secret_kinds"].items()))
            or "none",
            totals["env_secrets"],
            totals["missed_by_general_scanners"],
            totals["over_broad_rules"],
            totals["clean_rules"],
            totals["tracked_local_files"],
            totals["not_ignored_in_repo"],
            campaign["verdict"], campaign["verdict_evidence"]))
