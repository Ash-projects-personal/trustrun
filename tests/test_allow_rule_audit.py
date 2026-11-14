"""Tests for TRUSTRUN-AllowRuleAudit.

Every detector is covered on a positive and a negative case, plus
the priority order, the $VAR-reference rule, the placeholder rule,
the deny-does-not-clear rule, the file verdicts, and the repo
aggregation. Numbers here are the module's own bars, not the
Apiiro paper's: the paper's numbers live in the module docstring.
"""

from trustrun.allow_rule_audit import (
    FINDING_BROAD_PREFIX,
    FINDING_CLEAN,
    FINDING_INTERPRETER_WILDCARD,
    FINDING_KNOWN_FORMAT,
    FINDING_NOT_IGNORED,
    FINDING_SECRET_IN_COMMAND,
    FINDING_SECRET_IN_ENV,
    FINDING_SECRET_IN_HEADER,
    FINDING_SECRET_IN_URL,
    FINDING_TRACKED_LOCAL,
    FINDING_UNRESTRICTED_FETCH,
    FINDING_UNRESTRICTED_SHELL,
    FINDING_UNSCORED,
    VERDICT_BLOCK,
    VERDICT_PASS,
    VERDICT_REVIEW,
    audit_rule,
    audit_settings,
    format_summary,
    score_campaign,
)


def _settings(allow=None, env=None):
    data = {}
    if allow is not None:
        data["permissions"] = {"allow": allow}
    if env is not None:
        data["env"] = env
    return data


# --- secret-in-command ---

def test_pgpassword_prefix_is_secret():
    result = audit_rule("Bash(PGPASSWORD=hunter2 psql -h db -U app)")
    assert result["finding"] == FINDING_SECRET_IN_COMMAND
    assert result["severity"] == "high"


def test_api_key_var_prefix_is_secret():
    result = audit_rule("Bash(API_KEY=somepassword123 curl https://x)")
    assert result["finding"] == FINDING_SECRET_IN_COMMAND


def test_sshpass_flag_is_secret():
    result = audit_rule("Bash(sshpass -p hunter2 ssh deploy@host)")
    assert result["finding"] == FINDING_SECRET_IN_COMMAND


def test_mysql_attached_p_flag_is_secret():
    result = audit_rule("Bash(mysql -u root -psecret123 -h db)")
    assert result["finding"] == FINDING_SECRET_IN_COMMAND


def test_mysql_password_flag_is_secret():
    result = audit_rule("Bash(mysql --password=hunter2 -h db)")
    assert result["finding"] == FINDING_SECRET_IN_COMMAND


def test_ssh_port_flag_is_not_a_password():
    result = audit_rule("Bash(ssh -p 2222 deploy@host)")
    assert result["finding"] == FINDING_CLEAN


def test_psql_port_flag_is_not_a_password():
    result = audit_rule("Bash(psql -p 5432 -h db -U app)")
    assert result["finding"] == FINDING_CLEAN


def test_bare_pwd_is_not_a_credential_name():
    result = audit_rule("Bash(PWD=/home/user npm test)")
    assert result["finding"] == FINDING_CLEAN


# --- header, URL, known format ---

def test_bearer_header_is_secret():
    result = audit_rule(
        'Bash(curl -H "Authorization: Bearer sk-live-abc123" https://x)')
    assert result["finding"] == FINDING_SECRET_IN_HEADER


def test_x_api_key_header_is_secret():
    result = audit_rule(
        'Bash(curl -H "X-Api-Key: abc123def456" https://x)')
    assert result["finding"] == FINDING_SECRET_IN_HEADER


def test_url_userinfo_is_secret():
    result = audit_rule("Bash(curl https://user:p4ssw0rd@api.example.com)")
    assert result["finding"] == FINDING_SECRET_IN_URL


def test_github_token_is_known_format():
    result = audit_rule(
        "Bash(gh auth login --with-token <<< ghp_abcdefghij1234567890abcd)")
    assert result["finding"] == FINDING_KNOWN_FORMAT


