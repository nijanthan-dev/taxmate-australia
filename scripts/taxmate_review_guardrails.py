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
INDIVIDUAL_INTAKE_CONTRACT = "individual_intake_contract"
ATO_FETCH_BOUNDARY = "ato_fetch_boundary"
GENERATED_ARTIFACT_CONTRACT = "generated_artifact_contract"
FINANCE_JSON_WIRE_CONTRACT = "finance_json_wire_contract"
CALCULATOR_NUMERIC_CONTRACT = "calculator_numeric_contract"
CALCULATOR_TEMPORAL_CONTRACT = "calculator_temporal_scope_contract"
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
        f"{FINANCE_JSON_WIRE_CONTRACT}, {CALCULATOR_NUMERIC_CONTRACT}, {CALCULATOR_TEMPORAL_CONTRACT}, {GENERATED_ARTIFACT_CONTRACT}",
        "Preserve public JSON wire formats, reject non-finite numbers, keep half-up cent rounding, gate year-specific calculators by supported temporal scope, preserve generated source provenance, compare tracked generated artifacts, and remove stale Go/runtime docs.",
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
        "PR #27 / PR #53",
        TAXPACK_OUTPUT_LAYER,
        "Output layers must preserve Accountant review in main and extended sections, source provenance, falsey display values, dynamic generated dates, unique anchors, safe tab target lookup, and neutral mixed-area headings.",
    ),
    ReviewPattern(
        "PR #53 intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "Individual intake must keep missing, malformed, unparseable, or nested unknown answers as Evidence/review, require literal boolean AI confirmation while preserving review-like extraction metadata, keep BAS values as review, use taxpayer state plus state-wide holidays only for supported WFH income years/date ranges, route limited/regional/partial-day public holidays to Evidence, keep unknown WFH parser inputs and incomplete records out of calculated candidates, avoid stale checked-at literals, and keep mixed-use assets under review.",
    ),
    ReviewPattern(
        "PR #55 ESS intake",
        INDIVIDUAL_INTAKE_CONTRACT,
        "ESS intake must normalize nested items field-by-field, preserve item amounts when sibling labels or statements are unknown, reject placeholder-only item labels, and keep concrete statement-only inputs visible for review.",
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


def read_optional(root: Path, rel: str) -> str:
    path = root.joinpath(rel)
    return path.read_text(encoding="utf-8") if path.exists() else ""


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
        "def queue_item_text(",
        "fallback_tab_text(item.number, effective_status_kind(item))",
        "def row_anchor(item: GuideItem, row_index: int)",
        "render_queue(\"Missing facts queue\", data.missing_facts, 400)",
        "render_queue(\"Evidence queue\", data.evidence_items, 500)",
        "def render_queue(title: str, items: List[GuideItem], offset: int)",
        "data-anchor=\"{row_anchor(item, offset + index)}",
        "def rendered_tab_items(",
        "data.abn_items",
        "data.bas_items",
        "data.missing_facts",
        "data.evidence_items",
        "400 + index",
        "500 + index",
        "for item, row_index in tab_items",
        "findTarget(spread,value)",
        "el.dataset.anchor===value",
        "default_generated_date()",
        "canonical_status(item_status_kind)",
        "def malformed_section_item(",
        "def malformed_extraction_row(",
        "def extraction_status_kind(",
        "if raw.get(\"confirmed\") is True:",
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


def check_individual_intake_contract(root: Path) -> List[Finding]:
    text = read(root, "scripts/taxmate_intake.py")
    skill_text = read_optional(root, "skills/individual-return/SKILL.md")
    skill_rules = read_optional(root, "skills/individual-return/references/rules.md")
    findings: List[Finding] = []
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            text,
            [
                "def contains_unknown(",
                "STATE_ALIASES = {",
                "WEEKDAY_ALIASES = {",
                "def normalize_state(",
                "def wfh_answers(",
                "def has_abn_inputs(",
                "def has_bas_inputs(",
                "def parse_gst_registration(",
                "def base_item_status(",
                "REVIEWABLE_COMPLEX_FIELDS = (",
                "isinstance(value, (dict, list))",
                "key in REVIEWABLE_ABN_FIELDS or key in REVIEWABLE_BAS_FIELDS or key == \"gst_registered\"",
                "items.extend(wfh_rows(wfh_answers(answers)))",
                "items.extend(asset_rows(asset_answers(answers)))",
                "gst_registered = answers.get(\"gst_registered\")",
                "gst_status = parse_gst_registration(gst_registered)",
                "unknown_as_missing=True",
                "math.isfinite(amount)",
                "raise ValueError(f\"invalid money value: {value}\") from None",
                "phrase in lowered",
                '"not confirmed"',
                "confirmed = raw.get(\"confirmed\") is True",
                '"confirmed": confirmed',
                "def extraction_status(",
                "def contains_review_status(",
                'taxmate_taxpack.known_kind(value) == "review"',
                "def preserve_review_kinds(",
                "for key in (\"status\", \"status_kind\", \"tab_kind\")",
                "for key in (\"status_kind\", \"tab_kind\")",
                "row[key] = raw.get(key)",
                "state_key = normalize_state(enriched.get(\"state\"))",
                "if state_key is not None:",
                "enriched[\"income_year\"] = text(answers.get(\"income_year\"), DEFAULT_INCOME_YEAR)",
                "state_key = normalize_state(raw.get(\"state\"))",
                "if state_key is None:",
                "state_key = normalize_state(state)",
                "def normalize_state(value: Any) -> Optional[str]:",
                "SUPPORTED_WFH_START = date(2025, 7, 1)",
                "SUPPORTED_WFH_END = date(2026, 6, 30)",
                "LIMITED_PUBLIC_HOLIDAYS_BY_STATE = {",
                '"NSW": {"2025-08-04"}',
                '"TAS": {"2025-10-23", "2025-11-03", "2026-02-09", "2026-04-07"}',
                '"VIC": {"2025-09-26", "2026-03-09", "2026-04-04", "2026-04-05", "2026-06-08"}',
                '"NSW": {"2025-10-06", "2026-04-04", "2026-04-05", "2026-04-27", "2026-06-08"}',
                '"QLD": {"2025-10-06", "2026-04-04", "2026-04-05", "2026-05-04"}',
                '"SA": {"2025-10-06", "2026-03-09", "2026-04-04", "2026-04-05", "2026-06-08"}',
                '"TAS": {"2026-03-09", "2026-06-08"}',
                '"WA": {"2026-03-02", "2026-04-05", "2026-04-27", "2026-06-01"}',
                '"ACT": {"2025-10-06", "2026-03-09", "2026-04-04", "2026-04-05", "2026-04-27", "2026-06-01", "2026-06-08"}',
                '"NT": {"2025-08-04", "2026-04-04", "2026-04-05", "2026-05-04", "2026-06-08"}',
                "https://www.fairwork.gov.au/employment-conditions/public-holidays/2025-public-holidays",
                "https://www.fairwork.gov.au/employment-conditions/public-holidays/2026-public-holidays",
                "*PUBLIC_HOLIDAY_SOURCES",
                "holiday_not_worked = current in holidays and current not in worked_public",
                "holiday_worked = current in worked_public",
                "limited_holidays = limited_public_holidays(state_key)",
                "def limited_public_holidays(",
                "def limited_public_holiday_may_affect_period(",
                "if \"start\" not in raw or \"end\" not in raw:",
                "start = parse_iso_date(raw.get(\"start\"))",
                "end = parse_iso_date(raw.get(\"end\"))",
                "if not supported_wfh_income_year(raw):",
                "if not dates_within_supported_income_year(start, end):",
                "def supported_wfh_income_year(",
                "def dates_within_supported_income_year(",
                "weekdays = parse_weekdays(raw)",
                "if weekdays is None:",
                "def parse_weekdays(",
                '"weekdays" not in raw',
                "parsed_day = parse_weekday(day)",
                "if parsed_day is None:",
                "def parse_weekday(",
                "hours_per_day = money_value(raw.get(\"hours_per_day\"), unknown_as_missing=True)",
                "hours_per_day is None or hours_per_day <= 0 or hours_per_day > 24",
                "def has_complete_wfh_records(",
                "def wfh_fixed_rate_candidate(",
                "fixed_candidate = wfh_fixed_rate_candidate(hours, raw)",
                "actual_cost_record_value = raw.get(\"actual_cost_records\")",
                "or is_missing(actual_cost_record_value)",
                "if leave is None or worked_public is None or worked_weekends is None:",
                "fixed_rate_text = money_text(fixed_candidate)",
                "def wfh_adjustment_dates(",
                "required_keys = (\"leave_dates\", \"worked_public_holidays\", \"worked_weekends\")",
                "def valid_wfh_adjustment_dates(",
                "day not in holidays for day in worked_public",
                "day.weekday() < 5 for day in worked_weekends",
                "def asset_answers(",
                "if isinstance(raw_assets, list) and has_meaningful_value(raw_assets):",
                "work_use != 100",
                "mixed-use",
                "ATO_ESS_SOURCE = \"https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/employee-share-schemes\"",
                "ATO_ESS_STATEMENT_SOURCE = \"https://www.ato.gov.au/forms-and-instructions/employee-share-scheme-statement\"",
                "REVIEWABLE_ESS_FIELDS = (",
                "ESS_AMOUNT_FIELDS = (",
                "ESS_FLAT_AMOUNT_FIELDS = tuple(f\"ess_{field}\" for field in ESS_AMOUNT_FIELDS)",
                "ESS_ITEM_SIGNAL_FIELDS = (\"employer\"",
                "ESS_STATEMENT_MISSING_PHRASES = (",
                "\"statement not received\"",
                "\"do not have\"",
                "def has_meaningful_value(",
                "if isinstance(value, bool):",
                "return True",
                "spec.required or has_meaningful_value(value)",
                "if key == \"ess_statement\" and ess_statement_missing(value):",
                "if key in ESS_FLAT_AMOUNT_FIELDS and ess_amount_malformed(value):",
                "if not has_meaningful_value(raw):",
                "not has_meaningful_value(enriched.get(\"records\"))",
                "not has_meaningful_value(enriched.get(\"state\"))",
                "if not has_meaningful_value(asset):",
                "if not has_meaningful_value(value):",
                "not has_meaningful_value(raw)",
                "ess_taxed_upfront_discount",
                "ess_deferred_discount",
                "ess_foreign_source_discount",
                "ess_tfn_amount_withheld",
                "items.extend(ess_rows(ess_answers(answers)))",
                "def ess_answers(",
                "flat_values = {key: value for key, value in fields.items() if has_meaningful_value(value)}",
                "merged = dict(flat_values)",
                "has_explicit_ess_evidence_gap(key, value)",
                "def ess_rows(",
                "statement_evidence = ess_statement_missing(statement) or ess_items_need_statement_evidence(items)",
                "amount_conflict = ess_amount_conflict(raw, items)",
                "amount_evidence = ess_amounts_need_evidence(raw, items)",
                "tab_text = ess_tab_text(statement_evidence, amount_conflict, amount_evidence)",
                "def ess_item_values(",
                "def has_meaningful_ess_item(",
                "def has_meaningful_ess_signal(",
                "if contains_unknown(value):\n        return False",
                "def has_meaningful_ess_override(",
                "if key == \"items\":\n        return bool(ess_item_values(value))",
                "key in ESS_AMOUNT_FIELDS and isinstance(value, bool)",
                "def has_explicit_ess_evidence_gap(",
                "def ess_amount_value(",
                "def ess_item_amount_total(",
                "def ess_amount_conflict(",
                "def ess_amounts_need_evidence(",
                "def ess_amount_malformed(",
                "def ess_money_value(",
                "except ValueError:",
                "return None",
                "def ess_tab_text(",
                "ESS top-level and item amounts conflict; correct ESS amount totals before accountant review.",
                "ESS amount fields need numeric evidence before accountant review.",
                "def ess_statement_missing(",
                "if isinstance(statement, bool):",
                "return not statement",
                "return any(phrase in lowered for phrase in ESS_STATEMENT_MISSING_PHRASES)",
                "def ess_items_need_statement_evidence(",
                "return any(ess_statement_missing(item.get(\"statement\")) for item in items)",
                "def ess_items_text(",
                "def ess_employer_text(",
                "def ess_label_text(",
                "display_value(raw.get(\"provider\"))",
                "def has_ess_inputs(",
                "if has_meaningful_ess_statement(raw.get(\"statement\")):",
                "has_explicit_ess_evidence_gap(key, raw.get(key))",
                "def has_meaningful_ess_statement(",
                "def has_meaningful_ess_value(",
                "if isinstance(value, list):",
                "return any(has_meaningful_value(item) for item in value)",
                "taxed-upfront discount",
                "deferred discount",
                "foreign-source discount",
                "TFN amount withheld",
                "ESS discounts need the ESS statement",
                "def parse_iso_date(",
                "def parse_dates(raw_values: Any) -> Optional[Set[date]]:",
                "if contains_unknown(raw_values):",
                "if start is None or end is None or end < start:",
                "def generation_checked_at(",
                '"checked_at": generation_checked_at()',
            ],
        )
    )
    if '"checked_at": "2026-06-29"' in text:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "forbidden stale checked_at literal"))
    for forbidden in [
        'raw.get("start", "2025-07-01")',
        'raw.get("end", "2026-06-30")',
        'raw.get("leave_dates", [])',
        'raw.get("worked_public_holidays", [])',
        'raw.get("worked_weekends", [])',
        "return {int(day) for day in weekdays",
        "round(hours * WFH_FIXED_RATE_2025_26, 2)",
        '"status": "Used" if confirmed else "Evidence"',
    ]:
        if forbidden in text:
            findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, f"forbidden parser fallback: {forbidden}"))
    stale_holiday_source = "https://data.gov.au/data/dataset/australian-holidays-machine-readable-dataset"
    if stale_holiday_source in text or stale_holiday_source in skill_rules:
        findings.append(Finding(INDIVIDUAL_INTAKE_CONTRACT, "forbidden inactive public holiday source"))
    holiday_guidance = skill_text + "\n" + skill_rules
    findings.extend(
        fail_if_missing(
            INDIVIDUAL_INTAKE_CONTRACT,
            holiday_guidance,
            [
                "state-wide public holidays",
                "regional, capital-city-only, sector-only, and partial-day",
                "Evidence or `Accountant review`",
            ],
        )
    )
    return findings


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
    findings.extend(
        fail_if_missing(
            CALCULATOR_TEMPORAL_CONTRACT,
            calc,
            [
                'SUPPORTED_INCOME_YEAR = "2025-26"',
                'SUPPORTED_FBT_YEAR = "2026"',
                "def supported_income_year(",
                "def supported_fbt_year(",
                "def not_calculated_result(",
                "def normalize_fbt_type(",
                "if not supported_income_year(income_year):",
                "if not supported_fbt_year(fbt_year):",
                '"calculation": "not_calculated"',
                'parser.add_argument("--income-year", default=SUPPORTED_INCOME_YEAR)',
                'parser.add_argument("--fbt-year", default=SUPPORTED_FBT_YEAR)',
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
        "workflow_run:",
        'workflows: ["CI"]',
        "types: [completed]",
        "branches: [main]",
        "Require green CI",
        "GH_REPO: nijanthan-dev/taxmate-australia",
        "--workflow CI --branch main --commit",
        "Require main unchanged",
        "git ls-remote https://github.com/nijanthan-dev/taxmate-australia.git refs/heads/main",
        "RELEASE_PLEASE_TOKEN",
        "release-please-action@",
        "target-branch: main",
        "manifest-file: .release-please-manifest.json",
    ]
    findings.extend(fail_if_missing(RELEASE_GUARDRAIL_CONTRACT, release, required))
    if "workflow_run:" in release and "actions/checkout@" in release:
        findings.append(Finding(RELEASE_GUARDRAIL_CONTRACT, "release workflow_run must not checkout repository code"))
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

    if not isinstance(marketplace, dict):
        return [Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace root must be an object")]

    name = marketplace.get("name")
    plugins = marketplace.get("plugins")
    if not isinstance(name, str) or not name:
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing name"))
    if not isinstance(plugins, list) or not plugins:
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace missing plugins"))
        return findings

    plugin_entries = [plugin for plugin in plugins if isinstance(plugin, dict)]
    if len(plugin_entries) != len(plugins):
        findings.append(Finding(LOCAL_PLUGIN_MARKETPLACE_CONTRACT, "marketplace plugins entries must be objects"))

    taxmate_plugin = next((plugin for plugin in plugin_entries if plugin.get("name") == "taxmate-australia"), None)
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
    check_individual_intake_contract,
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
