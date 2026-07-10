#!/usr/bin/env python3
"""Structured individual-return handoff contracts and verified destinations."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse


DEFAULT_INCOME_YEAR = "2025-26"
MANIFEST_PATH = Path("config/handoff-destinations.json")
SOURCE_COVERAGE_PATH = Path("data/ato_knowledge_base/source_coverage.json")
SOURCE_REGISTRY_PATH = Path("data/ato_knowledge_base/source_registry.json")

TAXONOMY: Dict[str, Dict[str, str]] = {
    "enter-reviewed-value": {
        "label": "Enter reviewed value",
        "description": "Use a reviewed value only at an exact verified destination.",
    },
    "answer-guided-question": {
        "label": "Answer guided question",
        "description": "Use a reviewed fact to answer an exact verified return question.",
    },
    "retain-evidence": {
        "label": "Retain evidence",
        "description": "Keep the fact or record as support; it is not a return entry.",
    },
    "resolve-before-entry": {
        "label": "Resolve before entry",
        "description": "Resolve missing, conflicting, or incomplete facts before return entry.",
    },
    "accountant-handoff-only": {
        "label": "Accountant handoff only",
        "description": "Give the fact and supporting records to an accountant before return entry.",
    },
    "not-entered-directly": {
        "label": "Not entered directly",
        "description": "Keep the fact as context; it has no direct return field.",
    },
    "destination-requires-review": {
        "label": "Destination requires review",
        "description": "No exact verified destination is available for this fact.",
    },
}

ACTION_TEXT = {
    "enter-reviewed-value": "Use the reviewed value at the verified destination.",
    "answer-guided-question": "Use the reviewed fact to answer the verified guided question.",
    "retain-evidence": "Retain this fact and its supporting record. It is not a direct return entry.",
    "resolve-before-entry": "Resolve this fact or evidence gap before any return entry.",
    "accountant-handoff-only": "Give this fact and its supporting records to an accountant before any return entry.",
    "not-entered-directly": "Keep this fact as context. It is not entered directly.",
    "destination-requires-review": "Confirm the destination before any return entry.",
}

ANSWER_STATUS_KEYS = {"answer", "answer-used", "used", "green"}
ATO_STATUS_KEYS = {"ato", "ato-label", "label", "blue"}
EVIDENCE_STATUS_KEYS = {"evidence", "evidence-needed", "missing-evidence", "yellow"}
REVIEW_STATUS_KEYS = {"review", "accountant-review", "red"}
SKIPPED_STATUS_KEYS = {
    "skipped",
    "skip",
    "n-a",
    "na",
    "n-a-skipped",
    "na-skipped",
    "not-applicable",
    "grey",
    "gray",
}
STATUS_PRECEDENCE = ("review", "evidence", "answer", "ato", "skipped")

DESTINATION_KINDS = {"verified", "requires-review", "not-entered"}
CHANNEL_STATES = {"verified", "read-only", "not-entered", "requires-review"}
PHI_SUPPORTED_BENEFIT_CODES = {"30", "31", "35", "36", "40", "41"}
PHI_CODES = {"A", "B", "C", "D", "E", "F"}

PHI_TAX_CONTEXT = {
    "key": "tax_claim_code",
    "channels": {
        "mytax": {
            "A": "verified",
            "B": "verified",
            "C": "verified",
            "D": "read-only",
            "E": "verified",
            "F": "verified",
            "default": "requires-review",
        },
        "paper": {
            "A": "verified",
            "B": "verified",
            "C": "verified",
            "D": "verified",
            "E": "verified",
            "F": "verified",
            "default": "requires-review",
        },
    },
}

PHI_JKL_CONTEXT = {
    "key": "tax_claim_code",
    "channels": {
        "mytax": {
            "A": "verified",
            "B": "verified",
            "C": "verified",
            "D": "read-only",
            "E": "not-entered",
            "F": "not-entered",
            "default": "requires-review",
        },
        "paper": {
            "A": "verified",
            "B": "verified",
            "C": "verified",
            "D": "verified",
            "E": "verified",
            "F": "not-entered",
            "default": "requires-review",
        },
    },
}


def _channel(
    kind: str,
    location: str,
    source_id_value: str,
    *,
    state_locations: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "kind": kind,
        "location": location,
        "source_id": source_id_value,
    }
    if state_locations:
        value["state_locations"] = state_locations
    return value


APPROVED_DESTINATION_BINDINGS: Dict[str, Dict[str, Any]] = {
    "phi-tax-claim-code": {
        "label": "Private health insurance statement line - Tax claim code",
        "context": PHI_TAX_CONTEXT,
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance > Private health insurance > Statement line panel > Tax claim code",
            "ato-f99c3a4ad079",
            state_locations={
                "read-only": "Read-only spouse-share statement line created by myTax with tax claim code D",
                "requires-review": "Tax claim code destination requires review",
            },
        ),
        "paper": _channel(
            "verified",
            "Private health insurance policy details > Tax claim code box",
            "ato-2a2cf8a8c462",
            state_locations={"requires-review": "Tax claim code destination requires review"},
        ),
    },
    "phi-premiums-j": {
        "label": "Private health insurance statement line - Premiums eligible for rebate",
        "context": PHI_JKL_CONTEXT,
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance > Private health insurance > Your premiums eligible for Australian Government rebate",
            "ato-f99c3a4ad079",
            state_locations={
                "read-only": "Read-only spouse-share statement line created by myTax",
                "not-entered": "Not entered in myTax for this tax claim code",
                "requires-review": "Premium destination requires review",
            },
        ),
        "paper": _channel(
            "verified",
            "Private health insurance policy details > label J",
            "ato-2a2cf8a8c462",
            state_locations={
                "not-entered": "Not entered at label J for tax claim code F",
                "requires-review": "Label J destination requires review",
            },
        ),
    },
    "phi-rebate-k": {
        "label": "Private health insurance statement line - Rebate received",
        "context": PHI_JKL_CONTEXT,
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance > Private health insurance > Your Australian Government rebate received",
            "ato-f99c3a4ad079",
            state_locations={
                "read-only": "Read-only spouse-share statement line created by myTax",
                "not-entered": "Not entered in myTax for this tax claim code",
                "requires-review": "Rebate destination requires review",
            },
        ),
        "paper": _channel(
            "verified",
            "Private health insurance policy details > label K",
            "ato-2a2cf8a8c462",
            state_locations={
                "not-entered": "Not entered at label K for tax claim code F",
                "requires-review": "Label K destination requires review",
            },
        ),
    },
    "phi-benefit-code-l": {
        "label": "Private health insurance statement line - Benefit code",
        "context": PHI_JKL_CONTEXT,
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance > Private health insurance > Benefit code",
            "ato-f99c3a4ad079",
            state_locations={
                "read-only": "Read-only spouse-share statement line created by myTax",
                "not-entered": "Not entered in myTax for this tax claim code",
                "requires-review": "Benefit code destination requires review",
            },
        ),
        "paper": _channel(
            "verified",
            "Private health insurance policy details > label L",
            "ato-2a2cf8a8c462",
            state_locations={
                "not-entered": "Not entered at label L for tax claim code F",
                "requires-review": "Label L destination requires review",
            },
        ),
    },
    "m1-exemption-question": {
        "label": "Medicare levy exemption category question",
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance details > Medicare levy exemption > Were you in an exemption category during 2025-26?",
            "ato-4cedc9f93767",
        ),
        "paper": _channel(
            "requires-review",
            "Question M1 category instructions; no equivalent generic paper yes/no label is verified",
            "ato-39155fe09d00",
        ),
    },
    "m1-full-days-v": {
        "label": "Medicare levy full exemption days",
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance details > Full 2% levy exemption - number of days",
            "ato-4cedc9f93767",
        ),
        "paper": _channel("verified", "Question M1 > label V", "ato-39155fe09d00"),
    },
    "m1-half-days-w": {
        "label": "Medicare levy half exemption days",
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance details > Half 2% levy exemption - number of days",
            "ato-4cedc9f93767",
        ),
        "paper": _channel("verified", "Question M1 > label W", "ato-39155fe09d00"),
    },
    "m2-cover-question-e": {
        "label": "Medicare levy surcharge full-year appropriate family cover question",
        "mytax": _channel(
            "verified",
            "Prepare return > Medicare and private health insurance > Medicare levy surcharge > Were you and all your dependants covered by an appropriate level of private patient hospital cover from 1 July 2025 to 30 June 2026?",
            "ato-836a84c52e60",
        ),
        "paper": _channel(
            "verified",
            "Question M2 > label E Yes/No - full-year appropriate private patient hospital cover for you and all dependants",
            "ato-b8cc03014dc1",
        ),
    },
    "m2-days-not-liable-a": {
        "label": "Medicare levy surcharge days not liable",
        "mytax": _channel(
            "requires-review",
            "After an explicit No to full-year appropriate family cover, myTax may skip this field after its income check; if shown: Number of days you do not have to pay the surcharge",
            "ato-836a84c52e60",
        ),
        "paper": _channel("verified", "Question M2 > label A", "ato-b8cc03014dc1"),
    },
    "spouse-had-question": {
        "label": "Spouse details participation question",
        "mytax": _channel(
            "verified",
            "Personalise return > Did you have a spouse at any time between 1 July 2025 and 30 June 2026?",
            "ato-815a889d0a59",
        ),
        "paper": _channel(
            "requires-review",
            "Spouse details - married or de facto section; no separate paper had-spouse label is verified",
            "ato-29a73bbec8f5",
        ),
    },
}

APPROVED_FACT_DESTINATIONS = {
    ("private-health-statement", "tax-claim-code"): "phi-tax-claim-code",
    ("private-health-statement", "premiums-eligible-for-rebate"): "phi-premiums-j",
    ("private-health-statement", "rebate-received"): "phi-rebate-k",
    ("private-health-statement", "benefit-code"): "phi-benefit-code-l",
    ("medicare-levy-review", "exemption-signal"): "m1-exemption-question",
    ("medicare-levy-review", "full-exemption-days"): "m1-full-days-v",
    ("medicare-levy-review", "half-exemption-days"): "m1-half-days-w",
    ("medicare-surcharge-review", "full-year-family-cover"): "m2-cover-question-e",
    ("medicare-surcharge-review", "days-not-liable"): "m2-days-not-liable-a",
    ("spouse-review", "had-spouse"): "spouse-had-question",
}

MAPPING_CONTEXT_KEYS = {
    "phi-tax-claim-code": {"tax_claim_code", "conflicted"},
    "phi-premiums-j": {"tax_claim_code", "conflicted"},
    "phi-rebate-k": {"tax_claim_code", "conflicted"},
    "phi-benefit-code-l": {"tax_claim_code", "conflicted"},
    "m1-exemption-question": {"exemption", "conflicted"},
    "m1-full-days-v": {"exemption", "conflicted"},
    "m1-half-days-w": {"exemption", "conflicted"},
    "m2-cover-question-e": {"explicit_family_cover", "explicit_local_days", "conflicted"},
    "m2-days-not-liable-a": {"explicit_family_cover", "conflicted"},
    "spouse-had-question": {"had_spouse", "contradicted", "conflicted"},
}

MAPPING_ACTIONS = {
    "phi-tax-claim-code": "answer-guided-question",
    "phi-premiums-j": "enter-reviewed-value",
    "phi-rebate-k": "enter-reviewed-value",
    "phi-benefit-code-l": "enter-reviewed-value",
    "m1-exemption-question": "answer-guided-question",
    "m1-full-days-v": "enter-reviewed-value",
    "m1-half-days-w": "enter-reviewed-value",
    "m2-cover-question-e": "answer-guided-question",
    "m2-days-not-liable-a": "enter-reviewed-value",
    "spouse-had-question": "answer-guided-question",
}


def repository_root(root: Optional[Path] = None) -> Path:
    return Path(root) if root is not None else Path(__file__).resolve().parents[1]


def scalar_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def text_value(value: Any, default: str = "") -> str:
    rendered = scalar_text(value)
    return rendered if rendered.strip() else default


def _strict_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def read_json(path: Path) -> Dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def load_destination_manifest(root: Optional[Path] = None) -> Dict[str, Any]:
    return read_json(repository_root(root) / MANIFEST_PATH)


def canonical_url(raw: str) -> str:
    parsed = urlparse(raw)
    path = parsed.path.rstrip("/")
    host = parsed.hostname.lower() if parsed.hostname else ""
    return urlunparse(parsed._replace(fragment="", query="", path=path, netloc=host))


def _official_url(raw: Any) -> bool:
    if not isinstance(raw, str):
        return False
    parsed = urlparse(raw)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "www.ato.gov.au"
        and not parsed.query
        and not parsed.fragment
    )


def source_id(original_url: str, canonical: str) -> str:
    digest = hashlib.sha256(f"{original_url}|{canonical}".encode("utf-8")).hexdigest()
    return f"ato-{digest[:12]}"


def _valid_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _source_payloads(root: Optional[Path] = None) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    base = repository_root(root)
    return read_json(base / SOURCE_COVERAGE_PATH), read_json(base / SOURCE_REGISTRY_PATH)


def source_state(root: Optional[Path] = None) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    coverage_payload, registry_payload = _source_payloads(root)
    coverage = {
        _strict_text(entry.get("source_id")): entry
        for entry in coverage_payload.get("sources", [])
        if isinstance(entry, dict) and _strict_text(entry.get("source_id"))
    }
    registry: Dict[str, Dict[str, Any]] = {}
    for record in registry_payload.get("records", []):
        if not isinstance(record, dict):
            continue
        original = _strict_text(record.get("url"))
        canonical = canonical_url(_strict_text(record.get("final_url")) or original)
        if original and canonical:
            registry[source_id(original, canonical)] = record
    return coverage, registry


def _duplicate_source_errors(root: Optional[Path]) -> List[str]:
    coverage_payload, registry_payload = _source_payloads(root)
    errors: List[str] = []
    coverage_ids = [
        _strict_text(entry.get("source_id"))
        for entry in coverage_payload.get("sources", [])
        if isinstance(entry, dict) and _strict_text(entry.get("source_id"))
    ]
    for key in sorted(set(coverage_ids)):
        if coverage_ids.count(key) > 1:
            errors.append(f"duplicate source coverage id: {key}")
    registry_ids: List[str] = []
    for record in registry_payload.get("records", []):
        if not isinstance(record, dict):
            continue
        original = _strict_text(record.get("url"))
        canonical = canonical_url(_strict_text(record.get("final_url")) or original)
        if original and canonical:
            registry_ids.append(source_id(original, canonical))
    for key in sorted(set(registry_ids)):
        if registry_ids.count(key) > 1:
            errors.append(f"duplicate source registry id: {key}")
    return errors


def _source_integrity_errors(
    prefix: str,
    source_key: str,
    expected_hash: str,
    coverage: Dict[str, Dict[str, Any]],
    registry: Dict[str, Dict[str, Any]],
) -> List[str]:
    errors: List[str] = []
    covered = coverage.get(source_key)
    record = registry.get(source_key)
    if covered is None:
        errors.append(f"{prefix}: source missing from coverage: {source_key}")
        return errors
    if record is None:
        errors.append(f"{prefix}: source missing from registry: {source_key}")
        return errors

    original = _strict_text(covered.get("original_url"))
    canonical = _strict_text(covered.get("canonical_url"))
    registry_original = _strict_text(record.get("url"))
    registry_final_raw = _strict_text(record.get("final_url")) or registry_original
    registry_final = canonical_url(registry_final_raw)
    if not all(
        _official_url(url)
        for url in (original, canonical, registry_original, registry_final_raw)
    ):
        errors.append(f"{prefix}: source URL is not an exact official ATO URL")
    if original != registry_original or canonical_url(canonical) != registry_final:
        errors.append(f"{prefix}: registry and coverage URLs differ")
    if source_id(original, canonical_url(canonical)) != source_key:
        errors.append(f"{prefix}: source id does not match exact URLs")
    if _strict_text(covered.get("status")) != "verified":
        errors.append(f"{prefix}: source is not verified: {source_key}")
    if record.get("content_verified") is not True:
        errors.append(f"{prefix}: registry source is not content verified: {source_key}")
    if _strict_text(covered.get("content_hash")) != expected_hash:
        errors.append(f"{prefix}: coverage hash mismatch: {source_key}")
    if _strict_text(record.get("content_hash")) != expected_hash:
        errors.append(f"{prefix}: registry hash mismatch: {source_key}")
    if not _strict_text(covered.get("source_title")):
        errors.append(f"{prefix}: coverage source title is blank: {source_key}")
    if _strict_text(covered.get("source_title")) != _strict_text(record.get("title")):
        errors.append(f"{prefix}: source titles differ: {source_key}")
    if _strict_text(covered.get("source_last_updated")) != _strict_text(record.get("last_updated")):
        errors.append(f"{prefix}: source update dates differ: {source_key}")
    for field, value in (
        ("coverage checked_at", covered.get("checked_at")),
        ("registry last_checked", record.get("last_checked")),
        ("coverage source_last_updated", covered.get("source_last_updated")),
        ("registry last_updated", record.get("last_updated")),
    ):
        if not _valid_datetime(value):
            errors.append(f"{prefix}: {field} is invalid: {source_key}")
    if _strict_text(covered.get("checked_at")) != _strict_text(record.get("last_checked")):
        errors.append(f"{prefix}: source checked dates differ: {source_key}")
    return errors


def mapping_channel_errors(
    mapping_id: str,
    channel_name: str,
    channel: Any,
    coverage: Dict[str, Dict[str, Any]],
    registry: Dict[str, Dict[str, Any]],
) -> List[str]:
    prefix = f"{mapping_id}.{channel_name}"
    approved = APPROVED_DESTINATION_BINDINGS.get(mapping_id, {}).get(channel_name)
    if not isinstance(approved, dict):
        return [f"{prefix}: channel is not approved"]
    if not isinstance(channel, dict):
        return [f"{prefix}: channel must be an object"]
    errors: List[str] = []
    allowed_keys = {*approved, "content_hash"}
    if set(channel) != allowed_keys:
        errors.append(f"{prefix}: channel fields do not match the approved binding")
    for field in ("kind", "location", "source_id"):
        if channel.get(field) != approved.get(field):
            errors.append(f"{prefix}: {field} does not match the approved binding")
    if channel.get("state_locations") != approved.get("state_locations"):
        errors.append(f"{prefix}: state locations do not match the approved binding")
    kind = channel.get("kind")
    if kind not in CHANNEL_STATES:
        errors.append(f"{prefix}: channel kind is invalid")
    expected_hash = channel.get("content_hash")
    if not isinstance(expected_hash, str) or re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
        errors.append(f"{prefix}: content_hash is invalid")
        return errors
    source_key = channel.get("source_id")
    if not isinstance(source_key, str):
        errors.append(f"{prefix}: source_id is invalid")
        return errors
    errors.extend(_source_integrity_errors(prefix, source_key, expected_hash, coverage, registry))
    return errors


def destination_mapping_payload_errors(
    manifest: Any,
    *,
    root: Optional[Path] = None,
) -> List[str]:
    if not isinstance(manifest, dict):
        return ["handoff destination manifest must be an object"]
    try:
        coverage, registry = source_state(root)
        errors = _duplicate_source_errors(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"handoff destination source state unavailable: {exc}"]
    if type(manifest.get("schema_version")) is not int or manifest.get("schema_version") != 2:
        errors.append("handoff destination schema_version must be integer 2")
    if manifest.get("income_year") != DEFAULT_INCOME_YEAR:
        errors.append(f"handoff destination income_year must be {DEFAULT_INCOME_YEAR}")
    if set(manifest) != {"schema_version", "income_year", "destinations"}:
        errors.append("handoff destination manifest fields are invalid")
    destinations = manifest.get("destinations")
    if not isinstance(destinations, dict):
        return [*errors, "handoff destinations must be an object"]
    approved_ids = set(APPROVED_DESTINATION_BINDINGS)
    supplied_ids = set(destinations)
    for missing in sorted(approved_ids - supplied_ids):
        errors.append(f"approved destination missing: {missing}")
    for extra in sorted(supplied_ids - approved_ids):
        errors.append(f"unapproved destination mapping: {extra}")
    for mapping_id in sorted(approved_ids & supplied_ids):
        mapping = destinations.get(mapping_id)
        approved = APPROVED_DESTINATION_BINDINGS[mapping_id]
        if not isinstance(mapping, dict):
            errors.append(f"{mapping_id}: mapping must be an object")
            continue
        allowed_mapping_keys = {"label", "mytax", "paper"}
        if "context" in approved:
            allowed_mapping_keys.add("context")
        if set(mapping) != allowed_mapping_keys:
            errors.append(f"{mapping_id}: mapping fields do not match the approved binding")
        if mapping.get("label") != approved.get("label"):
            errors.append(f"{mapping_id}: label does not match the approved binding")
        if mapping.get("context") != approved.get("context"):
            errors.append(f"{mapping_id}: context rules do not match the approved binding")
        for channel_name in ("mytax", "paper"):
            errors.extend(
                mapping_channel_errors(
                    mapping_id,
                    channel_name,
                    mapping.get(channel_name),
                    coverage,
                    registry,
                )
            )
    return errors


def destination_mapping_errors(root: Optional[Path] = None) -> List[str]:
    try:
        manifest = load_destination_manifest(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"handoff destination state unavailable: {exc}"]
    return destination_mapping_payload_errors(manifest, root=root)


def _status_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", scalar_text(value).strip().lower()).strip("-")


def review_like_status(value: Any) -> bool:
    key = _status_key(value)
    parts = {part for part in key.split("-") if part}
    if key in REVIEW_STATUS_KEYS or "accountant" in parts:
        return True
    return "review" in parts and bool(
        parts.intersection({"required", "requires", "need", "needs", "needed", "must", "agent"})
    )


def known_status_kind(value: Any) -> Optional[str]:
    key = _status_key(value)
    if not key:
        return None
    if review_like_status(key):
        return "review"
    if key in EVIDENCE_STATUS_KEYS:
        return "evidence"
    if key in ANSWER_STATUS_KEYS:
        return "answer"
    if key in ATO_STATUS_KEYS:
        return "ato"
    if key in SKIPPED_STATUS_KEYS or "skipped" in key.split("-"):
        return "skipped"
    return "review"


def effective_status_kind(*values: Any) -> str:
    kinds = [kind for kind in (known_status_kind(value) for value in values) if kind]
    if not kinds:
        return "review"
    return next(kind for kind in STATUS_PRECEDENCE if kind in kinds)


def status_kind(value: Any) -> str:
    return effective_status_kind(value)


def _channel_stub(kind: str, location: str) -> Dict[str, Any]:
    return {"kind": kind, "location": location, "sources": []}


def unresolved_destination(label: str = "Destination requires review.") -> Dict[str, Any]:
    return {
        "kind": "requires-review",
        "label": label,
        "mapping_id": "",
        "mytax": "Not verified for direct use.",
        "paper": "Not verified for direct use.",
        "channels": {
            "mytax": _channel_stub("requires-review", "Not verified for direct use."),
            "paper": _channel_stub("requires-review", "Not verified for direct use."),
        },
        "sources": [],
        "context": {},
    }


def not_entered_destination(label: str = "Not entered directly.") -> Dict[str, Any]:
    return {
        "kind": "not-entered",
        "label": label,
        "mapping_id": "",
        "mytax": "Not entered directly.",
        "paper": "Not entered directly.",
        "channels": {
            "mytax": _channel_stub("not-entered", "Not entered directly."),
            "paper": _channel_stub("not-entered", "Not entered directly."),
        },
        "sources": [],
        "context": {},
    }


def destination_source(
    source_key: str,
    expected_hash: str,
    coverage: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    entry = coverage.get(source_key)
    if not isinstance(entry, dict):
        return None
    if entry.get("status") != "verified" or entry.get("content_hash") != expected_hash:
        return None
    required = ("source_title", "canonical_url", "checked_at", "source_last_updated")
    if any(not _strict_text(entry.get(field)) for field in required):
        return None
    return {
        "source_id": source_key,
        "title": entry["source_title"],
        "url": entry["canonical_url"],
        "checked_at": entry["checked_at"],
        "last_updated": entry["source_last_updated"],
        "content_hash": expected_hash,
    }


def _claim_code(value: Any) -> Optional[str]:
    if isinstance(value, bool) or value is None:
        return None
    code = str(value).strip().upper()
    return code if code in PHI_CODES else None


def _context_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _channel_state(mapping: Dict[str, Any], channel_name: str, context: Dict[str, Any]) -> str:
    if "conflicted" in context and _bool_value(context.get("conflicted")) is not False:
        return "requires-review"
    rules = mapping.get("context")
    if not isinstance(rules, dict):
        return mapping[channel_name]["kind"]
    code = _claim_code(context.get(rules.get("key")))
    states = rules["channels"][channel_name]
    return states.get(code, states["default"])


def _channel_location(channel: Dict[str, Any], state: str) -> str:
    if state == channel.get("kind"):
        return channel["location"]
    locations = channel.get("state_locations", {})
    if isinstance(locations, dict) and _strict_text(locations.get(state)):
        return locations[state]
    if state == "read-only":
        return "Read-only; no manual entry."
    if state == "not-entered":
        return "Not entered directly."
    return "Destination requires review."


def _unique_sources(values: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    seen: set[Tuple[str, str]] = set()
    for value in values:
        key = (str(value.get("source_id", "")), str(value.get("content_hash", "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def verified_destination(
    mapping_id: str,
    income_year: Any = "",
    root: Optional[Path] = None,
    *,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    year = income_year if isinstance(income_year, str) else ""
    if year != DEFAULT_INCOME_YEAR:
        return unresolved_destination(
            f"Destination requires review for income year {scalar_text(income_year, 'not supplied')}."
        )
    if mapping_id not in APPROVED_DESTINATION_BINDINGS or destination_mapping_errors(root):
        return unresolved_destination()
    manifest = load_destination_manifest(root)
    mapping = manifest["destinations"][mapping_id]
    coverage, _registry = source_state(root)
    resolved_context = _context_dict(context)
    channels: Dict[str, Dict[str, Any]] = {}
    for channel_name in ("mytax", "paper"):
        channel = mapping[channel_name]
        state = _channel_state(mapping, channel_name, resolved_context)
        source = destination_source(channel["source_id"], channel["content_hash"], coverage)
        if source is None:
            return unresolved_destination()
        channels[channel_name] = {
            "kind": state,
            "location": _channel_location(channel, state),
            "sources": [source],
        }
    states = {value["kind"] for value in channels.values()}
    if "verified" in states:
        aggregate_kind = "verified"
    elif states.issubset({"read-only", "not-entered"}):
        aggregate_kind = "not-entered"
    else:
        aggregate_kind = "requires-review"
    sources = _unique_sources(
        source
        for item in channels.values()
        for source in item["sources"]
    )
    if aggregate_kind == "verified":
        label = mapping["label"]
    elif aggregate_kind == "not-entered":
        label = f"Not entered directly - {mapping['label']}."
    else:
        label = "Destination requires review."
        sources = []
    return {
        "kind": aggregate_kind,
        "label": label,
        "mapping_id": mapping_id if aggregate_kind != "requires-review" else "",
        "mytax": channels["mytax"]["location"],
        "paper": channels["paper"]["location"],
        "channels": channels,
        "income_year": year,
        "sources": sources,
        "context": resolved_context,
    }


def effective_action_kind(requested: str, effective_status: str, destination_kind: str) -> str:
    if effective_status == "review":
        return "accountant-handoff-only"
    if effective_status == "skipped":
        return "not-entered-directly"
    if effective_status == "evidence":
        if requested in {"retain-evidence", "not-entered-directly"} or destination_kind == "not-entered":
            return "retain-evidence"
        return "resolve-before-entry"
    if destination_kind == "not-entered" and requested not in {
        "retain-evidence",
        "not-entered-directly",
    }:
        return "not-entered-directly"
    if requested in {"enter-reviewed-value", "answer-guided-question"} and destination_kind != "verified":
        return "destination-requires-review"
    if requested in TAXONOMY:
        return requested
    return "destination-requires-review"


def normalize_destination(value: Any, root: Optional[Path], income_year: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return unresolved_destination()
    mapping_id = _strict_text(value.get("mapping_id"))
    if mapping_id:
        return verified_destination(
            mapping_id,
            income_year,
            root,
            context=_context_dict(value.get("context")),
        )
    kind = _strict_text(value.get("kind"))
    if kind == "not-entered":
        return not_entered_destination(_strict_text(value.get("label")) or "Not entered directly.")
    return unresolved_destination(_strict_text(value.get("label")) or "Destination requires review.")


def normalize_handoff(
    value: Any,
    *,
    status_kind: Any,
    income_year: Any = "",
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    raw = value if isinstance(value, dict) else {}
    requested = _strict_text(raw.get("kind"))
    destination_value = normalize_destination(raw.get("destination"), root, income_year)
    effective_status = effective_status_kind(status_kind)
    kind = effective_action_kind(requested, effective_status, destination_value["kind"])
    if kind == "not-entered-directly":
        destination_value = not_entered_destination()
    elif kind == "retain-evidence" and destination_value["kind"] != "not-entered":
        destination_value = not_entered_destination()
    elif kind == "destination-requires-review":
        destination_value = unresolved_destination()
    return {
        "kind": kind,
        "label": TAXONOMY[kind]["label"],
        "next_action": ACTION_TEXT[kind],
        "destination": destination_value,
    }


def fact(
    key: str,
    label: str,
    value: Any,
    *,
    action_kind: str = "",
    destination_key: str = "",
    destination_context: Optional[Dict[str, Any]] = None,
    why: str = "",
) -> Dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "value": value,
        "action_kind": action_kind,
        "destination_key": destination_key,
        "destination_context": dict(destination_context or {}),
        "why": why,
    }


def _visible_value(value: Any) -> Any:
    if value is None or (isinstance(value, str) and not value.strip()):
        return "Not supplied"
    return value


def compatibility_facts(question: Any, answer: Any, why: Any = "") -> List[Dict[str, Any]]:
    return [
        fact(
            "supplied-detail",
            text_value(question, "Supplied detail"),
            _visible_value(answer),
            why=text_value(why),
        )
    ]


def _bool_value(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        key = value.strip().lower()
        if key in {"true", "yes", "y", "1"}:
            return True
        if key in {"false", "no", "n", "0"}:
            return False
    return None


def _whole_dollar_amount(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value >= 0 and value.is_integer() else None
    if not isinstance(value, str):
        return None
    text = value.strip()
    if re.fullmatch(r"(?:0|[1-9]\d*)", text):
        return int(text)
    if re.fullmatch(r"[1-9]\d{0,2}(?:,\d{3})+", text):
        return int(text.replace(",", ""))
    return None


def _day_count(value: Any) -> Optional[int]:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            return None
        parsed = int(value)
    elif isinstance(value, str) and re.fullmatch(r"\d+", value.strip()):
        parsed = int(value.strip())
    else:
        return None
    if parsed < 0 or parsed > 365:
        return None
    return parsed


def _binding_allowed(row_kind: str, fact_key: str, mapping_id: str) -> bool:
    return APPROVED_FACT_DESTINATIONS.get((row_kind, fact_key)) == mapping_id


def _mapping_applicability(
    mapping_id: str,
    value: Any,
    context: Dict[str, Any],
) -> str:
    if set(context) != MAPPING_CONTEXT_KEYS.get(mapping_id, set()):
        return "requires-review"
    if _bool_value(context.get("conflicted")) is not False:
        return "requires-review"
    if mapping_id == "phi-tax-claim-code":
        value_code = _claim_code(value)
        context_code = _claim_code(context.get("tax_claim_code"))
        return "verified" if value_code is not None and value_code == context_code else "requires-review"
    if mapping_id in {"phi-premiums-j", "phi-rebate-k"}:
        if _claim_code(context.get("tax_claim_code")) is None or _whole_dollar_amount(value) is None:
            return "requires-review"
        return "verified"
    if mapping_id == "phi-benefit-code-l":
        code = str(value).strip() if not isinstance(value, bool) and value is not None else ""
        if _claim_code(context.get("tax_claim_code")) is None or code not in PHI_SUPPORTED_BENEFIT_CODES:
            return "requires-review"
        return "verified"
    if mapping_id == "m1-exemption-question":
        exemption = _bool_value(context.get("exemption", value))
        visible = _bool_value(value)
        return "verified" if exemption is not None and visible == exemption else "requires-review"
    if mapping_id in {"m1-full-days-v", "m1-half-days-w"}:
        exemption = _bool_value(context.get("exemption"))
        days = _day_count(value)
        if exemption is False:
            missing = value is None or scalar_text(value).strip().lower() in {"", "not supplied"}
            return "not-entered" if missing or days == 0 else "requires-review"
        return "verified" if exemption is True and days is not None else "requires-review"
    if mapping_id == "m2-cover-question-e":
        cover = _bool_value(context.get("explicit_family_cover"))
        visible = _bool_value(value)
        if visible != cover:
            return "requires-review"
        days = _day_count(context.get("explicit_local_days"))
        if cover is False:
            return "verified"
        return "verified" if cover is True and days == 365 else "requires-review"
    if mapping_id == "m2-days-not-liable-a":
        cover = _bool_value(context.get("explicit_family_cover"))
        if cover is True:
            return "not-entered"
        return "verified" if cover is False and _day_count(value) is not None else "requires-review"
    if mapping_id == "spouse-had-question":
        had_spouse = _bool_value(context.get("had_spouse", value))
        visible = _bool_value(value)
        if _bool_value(context.get("contradicted")) is not False:
            return "requires-review"
        return "verified" if had_spouse is not None and visible == had_spouse else "requires-review"
    return "requires-review"


def requested_fact_handoff(
    raw: Dict[str, Any],
    income_year: Any,
    root: Optional[Path],
    effective_status: str,
    *,
    row_kind: str = "external-row",
    fact_key: str = "",
    fact_value: Any = None,
) -> Dict[str, Any]:
    destination_key = _strict_text(raw.get("destination_key"))
    requested = _strict_text(raw.get("action_kind"))
    if not requested and destination_key:
        requested = MAPPING_ACTIONS.get(destination_key, "destination-requires-review")
    if not requested and effective_status == "evidence":
        requested = "resolve-before-entry"
    elif not requested and effective_status == "skipped":
        requested = "not-entered-directly"
    if requested not in TAXONOMY:
        requested = "destination-requires-review"
    context = _context_dict(raw.get("destination_context"))
    if destination_key and not _binding_allowed(row_kind, fact_key, destination_key):
        destination_value = unresolved_destination()
        requested = "destination-requires-review"
    elif destination_key:
        applicability = _mapping_applicability(destination_key, fact_value, context)
        if applicability == "not-entered":
            destination_value = not_entered_destination()
            requested = "not-entered-directly"
        elif applicability == "requires-review":
            destination_value = unresolved_destination()
            requested = "destination-requires-review"
        else:
            destination_value = verified_destination(
                destination_key,
                income_year,
                root,
                context=context,
            )
    elif requested in {"retain-evidence", "not-entered-directly"}:
        destination_value = not_entered_destination()
    else:
        destination_value = unresolved_destination()
    return {
        "kind": requested,
        "next_action": ACTION_TEXT[requested],
        "destination": destination_value,
    }


def _raw_fact_key(value: Any, index: int) -> str:
    if isinstance(value, dict):
        key = _strict_text(value.get("key"))
        if key:
            return key
    return f"fact-{index}"


def _fact_binding_key(row_kind: str, key: str) -> str:
    if (row_kind, key) in APPROVED_FACT_DESTINATIONS:
        return key
    duplicate = re.fullmatch(r"(.+)-([2-9]\d*)", key)
    if duplicate and (row_kind, duplicate.group(1)) in APPROVED_FACT_DESTINATIONS:
        return duplicate.group(1)
    return key


def normalize_fact(
    value: Any,
    index: int,
    *,
    status: Any,
    income_year: Any,
    root: Optional[Path],
    row_kind: str = "external-row",
) -> Dict[str, Any]:
    raw = value if isinstance(value, dict) else {"value": value}
    key = _raw_fact_key(raw, index)
    binding_key = _fact_binding_key(row_kind, key)
    label = _strict_text(raw.get("label")) or f"Fact {index}"
    fact_value = _visible_value(raw.get("value"))
    destination_key = _strict_text(raw.get("destination_key"))
    action_kind = _strict_text(raw.get("action_kind"))
    destination_context = _context_dict(raw.get("destination_context"))
    raw_handoff = raw.get("handoff")
    if not destination_key and isinstance(raw_handoff, dict):
        raw_destination = raw_handoff.get("destination")
        if isinstance(raw_destination, dict):
            destination_key = _strict_text(raw_destination.get("mapping_id"))
            if not destination_context:
                destination_context = _context_dict(raw_destination.get("context"))
        if not action_kind:
            prior_kind = _strict_text(raw_handoff.get("kind"))
            if prior_kind in TAXONOMY and prior_kind != "accountant-handoff-only":
                action_kind = prior_kind
    if destination_key and not action_kind:
        action_kind = MAPPING_ACTIONS.get(destination_key, "destination-requires-review")
    declarative = dict(raw)
    declarative["destination_key"] = destination_key
    declarative["action_kind"] = action_kind
    declarative["destination_context"] = destination_context
    prepared_handoff = requested_fact_handoff(
        declarative,
        income_year,
        root,
        effective_status_kind(status),
        row_kind=row_kind,
        fact_key=binding_key,
        fact_value=fact_value,
    )
    normalized_handoff = normalize_handoff(
        prepared_handoff,
        status_kind=status,
        income_year=income_year,
        root=root,
    )
    declarative_action_kind = action_kind or prepared_handoff["kind"]
    return {
        "key": key,
        "binding_key": binding_key,
        "label": label,
        "value": fact_value,
        "why": _strict_text(raw.get("why")),
        "action_kind": declarative_action_kind,
        "destination_key": destination_key,
        "destination_context": destination_context,
        "handoff": normalized_handoff,
    }


def _fact_signature(value: Dict[str, Any]) -> str:
    comparable = {key: item for key, item in value.items() if key != "handoff"}
    return json.dumps(comparable, sort_keys=True, default=scalar_text)


def _deduplicate_facts(values: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    signatures: set[str] = set()
    key_counts: Dict[str, int] = {}
    for value in values:
        signature = _fact_signature(value)
        if signature in signatures:
            continue
        signatures.add(signature)
        base_key = value["key"]
        key_counts[base_key] = key_counts.get(base_key, 0) + 1
        if key_counts[base_key] > 1:
            value = dict(value)
            value["key"] = f"{base_key}-{key_counts[base_key]}"
        result.append(value)
    return result


def _common_destination(facts: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not facts:
        return None
    destinations = [fact["handoff"]["destination"] for fact in facts]
    first = json.dumps(destinations[0], sort_keys=True, default=scalar_text)
    if all(json.dumps(value, sort_keys=True, default=scalar_text) == first for value in destinations[1:]):
        return destinations[0]
    return None


def aggregate_handoff(status: Any, facts: List[Dict[str, Any]]) -> Dict[str, Any]:
    effective_status = effective_status_kind(status)
    common_destination = _common_destination(facts)
    if effective_status == "review":
        kind = "accountant-handoff-only"
        destination_value = common_destination or unresolved_destination(
            "Destination requires review. Follow each fact destination after accountant review."
        )
    elif effective_status == "skipped":
        kind = "not-entered-directly"
        destination_value = not_entered_destination()
    elif effective_status == "evidence":
        fact_kinds = {item["handoff"]["kind"] for item in facts}
        if fact_kinds.issubset({"retain-evidence", "not-entered-directly"}):
            kind = "retain-evidence"
            destination_value = not_entered_destination()
        else:
            kind = "resolve-before-entry"
            destination_value = common_destination or unresolved_destination()
    elif len(facts) == 1:
        kind = facts[0]["handoff"]["kind"]
        destination_value = facts[0]["handoff"]["destination"]
    elif all(item["handoff"]["kind"] == "not-entered-directly" for item in facts):
        kind = "not-entered-directly"
        destination_value = not_entered_destination()
    else:
        kind = "destination-requires-review"
        destination_value = unresolved_destination(
            "Destinations differ or require review. Follow each fact action."
        )
    return {
        "kind": kind,
        "label": TAXONOMY[kind]["label"],
        "next_action": ACTION_TEXT[kind],
        "destination": destination_value,
    }


def normalize_row_contract(
    *,
    row_kind: Any,
    facts: Any,
    handoff: Any,
    status: Any,
    income_year: Any,
    question: Any,
    answer: Any,
    why: Any,
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    effective_row_kind = _strict_text(row_kind) or "external-row"
    raw_facts = facts if isinstance(facts, list) and facts else compatibility_facts(question, answer, why)
    normalized_facts = [
        normalize_fact(
            item,
            index,
            status=status,
            income_year=income_year,
            root=root,
            row_kind=effective_row_kind,
        )
        for index, item in enumerate(raw_facts, start=1)
    ]
    normalized_facts = _deduplicate_facts(normalized_facts)
    return {
        "row_kind": effective_row_kind,
        "facts": normalized_facts,
        "handoff": aggregate_handoff(status, normalized_facts),
    }


def build_row_contract(
    row_kind: str,
    status: Any,
    facts: Iterable[Dict[str, Any]],
    *,
    income_year: Any = "",
    root: Optional[Path] = None,
) -> Dict[str, Any]:
    return normalize_row_contract(
        row_kind=row_kind,
        facts=list(facts),
        handoff={},
        status=status,
        income_year=income_year,
        question="",
        answer="",
        why="",
        root=root,
    )


def canonical_status(kind: str) -> str:
    return {
        "answer": "Used",
        "ato": "ATO label",
        "evidence": "Evidence",
        "review": "Accountant review",
        "skipped": "N/A skipped",
    }[kind]


def _extraction_has_status(raw: Dict[str, Any]) -> bool:
    return any(
        key in raw and raw.get(key) is not None and scalar_text(raw.get(key)).strip()
        for key in ("status", "status_kind", "tab_kind")
    )


def _extraction_has_provenance(raw: Dict[str, Any]) -> bool:
    missing = {"missing", "n/a", "none", "not supplied", "unknown"}
    return any(
        _strict_text(raw.get(key))
        and _strict_text(raw.get(key)).lower() not in missing
        for key in ("document", "source_file", "source_note")
    )


def _normalized_extraction_facts(raw: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    facts = raw.get("facts")
    if raw.get("row_kind") != "ai-extraction" or not isinstance(facts, list) or not facts:
        return None
    if any(not isinstance(item, dict) or not isinstance(item.get("handoff"), dict) for item in facts):
        return None
    return facts


def normalize_extraction_row(
    raw: Any,
    income_year: Any,
    *,
    index: int = 1,
    root: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    if isinstance(raw, dict) and not raw:
        return None
    malformed = not isinstance(raw, dict)
    if malformed:
        normalized: Dict[str, Any] = {
            "number": f"AI-MALFORMED-{index}",
            "document": "Malformed AI extraction input",
            "page": "",
            "field": "AI extraction",
            "value": raw,
            "confidence": "",
            "target_label": "",
            "status": "Accountant review",
            "status_kind": "review",
        }
        raw_facts: List[Dict[str, Any]] = [
            fact(
                "malformed-input",
                "Malformed extraction input",
                raw,
                action_kind="destination-requires-review",
                why="Malformed extraction input remains visible for review.",
            )
        ]
        kind = "review"
    else:
        normalized = dict(raw)
        if _extraction_has_status(normalized):
            kind = effective_status_kind(
                normalized.get("status"),
                normalized.get("status_kind"),
                normalized.get("tab_kind"),
            )
        else:
            kind = "answer" if normalized.get("confirmed") is True else "evidence"
        has_provenance = _extraction_has_provenance(normalized)
        if not has_provenance:
            kind = effective_status_kind(kind, "evidence")
            if not _strict_text(normalized.get("document")):
                normalized["document"] = "Not supplied"
        normalized.setdefault("number", f"AI-{index}")
        prior_facts = _normalized_extraction_facts(normalized)
        if prior_facts is not None:
            raw_facts = list(prior_facts)
        else:
            raw_facts = []
            for key, label in (
                ("document", "Source document"),
                ("source_file", "Source file"),
                ("page", "Page"),
                ("source_note", "Source note"),
            ):
                if key in normalized and normalized[key] is not None and scalar_text(normalized[key]).strip():
                    raw_facts.append(
                        fact(
                            key,
                            label,
                            normalized[key],
                            action_kind="retain-evidence",
                            why=(
                                "Source provenance was not supplied and must be resolved before use."
                                if key == "document" and not has_provenance
                                else "Source context for confirmation."
                            ),
                        )
                    )
            raw_facts.append(
                fact(
                    "extracted-value",
                    text_value(normalized.get("field"), "Extracted value"),
                    _visible_value(normalized.get("value")),
                    why="Confirm this value against the source document.",
                )
            )
            if "confidence" in normalized and normalized["confidence"] is not None and scalar_text(normalized["confidence"]).strip():
                raw_facts.append(
                    fact(
                        "confidence",
                        "Extraction confidence",
                        normalized["confidence"],
                        action_kind="not-entered-directly",
                        why="Confidence is context only and is not a return field.",
                    )
                )
            if "target_label" in normalized and normalized["target_label"] is not None and scalar_text(normalized["target_label"]).strip():
                raw_facts.append(
                    fact(
                        "suggested-target",
                        "Suggested target (unverified)",
                        normalized["target_label"],
                        action_kind="destination-requires-review",
                        why="A supplied target label is not a verified destination mapping.",
                    )
                )
            supplied_facts = normalized.get("facts")
            if isinstance(supplied_facts, list):
                raw_facts.extend(supplied_facts)
        if not has_provenance and not any(
            isinstance(item, dict) and item.get("key") == "document"
            for item in raw_facts
        ):
            raw_facts.insert(
                0,
                fact(
                    "document",
                    "Source document",
                    normalized.get("document", "Not supplied"),
                    action_kind="retain-evidence",
                    why="Source provenance was not supplied and must be resolved before use.",
                ),
            )
    normalized["status_kind"] = kind
    normalized["status"] = canonical_status(kind)
    normalized["row_kind"] = "ai-extraction"
    contract = normalize_row_contract(
        row_kind="ai-extraction",
        facts=raw_facts,
        handoff=normalized.get("handoff"),
        status=kind,
        income_year=income_year,
        question=normalized.get("field"),
        answer=normalized.get("value"),
        why="Confirm the extracted value against the source document before use.",
        root=root,
    )
    normalized.update(contract)
    return normalized
