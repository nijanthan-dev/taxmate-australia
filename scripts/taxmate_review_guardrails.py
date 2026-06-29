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
TAXPACK_OUTPUT_LAYER = "taxpack_output_layer_contract"
ATO_FETCH_BOUNDARY = "ato_fetch_boundary"
GENERATED_ARTIFACT_CONTRACT = "generated_artifact_contract"
FINANCE_JSON_WIRE_CONTRACT = "finance_json_wire_contract"
CALCULATOR_NUMERIC_CONTRACT = "calculator_numeric_contract"
PUBLIC_CLAIM_SURFACE_CONTRACT = "public_claim_surface_contract"
RELEASE_GUARDRAIL_CONTRACT = "release_guardrail_contract"
ENVIRONMENT_WORKTREE_CONTRACT = "environment_worktree_contract"
LOCAL_PLUGIN_MARKETPLACE_CONTRACT = "local_plugin_marketplace_contract"
PRE_COMMIT_CONTRACT = "pre_commit_contract"
REVIEW_GUARDRAIL_DOCS = "review_guardrail_docs"
MARKETPLACE_ADD_PREFIX = "codex plugin marketplace add "
LOCAL_MARKETPLACE_ADD_COMMAND = "codex plugin marketplace add ."
LOCAL_PLUGIN_ADD_COMMAND = "codex plugin add taxmate-australia@{name}"


@dataclass
class Finding:
    check: str
    detail: str


@dataclass
class ReviewPattern:
    id: str
    check: str
    summary: str


REVIEW_PATTERNS: List[ReviewPattern] = [
    ReviewPattern(
        "PR #7",
        f"{FINANCE_JSON_WIRE_CONTRACT}, {CALCULATOR_NUMERIC_CONTRACT}, {GENERATED_ARTIFACT_CONTRACT}",
        "Preserve public JSON wire formats, reject non-finite numbers, keep half-up cent rounding, preserve generated source provenance, compare tracked generated artifacts, and remove stale Go/runtime docs.",
    ),
    ReviewPattern(
        "PR #8",
        ENVIRONMENT_WORKTREE_CONTRACT,
        "Keep Codex setup/cleanup safe in linked Git worktrees, do not dirty a clean checkout, and avoid unsafe find-delete patterns.",
    ),
    ReviewPattern(
        "PR #10",
        PUBLIC_CLAIM_SURFACE_CONTRACT,
        "Public metadata must describe the real bash and Python runtime.",
    ),
    ReviewPattern(
        "PR #22",
        PUBLIC_CLAIM_SURFACE_CONTRACT,
        "Public claim scanners must include wrappers, discovery docs, workflows, and endorsement phrasing in both directions around ATO.",
    ),
    ReviewPattern(
        "PR #25",
        ATO_FETCH_BOUNDARY,
        "ATO fetches must call curl --disable -L so user curl config cannot alter source refreshes.",
    ),
    ReviewPattern(
        "PR #27",
        TAXPACK_OUTPUT_LAYER,
        "Output layers must preserve Accountant review, source provenance, falsey display values, dynamic generated dates, unique anchors, safe tab target lookup, and neutral mixed-area headings.",
    ),
    ReviewPattern(
        "PR #38",
        LOCAL_PLUGIN_MARKETPLACE_CONTRACT,
        "Local Codex plugin setup docs must point codex plugin marketplace add at the repo root when .agents/plugins/marketplace.json uses source.path ./.",
    ),
    ReviewPattern(
        "Release guardrails",
        RELEASE_GUARDRAIL_CONTRACT,
        "Release workflow edits must preserve green-CI checks, unchanged-main checks, version manifest alignment, and the Release Please bootstrap SHA.",
    ),
]


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


def fail_if_file_missing(root: Path, check: str, rel: str, tokens: Iterable[str]) -> List[Finding]:
    return fail_if_missing(check, read(root, rel), tokens)