def test_aws_access_key_id_is_known_format():
    result = audit_rule("Bash(aws s3 ls --profile AKIAIOSFODNN7EXAMPLE)")
    assert result["finding"] == FINDING_KNOWN_FORMAT


def test_header_beats_format_in_priority():
    # A bearer token that is also an sk- value: the header is the
    # primary finding, the format is still listed in kinds.
    result = audit_rule(
        'Bash(curl -H "Authorization: Bearer sk-live-0123456789abcdef" '
        "https://x)")
    assert result["finding"] == FINDING_SECRET_IN_HEADER
    assert FINDING_KNOWN_FORMAT in result["kinds"]


# --- references and placeholders are clean ---

def test_dollar_var_reference_in_header_is_clean():
    result = audit_rule(
        'Bash(curl -H "Authorization: Bearer $N8N_API_KEY" https://x)')
    assert result["finding"] == FINDING_CLEAN


def test_dollar_var_reference_in_var_prefix_is_clean():
    result = audit_rule("Bash(PGPASSWORD=$DB_PASS psql -h db -U app)")
    assert result["finding"] == FINDING_CLEAN


def test_placeholder_value_is_clean():
    result = audit_rule("Bash(PGPASSWORD=*** psql -h db -U app)")
    assert result["finding"] == FINDING_CLEAN


def test_redacted_marker_is_clean():
    result = audit_rule("Bash(curl https://user:<redacted>@api.example.com)")
    assert result["finding"] == FINDING_CLEAN


# --- over-broad rules ---

def test_unrestricted_shell():
    result = audit_rule("Bash(*)")
    assert result["finding"] == FINDING_UNRESTRICTED_SHELL
    assert result["severity"] == "medium"


def test_python_interpreter_wildcard():
    result = audit_rule("Bash(python:*)")
    assert result["finding"] == FINDING_INTERPRETER_WILDCARD


def test_node_interpreter_wildcard():
    result = audit_rule("Bash(node:*)")
    assert result["finding"] == FINDING_INTERPRETER_WILDCARD


def test_broad_prefix():
    result = audit_rule("Bash(npm *)")
    assert result["finding"] == FINDING_BROAD_PREFIX


def test_unrestricted_fetch():
    result = audit_rule("WebFetch(*)")
    assert result["finding"] == FINDING_UNRESTRICTED_FETCH


def test_exact_command_is_clean():
    result = audit_rule("Bash(npm test)")
    assert result["finding"] == FINDING_CLEAN


def test_scoped_webfetch_is_clean():
    result = audit_rule("WebFetch(domain:example.com)")
    assert result["finding"] == FINDING_CLEAN


def test_read_rule_is_clean():
    result = audit_rule("Read(~/.zshrc)")
    assert result["finding"] == FINDING_CLEAN


def test_secret_outranks_over_broad():
    result = audit_rule("Bash(PGPASSWORD=hunter2 python:*)")
    assert result["finding"] == FINDING_SECRET_IN_COMMAND


def test_non_string_rule_is_unscored_not_clean():
    result = audit_rule(None)
    assert result["finding"] == FINDING_UNSCORED


# --- file verdicts ---

def test_secret_file_blocks():
    result = audit_settings(_settings(
        allow=["Bash(PGPASSWORD=hunter2 psql -h db -U app)"]))
    assert result["verdict"] == VERDICT_BLOCK
    assert result["counts"]["secret_rules"] == 1
    assert result["counts"]["missed_by_general_scanners"] == 1


def test_known_format_secret_does_not_count_as_missed():
    result = audit_settings(_settings(
        allow=["Bash(gh auth login --with-token <<< "
               "ghp_abcdefghij1234567890abcd)"]))
    assert result["verdict"] == VERDICT_BLOCK
    assert result["counts"]["secret_rules"] == 1
    assert result["counts"]["missed_by_general_scanners"] == 0
    assert result["secret_kinds"] == {FINDING_KNOWN_FORMAT: 1}


def test_over_broad_only_is_review():
    result = audit_settings(_settings(allow=["Bash(python:*)"]))
    assert result["verdict"] == VERDICT_REVIEW
    assert result["counts"]["over_broad_rules"] == 1


