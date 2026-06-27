#!/usr/bin/env python3
"""TaxMate Australia validation command implementation (Python replacement)."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
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


EMPTY_CONTENT = skillgen.EmptyContentHashValue


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
    add("description_nonempty", all_skill_descriptions_long(root, required_skills), "")
    add(
        "portable_root_documented",
        (
            "portable" in readme_text.lower()
            and "TaxMate Australia path" in readme_text
            and "python3" in readme_text
        )
        or ("./scripts/taxmate" in readme_text and "Optional portable install" in readme_text),
        "",
    )
    full_runtime_text = read_text(os.path.join(root, "docs", "FULL_PLUGIN_INSTALL.md")) + read_text(
        os.path.join(root, "docs", "SKILL_GENERATION.md")
    )
    add(
        "python_runtime_documented",
        "scripts/taxmate.py" in full_runtime_text
        and "./scripts/taxmate" in full_runtime_text
        and "taxmate.py refresh" in full_runtime_text,
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
    add("plugin_lock_skill_paths_exist", plugin_lock_skill_paths_exist(root), "")
    add("wrapper_fallback_skill_paths_exist", wrapper_fallback_skill_paths_exist(root), "")


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
    bash5_hits = stale_bash5_prereq_hits(root)
    add("docs_no_stale_bash5_requirement", len(bash5_hits) == 0, "; ".join(bash5_hits))
    add("refresh_query_no_match_is_read_only", refresh_query_no_match_is_read_only(root), "")
    add("skills_refresh_unknown_topic_is_noop", skills_refresh_unknown_topic_is_noop(root), "")
    add("skills_refresh_missing_urls_is_read_only", skills_refresh_missing_urls_is_read_only(root), "")
    add("finance_record_rows_classify_before_income", finance_record_rows_classify_before_income(), "")
    add("finance_investment_income_classifies_as_income", finance_investment_income_classifies_as_income(), "")
    add("finance_investment_income_outranks_business_tag", finance_investment_income_outranks_business_tag(), "")
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


def read_plugin_manifest(root: str) -> Tuple[Dict[str, str], Optional[Exception]]:
    try:
        body = Path(os.path.join(root, ".codex-plugin", "plugin.json")).read_text(encoding="utf-8")
        raw = json.loads(body)
    except Exception as exc:
        return {}, exc
    out: Dict[str, str] = {}
    for key in ("name", "version", "skills", "repository"):
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
    for skill in skills:
        path = os.path.join(root, "skills", skill, "SKILL.md")
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


def all_skill_descriptions_long(root: str, skills: List[str]) -> bool:
    for skill in skills:
        path = os.path.join(root, "skills", skill, "SKILL.md")
        try:
            body = Path(path).read_text(encoding="utf-8")
        except OSError:
            return False
        fm = parse_frontmatter(body)
        if fm is None or len(fm.get("description", "")) < 40:
            return False
    return True


def read_text(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError:
        return ""


def public_doc_files(root: str) -> List[str]:
    files = [
        os.path.join(root, "README.md"),
        os.path.join(root, "DISCLAIMER.md"),
        os.path.join(root, ".codex-plugin", "plugin.json"),
        os.path.join(root, ".agents", "plugins", "marketplace.json"),
        os.path.join(root, "agents", "openai.yaml"),
        os.path.join(root, "plugin.lock.json"),
        os.path.join(root, ".gitleaks.toml"),
        os.path.join(root, "SECURITY.md"),
        os.path.join(root, "CONTRIBUTING.md"),
        os.path.join(root, "docs", "PLUGIN_SCANNER.md"),
        os.path.join(root, "docs", "PUBLICATION_CHECKLIST.md"),
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
        text = read_text(path)
        for needle in needles:
            if needle in text:
                hits.append(f"{relative_path(root, path)}:{needle}")
                break
    return hits


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
        if not isinstance(vendored_path, str) or not isinstance(integrity, str):
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
    public_paths = [os.path.join("skills", item) for item in public_manifest.get("portableSkills", []) if isinstance(item, str)]
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


def go_tooling_scan_files() -> List[str]:
    return [
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
        os.path.join(".agents", "plugins", "marketplace.json"),
        os.path.join("agents", "openai.yaml"),
        "plugin.lock.json",
        ".gitleaks.toml",
        "README.md",
        "DISCLAIMER.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        os.path.join("docs", "DEVELOPMENT.md"),
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
        if needle in text:
            hits.append(f"{rel}:{needle}")
    return hits


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
    original = atodata.urllib.request.urlopen

    def fake_urlopen(*_args, **_kwargs):
        raise atodata.HTTPError("https://www.ato.gov.au/missing", 404, "missing", {}, io.BytesIO(b"not found"))

    atodata.urllib.request.urlopen = fake_urlopen
    try:
        fetched = atodata.Fetch("https://www.ato.gov.au/missing")
        return fetched.status == 404 and fetched.body == b"not found"
    except Exception:
        return False
    finally:
        atodata.urllib.request.urlopen = original


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