def command_lines(text: str) -> List[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def wrong_local_marketplace_commands(commands: Iterable[str]) -> List[str]:
    return [
        command
        for command in commands
        if command.startswith(MARKETPLACE_ADD_PREFIX) and command != LOCAL_MARKETPLACE_ADD_COMMAND
    ]


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
    findings.extend(fail_if_missing(TAXPACK_OUTPUT_LAYER, text, required))
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
        findings.append(Finding(TAXPACK_OUTPUT_LAYER, "forbidden pattern: " + ", ".join(hits)))
    return findings


def check_taxpack_output_layer(root: Path) -> List[Finding]:
    return check_taxpack_output_layer_text(read(root, "scripts/taxmate_taxpack.py"))


def check_fetch_boundary(root: Path) -> List[Finding]:
    text = read(root, "scripts/atodata.py")
    findings: List[Finding] = []
    if "urllib.request.urlopen" in text:
        findings.append(Finding(ATO_FETCH_BOUNDARY, "urllib.request.urlopen must not return"))
    if not contains_in_order(text, ['"curl"', '"--disable"', '"-L"']):
        findings.append(Finding(ATO_FETCH_BOUNDARY, "curl command must start curl, --disable, -L"))
    required = ['"--write-out"', '"%{http_code}\\n%{url_effective}"', "FetchResult(status=status, final_url=final_url, body=body)"]
    findings.extend(fail_if_missing(ATO_FETCH_BOUNDARY, text, required))
    return findings


def check_generated_artifact_contract(root: Path) -> List[Finding]:
    return fail_if_file_missing(
        root,
        GENERATED_ARTIFACT_CONTRACT,
        "scripts/skillgen.py",
        [
            "def gitTrackedGeneratedArtifacts(",
            "def trackedGeneratedArtifacts(",
            "expected_files = set(trackedGeneratedArtifacts(root))",
            "generated_files = set(trackedGeneratedArtifacts(generated_root))",
            "isGeneratedArtifactPath",
            "current-values.json",
            "source_id",
            "checked_at",
            "content_hash",
        ],
    )


def check_finance_and_calc_wire_contract(root: Path) -> List[Finding]:
    finance = read(root, "scripts/taxmate_finance.py")
    calc = read(root, "scripts/taxmate_calc.py")
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            FINANCE_JSON_WIRE_CONTRACT,
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
            CALCULATOR_NUMERIC_CONTRACT,
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
        findings.append(Finding(CALCULATOR_NUMERIC_CONTRACT, "use Decimal ROUND_HALF_UP, not builtin round"))
    return findings


def check_public_claim_surfaces(root: Path) -> List[Finding]:
    return fail_if_file_missing(
        root,
        PUBLIC_CLAIM_SURFACE_CONTRACT,
        "scripts/taxmate_validate.py",
        [
            'os.path.join("docs", "DISCOVERY.md")',
            '"wrappers"',
            '"docs"',
            'os.path.join(".github", "workflows", "ci.yml")',
            'os.path.join(".github", "workflows", "release.yml")',
            'os.path.join(".github", "dependabot.yml")',
            "ato_endorsement_claim_hits",
            "public_metadata_no_go_runtime_claims",
        ],
    )


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
    findings.extend(fail_if_missing(RELEASE_GUARDRAIL_CONTRACT, release, required))
    bootstrap_sha = config.get("bootstrap-sha")
    if not isinstance(bootstrap_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", bootstrap_sha):
        findings.append(Finding(RELEASE_GUARDRAIL_CONTRACT, "release-please-config.json missing 40-char bootstrap-sha"))
    if "workflow_run:" not in release and "automatically" in development.lower():
        findings.append(Finding(RELEASE_GUARDRAIL_CONTRACT, "manual release workflow must not be documented as automatic"))
    return findings


def check_environment_contract(root: Path) -> List[Finding]:
    ci = read(root, ".github/workflows/ci.yml")
    setup = read(root, "scripts/codex-env-setup.sh")
    cleanup = read(root, "scripts/codex-env-cleanup.sh")
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            ENVIRONMENT_WORKTREE_CONTRACT,
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
            findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, f"{rel} must resolve linked worktree root with git rev-parse"))
    if "find " in cleanup and " -delete" in cleanup:
        findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, "cleanup must not combine find -delete with prune"))
    if "PYTHONDONTWRITEBYTECODE" not in setup:
        findings.append(Finding(ENVIRONMENT_WORKTREE_CONTRACT, "setup must disable Python bytecode writes"))
    return findings


