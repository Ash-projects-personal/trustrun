"""Focused verification for TRUSTRUN-AllowRuleAudit.

Scores the module's 25 labeled cases: the PGPASSWORD inline
password, the sshpass flag, the mysql -p flag, the bearer header,
the URL userinfo password, the GitHub token in a known format,
the AWS secret variable, the Supabase service-role key in env,
the env $VAR reference, the unrestricted shell, the python
wildcard, the node wildcard, the broad npm prefix, the exact
command, the $VAR reference in a header, the read rule, the
scoped WebFetch rule, the tracked clean file, the file not
ignored in the repo, the denied secret that still leaks, the
mixed file, the empty settings, the shared-file secret rule, the
rule carrying two secrets, and the unrestricted WebFetch rule.
Every case is a fixed scripted settings file with an expected
verdict and expected counts, scored by
trustrun.allow_rule_audit. The campaign block checks the
aggregate numbers by hand: 25 files, 12 BLOCK / 7 REVIEW / 6
PASS, 24 allow rules, 11 secret rules (7 password-in-command,
2 header, 1 URL userinfo, 1 known format), 1 env secret, 10
secret rules in the shape general scanners miss, 6 over-broad
rules, 7 clean rules, 1 tracked local file, 1 file not ignored
in the repo, verdict BLOCK.

Writes a machine-readable summary into
reports/allow-rule-audit-verify/summary.json. Expected yield: 25
labeled file cases, 25/25 match, campaign block matches.
Exits non-zero on any mismatch.

This script was derived from the cause-receipt labeled cases in
evals/run_cause_receipt_verify.py. Its REPORTS constant was
verified to point at allow-rule-audit-verify/ before the run, so
it cannot overwrite any round directory.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from trustrun.allow_rule_audit import (  # noqa: E402
    FINDING_KNOWN_FORMAT,
    FINDING_SECRET_IN_COMMAND,
    FINDING_SECRET_IN_HEADER,
    FINDING_SECRET_IN_URL,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    audit_settings,
    score_campaign,
)

REPORTS = os.path.join(HERE, "reports", "allow-rule-audit-verify")

EXPECTED_CAMPAIGN = {
    "verdicts": {VERDICT_BLOCK: 12, VERDICT_REVIEW: 7, VERDICT_PASS: 6},
    "totals": {
        "files": 25,
        "total_rules": 24,
        "secret_rules": 11,
        "env_secrets": 1,
        "missed_by_general_scanners": 10,
        "over_broad_rules": 6,
        "clean_rules": 7,
        "tracked_local_files": 1,
        "not_ignored_in_repo": 1,
    },
    "secret_kinds": {
        FINDING_SECRET_IN_COMMAND: 7,
        FINDING_SECRET_IN_HEADER: 2,
        FINDING_SECRET_IN_URL: 1,
        FINDING_KNOWN_FORMAT: 1,
    },
    "verdict": VERDICT_BLOCK,
}


def _file(case_id, allow=None, env=None, tracked=False,
          gitignore_covers=True, filename=".claude/settings.local.json",
          deny=None):
    settings = {}
    if allow is not None or deny is not None:
        permissions = {}
        if allow is not None:
            permissions["allow"] = allow
        if deny is not None:
            permissions["deny"] = deny
        settings["permissions"] = permissions
    if env is not None:
        settings["env"] = env
    return {
        "filename": filename,
        "settings": settings,
        "tracked": tracked,
        "gitignore_covers": gitignore_covers,
    }


def allow_rule_audit_cases():
    """25 labeled settings files: (case_id, file record, expected
    verdict, expected counts)."""
    cases = []

    # The PGPASSWORD inline password: the shape both general
    # scanners miss.
    cases.append((
        "pgpassword_inline",
        _file("pgpassword_inline", allow=[
            "Bash(PGPASSWORD=hunter2 psql -h db.example.com -U app)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The sshpass -p flag.
    cases.append((
        "sshpass_flag",
        _file("sshpass_flag", allow=[
            "Bash(sshpass -p hunter2 ssh deploy@host.example.com)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The mysql -p flag, attached value.
    cases.append((
        "mysql_p_flag",
        _file("mysql_p_flag", allow=[
            "Bash(mysql -u root -psecret123 -h db.example.com)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The bearer token in a curl header.
    cases.append((
        "bearer_curl",
        _file("bearer_curl", allow=[
            'Bash(curl -H "Authorization: Bearer '
            'sk-live-0123456789abcdef" https://api.example.com/v1)']),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The password in URL userinfo.
    cases.append((
        "url_userinfo",
        _file("url_userinfo", allow=[
            "Bash(curl https://deploy:p4ssw0rd@api.example.com/data)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The GitHub token: a known format, so the general scanners
    # catch this one. Missed count stays 0 for this case.
    cases.append((
        "github_token",
        _file("github_token", allow=[
            "Bash(gh auth login --with-token <<< "
            "ghp_abcdefghij1234567890abcdefghijklmnop)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The AWS secret access key as a VAR=value prefix.
    cases.append((
        "aws_secret_var",
        _file("aws_secret_var", allow=[
            "Bash(AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/"
            "bPxRfiCYEXAMPLEKEY aws s3 ls)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The Supabase service-role key in the env block.
    cases.append((
        "env_supabase_key",
        _file("env_supabase_key", env={
            "SUPABASE_SERVICE_ROLE_KEY":
                "sbp_0123456789abcdef0123456789abcdef0123456789abcdef"}),
        VERDICT_BLOCK,
        {"total_rules": 0, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 1,
         "missed_by_general_scanners": 0},
    ))

    # The env $VAR reference: a name, not a value.
    cases.append((
        "env_reference",
        _file("env_reference", env={"OPENAI_API_KEY": "$OPENAI_API_KEY"}),
        VERDICT_PASS,
        {"total_rules": 0, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The unrestricted shell: any command allowed.
    cases.append((
        "unrestricted_shell",
        _file("unrestricted_shell", allow=["Bash(*)"]),
        VERDICT_REVIEW,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 1,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The python interpreter wildcard.
    cases.append((
        "python_wildcard",
        _file("python_wildcard", allow=["Bash(python:*)"]),
        VERDICT_REVIEW,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 1,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The node interpreter wildcard.
    cases.append((
        "node_wildcard",
        _file("node_wildcard", allow=["Bash(node:*)"]),
        VERDICT_REVIEW,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 1,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The broad npm prefix: any npm invocation allowed.
    cases.append((
        "broad_prefix",
        _file("broad_prefix", allow=["Bash(npm *)"]),
        VERDICT_REVIEW,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 1,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The exact command: narrow and clean.
    cases.append((
        "exact_command",
        _file("exact_command", allow=["Bash(npm test)"]),
        VERDICT_PASS,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 1, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The $VAR reference in a header: the safe shape.
    cases.append((
        "var_reference",
        _file("var_reference", allow=[
            'Bash(curl -H "Authorization: Bearer $N8N_API_KEY" '
            "https://api.example.com)"]),
        VERDICT_PASS,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 1, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The read rule: no command content to audit.
    cases.append((
        "read_rule",
        _file("read_rule", allow=["Read(~/.zshrc)"]),
        VERDICT_PASS,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 1, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The scoped WebFetch rule.
    cases.append((
        "webfetch_domain",
        _file("webfetch_domain", allow=["WebFetch(domain:example.com)"]),
        VERDICT_PASS,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 1, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The tracked clean file: the rules are fine, the hygiene is
    # not, because a tracked local file leaks on every machine.
    cases.append((
        "tracked_clean",
        _file("tracked_clean", allow=["Bash(npm test)"], tracked=True),
        VERDICT_REVIEW,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 1, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The file the repo's own .gitignore does not cover.
    cases.append((
        "not_ignored",
        _file("not_ignored", allow=["Bash(npm test)"],
              gitignore_covers=False),
        VERDICT_REVIEW,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 1, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The denied secret still leaks: deny stops the command
    # running, but the secret is still in the file.
    cases.append((
        "denied_secret_still_leaks",
        _file("denied_secret_still_leaks",
              allow=["Bash(PGPASSWORD=hunter2 psql -h db -U app)"],
              deny=["Bash(PGPASSWORD=hunter2 psql -h db -U app)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The mixed file: one secret, one over-broad, one clean.
    cases.append((
        "mixed_file",
        _file("mixed_file", allow=[
            "Bash(PGPASSWORD=x psql -h db -U app)",
            "Bash(python:*)",
            "Bash(npm test)"]),
        VERDICT_BLOCK,
        {"total_rules": 3, "secret_rules": 1, "over_broad_rules": 1,
         "clean_rules": 1, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The empty settings file: no rules, no findings.
    cases.append((
        "empty_settings",
        _file("empty_settings"),
        VERDICT_PASS,
        {"total_rules": 0, "secret_rules": 0, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    # The shared-file secret rule: the shared settings file is
    # committed on purpose, so tracking it is normal, but the
    # secret in its allow rule still blocks.
    cases.append((
        "shared_secret_rule",
        _file("shared_secret_rule",
              allow=['Bash(curl -H "X-Api-Key: abc123def456" '
                    "https://api.example.com)"],
              tracked=True, filename=".claude/settings.json"),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The rule carrying two secrets counts once, under its
    # primary finding.
    cases.append((
        "multi_secret_rule",
        _file("multi_secret_rule", allow=[
            "Bash(PGPASSWORD=hunter2 psql --password=otherpass "
            "-h db -U app)"]),
        VERDICT_BLOCK,
        {"total_rules": 1, "secret_rules": 1, "over_broad_rules": 0,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 1},
    ))

    # The unrestricted WebFetch rule.
    cases.append((
        "webfetch_wildcard",
        _file("webfetch_wildcard", allow=["WebFetch(*)"]),
        VERDICT_REVIEW,
        {"total_rules": 1, "secret_rules": 0, "over_broad_rules": 1,
         "clean_rules": 0, "env_secrets": 0,
         "missed_by_general_scanners": 0},
    ))

    return cases


def _counts_match(actual, expected):
    return all(actual.get(key) == value for key, value in expected.items())


def main():
    cases = allow_rule_audit_cases()
    results = []
    files = []
    for case_id, entry, expected_verdict, expected_counts in cases:
        result = audit_settings(
            entry["settings"],
            tracked=entry.get("tracked", False),
            gitignore_covers=entry.get("gitignore_covers", True),
            filename=entry.get("filename", ".claude/settings.local.json"),
        )
        files.append(entry)
        match = result["verdict"] == expected_verdict and _counts_match(
            result["counts"], expected_counts)
        results.append({
            "case_id": case_id,
            "expected_verdict": expected_verdict,
            "actual_verdict": result["verdict"],
            "expected_counts": expected_counts,
            "actual_counts": result["counts"],
            "match": match,
        })
    matched = sum(1 for item in results if item["match"])

    campaign = score_campaign(files)
    campaign_match = (
        campaign["verdicts"] == EXPECTED_CAMPAIGN["verdicts"]
        and campaign["totals"] == EXPECTED_CAMPAIGN["totals"]
        and campaign["secret_kinds"] == EXPECTED_CAMPAIGN["secret_kinds"]
        and campaign["verdict"] == EXPECTED_CAMPAIGN["verdict"]
    )
    summary = {
        "cases": len(results),
        "matched": matched,
        "results": results,
        "campaign": campaign,
        "campaign_match": campaign_match,
    }
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "summary.json"), "w") as handle:
        json.dump(summary, handle, indent=1)
    print("allow-rule-audit labeled cases: %d/%d match"
          % (matched, len(results)))
    for item in results:
        if not item["match"]:
            print(
                "MISMATCH %s: expected %s/%s, got %s/%s"
                % (
                    item["case_id"],
                    item["expected_verdict"],
                    item["expected_counts"],
                    item["actual_verdict"],
                    item["actual_counts"],
                )
            )
    print("allow-rule-audit campaign block: %s"
          % ("match" if campaign_match else "MISMATCH"))
    if not campaign_match:
        print("expected: %s" % json.dumps(EXPECTED_CAMPAIGN, indent=1))
        print("actual: %s" % json.dumps({
            "verdicts": campaign["verdicts"],
            "totals": campaign["totals"],
            "secret_kinds": campaign["secret_kinds"],
            "verdict": campaign["verdict"],
        }, indent=1))
    if matched != len(results) or not campaign_match:
        sys.exit(1)


if __name__ == "__main__":
    main()
