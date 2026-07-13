"""Shared prep-only entity-return intake routing."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Tuple

CHECKED_AT = "2026-07-13"
SOURCES = {
    "company": "https://www.ato.gov.au/forms-and-instructions/company-tax-return-2026-instructions",
    "trust": "https://www.ato.gov.au/forms-and-instructions/trust-tax-return-2026-instructions",
    "partnership": "https://www.ato.gov.au/forms-and-instructions/partnership-tax-return-2026-instructions",
}
ALIASES = {
    "company": ("company_return", "company_intake", "company_entity"),
    "trust": ("trust_return", "trust_intake", "trust_entity"),
    "partnership": ("partnership_return", "partnership_intake", "partnership_entity"),
}
FIELDS = {
    "company": (
        "name", "abn", "acn", "tfn", "income_year", "residency",
        "business_activity", "directors", "shareholders", "related_entities",
    ),
    "trust": (
        "name", "tfn", "abn", "trustee", "trust_type", "income_year",
        "residency", "deed_evidence", "election_evidence", "beneficiaries",
    ),
    "partnership": (
        "name", "abn", "tfn", "income_year", "partners", "share_percentages",
        "business_activity", "accounting_basis", "agreement_evidence",
    ),
}
REQUIRED = {
    "company": (
        "name", "income_year", "residency", "business_activity", "directors", "shareholders",
    ),
    "trust": (
        "name", "trustee", "trust_type", "income_year", "residency",
        "deed_evidence", "beneficiaries",
    ),
    "partnership": (
        "name", "income_year", "partners", "share_percentages",
        "business_activity", "accounting_basis", "agreement_evidence",
    ),
}
LABELS = {"company": "Company", "trust": "Trust", "partnership": "Partnership"}
ROUTING_METADATA = {
    "entity_type", "type", "source_url", "source_urls", "checked_at",
    "status", "review_status",
}
REQUEST_MARKER = "__entity_return_requested__"
LEGACY_SHARE_FIELDS = {
    "trust": (
        "trust", "trust_share_entity_name", "trust_beneficiary_entity_name",
        "trust_share_abn", "trust_beneficiary_abn", "trust_share_tfn",
        "trust_beneficiary_tfn", "trust_share_statement", "trust_share_statement_status",
        "trust_beneficiary_statement", "trust_beneficiary_statement_status",
        "trust_share_income", "trust_beneficiary_income", "trust_share_loss",
        "trust_beneficiary_loss", "trust_share_tax_withheld", "trust_beneficiary_tax_withheld",
        "trust_share_credits", "trust_beneficiary_credits", "trust_entity_return_context",
        "trust_beneficiary_entity_return_context",
    ),
    "partnership": (
        "partnership", "partnership_entity_name", "partnership_statement",
        "partnership_statement_status", "partnership_income", "partnership_share_income",
        "partnership_loss", "partnership_share_loss", "partnership_tax_withheld",
        "partnership_credits", "partnership_entity_return_context",
    ),
}


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, (list, dict)):
        values = value.values() if isinstance(value, dict) else value
        return not any(not _missing(item) for item in values)
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    return not normalized or normalized in {
        "unknown", "unclear", "missing", "n/a", "not applicable",
    }


def _display(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def valid_checked_at(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def source_provenance(record: Dict[str, Any]) -> Tuple[List[str], List[Any]]:
    supplied: List[Any] = []
    for source_key in ("source_urls", "source_url"):
        source_value = record.get(source_key)
        if _missing(source_value):
            continue
        supplied.extend(source_value if isinstance(source_value, list) else [source_value])
    valid = [
        value.strip()
        for value in supplied
        if isinstance(value, str) and re.fullmatch(r"https?://[^\s]+", value.strip())
    ]
    invalid = [
        value
        for value in supplied
        if not isinstance(value, str) or not re.fullmatch(r"https?://[^\s]+", value.strip())
    ]
    return valid, invalid


def _decline(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0:
        return True
    return isinstance(value, str) and value.strip().lower() in {
        "no", "false", "none", "not applicable", "0", "off", "unchecked",
    }


def _entity_marker(value: Any) -> bool:
    if value is True:
        return True
    return isinstance(value, str) and value.strip().lower() in {"yes", "true", "on", "checked"}


def _entity_input(value: Any) -> bool:
    return not _decline(value) and not _missing(value)


def _first_meaningful(record: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        value = record.get(key)
        if not _missing(value):
            return value
    return None


def _flat_record(answers: Dict[str, Any], kind: str) -> Dict[str, Any]:
    record: Dict[str, Any] = {}
    has_legacy_marker = any(
        _entity_marker(answers.get(alias))
        for alias in ALIASES[kind]
    )
    for field in FIELDS[kind]:
        return_key = f"{kind}_return_{field}"
        legacy_key = f"{kind}_{field}"
        if return_key in answers:
            record[field] = answers[return_key]
        elif has_legacy_marker and legacy_key in answers:
            record[field] = answers[legacy_key]
        elif field == "name" and has_legacy_marker and kind in {"trust", "partnership"} and kind in answers:
            record[field] = answers[kind]
    for field in ("source_url", "source_urls", "checked_at", "status", "review_status"):
        return_key = f"{kind}_return_{field}"
        legacy_key = f"{kind}_{field}"
        if return_key in answers:
            record[field] = answers[return_key]
        elif has_legacy_marker and legacy_key in answers:
            record[field] = answers[legacy_key]
    prefix = f"{kind}_return_"
    for key, value in answers.items():
        if key.startswith(prefix):
            record.setdefault(key[len(prefix):], value)
    return record


def individual_share_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = dict(answers)
    metadata_fields = ("source_url", "source_urls", "checked_at", "status", "review_status")
    for kind in ("trust", "partnership"):
        if not _entity_request_present(answers, kind):
            continue
        for field in (*FIELDS[kind], *metadata_fields):
            sanitized.pop(f"{kind}_{field}", None)
        for key in LEGACY_SHARE_FIELDS[kind]:
            sanitized.pop(key, None)
    return sanitized


def _entity_request_present(answers: Dict[str, Any], kind: str) -> bool:
    if any(key.startswith(f"{kind}_return_") for key in answers):
        return True
    return any(
        alias in answers
        and not _decline(answers[alias])
        and (
            _entity_input(answers[alias])
            or isinstance(answers[alias], (dict, list))
        )
        for alias in ALIASES[kind]
    )


def entity_facts_present(value: Any) -> bool:
    return not _missing(value)


def _unsupported_evidence(kind: str, unsupported: Dict[str, Any], index: int) -> Dict[str, Any]:
    return {
        "number": f"ENTITY-EVID-{index}",
        "ato_area": f"{LABELS[kind]} return scope review",
        "question": f"{LABELS[kind]} facts outside skeleton scope",
        "answer": f"Preserved for accountant review only: {_display(unsupported)}",
        "why_included": "Facts outside skeleton routing are retained without importing downstream tax treatment.",
        "status": "Accountant review", "source_urls": [SOURCES[kind]],
        "checked_at": CHECKED_AT, "row_kind": f"entity-return-{kind}-unsupported",
        "facts": [{"key": "unsupported", "label": "Unsupported entity facts", "value": unsupported}],
    }


def _records(answers: Dict[str, Any]) -> Tuple[Dict[str, List[Any]], List[Any]]:
    grouped = {kind: [] for kind in ALIASES}
    malformed: List[Any] = []
    for kind, aliases in ALIASES.items():
        initial_count = len(grouped[kind])
        request_marker: Any = None
        for alias in aliases:
            if alias not in answers or _decline(answers[alias]) or answers[alias] is None:
                continue
            value = answers[alias]
            if isinstance(value, (dict, list)) and _missing(value):
                request_marker = value
                continue
            if _missing(value):
                continue
            if _entity_marker(value):
                request_marker = value
                continue
            grouped[kind].extend(value if isinstance(value, list) else [value])
        flat = _flat_record(answers, kind)
        if flat:
            if len(grouped[kind]) == initial_count + 1 and isinstance(grouped[kind][-1], dict):
                nested = grouped[kind][-1]
                conflicts: Dict[str, Dict[str, Any]] = {}
                for key, value in flat.items():
                    if key not in nested:
                        nested[key] = value
                    elif nested[key] != value:
                        conflicts[key] = {"nested": nested[key], "flat": value}
                if conflicts:
                    nested["conflicting_flat_facts"] = conflicts
            else:
                grouped[kind].append(flat)
        elif request_marker is not None and len(grouped[kind]) == initial_count:
            grouped[kind].append({REQUEST_MARKER: request_marker})
    for collection_key in ("entities", "entity_returns"):
        entities = answers.get(collection_key, [])
        if _decline(entities) or _missing(entities):
            continue
        collection = entities if isinstance(entities, list) else [entities]
        for item in collection:
            if not isinstance(item, dict):
                malformed.append(item)
                continue
            kind = str(_first_meaningful(item, ("entity_type", "type")) or "").strip().lower()
            if kind in grouped:
                grouped[kind].append(item)
            elif kind not in {"individual", "sole trader", "sole_trader"}:
                malformed.append(item)
    for kind, values in grouped.items():
        unique: List[Any] = []
        seen: set[str] = set()
        for value in values:
            marker = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
            if marker in seen:
                continue
            seen.add(marker)
            unique.append(value)
        grouped[kind] = unique
    return grouped, malformed


def route_entity_returns(
    answers: Dict[str, Any],
) -> Tuple[Dict[str, List[Dict[str, Any]]], List[Dict[str, Any]]]:
    grouped, malformed = _records(answers)
    sections = {f"{kind}_items": [] for kind in grouped}
    evidence: List[Dict[str, Any]] = []
    evidence_index = 1
    for kind, records in grouped.items():
        for index, raw in enumerate(records, start=1):
            if not isinstance(raw, dict):
                malformed.append(raw)
                continue
            if REQUEST_MARKER in raw:
                missing = [field.replace("_", " ") for field in REQUIRED[kind]]
                evidence.append({
                    "number": f"ENTITY-EVID-{evidence_index}",
                    "ato_area": f"{LABELS[kind]} return intake evidence",
                    "question": f"{LABELS[kind]} return requested; intake facts required",
                    "answer": f"Confirm {', '.join(missing)}",
                    "why_included": "An explicit entity-return request fails closed until skeleton intake facts are supplied.",
                    "status": "Evidence", "source_urls": [SOURCES[kind]],
                    "checked_at": CHECKED_AT, "row_kind": f"entity-return-{kind}-request",
                    "facts": [{"key": "request", "label": "Entity return requested", "value": raw[REQUEST_MARKER]}],
                })
                evidence_index += 1
                continue
            facts = [(field, raw[field]) for field in FIELDS[kind] if field in raw]
            unsupported = {
                key: value
                for key, value in raw.items()
                if key not in FIELDS[kind] and key not in ROUTING_METADATA
            }
            if not facts:
                if unsupported:
                    evidence.append(_unsupported_evidence(kind, unsupported, evidence_index))
                    evidence_index += 1
                else:
                    malformed.append(raw)
                continue
            gaps = [
                field.replace("_", " ")
                for field in REQUIRED[kind]
                if field not in raw or _missing(raw.get(field))
            ]
            if kind == "partnership" and "share_percentages" in raw:
                values = raw["share_percentages"]
                valid_values = (
                    isinstance(values, list)
                    and bool(values)
                    and all(
                        isinstance(value, (int, float)) and not isinstance(value, bool)
                        for value in values
                    )
                    and sum(values) == 100
                )
                if not valid_values:
                    gaps.append("partner share percentages")
            answer = "; ".join(f"{field.replace('_', ' ')} {_display(value)}" for field, value in facts)
            valid_sources, invalid_sources = source_provenance(raw)
            if invalid_sources:
                gaps.append("source provenance")
            checked_at = raw.get("checked_at")
            if "checked_at" in raw and not _missing(checked_at) and not valid_checked_at(checked_at):
                gaps.append(f"checked-at provenance ({_display(checked_at)})")
            source_urls = [SOURCES[kind], *valid_sources]
            row = {
                "number": f"{kind.upper()}-{index}", "ato_area": f"{LABELS[kind]} return preparation",
                "question": f"{LABELS[kind]} return intake", "answer": answer,
                "why_included": f"Separate prep-only {kind} return routing; no individual-return entry or final treatment.",
                "status": "Accountant review", "source_urls": list(dict.fromkeys(source_urls)),
                "checked_at": checked_at if valid_checked_at(checked_at) else CHECKED_AT,
                "row_kind": f"entity-return-{kind}",
                "facts": [{"key": field.replace("_", "-"), "label": field.replace("_", " ").title(), "value": value} for field, value in facts],
                "tab_text": f"{LABELS[kind]} facts stay in the separate prep-only workflow and require accountant review.",
            }
            sections[f"{kind}_items"].append(row)
            if unsupported:
                evidence.append(_unsupported_evidence(kind, unsupported, evidence_index))
                evidence_index += 1
            if gaps:
                gap_facts = [{
                    "key": "missing",
                    "label": "Missing or ambiguous facts",
                    "value": list(dict.fromkeys(gaps)),
                }]
                if invalid_sources:
                    gap_facts.append({
                        "key": "unresolved-source-provenance",
                        "label": "Unresolved source provenance",
                        "value": invalid_sources,
                    })
                evidence.append({
                    "number": f"ENTITY-EVID-{evidence_index}", "ato_area": f"{LABELS[kind]} return evidence",
                    "question": f"{LABELS[kind]} evidence required", "answer": f"Confirm {', '.join(dict.fromkeys(gaps))}",
                    "why_included": "Incomplete or ambiguous entity facts fail closed before any workflow handoff.",
                    "status": "Evidence", "source_urls": [SOURCES[kind]], "checked_at": CHECKED_AT,
                    "row_kind": f"entity-return-{kind}-evidence",
                    "facts": gap_facts,
                })
                evidence_index += 1
    for value in malformed:
        evidence.append({
            "number": f"ENTITY-EVID-{evidence_index}", "ato_area": "Entity return input shape review",
            "question": "Malformed entity item", "answer": f"Malformed entity item preserved: {_display(value)}",
            "why_included": "Malformed entity input fails closed instead of crossing a workflow boundary.",
            "status": "Evidence", "source_urls": [], "checked_at": CHECKED_AT,
            "row_kind": "entity-return-malformed", "facts": [{"key": "raw", "label": "Raw entity input", "value": value}],
        })
        evidence_index += 1
    return sections, evidence