def check_local_plugin_marketplace_contract(root: Path) -> List[Finding]:
    marketplace_path = root.joinpath(".agents", "plugins", "marketplace.json")
    docs = read(root, "docs/FULL_PLUGIN_INSTALL.md")
    findings: List[Finding] = []
    try:
        marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, f"invalid .agents/plugins/marketplace.json: {exc}")]

    name = marketplace.get("name")
    plugins = marketplace.get("plugins")
    if not isinstance(name, str) or not name:
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing name"))
    if not isinstance(plugins, list) or not plugins:
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing plugins"))
        return findings

    taxmate_plugin = next((plugin for plugin in plugins if plugin.get("name") == "taxmate-australia"), None)
    if not isinstance(taxmate_plugin, dict):
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing taxmate-australia plugin"))
        return findings

    source = taxmate_plugin.get("source")
    source_path = source.get("path") if isinstance(source, dict) else None
    if source_path == "./":
        commands = command_lines(docs)
        plugin_command = LOCAL_PLUGIN_ADD_COMMAND.format(name=name)
        for command in [LOCAL_MARKETPLACE_ADD_COMMAND, plugin_command]:
            if command not in commands:
                findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, f"missing exact command: {command}"))
        if wrong_local_marketplace_commands(commands):
            findings.append(
                Finding(
                    LOCAL_PLUGIN_MARKETPLACE_CONTRACT,
                    "docs must add repo root exactly because marketplace source.path is ./",
                )
            )
    else:
        findings.append(
            Finding(
                LOCAL_PLUGIN_MARKETPLACE_CONTRACT,
                "unexpected marketplace source.path; update docs and guardrail together",
            )
        )
    return findings


def check_precommit_contract(root: Path) -> List[Finding]:
    findings: List[Finding] = []
    for rel in [".pre-commit-config.yaml", ".githooks/pre-commit"]:
        path = root.joinpath(rel)
        if not path.exists():
            findings.append(Finding(PRE_COMMIT_CONTRACT, f"missing {rel}"))
            continue
        text = path.read_text(encoding="utf-8")
        if "./scripts/taxmate review-guardrails" not in text:
            findings.append(Finding(PRE_COMMIT_CONTRACT, f"{rel} must run ./scripts/taxmate review-guardrails"))
    return findings


def check_review_guardrail_docs(root: Path) -> List[Finding]:
    path = root.joinpath("docs", "DEVELOPMENT.md")
    if not path.exists():
        return [Finding(REVIEW_GUARDRAIL_DOCS, "missing docs/DEVELOPMENT.md")]
    text = path.read_text(encoding="utf-8")
    commands = command_lines(text)
    required_commands = [
        "./scripts/taxmate review-guardrails",
        "./scripts/taxmate review-guardrails --list-patterns",
        "./scripts/taxmate review-guardrails --list-patterns --format json",
    ]
    findings = [
        Finding(REVIEW_GUARDRAIL_DOCS, f"missing exact command: {command}")
        for command in required_commands
        if command not in commands
    ]
    findings.extend(
        fail_if_missing(
            REVIEW_GUARDRAIL_DOCS,
            text,
            [
                "The script is the canonical pattern inventory",
                "Do not duplicate PR pattern bullets",
            ],
        )
    )
    if re.search(r"^- PR #\d+:", text, re.MULTILINE):
        findings.append(Finding(REVIEW_GUARDRAIL_DOCS, "docs must not duplicate PR pattern bullets"))
    return findings


def review_patterns_payload() -> List[dict]:
    return [pattern.__dict__ for pattern in REVIEW_PATTERNS]


def render_review_patterns(fmt: str) -> str:
    if fmt == "json":
        return json.dumps({"patterns": review_patterns_payload()}, indent=2) + "\n"
    if fmt == "markdown":
        lines = ["| Pattern | Guardrail check | Contract |", "| --- | --- | --- |"]
        for pattern in REVIEW_PATTERNS:
            lines.append(f"| {pattern.id} | `{pattern.check}` | {pattern.summary} |")
        return "\n".join(lines) + "\n"
    lines = []
    for pattern in REVIEW_PATTERNS:
        lines.append(f"{pattern.id}: {pattern.check} - {pattern.summary}")
    return "\n".join(lines) + "\n"


CHECKS: List[Callable[[Path], List[Finding]]] = [
    check_taxpack_output_layer,
    check_fetch_boundary,
    check_generated_artifact_contract,
    check_finance_and_calc_wire_contract,
    check_public_claim_surfaces,
    check_release_contract,
    check_environment_contract,
    check_local_plugin_marketplace_contract,
    check_precommit_contract,
    check_review_guardrail_docs,
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
    parser.add_argument("--format", choices=["text", "json", "markdown"], default="text")
    parser.add_argument("--list-patterns", action="store_true", help="Print canonical review-pattern inventory and exit.")
    args = parser.parse_args(argv)
    if args.list_patterns:
        sys.stdout.write(render_review_patterns(args.format))
        return 0
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
