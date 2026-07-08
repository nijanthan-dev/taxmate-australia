#!/usr/bin/env python3
"""Source-to-runtime coverage audit command."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


VALID_STATUSES = {"structured", "triage_only", "review_only", "source_only", "out_of_scope"}
GENERIC_SOURCE_CONCEPTS = {
    "abn",
    "allowance",
    "allowances",
    "bas",
    "business",
    "cgt",
    "deduction",
    "deductions",
    "gst",
    "income",
    "investment",
    "investments",
    "super",
}


def repo_root() -> Path:
    explicit = os.environ.get("TAXMATE_AUSTRALIA_ROOT")
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
        if candidate.joinpath(".codex-plugin", "plugin.json").exists():
            return candidate
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if candidate.joinpath(".codex-plugin", "plugin.json").exists():
            return candidate
    return Path.cwd()


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must be a JSON object")
    return payload


def manifest_path(root: Path) -> Path:
    return root / "config" / "runtime-coverage.json"


def source_coverage_path(root: Path) -> Path:
    return root / "data" / "ato_knowledge_base" / "source_coverage.json"


def load_manifest(root: Path) -> Dict[str, Any]:
    payload = load_json(manifest_path(root))
    concepts = payload.get("concepts")
    if not isinstance(concepts, list):
        raise ValueError("runtime coverage manifest requires concepts list")
    return payload


def load_source_coverage(root: Path) -> Dict[str, Any]:
    return load_json(source_coverage_path(root))


def normalized_terms(values: Iterable[Any]) -> set[str]:
    terms: set[str] = set()
    for value in values:
        text = str(value).casefold().strip()
        if not text:
            continue
        terms.add(text)
        terms.add(text.replace(" ", "-"))
        terms.add(text.replace("-", " "))
    return terms


def source_matches(entry: Dict[str, Any], concept: Dict[str, Any]) -> bool:
    source_ids = {str(value) for value in concept.get("source_ids", [])}
    source_urls = {str(value) for value in concept.get("source_urls", [])}
    if source_ids or source_urls:
        entry_urls = {str(entry.get("canonical_url", "")), str(entry.get("original_url", ""))}
        return str(entry.get("source_id", "")) in source_ids or bool(source_urls.intersection(entry_urls))
    source_skills = {str(value) for value in concept.get("source_skills", [])}
    source_concepts = normalized_terms(concept.get("source_concepts", []))
    entry_skills = {str(value) for value in entry.get("skills", [])}
    covered_concepts = normalized_terms(entry.get("covered_concepts", []))
    specific_source_concepts = source_concepts.difference(GENERIC_SOURCE_CONCEPTS)
    if specific_source_concepts:
        source_concepts = specific_source_concepts
    return bool(source_skills.intersection(entry_skills)) and (
        not source_concepts or bool(source_concepts.intersection(covered_concepts))
    )


def verified_source_count(sources: Iterable[Dict[str, Any]], concept: Dict[str, Any]) -> int:
    return sum(1 for entry in sources if entry.get("status") == "verified" and source_matches(entry, concept))


def source_pin_errors(sources: Iterable[Dict[str, Any]], concept: Dict[str, Any]) -> List[str]:
    concept_id = str(concept.get("id", ""))
    verified_ids: set[str] = set()
    verified_urls: set[str] = set()
    for entry in sources:
        if entry.get("status") != "verified":
            continue
        verified_ids.add(str(entry.get("source_id", "")))
        verified_urls.update(str(entry.get(key, "")) for key in ("canonical_url", "original_url"))
    errors: List[str] = []
    for source_id in concept.get("source_ids", []):
        if str(source_id) not in verified_ids:
            errors.append(f"{concept_id} source_id not verified: {source_id}")
    for source_url in concept.get("source_urls", []):
        if str(source_url) not in verified_urls:
            errors.append(f"{concept_id} source_url not verified: {source_url}")
    return errors


def audit_payload(root: Path | str | None = None) -> Dict[str, Any]:
    root = Path(root) if root is not None else repo_root()
    manifest = load_manifest(root)
    coverage = load_source_coverage(root)
    sources = coverage.get("sources", [])
    if not isinstance(sources, list):
        raise ValueError("source_coverage sources must be a list")
    rows: List[Dict[str, Any]] = []
    for concept in manifest["concepts"]:
        row = dict(concept)
        row["source_count"] = verified_source_count(sources, concept)
        rows.append(row)
    return {
        "manifest": str(manifest_path(root)),
        "source_coverage": str(source_coverage_path(root)),
        "summary": {
            "concepts": len(rows),
            "structured": sum(1 for row in rows if row.get("runtime_status") == "structured"),
            "triage_or_review": sum(1 for row in rows if row.get("runtime_status") in {"triage_only", "review_only"}),
            "source_only": sum(1 for row in rows if row.get("runtime_status") == "source_only"),
        },
        "concepts": rows,
    }


def validate_manifest(root: Path | str | None = None) -> Tuple[bool, List[str]]:
    root = Path(root) if root is not None else repo_root()
    errors: List[str] = []
    try:
        payload = audit_payload(root)
        coverage = load_source_coverage(root)
    except Exception as exc:
        return False, [str(exc)]
    sources = coverage.get("sources", [])
    if not isinstance(sources, list):
        return False, ["source_coverage sources must be a list"]
    seen: set[str] = set()
    for row in payload["concepts"]:
        concept_id = str(row.get("id", ""))
        status = row.get("runtime_status")
        if not concept_id:
            errors.append("concept missing id")
        if concept_id in seen:
            errors.append(f"duplicate concept id {concept_id}")
        seen.add(concept_id)
        if status not in VALID_STATUSES:
            errors.append(f"{concept_id} invalid runtime_status {status}")
        if status == "structured" and (not row.get("runtime_functions") or not row.get("tests")):
            errors.append(f"{concept_id} structured concepts need runtime_functions and tests")
        if status in {"triage_only", "review_only", "source_only"} and not row.get("issue"):
            errors.append(f"{concept_id} non-structured concepts need linked issue")
        if row.get("source_count", 0) == 0 and status != "out_of_scope":
            errors.append(f"{concept_id} has no verified source matches")
        errors.extend(source_pin_errors(sources, row))
        for rel in row.get("docs", []):
            if not root.joinpath(str(rel)).exists():
                errors.append(f"{concept_id} doc missing: {rel}")
    required = {
        "employment-deductions",
        "phone-deductions",
        "wfh-fixed-rate",
        "wfh-actual-cost-occupancy",
        "abn-business-categories",
        "gst-bas-special-topics",
        "private-health-medicare-spouse-dependants",
        "super-contribution-deductions",
        "government-payments",
        "fbt-rfba-triage",
        "cgt-crypto-rental-investments",
    }
    missing = sorted(required.difference(seen))
    if missing:
        errors.append("missing required concepts: " + ", ".join(missing))
    return not errors, errors


def render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# Runtime Coverage Audit",
        "",
        "| Concept | Status | Sources | Runtime | Tests | Issue |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for row in payload["concepts"]:
        runtime = ", ".join(row.get("runtime_functions", [])) or "none"
        tests = ", ".join(row.get("tests", [])) or "none"
        lines.append(
            f"| {row.get('title', row.get('id'))} | {row.get('runtime_status')} | {row.get('source_count', 0)} | {runtime} | {tests} | {row.get('issue', '')} |"
        )
    return "\n".join(lines) + "\n"


def run(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="./scripts/taxmate coverage", description="Audit source-to-runtime coverage.")
    sub = parser.add_subparsers(dest="command")
    audit = sub.add_parser("audit", help="Print source-to-runtime coverage.")
    audit.add_argument("--format", choices=["json", "markdown"], default="markdown")
    args = parser.parse_args(argv)
    if args.command != "audit":
        parser.print_help()
        return 1
    payload = audit_payload()
    ok, errors = validate_manifest()
    if args.format == "json":
        payload["valid"] = ok
        payload["errors"] = errors
        print(json.dumps(payload, indent=2))
    else:
        print(render_markdown(payload), end="")
        if errors:
            print("\nValidation errors:", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:]))
