#!/usr/bin/env python3
"""TaxMate Australia validation command implementation (Python replacement)."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

import atodata
import skillgen


EMPTY_CONTENT = skillgen.EmptyContentHashValue


def run(argv: List[str] | None = None) -> int:
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
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

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
    add_runtime_binary_checks(root, add)

    return finish(root, checks, registry, True)


def add_plugin_manifest_checks(root: str, add, manifest: Dict[str, str], manifest_err: Exception | None, manifest_text: str) -> None:
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
    manifest_skill_err: Exception | None,
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


def add_public_disclaimer_checks(add, text: str) -> None:
    add("public_disclaimer_documented", has_public_disclaimers(text), "")


def add_source_coverage_checks(
    root: str,
    add,
    registry,
    coverage: skillgen.SourceCoverage,
    coverage_err: Exception | None,
) -> None:
    add("source_coverage_exists", coverage_err is None, "")
    if coverage_err is not None:
        return

    data_dir = atodata.DataDir(root)
    add("source_coverage_matches_registry", len(coverage.sources) == len(registry.records), "")

    try:
        skillgen.ValidateSourceCoverage(root)
        add("source_coverage_statuses_valid", True, "")
    except Exception as exc:
        add("source_coverage_statuses_valid", False, str(exc))

    add("verified_sources_have_content_hash", all_verified_sources_have_hash(coverage), "")
    add("metadata_only_sources_not_claimed_as_verified", not metadata_only_marked_as_verified(root, coverage), "")
    add("source_records_match_per_skill", source_coverage_matches_skill_files(root, coverage), "")
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


def add_runtime_binary_checks(root: str, add) -> None:
    add("audit_is_read_only", audit_is_read_only(root), "")
    add("generated_skills_validate", is_valid_exception_safe(lambda: skillgen.Validate(root)) is None, "")
    python_backend = (
        file_exists(os.path.join(root, "scripts", "taxmate_skills.py"))
        and file_exists(os.path.join(root, "scripts", "taxmate_validate.py"))
    )
    add("python_backend_exists", python_backend, "")
    add("no_go_source", len(find_by_suffix(root, ".go")) == 0, "")


def is_valid_exception_safe(fn) -> Exception | None:
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


def public_portable_skills(root: str) -> Tuple[List[str], Exception]:
    path = os.path.join(root, "config", "public-skills.json")
    body = Path(path).read_bytes()
    raw = json.loads(body)
    skills = list(raw.get("portableSkills", []))
    if not skills:
        return [], ValueError("portableSkills empty")
    return skills, None


def read_plugin_manifest(root: str) -> Tuple[Dict[str, str], Exception]:
    body = Path(os.path.join(root, ".codex-plugin", "plugin.json")).read_text(encoding="utf-8")
    raw = json.loads(body)
    out: Dict[str, str] = {}
    for key in ("name", "version", "skills"):
        value = raw.get(key)
        if isinstance(value, str):
            out[key] = value
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
        os.path.join(root, "docs", "PLUGIN_SCANNER.md"),
        os.path.join(root, "docs", "PUBLICATION_CHECKLIST.md"),
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


def parse_frontmatter(text: str) -> Dict[str, str] | None:
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


def generation_is_deterministic(root: str) -> Tuple[bool, Exception | None]:
    import shutil

    work_root = tempfile.mkdtemp(prefix="taxmate-validate-generation-check-")
    try:
        atodata.CopyDir(
            os.path.join(root, "data", "ato_knowledge_base"),
            os.path.join(work_root, "data", "ato_knowledge_base"),
        )
        skillgen.Generate(skillgen.Options(root=work_root, output_root=work_root))
        err = skillgen.CompareGeneratedArtifacts(root, work_root)
        return err is None, err
    except Exception as exc:
        return False, exc
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def audit_is_read_only(root: str) -> bool:
    try:
        skillgen.WriteCoverageReport(root, "markdown")
        return True
    except Exception:
        return False


def required_topics() -> List[str]:
    return [topic.slug for topic in skillgen.Topics()]


def load_per_skill_sources(root: str, skills: List[str]) -> Tuple[Dict[str, Dict[str, skillgen.Source]] | None, Exception | None]:
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


def main(argv: List[str] | None = None) -> int:
    return run(argv)


if __name__ == "__main__":
    raise SystemExit(main())