def test_env_secret_blocks():
    result = audit_settings(_settings(
        env={"SUPABASE_SERVICE_ROLE_KEY": "sbp_0123456789abcdefghij"}))
    assert result["verdict"] == VERDICT_BLOCK
    assert result["counts"]["env_secrets"] == 1
    assert result["env_findings"][0]["finding"] == FINDING_SECRET_IN_ENV


def test_env_reference_is_clean():
    result = audit_settings(_settings(
        env={"OPENAI_API_KEY": "$OPENAI_API_KEY"}))
    assert result["verdict"] == VERDICT_PASS
    assert result["counts"]["env_secrets"] == 0


def test_env_password_under_credential_name_blocks():
    result = audit_settings(_settings(env={"PGPASSWORD": "hunter2"}))
    assert result["verdict"] == VERDICT_BLOCK
    assert result["counts"]["env_secrets"] == 1


def test_tracked_local_file_is_review():
    result = audit_settings(_settings(allow=["Bash(npm test)"]),
                            tracked=True)
    assert result["verdict"] == VERDICT_REVIEW
    assert result["hygiene_findings"][0]["finding"] == FINDING_TRACKED_LOCAL


def test_not_ignored_local_file_is_review():
    result = audit_settings(_settings(allow=["Bash(npm test)"]),
                            gitignore_covers=False)
    assert result["verdict"] == VERDICT_REVIEW
    assert result["hygiene_findings"][0]["finding"] == FINDING_NOT_IGNORED


def test_tracked_shared_file_is_not_a_hygiene_finding():
    result = audit_settings(_settings(allow=["Bash(npm test)"]),
                            tracked=True,
                            filename=".claude/settings.json")
    assert result["verdict"] == VERDICT_PASS
    assert result["hygiene_findings"] == []


def test_deny_does_not_clear_a_secret():
    settings = _settings(
        allow=["Bash(PGPASSWORD=hunter2 psql -h db -U app)"])
    settings["permissions"]["deny"] = [
        "Bash(PGPASSWORD=hunter2 psql -h db -U app)"]
    result = audit_settings(settings)
    assert result["verdict"] == VERDICT_BLOCK
    assert result["counts"]["secret_rules"] == 1


def test_empty_settings_pass():
    result = audit_settings({})
    assert result["verdict"] == VERDICT_PASS
    assert result["counts"]["total_rules"] == 0


def test_non_dict_settings_is_review_not_pass():
    result = audit_settings("not a dict")
    assert result["verdict"] == VERDICT_REVIEW


# --- repo campaign ---

def test_repo_verdict_is_worst_file_verdict():
    campaign = score_campaign([
        {"filename": ".claude/settings.local.json",
         "settings": _settings(allow=["Bash(npm test)"])},
        {"filename": ".claude/settings.local.json",
         "settings": _settings(
             allow=["Bash(PGPASSWORD=hunter2 psql -h db -U app)"])},
    ])
    assert campaign["verdict"] == VERDICT_BLOCK
    assert campaign["verdicts"] == {
        VERDICT_BLOCK: 1, VERDICT_REVIEW: 0, VERDICT_PASS: 1}
    assert campaign["totals"]["secret_rules"] == 1
    assert campaign["totals"]["total_rules"] == 2


def test_empty_repo_is_review():
    campaign = score_campaign([])
    assert campaign["verdict"] == VERDICT_REVIEW


def test_clean_repo_passes():
    campaign = score_campaign([
        {"filename": ".claude/settings.local.json",
         "settings": _settings(allow=["Bash(npm test)"])},
    ])
    assert campaign["verdict"] == VERDICT_PASS


def test_summary_names_verdict_and_counts():
    campaign = score_campaign([
        {"filename": ".claude/settings.local.json",
         "settings": _settings(
             allow=["Bash(PGPASSWORD=hunter2 psql -h db -U app)"])},
    ])
    summary = format_summary(campaign)
    assert "verdict BLOCK" in summary
    assert "1 secret rules" in summary
    assert "1 of the secret rules in the shape general scanners miss" \
        in summary
