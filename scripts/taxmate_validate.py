#!/usr/bin/env python3
"""TaxMate Australia validation command implementation (Python replacement)."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import atodata
import skillgen
import taxmate_calc
import taxmate_finance
import taxmate_refresh
import taxmate_skills
import taxmate_taxpack


EMPTY_CONTENT = skillgen.EmptyContentHashValue
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
RESERVED_SKILL_PREFIXES = ("claude", "anthropic")
CODEX_MCP_SERVER_REQUIRED_FRAGMENTS = [
    "taxmate_run",
    "render_individual_html",
    '["command", "cwd"]',
    '["output_path", "cwd"]',
    '["answers_path", "output_path", "cwd"]',
    "function resolveCallerCwd(",
    "function resolveUserPath(value, callerCwd)",
    "cwd: callerCwd",
    "caller_cwd: callerCwd",
    "TAXMATE_AUSTRALIA_ROOT: PLUGIN_ROOT",
    "path.resolve(callerCwd, userPath)",
    'return runTaxmate("validate", [], PLUGIN_ROOT)',
]
TAXMATE_LAUNCHER_CWD_REQUIRED_FRAGMENTS = [
    "caller_cwd = Path.cwd()",
    "CALLER_CWD_COMMANDS",
    "ROOT_CWD_COMMANDS",
    "command_cwd = caller_cwd if command in CALLER_CWD_COMMANDS else root",
    "cwd=str(caller_cwd)",
    '"TAXMATE_AUSTRALIA_ROOT": str(root)',
]


def run(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Validate TaxMate Australia repository checks")
    if argv is None:
        import sys

        argv = sys.argv[1:]
    parser.parse_args(argv)

    root = atodata.SkillRoot()
    report, ok = validate(root)
    atodata.WriteJSON(report)
    return 0 if ok else 1


def validate(root: str) -> Tuple[Dict[str, Any], bool]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    manifest, manifest_err = read_plugin_manifest(root)
    manifest_text = read_text(os.path.join(root, ".codex-plugin", "plugin.json"))
    add_plugin_manifest_checks(root, add, manifest, manifest_err, manifest_text)
    add_openagentskill_checks(root, add, manifest, readme_text=read_text(os.path.join(root, "README.md")))

    required_skills, manifest_skill_err = public_portable_skills(root)
    skill_text, missing_skills, bad_frontmatter = load_skill_docs(root, required_skills)
    readme_text = read_text(os.path.join(root, "README.md"))
    add_skill_and_documentation_checks(
        root,
        add,
        manifest_skill_err,
        required_skills,
        missing_skills,
        bad_frontmatter,
        readme_text,
    )

    disclaimer_text = read_text(os.path.join(root, "DISCLAIMER.md"))
    add_public_disclaimer_checks(add, readme_text + disclaimer_text + skill_text + manifest_text)

    try:
        registry = atodata.LoadRegistry(root)
        add("source_registry_exists", True, "")
    except Exception as exc:
        add("source_registry_exists", False, str(exc))
        return finish(root, checks, None, False)

    coverage: skillgen.SourceCoverage
    try:
        coverage = skillgen.LoadSourceCoverage(root)
        coverage_err = None
    except Exception as exc:
        coverage = skillgen.SourceCoverage(sources=[])
        coverage_err = exc

    add_source_coverage_checks(root, add, registry, coverage, coverage_err)
    if coverage_err is not None:
        return finish(root, checks, registry, False)

    add_topic_checks(root, add, registry)

    deterministic, deterministic_err = generation_is_deterministic(root)
    add("generation_is_deterministic", deterministic, str(deterministic_err))
    add("current_values_preserved_without_cache", current_values_preserved_without_cache(root), "")
    add("blank_registry_hash_downgrades_previous_coverage", blank_registry_hash_downgrades_previous_coverage(root), "")
    add("unverified_registry_hash_downgrades_previous_coverage", unverified_registry_hash_downgrades_previous_coverage(root), "")
    add("stale_cache_text_does_not_verify_source", stale_cache_text_does_not_verify_source(root), "")
    add("stale_current_values_detected", stale_current_values_detected(root), "")
    add("stale_generated_reference_detected", stale_generated_reference_detected(root), "")
    add("untracked_generated_reference_ignored", untracked_generated_reference_ignored(root), "")
    add_runtime_binary_checks(root, add, registry)

    return finish(root, checks, registry, True)


def add_plugin_manifest_checks(root: str, add, manifest: Dict[str, str], manifest_err: Optional[Exception], manifest_text: str) -> None:
    add("codex_plugin_manifest_exists", manifest_err is None, str(manifest_err) if manifest_err else "")
    plugin_safety = False
    plugin_mcp_ready = False
    claude_plugin_ready = False
    try:
        raw_manifest = json.loads(manifest_text)
        safety = raw_manifest.get("safety", {})
        if isinstance(safety, dict):
            boundary = str(safety.get("noLodgmentBoundary", ""))
            plugin_safety = (
                safety.get("humanReviewRequired") is True
                and safety.get("noLodgment") is True
                and safety.get("preserveReviewFlags") is True
                and "Never lodge" in boundary
                and "ATO" in boundary
            )
        plugin_mcp_ready = raw_manifest.get("mcpServers") == "./.mcp.json" and codex_plugin_mcp_files_ready(root)
        claude_plugin_ready = claude_plugin_files_ready(root, str(raw_manifest.get("version", "")))
    except Exception:
        plugin_safety = False
        plugin_mcp_ready = False
        claude_plugin_ready = False
    add(
        "public_manifest_polished",
        "TaxMate Australia Maintainers" in manifest_text and '"Local"' not in manifest_text and '"Private"' not in manifest_text and '"repository": "local"' not in manifest_text,
        "",
    )
    add(
        "codex_plugin_manifest_required_keys",
        manifest.get("name") == "taxmate-australia" and bool(manifest.get("version")) and manifest.get("skills") == "./skills/",
        "",
    )
    add(
        "plugin_icon_declared",
        '"composerIcon": "./assets/icon.png"' in manifest_text
        and '"logo": "./assets/icon.png"' in manifest_text
        and file_exists(os.path.join(root, "assets", "icon.png")),
        "",
    )
    website_url = manifest.get("interface.websiteURL", "")
    add("plugin_website_is_repository", website_url == manifest.get("repository"), website_url)
    add("plugin_safety_boundary_metadata", plugin_safety, "")
    add("codex_plugin_mcp_runtime_wired", plugin_mcp_ready, "")
    add("claude_plugin_runtime_wired", claude_plugin_ready, "")
    add("codex_plugin_no_root_monolith", not file_exists(os.path.join(root, "SKILL.md")), "")
    add(
        "open_plugin_backend_dirs",
        file_exists(os.path.join(root, "scripts"))
        and not os.path.exists(os.path.join(root, "cmd"))
        and not os.path.exists(os.path.join(root, "internal"))
        and file_exists(os.path.join(root, "data"))
        and file_exists(os.path.join(root, "skills")),
        "",
    )
    add(
        "publication_docs_exist",
        file_exists(os.path.join(root, "README.md"))
        and file_exists(os.path.join(root, "DISCLAIMER.md"))
        and file_exists(os.path.join(root, "docs", "PUBLICATION_CHECKLIST.md")),
        "",
    )


def add_openagentskill_checks(root: str, add, manifest: Dict[str, str], readme_text: str) -> None:
    payload, err = read_json_file(os.path.join(root, "skill.json"))
    add("openagentskill_manifest_exists", err is None, str(err) if err else "")
    if err is not None:
        return

    expected_install = "npx skills@1.5.13 add nijanthan-dev/taxmate-australia --agent codex --global --skill '*' --yes"
    tags = payload.get("tags")
    platforms = payload.get("platforms")
    install_targets = payload.get("install_targets")
    do_not_use_for = payload.get("do_not_use_for")
    safety = payload.get("safety")

    add(
        "openagentskill_identity_matches_plugin",
        payload.get("slug") == "taxmate-australia"
        and payload.get("repository") == manifest.get("repository")
        and payload.get("homepage") == manifest.get("homepage")
        and payload.get("license") == "Apache-2.0",
        "",
    )
    openagentskill_public_text = f"{payload.get('description', '')} {payload.get('tagline', '')}".lower()
    add(
        "openagentskill_runtime_documented",
        "bash" in openagentskill_public_text
        and "python" in openagentskill_public_text
        and "node.js" in openagentskill_public_text
        and "claude code" in openagentskill_public_text,
        "",
    )
    add(
        "openagentskill_submission_metadata_ready",
        payload.get("category") == "business"
        and isinstance(tags, list)
        and 0 < len(tags) <= 10
        and all(isinstance(tag, str) and tag.strip() for tag in tags),
        "",
    )
    add("openagentskill_discovery_tags_ready", discovery_tags_ready(tags), "")
    add(
        "openagentskill_install_ready",
        payload.get("install") == expected_install
        and isinstance(platforms, list)
        and "Codex" in platforms
        and "Claude Code" in platforms
        and "Cowork" in platforms
        and "OpenAgentSkill CLI" in platforms
        and isinstance(install_targets, list)
        and any(isinstance(target, dict) and target.get("value") == expected_install for target in install_targets),
        "",
    )
    add(
        "openagentskill_codex_plugin_install_documented",
        isinstance(install_targets, list)
        and any(
            isinstance(target, dict)
            and target.get("id") == "codex"
            and "codex plugin marketplace add nijanthan-dev/taxmate-australia" in str(target.get("value", ""))
            and "codex plugin add taxmate-australia@taxmate-local-marketplace" in str(target.get("value", ""))
            for target in install_targets
        )
        and "guidance only" in openagentskill_public_text,
        "",
    )
    add(
        "openagentskill_claude_plugin_install_documented",
        isinstance(install_targets, list)
        and any(
            isinstance(target, dict)
            and target.get("id") == "claude-code"
            and "claude plugin marketplace add nijanthan-dev/taxmate-australia" in str(target.get("value", ""))
            and "claude plugin install taxmate-australia@taxmate-australia" in str(target.get("value", ""))
            for target in install_targets
        )
        and claude_plugin_files_ready(root, str(manifest.get("version", ""))),
        "",
    )
    agent_compatibility = payload.get("agent_compatibility")
    add(
        "agent_compatibility_declares_claude_cowork_codex",
        isinstance(agent_compatibility, list)
        and "Codex" in agent_compatibility
        and "Claude Code" in agent_compatibility
        and "Cowork" in agent_compatibility,
        "",
    )
    add(
        "openagentskill_safety_boundaries",
        isinstance(do_not_use_for, list)
        and any("lodgment" in str(item).lower() or "submission" in str(item).lower() for item in do_not_use_for)
        and isinstance(safety, dict)
        and safety.get("human_review_required") is True,
        "",
    )
    add(
        "openagentskill_readme_examples_ready",
        "npx skills@1.5.13 add nijanthan-dev/taxmate-australia" in readme_text
        and "Use the taxmate-australia-capital-gains-tax skill" in readme_text
        and "Use the taxmate-australia-gst-bas skill" in readme_text
        and "OpenAgentSkill badge" not in readme_text
        and "openagentskill.com/badge" not in readme_text.lower(),
        "",
    )
    license_text = read_text(os.path.join(root, "LICENSE"))
    add(
        "apache_license_detectable",
        "Apache License" in license_text
        and "Version 2.0, January 2004" in license_text
        and "APPENDIX: How to apply the Apache License to your work." in license_text,
        "",
    )


def add_skill_and_documentation_checks(
    root: str,
    add,
    manifest_skill_err: Optional[Exception],
    required_skills: List[str],
    missing_skills: List[str],
    bad_frontmatter: List[str],
    readme_text: str,
) -> None:
    add("public_skill_manifest_loaded", manifest_skill_err is None, str(manifest_skill_err) if manifest_skill_err else "")
    add("codex_plugin_required_skills_exist", len(missing_skills) == 0, ", ".join(missing_skills))
    add("skill_frontmatter_valid", len(bad_frontmatter) == 0, ", ".join(bad_frontmatter))
    claude_issues = claude_skill_frontmatter_issues(root)
    add("claude_skill_frontmatter_compatible", len(claude_issues) == 0, "; ".join(first_n(claude_issues, 8)))
    missing_skill_docs = skill_dirs_without_skill_md(root)
    add("skill_dirs_have_skill_md", len(missing_skill_docs) == 0, "; ".join(missing_skill_docs))
    readme_issues = skill_folder_readmes(root)
    add("skill_folders_do_not_contain_readme", len(readme_issues) == 0, "; ".join(readme_issues))
    add("description_nonempty", all_skill_descriptions_long(root, required_skills), "")
    add(
        "guidance_only_skills_documented",
        "npx skills" in readme_text and "guidance only" in readme_text and "No renderer or runtime scripts" in readme_text,
        "",
    )
    full_runtime_text = read_text(os.path.join(root, "docs", "FULL_PLUGIN_INSTALL.md")) + read_text(
        os.path.join(root, "docs", "SKILL_GENERATION.md")
    )
    add(
        "python_runtime_documented",
        "python runtime under the hood" in full_runtime_text
        and "./scripts/taxmate" in full_runtime_text
        and "./scripts/taxmate refresh --help" in full_runtime_text,
        "",
    )
    install_text = read_text(os.path.join(root, "docs", "INSTALLATION.md"))
    full_install_text = read_text(os.path.join(root, "docs", "FULL_PLUGIN_INSTALL.md"))
    prep_text = read_text(os.path.join(root, "docs", "INDIVIDUAL_RETURN_PREP.md"))
    add(
        "plugin_mcp_node_prerequisite_documented",
        all(
            "Node.js 20+ for the MCP launcher" in text
            for text in [readme_text, install_text, full_install_text, prep_text]
        ),
        "",
    )

    public_docs = public_doc_files(root)
    add(
        "public_docs_no_private_paths",
        no_private_paths(root, public_docs),
        "; ".join(first_n(private_path_hits(root, public_docs), 5)),
    )
    legacy_identity_docs = list(public_docs)
    legacy_identity_docs += find_by_suffix(os.path.join(root, ".github"), ".md")
    legacy_identity_docs += find_by_suffix(os.path.join(root, ".github"), ".yml")
    legacy_identity_docs += find_by_suffix(os.path.join(root, ".github"), ".yaml")
    add("public_docs_no_legacy_identity", no_legacy_public_identity(legacy_identity_docs), "")

    add("wrappers_mark_local_fallback", wrappers_mark_local_fallback(root), "")
    add("wrapper_frontmatter_names", wrapper_frontmatter_names_match_path(root), "")
    add("wrapper_invocations_use_australia_prefix", wrapper_invocations_use_australia_prefix(root), "")
    add("public_skill_names_use_taxmate_prefix", public_skill_names_use_taxmate_prefix(root), "")
    add("plugin_lock_skill_paths_exist", plugin_lock_skill_paths_exist(root), "")
    add("wrapper_fallback_skill_paths_exist", wrapper_fallback_skill_paths_exist(root), "")
    add("individual_return_prep_docs_ready", individual_return_prep_docs_ready(root, readme_text), "")
    add("discovery_metadata_documented", discovery_metadata_ready(root, readme_text), "")
    review_guardrail_gaps = review_feedback_guardrail_gaps(root)
    add("review_feedback_guardrails_documented", len(review_guardrail_gaps) == 0, "; ".join(review_guardrail_gaps))


def add_public_disclaimer_checks(add, text: str) -> None:
    add("public_disclaimer_documented", has_public_disclaimers(text), "")


def add_source_coverage_checks(
    root: str,
    add,
    registry,
    coverage: skillgen.SourceCoverage,
    coverage_err: Optional[Exception],
) -> None:
    add("source_coverage_exists", coverage_err is None, "")
    if coverage_err is not None:
        return

    data_dir = atodata.DataDir(root)
    add("source_coverage_matches_registry", len(coverage.sources) == len(registry.records), "")

    status_err = skillgen.ValidateSourceCoverage(root)
    add("source_coverage_statuses_valid", status_err is None, "" if status_err is None else str(status_err))

    add("verified_sources_have_content_hash", all_verified_sources_have_hash(coverage), "")
    add("metadata_only_sources_not_claimed_as_verified", not metadata_only_marked_as_verified(root, coverage), "")
    add("source_records_match_per_skill", source_coverage_matches_skill_files(root, coverage), "")
    add("bank_account_investment_source_routed", bank_account_investment_source_routed(coverage), "")
    add("home_business_sources_routed", home_business_sources_routed(coverage), "")
    add("source_record_count", len(registry.records) >= 290, str(len(registry.records)))
    add("source_scope_present", bool(registry.scope), "")
    add("scope_summary_exists", file_exists(os.path.join(data_dir, "SCOPE_SUMMARY.md")), "")
    add("readme_exists", file_exists(os.path.join(data_dir, "README.md")), "")
    add("source_coverage_file_present", file_exists(os.path.join(data_dir, "source_coverage.json")), "")
    add("source_registry_file_present", file_exists(os.path.join(data_dir, "source_registry.json")), "")
    add(
        "source_registry_missing_old_files",
        not file_exists(os.path.join(data_dir, "source_index.json"))
        and not file_exists(os.path.join(data_dir, "source_manifest.json"))
        and not file_exists(os.path.join(data_dir, "migration_report.json")),
        "",
    )
    add("migration_dir_missing", not file_exists(os.path.join(root, "migration")), "")
    add("raw_snapshots_not_committed", not file_exists(os.path.join(data_dir, "raw")) and not file_exists(os.path.join(data_dir, "text")), "")

    all_200 = all(item.status == 200 for item in registry.records)
    add("all_records_http_200", all_200, "")


def add_topic_checks(root: str, add, registry) -> None:
    hay = haystack(root, registry)
    missing_topics: List[str] = []
    for topic, needles in topic_queries().items():
        if not contains_any(hay, needles):
            missing_topics.append(topic)
    add("key_tax_topics_covered", len(missing_topics) == 0, ", ".join(missing_topics))

    unresolved: List[str] = []
    for failure in registry.failures:
        matched = False
        for stale, replacements in stale_seed_replacements().items():
            if stale in failure.url:
                if contains_any(hay, replacements):
                    matched = True
                break
        if not matched:
            unresolved.append(failure.url)
    add("stale_seed_failures_have_replacements", len(unresolved) == 0, "; ".join(first_n(unresolved, 5)))


def add_runtime_binary_checks(root: str, add, registry) -> None:
    add("audit_is_read_only", audit_is_read_only(root), "")
    add("audit_json_stdout_single_document", audit_json_stdout_single_document(root), "")
    add("audit_duplicates_not_unassigned", audit_duplicates_not_unassigned(root), "")
    add("audit_cgt_counts_metadata_assignments", audit_cgt_counts_metadata_assignments(root), "")
    add("audit_check_fails_missing_required_assignments", audit_check_fails_missing_required_assignments(root), "")
    add("audit_check_fails_missing_required_verified_sources", audit_check_fails_missing_required_verified_sources(root), "")
    add("skills_generate_check_catches_validation_error", skills_generate_check_catches_validation_error(root), "")
    add("source_coverage_status_check_consumes_return_error", source_coverage_status_check_consumes_return_error(root), "")
    add("plugin_manifest_errors_are_reported", plugin_manifest_errors_are_reported(), "")
    add("public_skills_errors_are_reported", public_skills_errors_are_reported(), "")
    add("save_registry_stamps_refreshed_at", save_registry_stamps_refreshed_at(), "")
    add("fetch_http_error_preserves_status", fetch_http_error_preserves_status(), "")
    add("finance_csv_trims_leading_space", finance_csv_trims_leading_space(), "")
    add("calc_rejects_non_finite_numbers", calc_rejects_non_finite_numbers(), "")
    add("finance_csv_rejects_non_finite_numbers", finance_csv_rejects_non_finite_numbers(), "")
    add("refresh_errors_use_python_formatting", refresh_errors_use_python_formatting(root), "")
    add("wrapper_help_uses_public_commands", wrapper_help_uses_public_commands(root), "")
    add("codex_environment_toml_valid", codex_environment_toml_valid(root), "")
    add("release_workflow_auto_after_ci", release_workflow_auto_after_ci(root), "")
    add("local_act_ci_ready", local_act_ci_ready(root), "")
    add("release_config_tracks_manifest_versions", release_config_tracks_manifest_versions(root), "")
    private_hits = tracked_private_path_hits(root)
    add("tracked_text_no_private_paths", len(private_hits) == 0, "; ".join(first_n(private_hits, 5)))
    add("gitleaks_no_broad_cache_allowlist", gitleaks_no_broad_cache_allowlist(root), "")
    bash5_hits = stale_bash5_prereq_hits(root)
    add("docs_no_stale_bash5_requirement", len(bash5_hits) == 0, "; ".join(bash5_hits))
    add("refresh_query_no_match_is_read_only", refresh_query_no_match_is_read_only(root), "")
    add("skills_refresh_unknown_topic_is_noop", skills_refresh_unknown_topic_is_noop(root), "")
    add("skills_refresh_missing_urls_is_read_only", skills_refresh_missing_urls_is_read_only(root), "")
    add("finance_record_rows_classify_before_income", finance_record_rows_classify_before_income(), "")
    add("finance_investment_income_classifies_as_income", finance_investment_income_classifies_as_income(), "")
    add("finance_investment_income_outranks_business_tag", finance_investment_income_outranks_business_tag(), "")
    add("taxpack_guide_html_contract", taxpack_guide_html_contract(), "")
    add("validate_json_uses_check_field", validate_json_uses_check_field(), "")
    add("recrawl_link_host_filter_strict", recrawl_link_host_filter_strict(), "")
    add("super_seed_matches_registry", super_seed_matches_registry(registry), "")
    add("generated_skills_validate", is_valid_exception_safe(lambda: skillgen.Validate(root)) is None, "")
    python_backend = (
        file_exists(os.path.join(root, "scripts", "taxmate_skills.py"))
        and file_exists(os.path.join(root, "scripts", "taxmate_validate.py"))
    )
    add("python_backend_exists", python_backend, "")
    add("no_go_source", len(find_by_suffix(root, ".go")) == 0, "")
    go_tooling_hits = stale_go_tooling_hits(root)
    add("no_go_tooling_config", len(go_tooling_hits) == 0, "; ".join(go_tooling_hits))
    go_runtime_claim_hits = stale_go_runtime_claim_hits(root)
    add("public_metadata_no_go_runtime_claims", len(go_runtime_claim_hits) == 0, "; ".join(go_runtime_claim_hits))
    stale_cache_claim_hits = stale_committed_source_cache_claim_hits(root)
    add("public_docs_no_committed_source_cache_claims", len(stale_cache_claim_hits) == 0, "; ".join(stale_cache_claim_hits))
    ato_claim_hits = ato_endorsement_claim_hits(root)
    add("public_docs_no_ato_backing_claims", len(ato_claim_hits) == 0, "; ".join(ato_claim_hits))


def is_valid_exception_safe(fn) -> Optional[Exception]:
    try:
        fn()
        return None
    except Exception as exc:
        return exc


def finish(root: str, checks: List[Dict[str, Any]], registry, include_index: bool) -> Tuple[Dict[str, Any], bool]:
    passed = 0
    for item in checks:
        if item["passed"]:
            passed += 1
    score = float(passed) / float(len(checks)) * 100 if checks else 0.0
    report: Dict[str, Any] = {
        "plugin": os.path.basename(root),
        "score": score,
        "passed": passed,
        "total": len(checks),
        "checks": checks,
    }
    if include_index and registry is not None:
        report["records"] = len(registry.records)
        report["source_failures"] = len(registry.failures)
    return report, passed == len(checks)


def public_portable_skills(root: str) -> Tuple[List[str], Optional[Exception]]:
    path = os.path.join(root, "config", "public-skills.json")
    try:
        body = Path(path).read_bytes()
        raw = json.loads(body)
    except Exception as exc:
        return [], exc
    skills = list(raw.get("portableSkills", []))
    if not skills:
        return [], ValueError("portableSkills empty")
    return skills, None


def public_skill_paths_by_name(root: str) -> Dict[str, str]:
    try:
        payload = json.loads(Path(os.path.join(root, "config", "public-skills.json")).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    raw_paths = payload.get("portableSkillPaths")
    if not isinstance(raw_paths, dict):
        return {}
    return {name: rel for name, rel in raw_paths.items() if isinstance(name, str) and isinstance(rel, str)}


def read_plugin_manifest(root: str) -> Tuple[Dict[str, str], Optional[Exception]]:
    try:
        body = Path(os.path.join(root, ".codex-plugin", "plugin.json")).read_text(encoding="utf-8")
        raw = json.loads(body)
    except Exception as exc:
        return {}, exc
    out: Dict[str, str] = {}
    for key in ("name", "version", "skills", "repository", "homepage"):
        value = raw.get(key)
        if isinstance(value, str):
            out[key] = value
    interface = raw.get("interface")
    if isinstance(interface, dict) and isinstance(interface.get("websiteURL"), str):
        out["interface.websiteURL"] = interface["websiteURL"]
    return out, None


def load_skill_docs(root: str, skills: List[str]) -> Tuple[str, List[str], List[str]]:
    text_parts: List[str] = []
    missing: List[str] = []
    bad: List[str] = []
    skill_paths = public_skill_paths_by_name(root)
    for skill in skills:
        rel = skill_paths.get(skill, os.path.join("skills", skill))
        path = os.path.join(root, rel, "SKILL.md")
        try:
            body = Path(path).read_text(encoding="utf-8")
        except OSError:
            missing.append(skill)
            continue
        fm = parse_frontmatter(body)
        if fm is None or fm.get("name") != skill or fm.get("description", "") == "":
            bad.append(skill)
        text_parts.append(body)
    return "\n".join(text_parts), missing, bad


def read_json_file(path: str) -> Tuple[Dict[str, Any], Optional[Exception]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as exc:
        return {}, exc
    if not isinstance(payload, dict):
        return {}, ValueError(f"expected object JSON: {path}")
    return payload, None


def all_skill_descriptions_long(root: str, skills: List[str]) -> bool:
    skill_paths = public_skill_paths_by_name(root)
    for skill in skills:
        rel = skill_paths.get(skill, os.path.join("skills", skill))
        path = os.path.join(root, rel, "SKILL.md")
        try:
            body = Path(path).read_text(encoding="utf-8")
        except OSError:
            return False
        fm = parse_frontmatter(body)
        if fm is None or len(fm.get("description", "")) < 40:
            return False
    return True


def discovery_tags_ready(tags: Any) -> bool:
    if not isinstance(tags, list):
        return False
    tag_set = {str(tag) for tag in tags}
    required = {"australian-tax", "tax-prep", "ato", "gst", "bas", "cgt", "payg", "superannuation", "accountant", "agent-skills"}
    stale = {"australia", "tax", "super"}
    return required.issubset(tag_set) and not stale.intersection(tag_set)


def discovery_metadata_ready(root: str, readme_text: str) -> bool:
    discovery = read_text(os.path.join(root, "docs", "DISCOVERY.md"))
    plugin = read_text(os.path.join(root, ".codex-plugin", "plugin.json"))
    agent = read_text(os.path.join(root, "agents", "openai.yaml"))
    required_readme_terms = [
        "linked to official ATO sources",
        "individual tax return",
        "GST/BAS",
        "CGT",
        "accountant handoff",
        "Codex",
        "Claude Code",
        "Cowork",
    ]
    required_discovery_terms = [
        "GitHub About",
        "claude-code",
        "cowork",
        "openagentskill",
        "individual tax return prep",
        "Leave blank until there is a dedicated external landing page.",
    ]
    return (
        all(term in readme_text for term in required_readme_terms)
        and all(term in discovery for term in required_discovery_terms)
        and "Australian tax prep with ATO source links" in plugin
        and "Australian tax prep with ATO source links" in agent
        and ("ATO-" + "backed") not in readme_text
        and ("ATO-" + "backed") not in discovery
        and ("ATO-" + "backed") not in plugin
        and ("ATO-" + "backed") not in agent
        and "turn Australian tax records into" not in readme_text
        and "messy tax records" not in plugin
        and "tax records" not in discovery
        and '"assistant"' not in plugin
        and '"super"' not in plugin
    )


def codex_plugin_mcp_files_ready(root: str) -> bool:
    if os.path.exists(os.path.join(root, ".codex-plugin", "mcp.json")):
        return False
    payload, err = read_json_file(os.path.join(root, ".mcp.json"))
    if err is not None:
        return False
    servers = payload.get("mcpServers")
    if not isinstance(servers, dict):
        return False
    taxmate = servers.get("taxmateAustralia")
    if not isinstance(taxmate, dict):
        return False
    server_text = read_text(os.path.join(root, "mcp", "server.cjs"))
    return (
        taxmate.get("command") == "node"
        and taxmate.get("args") == ["./mcp/server.cjs", "--stdio"]
        and taxmate.get("cwd") == "."
        and file_exists(os.path.join(root, "mcp", "server.cjs"))
        and all(fragment in server_text for fragment in CODEX_MCP_SERVER_REQUIRED_FRAGMENTS)
        and taxmate_launcher_preserves_caller_cwd(root)
    )


def taxmate_launcher_preserves_caller_cwd(root: str) -> bool:
    launcher = read_text(os.path.join(root, "scripts", "taxmate.py"))
    return all(fragment in launcher for fragment in TAXMATE_LAUNCHER_CWD_REQUIRED_FRAGMENTS)


def claude_plugin_files_ready(root: str, plugin_version: str) -> bool:
    plugin, plugin_err = read_json_file(os.path.join(root, ".claude-plugin", "plugin.json"))
    marketplace, marketplace_err = read_json_file(os.path.join(root, ".claude-plugin", "marketplace.json"))
    if plugin_err is not None or marketplace_err is not None:
        return False

    servers = plugin.get("mcpServers")
    taxmate = servers.get("taxmateAustralia") if isinstance(servers, dict) else None
    taxmate_env = taxmate.get("env") if isinstance(taxmate, dict) else None
    marketplace_plugins = marketplace.get("plugins")
    marketplace_entry = plugin_entry(marketplace_plugins, "taxmate-australia")
    author = plugin.get("author")
    owner = marketplace.get("owner")

    plugin_ready = (
        plugin.get("name") == "taxmate-australia"
        and plugin.get("version") == plugin_version
        and plugin.get("skills") == "./skills"
        and isinstance(author, dict)
        and author.get("name") == "TaxMate Australia Maintainers"
    )
    mcp_ready = (
        isinstance(taxmate, dict)
        and taxmate.get("command") == "node"
        and taxmate.get("args") == ["${CLAUDE_PLUGIN_ROOT}/mcp/server.cjs", "--stdio"]
        and isinstance(taxmate_env, dict)
        and taxmate_env.get("TAXMATE_AUSTRALIA_ROOT") == "${CLAUDE_PLUGIN_ROOT}"
        and taxmate_env.get("PYTHONDONTWRITEBYTECODE") == "1"
        and file_exists(os.path.join(root, "mcp", "server.cjs"))
    )
    marketplace_ready = (
        marketplace.get("name") == "taxmate-australia"
        and isinstance(owner, dict)
        and owner.get("name") == "TaxMate Australia Maintainers"
        and isinstance(marketplace_entry, dict)
        and marketplace_entry.get("source") == "./"
    )
    return plugin_ready and mcp_ready and marketplace_ready


def plugin_entry(entries: Any, name: str) -> Optional[Dict[str, Any]]:
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return None


def individual_return_prep_docs_ready(root: str, readme_text: str) -> bool:
    doc = read_text(os.path.join(root, "docs", "INDIVIDUAL_RETURN_PREP.md"))
    full_install = read_text(os.path.join(root, "docs", "FULL_PLUGIN_INSTALL.md"))
    required_readme_terms = [
        "Individual Return Prep",
        "docs/INDIVIDUAL_RETURN_PREP.md",
        "prep-only boundaries",
    ]
    required_doc_terms = [
        "TaxMate is prep-only",
        "individual-return",
        "Plugin Runtime Path",
        "codex plugin marketplace add nijanthan-dev/taxmate-australia",
        "claude plugin marketplace add nijanthan-dev/taxmate-australia",
        "Node.js 20+ for the MCP launcher",
        "./scripts/taxmate intake individual --help",
        "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json",
        "./scripts/taxmate intake individual",
        "--answers /tmp/taxmate-answers.json",
        "No-answer plus facts stays Evidence",
        "`Accountant review`",
        "myTax, paper ATO form, or accountant handoff",
    ]
    stale_prep_commands = [
        "./scripts/taxmate taxpack sample-json --output /tmp/taxmate-guide-input.json",
        "--input /tmp/taxmate-guide-input.json",
    ]
    return (
        all(term in readme_text for term in required_readme_terms)
        and all(term in doc for term in required_doc_terms)
        and "./scripts/taxmate intake sample-json --output /tmp/taxmate-answers.json" in full_install
        and "--answers /tmp/taxmate-answers.json" in full_install
        and not any(term in readme_text or term in doc or term in full_install for term in stale_prep_commands)
    )


def claude_skill_frontmatter_issues(root: str) -> List[str]:
    issues: List[str] = []
    public_names_by_path = public_skill_names_by_source_path(root)
    for path in skill_doc_paths(root):
        rel = relative_path(root, path)
        text = read_text(path)
        fm = parse_frontmatter(text)
        fm_text = frontmatter_text(text)
        folder_name = Path(path).parent.name
        expected_name = public_names_by_path.get(relative_path(root, str(Path(path).parent)), folder_name)
        name = (fm or {}).get("name", "")
        description = (fm or {}).get("description", "")
        compatibility = (fm or {}).get("compatibility", "")

        if fm is None:
            issues.append(f"{rel}: invalid frontmatter")
            continue
        if name != expected_name:
            if expected_name == folder_name:
                issues.append(f"{rel}: name must match folder")
            else:
                issues.append(f"{rel}: name must match public skill name {expected_name}")
        if not SKILL_NAME_RE.fullmatch(name):
            issues.append(f"{rel}: name must be kebab-case")
        if name.startswith(RESERVED_SKILL_PREFIXES):
            issues.append(f"{rel}: reserved skill name prefix")
        if len(description) > 1024:
            issues.append(f"{rel}: description too long")
        if not skill_description_has_trigger(description):
            issues.append(f"{rel}: description must start with Use when")
        if not compatibility or len(compatibility) > 500:
            issues.append(f"{rel}: compatibility missing or too long")
        if "<" in fm_text or ">" in fm_text:
            issues.append(f"{rel}: frontmatter contains XML angle bracket")
        if "## Quick Reference" not in text:
            issues.append(f"{rel}: missing quick reference section")
        if "## Common Mistakes" not in text:
            issues.append(f"{rel}: missing common mistakes section")
    return issues


def public_skill_names_by_source_path(root: str) -> Dict[str, str]:
    return {rel: name for name, rel in public_skill_paths_by_name(root).items()}


def public_skill_names_use_taxmate_prefix(root: str) -> bool:
    try:
        public_manifest = json.loads(Path(os.path.join(root, "config", "public-skills.json")).read_text(encoding="utf-8"))
        packaging = json.loads(Path(os.path.join(root, "config", "skill-packaging.json")).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    public_names = public_manifest.get("portableSkills")
    package_names = packaging.get("publicPortable")
    public_paths = public_manifest.get("portableSkillPaths")
    package_paths = packaging.get("publicPortablePaths")
    if not isinstance(public_names, list) or not isinstance(package_names, list):
        return False
    if public_names != package_names:
        return False
    if not isinstance(public_paths, dict) or public_paths != package_paths:
        return False
    for name in public_names:
        if not isinstance(name, str) or not name.startswith("taxmate-australia"):
            return False
        rel = public_paths.get(name)
        if not isinstance(rel, str):
            return False
        fm = parse_frontmatter(read_text(os.path.join(root, rel, "SKILL.md")))
        if fm is None or fm.get("name") != name:
            return False
    return True


def skill_doc_paths(root: str) -> List[str]:
    paths: List[str] = []
    for base in ("skills", os.path.join("runtime", "skills"), "wrappers"):
        base_path = Path(root, base)
        if not base_path.exists():
            continue
        for skill_path in base_path.glob("*/SKILL.md"):
            paths.append(str(skill_path))
    return sorted(paths)


def skill_description_has_trigger(description: str) -> bool:
    return description.startswith("Use when ")


def frontmatter_text(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    if end < 0:
        return ""
    return text[4:end]


def skill_dirs_without_skill_md(root: str) -> List[str]:
    missing: List[str] = []
    for base in ("skills", os.path.join("runtime", "skills"), "wrappers"):
        base_path = Path(root, base)
        if not base_path.exists():
            continue
        for item in sorted(base_path.iterdir()):
            if item.is_dir() and not (item / "SKILL.md").exists():
                missing.append(relative_path(root, str(item)))
    return missing


def skill_folder_readmes(root: str) -> List[str]:
    readmes: List[str] = []
    for path in skill_doc_paths(root):
        skill_dir = Path(path).parent
        for readme in skill_dir.rglob("README.md"):
            readmes.append(relative_path(root, str(readme)))
    return sorted(readmes)


def read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def public_doc_files(root: str) -> List[str]:
    files = [
        os.path.join(root, "README.md"),
        os.path.join(root, "DISCLAIMER.md"),
        os.path.join(root, "skill.json"),
        os.path.join(root, ".codex-plugin", "plugin.json"),
        os.path.join(root, ".agents", "plugins", "marketplace.json"),
        os.path.join(root, "agents", "openai.yaml"),
        os.path.join(root, "plugin.lock.json"),
        os.path.join(root, ".gitleaks.toml"),
        os.path.join(root, "SECURITY.md"),
        os.path.join(root, "CONTRIBUTING.md"),
        os.path.join(root, "docs", "PLUGIN_SCANNER.md"),
        os.path.join(root, "docs", "PUBLICATION_CHECKLIST.md"),
        os.path.join(root, "docs", "DISCOVERY.md"),
        os.path.join(root, "docs", "INSTALLATION.md"),
        os.path.join(root, "docs", "FULL_PLUGIN_INSTALL.md"),
        os.path.join(root, "docs", "DEVELOPMENT.md"),
        os.path.join(root, "docs", "SKILL_GENERATION.md"),
    ]
    for base in (os.path.join(root, "skills"), os.path.join(root, "wrappers")):
        for path in find_by_suffix(base, ""):
            files.append(path)
    return files


def no_private_paths(root: str, paths: List[str]) -> bool:
    return len(private_path_hits(root, paths)) == 0


def no_legacy_public_identity(paths: List[str]) -> bool:
    for path in paths:
        text = read_text(path)
        if "TaxMate AU" in text or "TAXMATE_AU_ROOT" in text or "taxmate-au:" in text:
            return False
        if "taxmate-au" in text.replace("taxmate-australia", ""):
            return False
    return True


def private_path_hits(root: str, paths: List[str]) -> List[str]:
    hits: List[str] = []
    needles = ["/Users/", "custom_apps/skills_and_plugins", "Developer/custom_apps"]
    for path in paths:
        for line in read_text(path).splitlines():
            if private_path_scan_ignore_line(line):
                continue
            for needle in needles:
                if needle in line:
                    hits.append(f"{relative_path(root, path)}:{needle}")
                    break
    return hits


def private_path_scan_ignore_line(line: str) -> bool:
    return (
        "/Users/[[:alnum:]_.-]+" in line
        or "needles = [" in line
        or (
            "custom_apps/skills_and_plugins" in line
            and "Developer/custom_apps" in line
            and "/Users/" in line
        )
    )


def wrappers_mark_local_fallback(root: str) -> bool:
    wrappers = find_by_suffix(os.path.join(root, "wrappers"), "SKILL.md")
    if len(wrappers) < 1:
        return False
    for path in wrappers:
        text = read_text(path)
        if "TAXMATE_AUSTRALIA_ROOT" not in text or "when available" not in text:
            return False
    return True


def wrapper_frontmatter_names_match_path(root: str) -> bool:
    wrappers = find_by_suffix(os.path.join(root, "wrappers"), "SKILL.md")
    if len(wrappers) == 0:
        return False
    for path in wrappers:
        wrapper_name = Path(path).parent.name
        if not wrapper_name.startswith("taxmate-australia"):
            return False
        fm = parse_frontmatter(read_text(path))
        if fm is None or fm.get("name") != wrapper_name:
            return False
    return True


def wrapper_invocations_use_australia_prefix(root: str) -> bool:
    for path in find_by_suffix(os.path.join(root, "wrappers"), "SKILL.md"):
        text = read_text(path)
        if "$taxmate-au:" in text or "$taxmate-australia:" not in text:
            return False
    return True


def plugin_lock_skill_paths_exist(root: str) -> bool:
    try:
        payload = json.loads(Path(os.path.join(root, "plugin.lock.json")).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    skills = payload.get("skills")
    if not isinstance(skills, list) or not skills:
        return False
    public_name_by_path = public_skill_names_by_source_path(root)
    for skill in skills:
        if not isinstance(skill, dict):
            return False
        source = skill.get("source")
        if not isinstance(source, dict):
            return False
        paths = [skill.get("vendoredPath"), source.get("path")]
        for rel in paths:
            if not isinstance(rel, str) or not file_exists(os.path.join(root, rel, "SKILL.md")):
                return False
        vendored_path = skill.get("vendoredPath")
        integrity = skill.get("integrity")
        skill_id = skill.get("id")
        if not isinstance(vendored_path, str) or not isinstance(integrity, str) or not isinstance(skill_id, str):
            return False
        expected_public_id = public_name_by_path.get(vendored_path)
        if expected_public_id is not None and skill_id != expected_public_id:
            return False
        body = Path(os.path.join(root, vendored_path, "SKILL.md")).read_bytes()
        if integrity != "sha256:" + hashlib.sha256(body).hexdigest():
            return False
    expected = expected_plugin_lock_paths(root)
    actual = sorted(skill.get("vendoredPath") for skill in skills if isinstance(skill.get("vendoredPath"), str))
    if expected != actual:
        return False
    return True


def expected_plugin_lock_paths(root: str) -> List[str]:
    try:
        public_manifest = json.loads(Path(os.path.join(root, "config", "public-skills.json")).read_text(encoding="utf-8"))
        packaging = json.loads(Path(os.path.join(root, "config", "skill-packaging.json")).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    public_path_map = public_manifest.get("portableSkillPaths", {})
    public_paths = [
        item
        for item in public_path_map.values()
        if isinstance(item, str) and item.startswith("skills/")
    ]
    runtime_paths = [
        item
        for item in packaging.get("runtimeOnlyPaths", [])
        if isinstance(item, str) and item.startswith("runtime/skills/")
    ]
    return sorted(public_paths + runtime_paths)


def wrapper_fallback_skill_paths_exist(root: str) -> bool:
    wrappers = find_by_suffix(os.path.join(root, "wrappers"), "SKILL.md")
    if len(wrappers) == 0:
        return False
    for path in wrappers:
        found = False
        for line in read_text(path).splitlines():
            marker = "$TAXMATE_AUSTRALIA_ROOT/"
            if marker not in line or not line.strip().endswith('/SKILL.md"'):
                continue
            rel = line.split(marker, 1)[1].split('"', 1)[0]
            if not file_exists(os.path.join(root, rel)):
                return False
            found = True
        if not found:
            return False
    return True


def has_public_disclaimers(text: str) -> bool:
    needles = [
        "not tax, legal, accounting, financial",
        "not affiliated with",
        "endorsed",
        "australian taxation office",
        "registered-tax-agent advice",
        "does not lodge",
        "accountant review",
    ]
    lower = text.lower()
    return all(item in lower for item in needles)


def review_feedback_guardrail_gaps(root: str) -> List[str]:
    required = {
        "AGENTS.md": [
            "spawn or reuse a focused explorer",
            "source URL lists",
            "checked-at provenance",
            "docs/skills/AGENTS guardrails",
        ],
        "docs/DEVELOPMENT.md": [
            "Use a focused explorer/subagent",
            "file-backed data",
            "falsey output bugs",
        ],
        ".github/pull_request_template.md": [
            "same-class scan completed before requesting review",
            "docs/skills/AGENTS guardrails updated",
        ],
        "skills/taxmate-australia/SKILL.md": [
            "docs/skills/AGENTS guardrails",
            "top-level metadata",
            "source URL lists",
            "checked-at provenance",
        ],
        "skills/taxmate-australia/references/rules.md": [
            "file-backed data",
            "docs/skills/AGENTS guardrails",
        ],
        "skills/taxpack/SKILL.md": [
            "file-backed guide data",
            "Falsey-value regressions",
            "source URL lists",
            "checked-at provenance",
        ],
        "skills/taxpack/references/rules.md": [
            "file-backed guide data",
            "Falsey-value regressions",
            "source URL lists",
            "checked-at provenance",
        ],
        "skills/taxpack/references/topic-inputs.md": [
            "file-backed data",
            "docs/skills/AGENTS guardrails",
            "list fields",
            "direct constructors",
        ],
        "skills/workbook/SKILL.md": [
            "file-backed data",
            "raw string conversion",
        ],
        "skills/workbook/references/rules.md": [
            "file-backed data",
            "raw string conversion",
        ],
        "skills/workbook/references/topic-inputs.md": [
            "file-backed data",
            "docs/skills/AGENTS guardrails",
            "list fields",
            "direct constructors",
        ],
    }
    gaps: List[str] = []
    for rel_path, needles in required.items():
        body = read_text(os.path.join(root, rel_path))
        for needle in needles:
            if needle not in body:
                gaps.append(f"{rel_path}:{needle}")
    return gaps


def parse_frontmatter(text: str) -> Optional[Dict[str, str]]:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end < 0:
        return None
    body = text[4:end]
    out: Dict[str, str] = {}
    for line in body.split("\n"):
        if not line.strip() or line.startswith(" ") or line.startswith("\t"):
            continue
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        out[key.strip()] = value.strip().strip('"')
    return out


def file_exists(path: str) -> bool:
    return os.path.exists(path)


def all_verified_sources_have_hash(coverage: skillgen.SourceCoverage) -> bool:
    for entry in coverage.sources:
        if entry.status == skillgen.StatusVerified:
            hash_value = (entry.content_hash or "").strip()
            if not hash_value or hash_value.lower() == EMPTY_CONTENT.lower():
                return False
    return True


def metadata_only_marked_as_verified(root: str, coverage: skillgen.SourceCoverage) -> bool:
    metadata_only: Set[str] = set()
    for entry in coverage.sources:
        if entry.status == skillgen.StatusMetadataOnly:
            metadata_only.add(entry.source_id)
    if not metadata_only:
        return False

    for topic in skillgen.Topics():
        path = os.path.join(root, "skills", topic.slug, "references", "rules.md")
        try:
            body = Path(path).read_text(encoding="utf-8")
        except OSError:
            return True
        in_verified = False
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if line.startswith("## "):
                in_verified = line == "## Verified official-source content"
                continue
            if not in_verified:
                continue
            if "Source ID:" in line:
                idx = line.find("Source ID:")
                source_id = line[idx + len("Source ID:"):].strip()
                if source_id in metadata_only:
                    return True
    return False


def source_coverage_matches_skill_files(root: str, coverage: skillgen.SourceCoverage) -> bool:
    per_skill, err = load_per_skill_sources(root, required_topics())
    if err is not None:
        return False
    seen: Set[str] = set()
    by_id: Dict[str, skillgen.SourceCoverageEntry] = {}

    for entry in coverage.sources:
        source_id = (entry.source_id or "").strip()
        if source_id == "":
            return False
        if source_id in seen:
            return False
        seen.add(source_id)
        by_id[source_id] = entry

        if entry.status in (skillgen.StatusVerified, skillgen.StatusMetadataOnly):
            if not entry.skills:
                if entry.status != skillgen.StatusMetadataOnly or entry.references:
                    return False
                continue
            if not source_matches_per_skill(entry, per_skill):
                return False
        elif entry.status == skillgen.StatusDuplicate:
            if not entry.duplicate_of or not entry.duplicate_evidence:
                return False
        elif entry.status == skillgen.StatusExcluded:
            pass
        elif entry.status == skillgen.StatusNeedsReview:
            return False
        else:
            return False

    for by_id_map in per_skill.values():
        for source_id, _source in by_id_map.items():
            entry = by_id.get(source_id)
            if entry is None:
                continue
            if entry.status not in (skillgen.StatusVerified, skillgen.StatusMetadataOnly):
                return False
    return True


def bank_account_investment_source_routed(coverage: skillgen.SourceCoverage) -> bool:
    target = "investing-in-bank-accounts-and-income-bonds"
    for entry in coverage.sources:
        if target in entry.original_url or target in entry.canonical_url:
            return "shares-etfs-managed-funds" in entry.skills
    return False


def home_business_sources_routed(coverage: skillgen.SourceCoverage) -> bool:
    matched = 0
    for entry in coverage.sources:
        if "home-based-business-expenses" not in entry.original_url and "home-based-business-expenses" not in entry.canonical_url:
            continue
        matched += 1
        if "abn-business" not in entry.skills:
            return False
    return matched > 0


def source_matches_per_skill(
    entry: skillgen.SourceCoverageEntry,
    per_skill: Dict[str, Dict[str, skillgen.Source]],
) -> bool:
    if not entry.skills or not entry.references:
        return False
    for skill in entry.skills:
        by_id = per_skill.get(skill, {})
        local = by_id.get(entry.source_id)
        if local is None:
            return False
        if not matches_canonical_or_blank(local, entry.canonical_url):
            return False
        if local.status != entry.status:
            return False
        if (local.checked_at or "") != (entry.checked_at or ""):
            return False
    return True


def matches_canonical_or_blank(local: skillgen.Source, canonical: str) -> bool:
    canonical = canonical.strip()
    if not canonical:
        return True
    return (local.url or "").strip() == canonical or (local.final_url or "").strip() == canonical


def generation_is_deterministic(root: str) -> Tuple[bool, Optional[Exception]]:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-generation-check-")
    try:
        skillgen.Generate(skillgen.Options(root=root, output_root=work_root))
        err = skillgen.CompareGeneratedArtifacts(root, work_root)
        return err is None, err
    except Exception as exc:
        return False, exc
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def current_values_preserved_without_cache(root: str) -> bool:
    import shutil

    value_files = current_value_files(root)
    work_root = tempfile.mkdtemp(prefix="taxmate-validate-values-preserved-")
    try:
        skillgen.Generate(skillgen.Options(root=root, output_root=work_root))
        if not value_files:
            return len(current_value_files(work_root)) == 0
        for rel in value_files:
            expected = Path(os.path.join(root, rel)).read_bytes().strip()
            generated = Path(os.path.join(work_root, rel)).read_bytes().strip()
            if generated != expected:
                return False
        return True
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def blank_registry_hash_downgrades_previous_coverage(root: str) -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-blank-registry-hash-")
    generated_root = tempfile.mkdtemp(prefix="taxmate-validate-blank-registry-generated-")
    try:
        atodata.CopyDir(os.path.join(root, "skills"), os.path.join(work_root, "skills"))
        atodata.CopyDir(os.path.join(root, "data", "ato_knowledge_base"), os.path.join(work_root, "data", "ato_knowledge_base"))

        target = first_current_value_source(work_root)
        if target is None:
            return False
        skill, source_url = target

        registry = atodata.LoadRegistry(work_root)
        rec = find_registry_record(registry, source_url)
        if rec is None:
            return False
        rec.content_hash = ""
        rec.content_verified = False
        atodata.SaveRegistry(work_root, registry)

        skillgen.Generate(skillgen.Options(root=work_root, output_root=generated_root))
        generated_registry = atodata.LoadRegistry(generated_root)
        generated_rec = find_registry_record(generated_registry, source_url)
        if generated_rec is None or generated_rec.content_hash != "" or generated_rec.content_verified:
            return False

        coverage = skillgen.LoadSourceCoverage(generated_root)
        source_id = skillgen.sourceID(rec.url, skillgen.coverageCanonicalURL(rec.url, rec.final_url))
        entry = next((item for item in coverage.sources if item.source_id == source_id), None)
        if entry is None or entry.status == skillgen.StatusVerified:
            return False

        return current_values_exclude_source(generated_root, skill, source_url)
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
        shutil.rmtree(generated_root, ignore_errors=True)


def unverified_registry_hash_downgrades_previous_coverage(root: str) -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-unverified-registry-hash-")
    generated_root = tempfile.mkdtemp(prefix="taxmate-validate-unverified-registry-generated-")
    try:
        atodata.CopyDir(os.path.join(root, "skills"), os.path.join(work_root, "skills"))
        atodata.CopyDir(os.path.join(root, "data", "ato_knowledge_base"), os.path.join(work_root, "data", "ato_knowledge_base"))

        target = first_current_value_source(work_root)
        if target is None:
            return False
        skill, source_url = target

        registry = atodata.LoadRegistry(work_root)
        rec = find_registry_record(registry, source_url)
        if rec is None or not rec.content_hash:
            return False
        rec.content_verified = False
        atodata.SaveRegistry(work_root, registry)

        skillgen.Generate(skillgen.Options(root=work_root, output_root=generated_root))
        coverage = skillgen.LoadSourceCoverage(generated_root)
        source_id = skillgen.sourceID(rec.url, skillgen.coverageCanonicalURL(rec.url, rec.final_url))
        entry = next((item for item in coverage.sources if item.source_id == source_id), None)
        if entry is None or entry.status == skillgen.StatusVerified:
            return False

        return current_values_exclude_source(generated_root, skill, source_url)
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
        shutil.rmtree(generated_root, ignore_errors=True)


def stale_cache_text_does_not_verify_source(root: str) -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-stale-cache-")
    generated_root = tempfile.mkdtemp(prefix="taxmate-validate-stale-cache-generated-")
    try:
        atodata.CopyDir(os.path.join(root, "skills"), os.path.join(work_root, "skills"))
        atodata.CopyDir(os.path.join(root, "data", "ato_knowledge_base"), os.path.join(work_root, "data", "ato_knowledge_base"))

        target = first_current_value_source(work_root)
        if target is None:
            return False
        skill, source_url = target

        registry = atodata.LoadRegistry(work_root)
        rec = find_registry_record(registry, source_url)
        if rec is None:
            return False
        rec.content_hash = ""
        rec.content_verified = False
        atodata.SaveRegistry(work_root, registry)

        cache_path = os.path.join(atodata.CacheDir(work_root), rec.text_file)
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        Path(cache_path).write_text(
            "Working from home expenses fake stale cache 99 cents per hour from 1 July 2026.",
            encoding="utf-8",
        )

        skillgen.Generate(skillgen.Options(root=work_root, output_root=generated_root))
        generated_registry = atodata.LoadRegistry(generated_root)
        generated_rec = find_registry_record(generated_registry, source_url)
        if generated_rec is None or generated_rec.content_hash != "" or generated_rec.content_verified:
            return False

        coverage = skillgen.LoadSourceCoverage(generated_root)
        source_id = skillgen.sourceID(rec.url, skillgen.coverageCanonicalURL(rec.url, rec.final_url))
        entry = next((item for item in coverage.sources if item.source_id == source_id), None)
        if entry is None or entry.status == skillgen.StatusVerified:
            return False

        return current_values_exclude_source(generated_root, skill, source_url)
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)
        shutil.rmtree(generated_root, ignore_errors=True)


def first_current_value_source(root: str) -> Optional[Tuple[str, str]]:
    for skill in required_topics():
        path = os.path.join(root, "skills", skill, "references", "current-values.json")
        try:
            values = json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in values:
            if isinstance(item, dict) and item.get("source_url"):
                return skill, str(item["source_url"])
    return None


def current_values_exclude_source(root: str, skill: str, source_url: str) -> bool:
    values_path = os.path.join(root, "skills", skill, "references", "current-values.json")
    if not os.path.exists(values_path):
        return True
    values = json.loads(Path(values_path).read_text(encoding="utf-8"))
    source_url = skillgen.canonicalURL(source_url)
    return all(skillgen.canonicalURL(str(item.get("source_url", ""))) != source_url for item in values)


def find_registry_record(registry, source_url: str):
    canonical = skillgen.canonicalURL(source_url)
    for rec in registry.records:
        if skillgen.canonicalURL(rec.url) == canonical or skillgen.canonicalURL(rec.final_url) == canonical:
            return rec
    return None


def stale_current_values_detected(root: str) -> bool:
    import shutil

    value_files = current_value_files(root)
    expected_root = tempfile.mkdtemp(prefix="taxmate-validate-stale-expected-")
    generated_root = tempfile.mkdtemp(prefix="taxmate-validate-stale-generated-")
    try:
        copy_generated_check_inputs(root, expected_root, generated_root)
        if value_files:
            os.remove(os.path.join(generated_root, value_files[0]))
        else:
            stale_rel = os.path.join("skills", required_topics()[0], "references", "current-values.json")
            write_stale_current_values(os.path.join(expected_root, stale_rel))
        return skillgen.CompareGeneratedArtifacts(expected_root, generated_root) is not None
    except Exception:
        return False
    finally:
        shutil.rmtree(expected_root, ignore_errors=True)
        shutil.rmtree(generated_root, ignore_errors=True)


def stale_generated_reference_detected(root: str) -> bool:
    import shutil

    expected_root = tempfile.mkdtemp(prefix="taxmate-validate-stale-reference-expected-")
    generated_root = tempfile.mkdtemp(prefix="taxmate-validate-stale-reference-generated-")
    stale_rel = os.path.join("skills", required_topics()[0], "references", "stale-generated.md")
    try:
        copy_generated_check_inputs(root, expected_root, generated_root)
        Path(os.path.join(expected_root, stale_rel)).write_text("stale generated reference\n", encoding="utf-8")
        init_git_index(expected_root, ["skills", os.path.join("data", "ato_knowledge_base", skillgen.SOURCE_COVERAGE_FILE)])
        return skillgen.CompareGeneratedArtifacts(expected_root, generated_root) is not None
    except Exception:
        return False
    finally:
        shutil.rmtree(expected_root, ignore_errors=True)
        shutil.rmtree(generated_root, ignore_errors=True)


def untracked_generated_reference_ignored(root: str) -> bool:
    import shutil

    expected_root = tempfile.mkdtemp(prefix="taxmate-validate-untracked-reference-expected-")
    generated_root = tempfile.mkdtemp(prefix="taxmate-validate-untracked-reference-generated-")
    scratch_rel = os.path.join("skills", required_topics()[0], "references", "scratch.md")
    try:
        copy_generated_check_inputs(root, expected_root, generated_root)
        Path(os.path.join(expected_root, scratch_rel)).write_text("local scratch\n", encoding="utf-8")
        init_git_index(expected_root, ["skills", os.path.join("data", "ato_knowledge_base", skillgen.SOURCE_COVERAGE_FILE)])
        subprocess.run(
            ["git", "-C", expected_root, "reset", "-q", "--", scratch_rel],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return skillgen.CompareGeneratedArtifacts(expected_root, generated_root) is None
    except Exception:
        return False
    finally:
        shutil.rmtree(expected_root, ignore_errors=True)
        shutil.rmtree(generated_root, ignore_errors=True)


def copy_generated_check_inputs(root: str, expected_root: str, generated_root: str) -> None:
    atodata.CopyDir(os.path.join(root, "skills"), os.path.join(expected_root, "skills"))
    atodata.CopyDir(os.path.join(root, "data", "ato_knowledge_base"), os.path.join(expected_root, "data", "ato_knowledge_base"))
    atodata.CopyDir(os.path.join(expected_root, "skills"), os.path.join(generated_root, "skills"))
    atodata.CopyDir(os.path.join(expected_root, "data", "ato_knowledge_base"), os.path.join(generated_root, "data", "ato_knowledge_base"))


def init_git_index(root: str, paths: List[str]) -> None:
    subprocess.run(
        ["git", "-C", root, "init", "-q"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    subprocess.run(
        ["git", "-C", root, "add", "--", *paths],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def write_stale_current_values(path: str) -> None:
    Path(os.path.dirname(path)).mkdir(parents=True, exist_ok=True)
    Path(path).write_text("[]\n", encoding="utf-8")


def current_value_files(root: str) -> List[str]:
    out: List[str] = []
    for skill in required_topics():
        rel = os.path.join("skills", skill, "references", "current-values.json")
        if file_exists(os.path.join(root, rel)):
            out.append(rel)
    return sorted(out)


def stale_go_tooling_hits(root: str) -> List[str]:
    hits: List[str] = []
    for rel in go_tooling_scan_files():
        hits.extend(text_hits(root, rel, go_tooling_needles()))
    return hits


def stale_go_runtime_claim_hits(root: str) -> List[str]:
    hits: List[str] = []
    for rel in public_runtime_claim_scan_files():
        hits.extend(text_hits(root, rel, go_runtime_claim_needles()))
    return hits


def stale_committed_source_cache_claim_hits(root: str) -> List[str]:
    hits: List[str] = []
    for rel in public_runtime_claim_scan_files():
        hits.extend(text_hits(root, rel, committed_source_cache_claim_needles()))
    return hits


def ato_endorsement_claim_hits(root: str) -> List[str]:
    files = public_ato_claim_scan_files(root)
    banned = [
        "ATO-" + "backed",
        "ATO " + "backed",
        "Australian Taxation Office-" + "backed",
        "Australian Taxation Office " + "backed",
        "backed by " + "ATO",
        "backed by the " + "ATO",
        "backed by Australian Taxation Office",
        "backed by the Australian Taxation Office",
        "supported by " + "ATO",
        "supported by the " + "ATO",
        "supported by Australian Taxation Office",
        "supported by the Australian Taxation Office",
        "sponsored by " + "ATO",
        "sponsored by the " + "ATO",
        "sponsored by Australian Taxation Office",
        "sponsored by the Australian Taxation Office",
        "endorsed by " + "ATO",
        "endorsed by the " + "ATO",
        "endorsed by Australian Taxation Office",
        "endorsed by the Australian Taxation Office",
        "approved by " + "ATO",
        "approved by the " + "ATO",
        "approved by Australian Taxation Office",
        "approved by the Australian Taxation Office",
        "certified by " + "ATO",
        "certified by the " + "ATO",
        "certified by Australian Taxation Office",
        "certified by the Australian Taxation Office",
        "authorised by " + "ATO",
        "authorised by the " + "ATO",
        "authorised by Australian Taxation Office",
        "authorised by the Australian Taxation Office",
        "authorized by " + "ATO",
        "authorized by the " + "ATO",
        "authorized by Australian Taxation Office",
        "authorized by the Australian Taxation Office",
        "affiliated with " + "ATO",
        "affiliated with the " + "ATO",
        "affiliated with Australian Taxation Office",
        "affiliated with the Australian Taxation Office",
        "partnered with " + "ATO",
        "partnered with the " + "ATO",
        "partnered with Australian Taxation Office",
        "partnered with the Australian Taxation Office",
        "in partnership with " + "ATO",
        "in partnership with the " + "ATO",
        "in partnership with Australian Taxation Office",
        "in partnership with the Australian Taxation Office",
        "ATO-" + "supported",
        "ATO " + "supported",
        "Australian Taxation Office-" + "supported",
        "Australian Taxation Office " + "supported",
        "ATO-" + "sponsored",
        "ATO " + "sponsored",
        "Australian Taxation Office-" + "sponsored",
        "Australian Taxation Office " + "sponsored",
        "ATO-" + "endorsed",
        "ATO " + "endorsed",
        "Australian Taxation Office-" + "endorsed",
        "Australian Taxation Office " + "endorsed",
        "ATO-" + "approved",
        "ATO " + "approved",
        "Australian Taxation Office-" + "approved",
        "Australian Taxation Office " + "approved",
        "ATO-" + "certified",
        "ATO " + "certified",
        "Australian Taxation Office-" + "certified",
        "Australian Taxation Office " + "certified",
        "ATO-" + "authorised",
        "ATO " + "authorised",
        "Australian Taxation Office-" + "authorised",
        "Australian Taxation Office " + "authorised",
        "ATO-" + "authorized",
        "ATO " + "authorized",
        "Australian Taxation Office-" + "authorized",
        "Australian Taxation Office " + "authorized",
        "ATO partner",
        "official ATO partner",
        "Australian Taxation Office partner",
        "official Australian Taxation Office partner",
    ]
    hits: List[str] = []
    for rel in files:
        hits.extend(ato_endorsement_text_hits(root, rel, banned))
    return hits


def ato_endorsement_text_hits(root: str, rel: str, needles: List[str]) -> List[str]:
    text = read_text(os.path.join(root, rel))
    lowered = text.lower()
    hits: List[str] = []
    if not lowered:
        return hits
    for needle in needles:
        lowered_needle = needle.lower()
        start = 0
        while True:
            index = lowered.find(lowered_needle, start)
            if index == -1:
                break
            if not is_negated_ato_claim(lowered, index):
                hits.append(f"{rel}:{needle}")
            start = index + 1
    return hits


def is_negated_ato_claim(lowered_text: str, start_index: int) -> bool:
    sentence_start = max(
        lowered_text.rfind(".", 0, start_index),
        lowered_text.rfind("!", 0, start_index),
        lowered_text.rfind("?", 0, start_index),
        lowered_text.rfind(";", 0, start_index),
        lowered_text.rfind("\n", 0, start_index),
    )
    prefix = lowered_text[sentence_start + 1 : start_index]
    comma_index = prefix.rfind(",")
    if comma_index != -1 and not re.fullmatch(r"\s*(and|or)\s*", prefix[comma_index + 1 :]):
        prefix = prefix[comma_index + 1 :]

    negation_matches = list(re.finditer(r"\b(?:never|do not|does not|must not|not)\b", prefix))
    for match in reversed(negation_matches):
        tail = prefix[match.start() :]
        if re.match(r"not\s+only\b", tail):
            continue
        if re.search(r"\b(?:but|however|yet|though|although)\b", tail):
            continue
        return True
    return False


def public_ato_claim_scan_files(root: str) -> List[str]:
    files = set(public_runtime_claim_scan_files())
    files.update(
        [
            "skill.json",
            "hooks.json",
            os.path.join(".github", "workflows", "ci.yml"),
            os.path.join(".github", "workflows", "release.yml"),
            os.path.join(".github", "dependabot.yml"),
            os.path.join(".github", "dependabot.yaml"),
        ]
    )
    for base in [
        "agents",
        "docs",
        "skills",
        "runtime/skills",
        "wrappers",
        ".codex-plugin",
        ".agents",
    ]:
        abs_base = os.path.join(root, base)
        if not os.path.isdir(abs_base):
            continue
        for dirpath, _, filenames in os.walk(abs_base):
            for filename in filenames:
                if filename.endswith((".md", ".json", ".yaml", ".yml")) or filename == "SKILL.md":
                    files.add(os.path.relpath(os.path.join(dirpath, filename), root))
    return sorted(rel for rel in files if file_exists(os.path.join(root, rel)))


def go_tooling_scan_files() -> List[str]:
    return [
        ".gitignore",
        os.path.join(".devcontainer", "Dockerfile"),
        os.path.join(".devcontainer", "devcontainer.json"),
        "docker-compose.dev.yml",
        "CONTRIBUTING.md",
        "README.md",
        os.path.join("docs", "DEVELOPMENT.md"),
        os.path.join("docs", "FULL_PLUGIN_INSTALL.md"),
        os.path.join(".github", "workflows", "ci.yml"),
        os.path.join(".github", "workflows", "release.yml"),
        os.path.join(".github", "dependabot.yml"),
        os.path.join(".github", "dependabot.yaml"),
    ]


def public_runtime_claim_scan_files() -> List[str]:
    return [
        os.path.join(".codex-plugin", "plugin.json"),
        os.path.join(".claude-plugin", "plugin.json"),
        os.path.join(".claude-plugin", "marketplace.json"),
        os.path.join(".agents", "plugins", "marketplace.json"),
        os.path.join("agents", "openai.yaml"),
        "plugin.lock.json",
        ".gitleaks.toml",
        "README.md",
        "DISCLAIMER.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        os.path.join("docs", "DEVELOPMENT.md"),
        os.path.join("docs", "DISCOVERY.md"),
        os.path.join("docs", "FULL_PLUGIN_INSTALL.md"),
        os.path.join("docs", "INSTALLATION.md"),
        os.path.join("docs", "PUBLICATION_CHECKLIST.md"),
    ]


def committed_source_cache_claim_needles() -> List[str]:
    return [
        "repository contains an ato source cache",
        "bundled ato source cache",
        "committed ato source cache",
        "committed source cache",
        "source cache and test fixtures",
    ]


def go_tooling_needles() -> List[str]:
    return [
        "# go",
        "*.test",
        "devcontainers/go",
        "golang.go",
        "gomodcache",
        "gocache",
        "go version",
        "go test",
        "go build",
        "go run",
        "package-ecosystem: gomod",
    ]


def go_runtime_claim_needles() -> List[str]:
    return [
        "shared go backend",
        "go backend",
        "go runtime",
        "go toolchain",
        "go-based",
        "golang backend",
        "golang runtime",
    ]


def text_hits(root: str, rel: str, needles: List[str]) -> List[str]:
    text = read_text(os.path.join(root, rel)).lower()
    hits: List[str] = []
    if not text:
        return hits
    for needle in needles:
        if needle.lower() in text:
            hits.append(f"{rel}:{needle}")
    return hits


def codex_environment_toml_valid(root: str) -> bool:
    path = os.path.join(root, ".codex", "environments", "environment.toml")
    text = read_text(path)
    if not text:
        return False
    try:
        data = parse_toml(text)
    except ValueError:
        return False
    if data.get("version") != 1:
        return False
    setup = data.get("setup")
    cleanup = data.get("cleanup")
    if not isinstance(setup, dict) or setup.get("script") != "bash scripts/codex-env-setup.sh":
        return False
    if not isinstance(cleanup, dict) or cleanup.get("script") != "bash scripts/codex-env-cleanup.sh":
        return False
    actions = data.get("actions")
    if not isinstance(actions, list) or not actions:
        return False
    has_full_check = False
    for action in actions:
        if not isinstance(action, dict):
            return False
        if not all(isinstance(action.get(key), str) and action.get(key) for key in ("name", "icon", "command")):
            return False
        if action.get("icon") == "tool" and action.get("command") == "bash scripts/codex-env-full-check.sh":
            has_full_check = True
    if not has_full_check:
        return False
    return True


def parse_toml(text: str) -> Dict[str, Any]:
    try:
        import tomllib  # type: ignore

        return tomllib.loads(text)
    except ModuleNotFoundError:
        return parse_simple_toml(text)
    except Exception as exc:
        raise ValueError(str(exc)) from exc


def parse_simple_toml(text: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    current: Dict[str, Any] = data
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[[") and line.endswith("]]"):
            name = line[2:-2].strip()
            if not name or "[" in name or "]" in name:
                raise ValueError("invalid TOML array table")
            actions = data.setdefault(name, [])
            if not isinstance(actions, list):
                raise ValueError("array table conflicts with scalar")
            current = {}
            actions.append(current)
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            if not name or "[" in name or "]" in name:
                raise ValueError("invalid TOML table")
            section = data.setdefault(name, {})
            if not isinstance(section, dict):
                raise ValueError("table conflicts with scalar")
            current = section
            continue
        if "=" not in line:
            raise ValueError("invalid TOML assignment")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        value = raw_value.strip()
        if not key:
            raise ValueError("invalid TOML key")
        if value.startswith('"'):
            if len(value) < 2 or not value.endswith('"'):
                raise ValueError("unterminated TOML string")
            current[key] = value[1:-1]
            continue
        try:
            current[key] = int(value)
        except ValueError as exc:
            raise ValueError("unsupported TOML value") from exc
    return data


def tracked_private_path_hits(root: str) -> List[str]:
    return private_path_hits(root, tracked_text_files(root))


def tracked_text_files(root: str) -> List[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", root, "ls-files"],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except Exception:
        return []

    out: List[str] = []
    allowed_suffixes = (
        ".json",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".txt",
        ".yaml",
        ".yml",
    )
    allowed_names = {
        ".gitignore",
        "hooks.json",
        "plugin.lock.json",
        "skill.json",
    }
    ignored_prefixes = (
        "data/ato_knowledge_base/raw/",
        "data/ato_knowledge_base/text/",
    )
    scanner_files = {
        ".github/workflows/ci.yml",
        "scripts/check-publication-ready.sh",
        "scripts/taxmate_validate.py",
    }
    for rel in proc.stdout.splitlines():
        if rel in scanner_files:
            continue
        if rel.startswith(ignored_prefixes):
            continue
        if rel in allowed_names or rel.endswith(allowed_suffixes) or "/SKILL.md" in rel:
            out.append(os.path.join(root, rel))
    return out


def gitleaks_no_broad_cache_allowlist(root: str) -> bool:
    text = read_text(os.path.join(root, ".gitleaks.toml"))
    broad_needles = [
        "data/ato_knowledge_base/raw",
        "data/ato_knowledge_base/text",
        ".cache/ato",
    ]
    return not contains_any(text, broad_needles)


def audit_is_read_only(root: str) -> bool:
    try:
        skillgen.WriteCoverageReport(root, "markdown")
        return True
    except Exception:
        return False


def audit_json_stdout_single_document(root: str) -> bool:
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            code = taxmate_skills._audit(root, "", "json", False)
        if code != 0:
            return False
        payload = json.loads(out.getvalue())
        return "summary" in payload and "source_coverage" in payload
    except Exception:
        return False


def audit_duplicates_not_unassigned(root: str) -> bool:
    try:
        coverage = skillgen.LoadSourceCoverage(root)
        summary = skillgen.Audit(root, coverage)
    except Exception:
        return False

    duplicate_ids = sorted(entry.source_id for entry in coverage.sources if entry.status == skillgen.StatusDuplicate)
    return (
        duplicate_ids == sorted(summary.duplicate_entries)
        and len(set(duplicate_ids).intersection(summary.not_used_entries)) == 0
    )


def audit_cgt_counts_metadata_assignments(root: str) -> bool:
    try:
        summary = skillgen.Audit(root, skillgen.LoadSourceCoverage(root))
    except Exception:
        return False
    return all(
        summary.cgt_coverage.get(key)
        for key in ["general", "shares_etfs_managed_funds", "crypto", "property_rental"]
    )


def audit_check_fails_missing_required_assignments(root: str) -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-required-assignment-")
    try:
        atodata.CopyDir(os.path.join(root, "skills"), os.path.join(work_root, "skills"))
        atodata.CopyDir(os.path.join(root, "data", "ato_knowledge_base"), os.path.join(work_root, "data", "ato_knowledge_base"))
        target = required_topics()[0]
        downgrade_topic_sources(work_root, target, "test assignment removal", remove_assignment=True)
        err = skillgen.ValidateSourceCoverage(work_root)
        return err is not None and "required tax areas missing source assignments" in str(err)
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def audit_check_fails_missing_required_verified_sources(root: str) -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-required-verified-")
    try:
        atodata.CopyDir(os.path.join(root, "skills"), os.path.join(work_root, "skills"))
        atodata.CopyDir(os.path.join(root, "data", "ato_knowledge_base"), os.path.join(work_root, "data", "ato_knowledge_base"))
        target = required_topics()[0]
        downgrade_topic_sources(work_root, target, "test metadata-only downgrade", remove_assignment=False)
        err = skillgen.ValidateSourceCoverage(work_root)
        return err is not None and "required tax areas missing verified source content" in str(err)
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def downgrade_topic_sources(work_root: str, target: str, reason: str, remove_assignment: bool) -> None:
    coverage_path = os.path.join(work_root, "data", "ato_knowledge_base", skillgen.SOURCE_COVERAGE_FILE)
    payload = json.loads(Path(coverage_path).read_text(encoding="utf-8"))
    for entry in payload.get("sources", []):
        skills = entry.get("skills", [])
        if not isinstance(skills, list) or target not in skills:
            continue
        if remove_assignment:
            entry["skills"] = [skill for skill in skills if skill != target]
        entry["status"] = skillgen.StatusMetadataOnly
        entry["reason"] = reason
    Path(coverage_path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    sources_path = os.path.join(work_root, "skills", target, "references", "sources.json")
    sources = json.loads(Path(sources_path).read_text(encoding="utf-8"))
    for entry in sources:
        entry["status"] = skillgen.StatusMetadataOnly
        entry["assignment_reason"] = reason
    Path(sources_path).write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")


def skills_generate_check_catches_validation_error(root: str) -> bool:
    original = taxmate_skills.skillgen.Generate

    def fail_generate(_opts):
        raise RuntimeError("synthetic validation error")

    taxmate_skills.skillgen.Generate = fail_generate
    try:
        _, err = taxmate_skills._check_generation(root, "")
        return err is not None and "synthetic validation error" in str(err)
    except Exception:
        return False
    finally:
        taxmate_skills.skillgen.Generate = original


def source_coverage_status_check_consumes_return_error(root: str) -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-coverage-status-")
    try:
        atodata.CopyDir(os.path.join(root, "skills"), os.path.join(work_root, "skills"))
        atodata.CopyDir(os.path.join(root, "data", "ato_knowledge_base"), os.path.join(work_root, "data", "ato_knowledge_base"))
        path = os.path.join(work_root, "data", "ato_knowledge_base", skillgen.SOURCE_COVERAGE_FILE)
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        payload["sources"] = payload.get("sources", [])[1:]
        Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        registry = atodata.LoadRegistry(work_root)
        coverage = skillgen.LoadSourceCoverage(work_root)
        checks: List[Dict[str, Any]] = []
        add_source_coverage_checks(
            work_root,
            lambda name, passed, detail: checks.append({"check": name, "passed": passed, "detail": detail}),
            registry,
            coverage,
            None,
        )
        status = next((check for check in checks if check["check"] == "source_coverage_statuses_valid"), None)
        return status is not None and status["passed"] is False and "does not match registry count" in status["detail"]
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def plugin_manifest_errors_are_reported() -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-bad-manifest-")
    try:
        os.makedirs(os.path.join(work_root, ".codex-plugin"), exist_ok=True)
        Path(os.path.join(work_root, ".codex-plugin", "plugin.json")).write_text("{", encoding="utf-8")
        manifest, err = read_plugin_manifest(work_root)
        return manifest == {} and err is not None
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def public_skills_errors_are_reported() -> bool:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-missing-public-skills-")
    try:
        skills, err = public_portable_skills(work_root)
        return skills == [] and err is not None
    except Exception:
        return False
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def fetch_http_error_preserves_status() -> bool:
    original = atodata.subprocess.run

    def fake_run(command, **_kwargs):
        output_path = command[command.index("--output") + 1]
        Path(output_path).write_bytes(b"not found")
        return subprocess.CompletedProcess(
            command,
            0,
            b"404\nhttps://www.ato.gov.au/missing",
            b"",
        )

    atodata.subprocess.run = fake_run
    try:
        fetched = atodata.Fetch("https://www.ato.gov.au/missing")
        return (
            fetched.status == 404
            and fetched.final_url == "https://www.ato.gov.au/missing"
            and fetched.body == b"not found"
        )
    except Exception:
        return False
    finally:
        atodata.subprocess.run = original


def finance_csv_trims_leading_space() -> bool:
    body = 'date,description,amount\n2026-01-01, "Quoted desk",10\n'
    try:
        rows = taxmate_finance.read_csv(io.StringIO(body))
    except Exception:
        return False
    return len(rows) == 1 and rows[0].description == "Quoted desk"


def calc_rejects_non_finite_numbers() -> bool:
    out = io.StringIO()
    err = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            taxmate_calc.main(["payg", "--gross-pay", "nan"])
    except SystemExit as exc:
        return exc.code != 0 and out.getvalue() == ""
    return False


def finance_csv_rejects_non_finite_numbers() -> bool:
    body = "date,description,amount,gst,units\n2026-01-01,Bad,nan,0,1\n"
    try:
        taxmate_finance.read_csv(io.StringIO(body))
    except ValueError:
        return True
    return False


def refresh_errors_use_python_formatting(root: str) -> bool:
    text = read_text(os.path.join(root, "scripts", "taxmate_refresh.py"))
    return '"%v"' not in text and "'%v'" not in text


def wrapper_help_uses_public_commands(root: str) -> bool:
    script = os.path.join(root, "scripts", "taxmate")
    commands = [
        [script, "--help"],
        [script, "finance", "--help"],
        [script, "refresh", "--help"],
        [script, "skills", "--help"],
        [script, "skills", "audit", "--help"],
        [script, "calc", "payg", "--help"],
    ]
    for command in commands:
        try:
            proc = subprocess.run(command, cwd=root, text=True, capture_output=True, timeout=10)
        except Exception:
            return False
        help_text = proc.stdout + proc.stderr
        if proc.returncode != 0 or "taxmate_" in help_text or ".py" in help_text:
            return False
        if "./scripts/taxmate" not in help_text:
            return False
    return True


def stale_bash5_prereq_hits(root: str) -> List[str]:
    hits: List[str] = []
    for rel in [
        "README.md",
        os.path.join("docs", "DEVELOPMENT.md"),
        os.path.join("docs", "FULL_PLUGIN_INSTALL.md"),
        os.path.join("runtime", "skills", "calculators", "SKILL.md"),
        os.path.join("runtime", "skills", "finance-review", "SKILL.md"),
        os.path.join("runtime", "skills", "research", "SKILL.md"),
    ]:
        hits.extend(text_hits(root, rel, ["bash 5", "bash 5+"]))
    return hits


def text_contains_all(text: str, required: List[str]) -> bool:
    return all(item in text for item in required)


def release_workflow_has_common_guards(text: str) -> bool:
    return text_contains_all(
        text,
        [
            "steps.target.outputs.sha",
            "GH_REPO: nijanthan-dev/taxmate-australia",
            "--commit \"$TARGET_SHA\"",
            "Require main unchanged",
            "git ls-remote https://github.com/nijanthan-dev/taxmate-australia.git refs/heads/main",
            "main moved from $TARGET_SHA",
            "RELEASE_PLEASE_TOKEN",
            "target-branch: main",
            "config-file: release-please-config.json",
            "manifest-file: .release-please-manifest.json",
        ],
    )


def release_workflow_has_auto_trigger(text: str) -> bool:
    return text_contains_all(
        text,
        [
            "workflow_run:",
            'workflows: ["CI"]',
            "types: [completed]",
            "branches: [main]",
            "github.event.workflow_run.conclusion == 'success'",
            "github.event.workflow_run.head_branch == 'main'",
            "github.event.workflow_run.head_sha",
        ],
    )


def release_workflow_avoids_privileged_checkout(text: str) -> bool:
    return "actions/checkout@" not in text


def release_workflow_has_manual_trigger(text: str) -> bool:
    return text_contains_all(
        text,
        [
            "workflow_dispatch:",
            "github.event_name == 'workflow_dispatch'",
            "github.ref == 'refs/heads/main'",
            'echo "sha=$GITHUB_SHA" >> "$GITHUB_OUTPUT"',
        ],
    )


def release_workflow_auto_after_ci(root: str) -> bool:
    text = read_text(os.path.join(root, ".github", "workflows", "release.yml"))
    return (
        release_workflow_has_common_guards(text)
        and release_workflow_has_auto_trigger(text)
        and release_workflow_has_manual_trigger(text)
        and release_workflow_avoids_privileged_checkout(text)
    )


def github_ci_workflow_has_required_triggers(text: str) -> bool:
    return (
        "workflow_dispatch:" in text
        and any(re.match(r"^\s*pull_request:\s*$", line) for line in text.splitlines())
        and any(re.match(r"^\s*push:\s*$", line) for line in text.splitlines())
        and "branches: [main]" in text
    )


def local_act_ci_ready(root: str) -> bool:
    actrc = read_text(os.path.join(root, ".actrc"))
    local_ci = read_text(os.path.join(root, ".github", "workflows", "local-ci.yml"))
    ci = read_text(os.path.join(root, ".github", "workflows", "ci.yml"))
    scanner = read_text(os.path.join(root, ".github", "workflows", "hol-plugin-scanner.yml"))
    check_script = read_text(os.path.join(root, "scripts", "check-local-ci-ready.sh"))
    run_script = read_text(os.path.join(root, "scripts", "run-local-ci-act.sh"))
    required_local_steps = [
        "actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0",
        "rm -rf .git",
        "git commit -m act-baseline",
        "python3 -m py_compile scripts/*.py tests/*.py",
        "python3 -m unittest discover -s tests -p 'test_*.py'",
        "./scripts/taxmate review-guardrails",
        "./scripts/taxmate validate",
        "./scripts/taxmate skills generate --check",
        "./scripts/taxmate skills audit --check",
        "bash scripts/test-mcp-server.sh",
        "bash scripts/check-publication-ready.sh",
    ]
    return (
        "catthehacker/ubuntu:act-22.04" in actrc
        and "act workflow_dispatch -W .github/workflows/local-ci.yml" in run_script
        and "docker info" in run_script
        and "gitleaks dir . --redact --no-banner" in run_script
        and "gitleaks detect --source . --redact --no-banner" in run_script
        and "CI must retain pull_request trigger" in check_script
        and "CI must retain main push trigger" in check_script
        and "disable the workflow in GitHub when pausing hosted spend" in check_script
        and github_ci_workflow_has_required_triggers(ci)
        and "workflow_dispatch:" in scanner
        and all(step in local_ci for step in required_local_steps)
    )


def release_config_tracks_manifest_versions(root: str) -> bool:
    config, config_err = read_json_file(os.path.join(root, "release-please-config.json"))
    manifest, manifest_err = read_json_file(os.path.join(root, ".release-please-manifest.json"))
    plugin, plugin_err = read_json_file(os.path.join(root, ".codex-plugin", "plugin.json"))
    claude_plugin, claude_plugin_err = read_json_file(os.path.join(root, ".claude-plugin", "plugin.json"))
    skill, skill_err = read_json_file(os.path.join(root, "skill.json"))
    lock, lock_err = read_json_file(os.path.join(root, "plugin.lock.json"))
    if any(err is not None for err in [config_err, manifest_err, plugin_err, claude_plugin_err, skill_err, lock_err]):
        return False

    version = plugin.get("version")
    if not (version == claude_plugin.get("version") == skill.get("version") == lock.get("pluginVersion") == manifest.get(".")):
        return False
    if not isinstance(version, str) or not version.startswith("0."):
        return False
    bootstrap_sha = config.get("bootstrap-sha")
    if not (isinstance(bootstrap_sha, str) and re.fullmatch(r"[0-9a-f]{40}", bootstrap_sha)):
        return False

    root_package = config.get("packages", {}).get(".")
    if not isinstance(root_package, dict):
        return False
    extra_files = root_package.get("extra-files")
    if not isinstance(extra_files, list):
        return False

    required = {
        (".codex-plugin/plugin.json", "$.version"),
        (".claude-plugin/plugin.json", "$.version"),
        ("skill.json", "$.version"),
        ("plugin.lock.json", "$.pluginVersion"),
    }
    seen = set()
    for item in extra_files:
        if isinstance(item, dict) and item.get("type") == "json":
            seen.add((item.get("path"), item.get("jsonpath")))

    return (
        config.get("release-type") == "simple"
        and config.get("bump-minor-pre-major") is True
        and root_package.get("include-component-in-tag") is False
        and required.issubset(seen)
    )


def refresh_query_no_match_is_read_only(root: str) -> bool:
    original = taxmate_refresh.atodata.SaveRegistry

    def fail_save_registry(_root: str, _registry) -> None:
        raise RuntimeError("SaveRegistry should not run when refresh query matches no records")

    taxmate_refresh.atodata.SaveRegistry = fail_save_registry
    out = io.StringIO()
    err = io.StringIO()
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = taxmate_refresh.run(["--query", "zzzz-not-a-topic"])
        if code != 0:
            return False
        payload = json.loads(out.getvalue())
        return payload.get("matched") == 0 and payload.get("changed") == 0
    except Exception:
        return False
    finally:
        taxmate_refresh.atodata.SaveRegistry = original


def skills_refresh_unknown_topic_is_noop(root: str) -> bool:
    original = taxmate_skills.atodata.LoadRegistry

    def fail_load_registry(_root: str):
        raise RuntimeError("LoadRegistry should not run for unknown topic")

    taxmate_skills.atodata.LoadRegistry = fail_load_registry
    try:
        payload = taxmate_skills._refresh(root, "does-not-exist", False)
        return payload == {"requested": 0, "matched": 0, "results": []}
    except Exception:
        return False
    finally:
        taxmate_skills.atodata.LoadRegistry = original


def skills_refresh_missing_urls_is_read_only(root: str) -> bool:
    original_load = taxmate_skills.atodata.LoadRegistry
    original_select = taxmate_skills.atodata.SelectByURL
    original_save = taxmate_skills.atodata.SaveRegistry

    class EmptyRegistry:
        records: List[Any] = []

    def empty_registry(_root: str):
        return EmptyRegistry()

    def all_missing(_records, urls):
        return [], list(urls)

    def fail_save_registry(_root: str, _registry) -> None:
        raise RuntimeError("SaveRegistry should not run when skills refresh matches no registry records")

    taxmate_skills.atodata.LoadRegistry = empty_registry
    taxmate_skills.atodata.SelectByURL = all_missing
    taxmate_skills.atodata.SaveRegistry = fail_save_registry
    try:
        payload = taxmate_skills._refresh(root, "abn-business", False)
        return payload.get("requested", 0) > 0 and payload.get("matched") == 0 and bool(payload.get("results"))
    except Exception:
        return False
    finally:
        taxmate_skills.atodata.LoadRegistry = original_load
        taxmate_skills.atodata.SelectByURL = original_select
        taxmate_skills.atodata.SaveRegistry = original_save


def finance_record_rows_classify_before_income() -> bool:
    tx = taxmate_finance.Transaction(
        row=2,
        description="Private health premium",
        amount=120.0,
        direction="income",
        category="private health",
    )
    finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)
    return finding.bucket == "private_health" and finding.tax_treatment == "tax_return_info_only"


def finance_investment_income_classifies_as_income() -> bool:
    tx = taxmate_finance.Transaction(
        row=2,
        description="ETF dividend distribution",
        amount=50.0,
        direction="income",
        asset="ETF",
        units=10.0,
    )
    finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)
    return finding.bucket == "investment_income" and finding.tax_treatment == "tax_statement_record"


def finance_investment_income_outranks_business_tag() -> bool:
    tx = taxmate_finance.Transaction(
        row=2,
        description="Payment received",
        amount=50.0,
        direction="income",
        purpose="business records",
        abn="12345678901",
        asset="ETF",
        units=10.0,
    )
    finding = taxmate_finance.classify(tx, taxmate_finance.ModeStrict)
    return finding.bucket == "investment_income" and finding.tax_treatment == "tax_statement_record"


def taxpack_guide_html_contract() -> bool:
    try:
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_data(None))
    except Exception:
        return False

    required = [
        "Self-prepared HTML guide",
        "Prepared by user",
        "Not an ATO form",
        "Not fileable",
        "background:#fff0f1",
        "background:#eef5ff",
        "background:#effbf4",
        "background:#fff7dc",
        "left:-64px",
        "spotlight-target",
        "hide-tabs",
        "only-review",
        "only-evidence",
        "Tax items and review flags",
        "ATO-aligned manual copy worksheet",
        "<th>Source</th>",
        "source-url",
        "Checked 2026-06-23T09:04:57Z",
    ]
    if not all(item in body for item in required):
        return False
    if "Deductions and review flags" in body or "ATO-aligned deduction worksheet" in body:
        return False
    if "target-dot" in body or "border-radius:50%" in body:
        return False
    if ("Prepared by " + "TaxMate") in body:
        return False
    if "function findTarget" not in body or "tab.dataset.target+'" in body:
        return False
    targets = set(re.findall(r'data-target="([^"]+)"', body))
    anchors = set(re.findall(r'data-anchor="([^"]+)"', body))
    if not targets or not targets.issubset(anchors):
        return False

    quoted = taxmate_taxpack.guide_item(
        {
            "number": 'D"1',
            "ato_area": "Other",
            "question": "Quoted number?",
            "answer": "User-entered value",
            "why_included": "Selector escape regression.",
            "status": "Evidence",
            "tab_text": "Quoted row number should not break tabs.",
        }
    )
    quoted_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Selector regression.",
            items=[quoted],
        )
    )
    quoted_ok = (
        'data-anchor="row-1-D&quot;1"' in quoted_body
        and 'data-target="row-1-D&quot;1"' in quoted_body
        and "findTarget(spread,tab.dataset.target)" in quoted_body
        and "tab.dataset.target+'" not in quoted_body
    )
    duplicate = taxmate_taxpack.guide_item(
        {
            "number": "D1",
            "ato_area": "Other",
            "question": "Duplicate number?",
            "answer": "User-entered value",
            "why_included": "Duplicate anchor regression.",
            "status": "Evidence",
            "tab_text": "Duplicate row should keep its own target.",
        }
    )
    duplicate_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Duplicate regression.",
            items=[duplicate, duplicate],
        )
    )
    duplicate_anchors = re.findall(r'<td data-anchor="([^"]+)"', duplicate_body)
    duplicate_targets = [
        target
        for target in re.findall(r'<div class="tab [^"]+" data-target="([^"]+)"', duplicate_body)
        if target.startswith("row-")
    ]
    source_url = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/records-you-need-to-keep"
    second_url = "https://www.ato.gov.au/individuals-and-families/your-tax-return/how-to-lodge-your-tax-return"
    sourced = taxmate_taxpack.guide_item(
        {
            "number": "S1",
            "ato_area": "Other",
            "question": "Has source?",
            "answer": "User-entered value",
            "why_included": "Source provenance regression.",
            "source_url": source_url,
            "source_urls": [source_url, second_url],
            "checked_at": "2026-06-28T00:00:00Z",
            "status": "Evidence",
            "tab_text": "Source row should keep provenance.",
        }
    )
    sourced_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Source regression.",
            items=[sourced],
        )
    )
    sourced_ok = (
        f'<span class="source-url">{source_url}</span>' in sourced_body
        and f'<span class="source-url">{second_url}</span>' in sourced_body
        and '<span class="checked-at">Checked 2026-06-28T00:00:00Z</span>' in sourced_body
        and sourced_body.count(f'<span class="source-url">{source_url}</span>') == 1
    )
    stale_kinds = ["evidence", "answer", "ato", "skipped", "grey"]
    downgraded_badges = [
        '<span class="status gap">Evidence</span>',
        '<span class="status used">Used</span>',
        '<span class="status label">ATO label</span>',
        '<span class="status skipped">N/A skipped</span>',
    ]
    conflicting_ok = True
    for status_kind in stale_kinds:
        for tab_kind in stale_kinds:
            conflicting = taxmate_taxpack.guide_item(
                {
                    "number": "R1",
                    "ato_area": "Other",
                    "question": "Conflicting status?",
                    "answer": "User-entered value",
                    "why_included": "Explicit review status must not be downgraded.",
                    "status": "Accountant review",
                    "status_kind": status_kind,
                    "tab_kind": tab_kind,
                    "tab_text": "Conflicting status fields require accountant review.",
                }
            )
            conflicting_body = taxmate_taxpack.render_html(
                taxmate_taxpack.GuideData(
                    income_year="2025-26",
                    generated_date=taxmate_taxpack.default_generated_date(),
                    summary_note="Conflicting status regression.",
                    items=[conflicting],
                )
            )
            if not (
                conflicting.status_kind == "review"
                and conflicting.tab_kind == "review"
                and '<span class="status review-badge">Accountant review</span>' in conflicting_body
                and 'class="tab red review"' in conflicting_body
                and '<ul class="review-list">' in conflicting_body
                and "<li>Conflicting status fields require accountant review.</li>" in conflicting_body
                and not any(badge in conflicting_body for badge in downgraded_badges)
            ):
                conflicting_ok = False
    for review_field in ("status", "status_kind", "tab_kind"):
        raw = {
            "number": "R1",
            "ato_area": "Other",
            "question": "Split status?",
            "answer": "User-entered value",
            "why_included": "Any explicit review field must control output.",
            "status": "Evidence",
            "status_kind": "evidence",
            "tab_kind": "evidence",
            "tab_text": "One field still requires accountant review.",
        }
        raw[review_field] = "Accountant review"
        conflicting = taxmate_taxpack.guide_item(raw)
        conflicting_body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date=taxmate_taxpack.default_generated_date(),
                summary_note="Split status regression.",
                items=[conflicting],
            )
        )
        if not (
            conflicting.status_kind == "review"
            and conflicting.tab_kind == "review"
            and "<li>One field still requires accountant review.</li>" in conflicting_body
            and not any(badge in conflicting_body for badge in downgraded_badges)
        ):
            conflicting_ok = False
    review_like_labels = [
        "Accountant review required",
        "Requires accountant review",
        "Review required",
        "Needs review",
        "Tax agent review required",
    ]
    for label in review_like_labels:
        conflicting = taxmate_taxpack.guide_item(
            {
                "number": "R1",
                "ato_area": "Other",
                "question": "Review-like label?",
                "answer": "User-entered value",
                "why_included": "Review-like status labels must not be downgraded.",
                "status": label,
                "status_kind": "evidence",
                "tab_kind": "answer",
                "tab_text": "Review-like label requires accountant review.",
            }
        )
        conflicting_body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date=taxmate_taxpack.default_generated_date(),
                summary_note="Review-like status regression.",
                items=[conflicting],
            )
        )
        if not (
            conflicting.status_kind == "review"
            and conflicting.tab_kind == "review"
            and '<span class="status review-badge">Accountant review</span>' in conflicting_body
            and "<li>Review-like label requires accountant review.</li>" in conflicting_body
            and not any(badge in conflicting_body for badge in downgraded_badges)
        ):
            conflicting_ok = False
    blank_review = taxmate_taxpack.guide_item(
        {
            "number": "R2",
            "ato_area": "Other",
            "question": "Blank review explanation?",
            "answer": "User-entered value",
            "status": "Accountant review",
            "status_kind": "review",
            "tab_kind": "review",
        }
    )
    blank_review_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Blank review regression.",
            items=[blank_review],
        )
    )
    blank_review_ok = (
        blank_review.tab_text == "Row R2: Accountant review."
        and "<li>Row R2: Accountant review.</li>" in blank_review_body
        and "<p>Row R2: Accountant review.</p>" in blank_review_body
    )
    direct_blank = taxmate_taxpack.GuideItem(
        number="R3",
        ato_area="Other",
        question="Direct blank review?",
        answer="User-entered value",
        why_included="",
        source_urls=[],
        checked_at="",
        status="Accountant review",
        status_kind="review",
        tab_title="Row R3 direct review",
        tab_text="",
        tab_kind="review",
    )
    direct_blank_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Direct blank review regression.",
            items=[direct_blank],
        )
    )
    direct_blank_ok = (
        "<li>Row R3: Accountant review.</li>" in direct_blank_body
        and "<p>Row R3: Accountant review.</p>" in direct_blank_body
    )
    direct_conflict = taxmate_taxpack.GuideItem(
        number="R4",
        ato_area="Other",
        question="Direct conflicting review?",
        answer="User-entered value",
        why_included="",
        source_urls=[],
        checked_at="",
        status="Accountant review required",
        status_kind="evidence",
        tab_title="Row R4 direct conflict",
        tab_text="",
        tab_kind="answer",
    )
    direct_conflict_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Direct conflict regression.",
            items=[direct_conflict],
        )
    )
    direct_conflict_ok = (
        '<span class="status review-badge">Accountant review</span>' in direct_conflict_body
        and 'class="tab red review"' in direct_conflict_body
        and "<li>Row R4: Accountant review.</li>" in direct_conflict_body
    )
    extended_review_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Extended review regression.",
            items=[],
            abn_items=[
                taxmate_taxpack.GuideItem(
                    number="ABN",
                    ato_area="Sole-trader ABN",
                    question="ABN review row?",
                    answer="Income 100.00; expenses 40.00",
                    why_included="Extended ABN review must appear in side tabs and queue.",
                    source_urls=[],
                    checked_at="",
                    status="Accountant review",
                    status_kind="review",
                    tab_title="ABN review",
                    tab_text="ABN review queue text.",
                    tab_kind="review",
                )
            ],
            bas_items=[
                taxmate_taxpack.GuideItem(
                    number="BAS",
                    ato_area="BAS worksheet",
                    question="BAS review row?",
                    answer="1A 10.00; 1B 5.00; net GST 5.00",
                    why_included="Extended BAS review must appear in side tabs and queue.",
                    source_urls=[],
                    checked_at="",
                    status="Accountant review",
                    status_kind="review",
                    tab_title="BAS review",
                    tab_text="BAS review queue text.",
                    tab_kind="review",
                )
            ],
            missing_facts=[
                taxmate_taxpack.GuideItem(
                    number="MISS-1",
                    ato_area="Missing facts",
                    question="Missing review row?",
                    answer="Missing WFH weekdays",
                    why_included="Missing review rows must have tab targets.",
                    source_urls=[],
                    checked_at="",
                    status="Accountant review",
                    status_kind="review",
                    tab_title="Missing review",
                    tab_text="Missing review queue text.",
                    tab_kind="review",
                )
            ],
            evidence_items=[
                taxmate_taxpack.GuideItem(
                    number="EVID-1",
                    ato_area="Evidence",
                    question="Evidence review row?",
                    answer="Missing receipt",
                    why_included="Evidence review rows must have tab targets.",
                    source_urls=[],
                    checked_at="",
                    status="Accountant review",
                    status_kind="review",
                    tab_title="Evidence review",
                    tab_text="Evidence review queue text.",
                    tab_kind="review",
                )
            ],
        )
    )
    extended_review_ok = (
        'data-anchor="row-201-ABN"' in extended_review_body
        and 'data-target="row-201-ABN"' in extended_review_body
        and 'data-anchor="row-301-BAS"' in extended_review_body
        and 'data-target="row-301-BAS"' in extended_review_body
        and 'data-anchor="row-401-MISS-1"' in extended_review_body
        and 'data-target="row-401-MISS-1"' in extended_review_body
        and 'data-anchor="row-501-EVID-1"' in extended_review_body
        and 'data-target="row-501-EVID-1"' in extended_review_body
        and "<li>ABN review queue text.</li>" in extended_review_body
        and "<li>BAS review queue text.</li>" in extended_review_body
        and "<li>Missing review queue text.</li>" in extended_review_body
        and "<li>Evidence review queue text.</li>" in extended_review_body
        and "ABN review queue text.; BAS review queue text." not in extended_review_body
    )
    falsey = taxmate_taxpack.guide_item(
        {
            "number": 0,
            "ato_area": 0,
            "question": False,
            "answer": 0,
            "why_included": 0,
            "checked_at": 0,
            "status": "Evidence",
            "tab_title": 0,
            "tab_text": 0,
            "source_urls": [False],
        }
    )
    falsey_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Falsey value regression.",
            items=[falsey],
        )
    )
    falsey_ok = (
        falsey.number == "0"
        and falsey.ato_area == "0"
        and falsey.question == "false"
        and falsey.answer == "0"
        and falsey.why_included == "0"
        and falsey.checked_at == "0"
        and falsey.tab_title == "0"
        and falsey.tab_text == "0"
        and falsey.source_urls == ["false"]
        and "<td>0</td>" in falsey_body
        and "<td>false</td>" in falsey_body
        and "<b>0</b>" in falsey_body
        and "<p>0</p>" in falsey_body
        and "Checked 0" in falsey_body
        and '<span class="source-url">false</span>' in falsey_body
    )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json") as handle:
        json.dump(
            {
                "income_year": 0,
                "generated_date": False,
                "summary_note": 0,
                "items": [
                    {
                        "number": 0,
                        "ato_area": 0,
                        "question": False,
                        "answer": 0,
                        "why_included": 0,
                        "status": "Evidence",
                    }
                ],
            },
            handle,
        )
        handle.flush()
        falsey_file = taxmate_taxpack.load_guide_data(handle.name)
    falsey_file_body = taxmate_taxpack.render_html(falsey_file)
    falsey_file_ok = (
        falsey_file.income_year == "0"
        and falsey_file.generated_date == "false"
        and falsey_file.summary_note == "0"
        and "Income year 0" in falsey_file_body
        and "Generated false" in falsey_file_body
        and "0</p>" in falsey_file_body
    )
    direct_falsey = taxmate_taxpack.GuideItem(
        number=0,
        ato_area=0,
        question=False,
        answer=0,
        why_included=0,
        source_urls=[0],
        checked_at=0,
        status="Evidence",
        status_kind="evidence",
        tab_title=0,
        tab_text=0,
        tab_kind="evidence",
    )
    direct_falsey_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Direct falsey value regression.",
            items=[direct_falsey],
        )
    )
    direct_falsey_ok = (
        "<td>0</td>" in direct_falsey_body
        and "<td>false</td>" in direct_falsey_body
        and '<span class="source-url">0</span>' in direct_falsey_body
        and "<b>0</b>" in direct_falsey_body
        and "<p>0</p>" in direct_falsey_body
        and "Checked 0" in direct_falsey_body
        and 'data-anchor="row-1-0"' in direct_falsey_body
    )
    direct_blank_false_number = taxmate_taxpack.GuideItem(
        number=False,
        ato_area="Other",
        question="Direct false number?",
        answer=0,
        why_included="",
        source_urls=[],
        checked_at="",
        status="Accountant review",
        status_kind="review",
        tab_title="Direct false number",
        tab_text="",
        tab_kind="review",
    )
    direct_blank_false_number_body = taxmate_taxpack.render_html(
        taxmate_taxpack.GuideData(
            income_year="2025-26",
            generated_date=taxmate_taxpack.default_generated_date(),
            summary_note="Direct false number fallback.",
            items=[direct_blank_false_number],
        )
    )
    direct_blank_false_number_ok = (
        "Row false: Accountant review." in direct_blank_false_number_body
        and 'data-anchor="row-1-false"' in direct_blank_false_number_body
    )
    return (
        quoted_ok
        and duplicate_anchors == ["row-1-D1", "row-2-D1"]
        and duplicate_targets == ["row-1-D1", "row-2-D1"]
        and sourced_ok
        and conflicting_ok
        and blank_review_ok
        and direct_blank_ok
        and direct_conflict_ok
        and extended_review_ok
        and falsey_ok
        and falsey_file_ok
        and direct_falsey_ok
        and direct_blank_false_number_ok
    )


def validate_json_uses_check_field() -> bool:
    report, _ = finish("", [{"check": "sample", "passed": True, "detail": ""}], None, False)
    checks = report.get("checks", [])
    if not isinstance(checks, list) or not checks:
        return False
    first = checks[0]
    return isinstance(first, dict) and first.get("check") == "sample" and "name" not in first


def save_registry_stamps_refreshed_at() -> bool:
    work_root = tempfile.mkdtemp(prefix="taxmate-validate-registry-save-")
    try:
        registry = atodata.SourceRegistry(fetched_at="2000-01-01T00:00:00Z", refreshed_at="2000-01-01T00:00:00Z")
        atodata.SaveRegistry(work_root, registry)
        saved = atodata.LoadRegistry(work_root)
        return saved.refreshed_at != "2000-01-01T00:00:00Z" and saved.refreshed_at.endswith("Z")
    except Exception:
        return False
    finally:
        import shutil

        shutil.rmtree(work_root, ignore_errors=True)


def recrawl_link_host_filter_strict() -> bool:
    body = b"""
    <a href="https://www.ato.gov.au.evil/tax-rates-and-codes/x">bad host</a>
    <a href="https://www.ato.gov.au@evil.example/tax-rates-and-codes/x">bad userinfo</a>
    <a href="https://user@www.ato.gov.au/tax-rates-and-codes/x">bad user</a>
    <a href="/tax-rates-and-codes/tax-rates-australian-residents">good</a>
    """
    links = atodata.DiscoverLinks("https://www.ato.gov.au/tax-rates-and-codes", body)
    return links == ["https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents"]


def super_seed_matches_registry(registry) -> bool:
    canonical = "https://www.ato.gov.au/businesses-and-organisations/super-for-employers/paying-super-contributions/how-much-super-to-pay"
    stale = "https://www.ato.gov.au/businesses-and-organisations/super-for-employers/paying-super-contributions/how-much-to-pay"
    seed_ok = canonical in atodata.SEED_URLS and stale not in atodata.SEED_URLS
    registry_ok = any(rec.url == canonical or rec.final_url == canonical for rec in registry.records)
    return seed_ok and registry_ok


def required_topics() -> List[str]:
    return [topic.slug for topic in skillgen.Topics()]


def load_per_skill_sources(root: str, skills: List[str]) -> Tuple[Optional[Dict[str, Dict[str, skillgen.Source]]], Optional[Exception]]:
    per_skill: Dict[str, Dict[str, skillgen.Source]] = {}
    for topic in skills:
        path = os.path.join(root, "skills", topic, "references", "sources.json")
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except OSError as exc:
            return None, exc
        except json.JSONDecodeError as exc:
            return None, exc
        if not isinstance(payload, list):
            return None, ValueError(f"invalid sources list: {path}")

        by_id: Dict[str, skillgen.Source] = {}
        for row in payload:
            if not isinstance(row, dict):
                return None, ValueError(f"invalid source row in {path}")
            source = row.get("source_id", "")
            if not source:
                return None, ValueError(f"missing source_id in {path}")
            if source in by_id:
                return None, ValueError(f"duplicate source_id {source} in {path}")
            src = skillgen.Source(
                source_id=source,
                url=str(row.get("url", "")),
                final_url=str(row.get("final_url", row.get("FinalURL", ""))),
                title=str(row.get("title", "")),
                assigned_skill=str(row.get("assigned_skill", row.get("AssignedSkill", ""))),
                status=str(row.get("status", row.get("Status", ""))),
                checked_at=str(row.get("checked_at", row.get("CheckedAt", ""))),
                content_hash=str(row.get("content_hash", row.get("ContentHash", ""))),
                reason=str(row.get("reason", row.get("Reason", ""))),
                assignment_reason=str(row.get("assignment_reason", row.get("AssignmentReason", ""))),
                reference=str(row.get("reference", row.get("Reference", ""))),
                duplicate_of=str(row.get("duplicate_of", row.get("DuplicateOf", ""))),
            )
            by_id[source] = src
        per_skill[topic] = by_id
    return per_skill, None


def haystack(root: str, idx) -> str:
    out = []
    for rec in idx.records:
        out.append(rec.title)
        out.append(rec.url)
        out.append(rec.final_url)

    text_dir = os.path.join(atodata.DataDir(root), "text")
    for path, body in walk_files_with_suffix(text_dir, ".txt"):
        out.append(os.path.basename(path))
        if len(body) > 20000:
            body = body[:20000]
        out.append(body)

    for base in (os.path.join(root, "skills"), os.path.join(root, "data", "ato_knowledge_base")):
        for path, body in walk_files_with_suffixes(base, [".md", ".json"]):
            out.append(os.path.basename(path))
            if len(body) > 40000:
                body = body[:40000]
            out.append(body)
    return "\n".join(out).lower()


def walk_files_with_suffix(base: str, suffix: str):
    if not os.path.isdir(base):
        return
    for entry in os.listdir(base):
        path = os.path.join(base, entry)
        if os.path.isdir(path):
            yield from walk_files_with_suffix(path, suffix)
        elif path.endswith(suffix):
            try:
                yield path, Path(path).read_text(encoding="utf-8")
            except OSError:
                continue


def walk_files_with_suffixes(base: str, suffixes: List[str]):
    if not os.path.isdir(base):
        return
    for entry in os.listdir(base):
        path = os.path.join(base, entry)
        if os.path.isdir(path):
            yield from walk_files_with_suffixes(path, suffixes)
        elif any(path.endswith(item) for item in suffixes):
            try:
                yield path, Path(path).read_text(encoding="utf-8")
            except OSError:
                continue


def contains_any(hay: str, needles: List[str]) -> bool:
    return any(needle in hay for needle in needles)


def first_n(values: List[str], n: int) -> List[str]:
    return values if len(values) <= n else values[:n]


def relative_paths(root: str, paths: List[str]) -> List[str]:
    return [relative_path(root, value) for value in paths]


def relative_path(root: str, path: str) -> str:
    try:
        rel = os.path.relpath(path, root)
        return rel if not rel.startswith("..") else path
    except Exception:
        return path


def find_by_suffix(root: str, suffix: str) -> List[str]:
    if not os.path.isdir(root):
        return []

    out: List[str] = []
    for path in Path(root).rglob("*"):
        if path.is_file():
            if suffix == "" or str(path).endswith(suffix):
                out.append(str(path))
    return out


def topic_queries() -> Dict[str, List[str]]:
    return {
        "wfh_fixed_rate_2025_26": ["working-from-home-expenses/fixed-rate-method", "70 cents per work hour"],
        "wfh_actual_cost": ["working-from-home-expenses/actual-cost-method"],
        "employee_records": ["records-you-need-to-keep", "work-related expenses"],
        "employee_software_assets": ["computers-laptops-and-software", "assets-costing-300"],
        "abn_business_income": ["assessable-income", "business-partnership-and-trust-income"],
        "abn_business_deductions": ["deductions-for-digital-product-expenses", "deductions-for-other-operating-expenses"],
        "abn_business_losses": ["business-losses"],
        "psi": ["personal-services-income"],
        "home_business": ["deductions-for-home-based-business-expenses", "home-based-business-and-cgt-implications"],
        "gst_credits": ["claiming-gst-credits", "when-you-can-claim-a-gst-credit"],
        "gst_tax_invoices": ["tax-invoices"],
        "gst_bas": ["business-activity-statements-bas", "goods-and-services-tax-gst"],
        "payg_instalments": ["payg instalments", "instalment notices"],
        "payg_withholding": ["payg withholding", "tax tables"],
        "stp_income_statements": ["single touch payroll", "income statement"],
        "fbt": ["fringe benefits tax", "gross-up rate"],
        "investments_income": ["income-you-must-declare/investment-income", "shares-funds-and-trusts"],
        "cgt_calculation": ["calculating your cgt", "cgt discount"],
        "shares_cgt": ["capital-gains-tax/shares-and-similar-investments", "dividend-reinvestment-plans"],
        "crypto_records": ["crypto-asset-investments", "keeping crypto records"],
        "rental_property_records": ["records-for-rental-properties-and-holiday-homes", "rental properties"],
        "non_commercial_losses": ["non-commercial loss", "business-losses", "business versus hobby"],
        "tpar": ["taxable payments annual report", "contractor payments"],
        "super": ["personal-super-contributions", "concessional-contributions", "super guarantee"],
        "private_health": ["private-health-insurance-rebate", "medicare-levy-surcharge"],
    }


def stale_seed_replacements() -> Dict[str, List[str]]:
    return {
        "deductions-you-can-claim/tools-and-equipment": ["tools-and-equipment-to-perform-your-work"],
        "deductions-you-can-claim/other-work-related-deductions": ["deductions-you-can-claim/claiming-deductions"],
        "income-and-deductions-for-business/business-income": ["income-and-deductions-for-business/assessable-income"],
        "claiming-a-tax-deduction-for-business-expenses": ["income-and-deductions-for-business/deductions"],
        "deductions/motor-vehicle-and-car-expenses": ["deductions-for-motor-vehicle-expenses"],
        "gst-credits-and-income-tax-deductions": ["effect-of-gst-credits-on-income-tax-deductions"],
        "managed-investment-funds": ["shares-funds-and-trusts", "trust-non-assessable-payments-cgt-event-e4"],
        "investments-and-assets/investment-income": ["income-you-must-declare/investment-income"],
        "how-to-save-more-in-your-super/personal-super-contributions": [
            "super/growing-and-keeping-track-of-your-super/how-to-save-more-in-your-super/personal-super-contributions"
        ],
        "claiming-deductions-for-personal-super-contributions": ["personal-super-contributions"],
    }


def main(argv: Optional[List[str]] = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
