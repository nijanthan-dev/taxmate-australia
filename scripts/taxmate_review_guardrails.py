#!/usr/bin/env python3
"""Review-pattern guardrails learned from Codex PR feedback."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, List


ROOT_MARKER = os.path.join(".codex-plugin", "plugin.json")


@dataclass
class Finding:
    check: str
    detail: str


def repo_root() -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if candidate.joinpath(ROOT_MARKER).exists():
            return candidate
    return Path.cwd()


def read(root: Path, rel: str) -> str:
    return root.joinpath(rel).read_text(encoding="utf-8")


def contains_in_order(text: str, tokens: Iterable[str]) -> bool:
    offset = 0
    for token in tokens:
        found = text.find(token, offset)
        if found < 0:
            return False
        offset = found + len(token)
    return True


def missing_tokens(text: str, tokens: Iterable[str]) -> List[str]:
    return [token for token in tokens if token not in text]


def fail_if_missing(check: str, text: str, tokens: Iterable[str]) -> List[Finding]:
    missing = missing_tokens(text, tokens)
    if missing:
        return [Finding(check, "missing: " + ", ".join(missing))]
    return []


def check_taxpack_output_layer_text(text: str) -> List[Finding]:
    findings: List[Finding] = []
    required = [
        "def scalar_text(",
        "def text_value(",
        "def source_urls(",
        "def render_provenance(",
        "def is_review_like_key(",
        "def effective_status_kind(",
        "def effective_tab_kind(",
        "def review_text(",
        "def row_anchor(item: GuideItem, row_index: int)",
        "findTarget(spread,value)",
        "el.dataset.anchor===value",
        "default_generated_date()",
        "canonical_status(item_status_kind)",
    ]
    findings.extend(fail_if_missing("taxpack_output_layer_contract", text, required))
    forbidden = [
        'querySelector(`[data-anchor="${',
        "querySelector('[data-anchor=\"' +",
        'querySelector("[data-anchor=\\"" +',
        '"generated_date":',
        " or \"\"",
        " or ''",
    ]
    hits = [token for token in forbidden if token in text]
    if hits:
        findings.append(Finding("taxpack_output_layer_contract", "forbidden pattern: " + ", ".join(hits)))
    return findings


def check_taxpack_output_layer(root: Path) -> List[Finding]:
    return check_taxpack_output_layer_text(read(root, "scripts/taxmate_taxpack.py"))


def check_fetch_boundary(root: Path) -> List[Finding]:
    text = read(root, "scripts/atodata.py")
    findings: List[Finding] = []
    if "urllib.request.urlopen" in text:
        findings.append(Finding("ato_fetch_boundary", "urllib.request.urlopen must not return"))
    if not contains_in_order(text, ['"curl"', '"--disable"', '"-L"']):
        findings.append(Finding("ato_fetch_boundary", "curl command must start curl, --disable, -L"))
    required = ['"--write-out"', '"%{http_code}\\n%{url_effective}"', "FetchResult(status=status, final_url=final_url, body=body)"]
    findings.extend(fail_if_missing("ato_fetch_boundary", text, required))
    return findings


def check_generated_artifact_contract(root: Path) -> List[Finding]:
    text = read(root, "scripts/skillgen.py")
    required = [
        "def gitTrackedGeneratedArtifacts(",
        "def trackedGeneratedArtifacts(",
        "expected_files = set(trackedGeneratedArtifacts(root))",
        "generated_files = set(trackedGeneratedArtifacts(generated_root))",
        "isGeneratedArtifactPath",
        "current-values.json",
        "source_id",
        "checked_at",
        "content_hash",
    ]
    return fail_if_missing("generated_artifact_contract", text, required)


def check_finance_and_calc_wire_contract(root: Path) -> List[Finding]:
    finance = read(root, "scripts/taxmate_finance.py")
    calc = read(root, "scripts/taxmate_calc.py")
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            "finance_json_wire_contract",
            finance,
            [
                '"generated_at"',
                '"findings"',
                "tax_treatment",
                '"bas_summary"',
                "json.dump(payload, out, indent=2, allow_nan=False)",
                "ROUND_HALF_UP",
                "math.isfinite",
            ],
        )
    )
    findings.extend(
        fail_if_missing(
            "calculator_numeric_contract",
            calc,
            [
                "def finite_float(",
                "math.isfinite",
                "ROUND_HALF_UP",
                "json.dump(result, out, indent=2, allow_nan=False)",
            ],
        )
    )
    if re.search(r"\bround\([^)]*\)", calc) or re.search(r"\bround\([^)]*\)", finance):
        findings.append(Finding("calculator_numeric_contract", "use Decimal ROUND_HALF_UP, not builtin round"))
    return findings


def check_public_claim_surfaces(root: Path) -> List[Finding]:
    validate = read(root, "scripts/taxmate_validate.py")
    required = [
        'os.path.join("docs", "DISCOVERY.md")',
        '"wrappers"',
        '"docs"',
        'os.path.join(".github", "workflows", "ci.yml")',
        'os.path.join(".github", "workflows", "release.yml")',
        'os.path.join(".github", "dependabot.yml")',
        "ato_endorsement_claim_hits",
        "public_metadata_no_go_runtime_claims",
    ]
    return fail_if_missing("public_claim_surface_contract", validate, required)


def check_release_contract(root: Path) -> List[Finding]:
    release = read(root, ".github/workflows/release.yml")
    development = read(root, "docs/DEVELOPMENT.md")
    config = json.loads(read(root, "release-please-config.json"))
    findings: List[Finding] = []
    required = [
        "workflow_dispatch:",
        "Require green CI",
        "--workflow CI --branch main --commit",
        "Require main unchanged",
        "git ls-remote origin refs/heads/main",
        "RELEASE_PLEASE_TOKEN",
        "release-please-action@",
        "target-branch: main",
        "manifest-file: .release-please-manifest.json",
    ]
    findings.extend(fail_if_missing("release_guardrail_contract", release, required))
    bootstrap_sha = config.get("bootstrap-sha")
    if not isinstance(bootstrap_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", bootstrap_sha):
        findings.append(Finding("release_guardrail_contract", "release-please-config.json missing 40-char bootstrap-sha"))
    if "workflow_run:" not in release and "automatically" in development.lower():
        findings.append(Finding("release_guardrail_contract", "manual release workflow must not be documented as automatic"))
    return findings


def check_environment_contract(root: Path) -> List[Finding]:
    ci = read(root, ".github/workflows/ci.yml")
    setup = read(root, "scripts/codex-env-setup.sh")
    cleanup = read(root, "scripts/codex-env-cleanup.sh")
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            "environment_worktree_contract",
            ci,
            [
                "bash scripts/test-codex-env-cleanup.sh",
                "bash scripts/test-codex-env-setup-clean.sh",
                "./scripts/taxmate review-guardrails",
            ],
        )
    )
    for rel, text in [("scripts/codex-env-setup.sh", setup), ("scripts/codex-env-cleanup.sh", cleanup)]:
        if "rev-parse --show-toplevel" not in text:
            findings.append(Finding("environment_worktree_contract", f"{rel} must resolve linked worktree root with git rev-parse"))
    if "find " in cleanup and " -delete" in cleanup:
        findings.append(Finding("environment_worktree_contract", "cleanup must not combine find -delete with prune"))
    if "PYTHONDONTWRITEBYTECODE" not in setup:
        findings.append(Finding("environment_worktree_contract", "setup must disable Python bytecode writes"))
    return findings


def check_precommit_contract(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for rel in [".pre-commit-config.yaml", ".githooks/pre-commit"]:
        path = root.joinpath(rel)
        if not path.exists():
            findings.append(Finding("pre_commit_contract", f"missing {rel}"))
            continue
        text = path.read_text(encoding="utf-8")
        if "./scripts/taxmate review-guardrails" not in text:
            findings.append(Finding("pre_commit_contract", f"{rel} must run ./scripts/taxmate review-guardrails"))
    return findings


def check_pattern_docs(root: Path) -> List[Finding]:
    path = root.joinpath("docs", "CODEX_REVIEW_PATTERNS.md")
    if not path.exists():
        return [Finding("review_pattern_docs", "missing docs/CODEX_REVIEW_PATTERNS.md")]
    text = path.read_text(encoding="utf-8")
    required = [
        "PR #7",
        "PR #22",
        "PR #27",
        "falsey",
        "Accountant review",
        "generated artifacts",
        "public claim",
        "Release guardrails",
    ]
    return fail_if_missing("review_pattern_docs", text, required)


CHECKS: List[Callable[[Path], List[Finding]]] = [
    check_taxpack_output_layer,
    check_fetch_boundary,
    check_generated_artifact_contract,
    check_finance_and_calc_wire_contract,
    check_public_claim_surfaces,
    check_release_contract,
    check_environment_contract,
    check_precommit_contract,
    check_pattern_docs,
]


def run(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for check in CHECKS:
        findings.extend(check(root))
    return findings


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="./scripts/taxmate review-guardrails",
        description="Run static guardrails learned from repeated Codex PR review comments.",
    )
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args(argv)
    findings = run(repo_root())
    if args.format == "json":
        payload = {"ok": not findings, "findings": [finding.__dict__ for finding in findings]}
        json.dump(payload, sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif findings:
        for finding in findings:
            print(f"{finding.check}: {finding.detail}", file=sys.stderr)
    else:
        print("review guardrails passed")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
