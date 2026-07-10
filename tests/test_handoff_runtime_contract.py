from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import taxmate_handoff  # noqa: E402
import taxmate_intake  # noqa: E402
import taxmate_taxpack  # noqa: E402


EXPECTED_MAPPING_SOURCES = {
    "phi-tax-claim-code": {
        "mytax": "ato-f99c3a4ad079",
        "paper": "ato-2a2cf8a8c462",
    },
    "phi-premiums-j": {
        "mytax": "ato-f99c3a4ad079",
        "paper": "ato-2a2cf8a8c462",
    },
    "phi-rebate-k": {
        "mytax": "ato-f99c3a4ad079",
        "paper": "ato-2a2cf8a8c462",
    },
    "phi-benefit-code-l": {
        "mytax": "ato-f99c3a4ad079",
        "paper": "ato-2a2cf8a8c462",
    },
    "m1-exemption-question": {
        "mytax": "ato-4cedc9f93767",
        "paper": "ato-39155fe09d00",
    },
    "m1-full-days-v": {
        "mytax": "ato-4cedc9f93767",
        "paper": "ato-39155fe09d00",
    },
    "m1-half-days-w": {
        "mytax": "ato-4cedc9f93767",
        "paper": "ato-39155fe09d00",
    },
    "m2-cover-question-e": {
        "mytax": "ato-836a84c52e60",
        "paper": "ato-b8cc03014dc1",
    },
    "m2-days-not-liable-a": {
        "mytax": "ato-836a84c52e60",
        "paper": "ato-b8cc03014dc1",
    },
    "spouse-had-question": {
        "mytax": "ato-815a889d0a59",
        "paper": "ato-29a73bbec8f5",
    },
}

EXPECTED_BASE_CHANNEL_STATES = {
    mapping_id: {
        channel_name: (
            "requires-review"
            if (mapping_id, channel_name)
            in {
                ("m1-exemption-question", "paper"),
                ("m2-days-not-liable-a", "mytax"),
                ("spouse-had-question", "paper"),
            }
            else "verified"
        )
        for channel_name in ("mytax", "paper")
    }
    for mapping_id in EXPECTED_MAPPING_SOURCES
}

ALLOWED_DESTINATION_KINDS = {"verified", "requires-review", "not-entered"}
ALLOWED_CHANNEL_STATES = {
    "verified",
    "read-only",
    "not-entered",
    "requires-review",
}


def required_answers(**overrides: Any) -> dict[str, Any]:
    answers: dict[str, Any] = {
        "income_year": "2025-26",
        "resident": True,
        "state": "VIC",
        "date_of_birth": "1990-01-01",
        "under_18": False,
        "final_return": False,
        "tfn_present": True,
    }
    answers.update(overrides)
    return answers


def statement(code: Any, **overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "insurer": "Example Health Fund",
        "membership_id": "SYNTHETIC-1",
        "benefit_code": "30",
        "premiums_eligible_for_rebate": 0,
        "rebate_received": 0,
        "tax_claim_code": code,
        "days_covered": 365,
        "period_start": "2025-07-01",
        "period_end": "2026-06-30",
        "evidence": "private health statement held",
    }
    value.update(overrides)
    return value


def phi_payload(code: Any, **statement_overrides: Any) -> dict[str, Any]:
    return taxmate_intake.answers_to_pack_payload(
        required_answers(
            private_health_medicare={
                "private_health_cover": True,
                "cover_period_start": "2025-07-01",
                "cover_period_end": "2026-06-30",
                "days_covered": 365,
                "statements": [statement(code, **statement_overrides)],
            }
        )
    )


def all_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("items", "abn_items", "bas_items", "missing_facts", "evidence_items"):
        rows.extend(payload.get(key, []))
    return rows


def row(payload: dict[str, Any], number: str) -> dict[str, Any]:
    return next(item for item in all_rows(payload) if str(item.get("number")) == number)


def facts_by_key(item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(fact["key"]): fact for fact in item["facts"]}


def destination(fact: dict[str, Any]) -> dict[str, Any]:
    value = fact["handoff"]["destination"]
    if not isinstance(value, dict):
        raise AssertionError("destination must be an object")
    return value


def channel(destination_value: dict[str, Any], name: str) -> dict[str, Any]:
    value = destination_value["channels"][name]
    if not isinstance(value, dict):
        raise AssertionError(f"{name} channel must be an object")
    return value


def channel_source_ids(destination_value: dict[str, Any], name: str) -> set[str]:
    return {
        str(source["source_id"])
        for source in channel(destination_value, name)["sources"]
    }


class DestinationManifestContractTests(unittest.TestCase):
    def test_manifest_and_runtime_binding_sets_are_exact(self) -> None:
        manifest = taxmate_handoff.load_destination_manifest(ROOT)
        self.assertIs(type(manifest["schema_version"]), int)
        self.assertEqual(2, manifest["schema_version"])
        self.assertEqual(set(EXPECTED_MAPPING_SOURCES), set(manifest["destinations"]))

        self.assertTrue(hasattr(taxmate_handoff, "APPROVED_DESTINATION_BINDINGS"))
        bindings = taxmate_handoff.APPROVED_DESTINATION_BINDINGS
        self.assertEqual(set(EXPECTED_MAPPING_SOURCES), set(bindings))
        self.assertEqual(
            {
                ("private-health-statement", "tax-claim-code"),
                ("private-health-statement", "premiums-eligible-for-rebate"),
                ("private-health-statement", "rebate-received"),
                ("private-health-statement", "benefit-code"),
                ("medicare-levy-review", "exemption-signal"),
                ("medicare-levy-review", "full-exemption-days"),
                ("medicare-levy-review", "half-exemption-days"),
                ("medicare-surcharge-review", "full-year-family-cover"),
                ("medicare-surcharge-review", "days-not-liable"),
                ("spouse-review", "had-spouse"),
            },
            set(taxmate_handoff.APPROVED_FACT_DESTINATIONS),
        )

    def test_manifest_sources_locations_and_base_channel_states_match_bindings(self) -> None:
        manifest = taxmate_handoff.load_destination_manifest(ROOT)
        bindings = taxmate_handoff.APPROVED_DESTINATION_BINDINGS

        for mapping_id, expected_channels in EXPECTED_MAPPING_SOURCES.items():
            for channel_name, expected_source_id in expected_channels.items():
                with self.subTest(mapping=mapping_id, channel=channel_name):
                    manifest_channel = manifest["destinations"][mapping_id][channel_name]
                    binding_channel = bindings[mapping_id][channel_name]
                    self.assertEqual(expected_source_id, manifest_channel["source_id"])
                    self.assertEqual(expected_source_id, binding_channel["source_id"])
                    self.assertEqual(
                        EXPECTED_BASE_CHANNEL_STATES[mapping_id][channel_name],
                        manifest_channel["kind"],
                    )
                    self.assertEqual(manifest_channel["kind"], binding_channel["kind"])
                    self.assertEqual(manifest_channel["location"], binding_channel["location"])
                    self.assertTrue(str(manifest_channel["location"]).strip())

    def test_only_documented_destination_and_channel_kinds_are_used(self) -> None:
        manifest = taxmate_handoff.load_destination_manifest(ROOT)
        self.assertEqual(
            ALLOWED_DESTINATION_KINDS,
            set(taxmate_handoff.DESTINATION_KINDS),
        )
        self.assertEqual(
            ALLOWED_CHANNEL_STATES,
            set(taxmate_handoff.CHANNEL_STATES),
        )
        for mapping in manifest["destinations"].values():
            for name in ("mytax", "paper"):
                self.assertIn(mapping[name]["kind"], ALLOWED_CHANNEL_STATES)

    def test_destination_mapping_errors_rejects_an_unapproved_extra_mapping(self) -> None:
        manifest = taxmate_handoff.load_destination_manifest(ROOT)
        mutated = copy.deepcopy(manifest)
        mutated["destinations"]["unapproved-broad-topic"] = copy.deepcopy(
            mutated["destinations"]["m1-full-days-v"]
        )
        errors = taxmate_handoff.destination_mapping_payload_errors(
            mutated,
            root=ROOT,
        )
        self.assertTrue(any("unapproved" in error for error in errors), errors)

    def test_destination_mapping_errors_rejects_wrong_location_kind_and_schema_types(self) -> None:
        manifest = taxmate_handoff.load_destination_manifest(ROOT)
        mutations = {
            "location": lambda value: value["destinations"]["phi-premiums-j"]["mytax"].update(
                location="Question M1 label V"
            ),
            "kind": lambda value: value["destinations"]["spouse-had-question"]["paper"].update(
                kind="verified"
            ),
            "schema": lambda value: value.update(schema_version=True),
            "hash": lambda value: value["destinations"]["phi-premiums-j"]["mytax"].update(
                content_hash="Z" * 64
            ),
        }
        for name, mutate in mutations.items():
            with self.subTest(mutation=name):
                mutated = copy.deepcopy(manifest)
                mutate(mutated)
                self.assertTrue(
                    taxmate_handoff.destination_mapping_payload_errors(mutated, root=ROOT)
                )


class CanonicalStatusAndActionTests(unittest.TestCase):
    def test_effective_status_precedence_includes_na_skipped(self) -> None:
        cases = (
            (("N/A skipped",), "skipped"),
            (("n/a",), "skipped"),
            (("grey",), "skipped"),
            (("Used", "Evidence"), "evidence"),
            (("ATO label", "Used"), "answer"),
            (("N/A skipped", "Accountant review"), "review"),
            (("", "Claimable"), "review"),
        )
        for values, expected in cases:
            with self.subTest(values=values):
                self.assertEqual(
                    expected,
                    taxmate_handoff.effective_status_kind(*values),
                )

    def test_status_policy_uses_canonical_action_text_and_safe_destinations(self) -> None:
        verified = taxmate_handoff.verified_destination(
            "m1-full-days-v",
            "2025-26",
            ROOT,
        )
        raw = {
            "kind": "enter-reviewed-value",
            "next_action": "Copy now.",
            "destination": verified,
        }
        expected = {
            "Used": ("enter-reviewed-value", "verified"),
            "Evidence": ("resolve-before-entry", "verified"),
            "N/A skipped": ("not-entered-directly", "not-entered"),
            "Accountant review": ("accountant-handoff-only", "verified"),
        }
        for status, (action_kind, destination_kind) in expected.items():
            with self.subTest(status=status):
                normalized = taxmate_handoff.normalize_handoff(
                    raw,
                    status_kind=status,
                    income_year="2025-26",
                    root=ROOT,
                )
                self.assertEqual(action_kind, normalized["kind"])
                self.assertEqual(destination_kind, normalized["destination"]["kind"])
                self.assertEqual(
                    taxmate_handoff.ACTION_TEXT[action_kind],
                    normalized["next_action"],
                )
                if action_kind == "accountant-handoff-only":
                    self.assertNotRegex(normalized["next_action"].lower(), r"\b(?:copy|enter)\b")

    def test_row_handoff_cannot_weaken_fact_aggregate(self) -> None:
        contract = taxmate_handoff.normalize_row_contract(
            row_kind="individual-return",
            facts=[
                taxmate_handoff.fact(
                    "unresolved",
                    "Unresolved fact",
                    0,
                    action_kind="destination-requires-review",
                )
            ],
            handoff={
                "kind": "enter-reviewed-value",
                "next_action": "Enter now.",
                "destination": {
                    "kind": "verified",
                    "label": "Wrong destination",
                    "mapping_id": "m1-full-days-v",
                },
            },
            status="Used",
            income_year="2025-26",
            question="",
            answer=0,
            why="",
            root=ROOT,
        )
        self.assertEqual("destination-requires-review", contract["facts"][0]["handoff"]["kind"])
        self.assertEqual("destination-requires-review", contract["handoff"]["kind"])
        self.assertEqual("requires-review", contract["handoff"]["destination"]["kind"])

    def test_known_non_entry_destination_remains_explicit_for_used_status(self) -> None:
        contract = taxmate_handoff.build_row_contract(
            "private-health-statement",
            "Used",
            [
                taxmate_handoff.fact(
                    "premiums-eligible-for-rebate",
                    "Premiums eligible for rebate",
                    0,
                    action_kind="enter-reviewed-value",
                    destination_key="phi-premiums-j",
                    destination_context={"tax_claim_code": "F", "conflicted": False},
                )
            ],
            income_year="2025-26",
            root=ROOT,
        )
        prepared = contract["facts"][0]["handoff"]
        self.assertEqual("not-entered-directly", prepared["kind"])
        self.assertEqual("not-entered", prepared["destination"]["kind"])


class MalformedAndFalseyFactTests(unittest.TestCase):
    def test_blank_row_normalizes_to_one_visible_unresolved_fact(self) -> None:
        contract = taxmate_handoff.normalize_row_contract(
            row_kind="",
            facts=None,
            handoff={"kind": "enter-reviewed-value"},
            status="",
            income_year="2025-26",
            question="",
            answer=None,
            why="",
            root=ROOT,
        )
        self.assertEqual("external-row", contract["row_kind"])
        self.assertEqual(1, len(contract["facts"]))
        self.assertEqual("Not supplied", contract["facts"][0]["value"])
        self.assertEqual("accountant-handoff-only", contract["handoff"]["kind"])

    def test_falsey_and_duplicate_facts_are_preserved_with_unique_keys(self) -> None:
        contract = taxmate_handoff.build_row_contract(
            "test-row",
            "Evidence",
            [
                taxmate_handoff.fact("amount", "Amount", 0, action_kind="retain-evidence"),
                taxmate_handoff.fact("amount", "Flag", False, action_kind="retain-evidence"),
            ],
            income_year="2025-26",
            root=ROOT,
        )
        self.assertEqual([0, False], [fact["value"] for fact in contract["facts"]])
        self.assertEqual(2, len({fact["key"] for fact in contract["facts"]}))

    def test_unapproved_fact_to_destination_binding_fails_closed(self) -> None:
        contract = taxmate_handoff.build_row_contract(
            "individual-return",
            "Used",
            [
                taxmate_handoff.fact(
                    "gross-interest",
                    "Gross interest",
                    10,
                    action_kind="enter-reviewed-value",
                    destination_key="phi-premiums-j",
                )
            ],
            income_year="2025-26",
            root=ROOT,
        )
        fact = contract["facts"][0]
        self.assertEqual("destination-requires-review", fact["handoff"]["kind"])
        self.assertEqual("requires-review", destination(fact)["kind"])

        forged = taxmate_handoff.normalize_row_contract(
            row_kind="private-health-statement",
            facts=[
                {
                    "key": "gross-interest",
                    "binding_key": "premiums-eligible-for-rebate",
                    "label": "Gross interest",
                    "value": 10,
                    "action_kind": "enter-reviewed-value",
                    "destination_key": "phi-premiums-j",
                    "destination_context": {
                        "tax_claim_code": "A",
                        "conflicted": False,
                    },
                }
            ],
            handoff={},
            status="Used",
            income_year="2025-26",
            question="",
            answer="",
            why="",
            root=ROOT,
        )
        forged_fact = forged["facts"][0]
        self.assertEqual("gross-interest", forged_fact["binding_key"])
        self.assertEqual("requires-review", destination(forged_fact)["kind"])

    def test_mapped_duplicate_facts_remain_bound_after_renormalization(self) -> None:
        context = {"tax_claim_code": "A", "conflicted": False}
        contract = taxmate_handoff.build_row_contract(
            "private-health-statement",
            "Used",
            [
                taxmate_handoff.fact(
                    "premiums-eligible-for-rebate",
                    "Premium line one",
                    10,
                    destination_key="phi-premiums-j",
                    destination_context=context,
                ),
                taxmate_handoff.fact(
                    "premiums-eligible-for-rebate",
                    "Premium line two",
                    20,
                    destination_key="phi-premiums-j",
                    destination_context=context,
                ),
            ],
            income_year="2025-26",
            root=ROOT,
        )
        repeated = taxmate_handoff.normalize_row_contract(
            row_kind=contract["row_kind"],
            facts=contract["facts"],
            handoff=contract["handoff"],
            status="Used",
            income_year="2025-26",
            question="",
            answer="",
            why="",
            root=ROOT,
        )
        self.assertEqual(
            ["premiums-eligible-for-rebate", "premiums-eligible-for-rebate-2"],
            [fact["key"] for fact in repeated["facts"]],
        )
        self.assertTrue(
            all(destination(fact)["mapping_id"] == "phi-premiums-j" for fact in repeated["facts"])
        )


class PrivateHealthConditionalDestinationTests(unittest.TestCase):
    def test_phi_mapping_requires_exact_context_and_matching_claim_code(self) -> None:
        contexts = (
            {},
            {"tax_claim_code": "A"},
            {"tax_claim_code": "A", "conflicted": False, "extra": False},
            {"tax_claim_code": "E", "conflicted": False},
            {"tax_claim_code": "A", "conflicted": "unknown"},
            {"tax_claim_code": "A", "conflicted": 1},
        )
        for context in contexts:
            with self.subTest(context=context):
                contract = taxmate_handoff.build_row_contract(
                    "private-health-statement",
                    "Used",
                    [
                        taxmate_handoff.fact(
                            "tax-claim-code",
                            "Tax claim code",
                            "A",
                            destination_key="phi-tax-claim-code",
                            destination_context=context,
                        )
                    ],
                    income_year="2025-26",
                    root=ROOT,
                )
                self.assertEqual(
                    "requires-review",
                    destination(contract["facts"][0])["kind"],
                )

        valid = taxmate_handoff.build_row_contract(
            "private-health-statement",
            "Used",
            [
                taxmate_handoff.fact(
                    "tax-claim-code",
                    "Tax claim code",
                    "A",
                    destination_key="phi-tax-claim-code",
                    destination_context={"tax_claim_code": "A", "conflicted": False},
                )
            ],
            income_year="2025-26",
            root=ROOT,
        )
        self.assertEqual("verified", destination(valid["facts"][0])["kind"])

    def test_phi_tax_claim_code_channel_matrix(self) -> None:
        expected = {
            "A": ("verified", "verified", "verified"),
            "B": ("verified", "verified", "verified"),
            "C": ("verified", "verified", "verified"),
            "D": ("verified", "read-only", "verified"),
            "E": ("verified", "verified", "verified"),
            "F": ("verified", "verified", "verified"),
            "unknown": ("requires-review", "requires-review", "requires-review"),
            "99": ("requires-review", "requires-review", "requires-review"),
        }
        for code, (aggregate, mytax, paper) in expected.items():
            with self.subTest(code=code):
                fact = facts_by_key(row(phi_payload(code), "PHI-STMT-1"))["tax-claim-code"]
                target = destination(fact)
                self.assertEqual(aggregate, target["kind"])
                self.assertEqual(mytax, channel(target, "mytax")["kind"])
                self.assertEqual(paper, channel(target, "paper")["kind"])

    def test_phi_jkl_channel_matrix(self) -> None:
        expected = {
            "A": ("verified", "verified", "verified"),
            "B": ("verified", "verified", "verified"),
            "C": ("verified", "verified", "verified"),
            "D": ("verified", "read-only", "verified"),
            "E": ("verified", "not-entered", "verified"),
            "F": ("not-entered", "not-entered", "not-entered"),
            "unknown": ("requires-review", "requires-review", "requires-review"),
            "99": ("requires-review", "requires-review", "requires-review"),
        }
        fact_keys = (
            "premiums-eligible-for-rebate",
            "rebate-received",
            "benefit-code",
        )
        for code, (aggregate, mytax, paper) in expected.items():
            for fact_key in fact_keys:
                with self.subTest(code=code, fact=fact_key):
                    fact = facts_by_key(row(phi_payload(code), "PHI-STMT-1"))[fact_key]
                    target = destination(fact)
                    self.assertEqual(aggregate, target["kind"])
                    self.assertEqual(mytax, channel(target, "mytax")["kind"])
                    self.assertEqual(paper, channel(target, "paper")["kind"])

    def test_phi_zero_amounts_are_concrete_for_code_c(self) -> None:
        facts = facts_by_key(row(phi_payload("C"), "PHI-STMT-1"))
        for key in ("premiums-eligible-for-rebate", "rebate-received"):
            with self.subTest(key=key):
                self.assertEqual(0, facts[key]["value"])
                self.assertEqual("verified", destination(facts[key])["kind"])

    def test_phi_invalid_values_fail_closed_without_downgrading_valid_siblings(self) -> None:
        payload = phi_payload(
            "C",
            benefit_code="99",
            premiums_eligible_for_rebate=-1,
            rebate_received="unknown",
        )
        facts = facts_by_key(row(payload, "PHI-STMT-1"))
        for key in (
            "benefit-code",
            "premiums-eligible-for-rebate",
            "rebate-received",
        ):
            with self.subTest(key=key):
                self.assertEqual("requires-review", destination(facts[key])["kind"])
                self.assertFalse(str(destination(facts[key]).get("mapping_id", "")).strip())
        self.assertEqual("verified", destination(facts["tax-claim-code"])["kind"])

        for malformed in ("1$2", "1e3", "600.50"):
            with self.subTest(premiums=malformed):
                malformed_facts = facts_by_key(
                    row(
                        phi_payload("C", premiums_eligible_for_rebate=malformed),
                        "PHI-STMT-1",
                    )
                )
                self.assertEqual(
                    "requires-review",
                    destination(malformed_facts["premiums-eligible-for-rebate"])["kind"],
                )
                self.assertEqual(
                    "verified",
                    destination(malformed_facts["tax-claim-code"])["kind"],
                )

    def test_phi_conflicting_claim_code_aliases_fail_closed(self) -> None:
        facts = facts_by_key(
            row(phi_payload("A", claim_code="E"), "PHI-STMT-1")
        )
        for key in (
            "tax-claim-code",
            "premiums-eligible-for-rebate",
            "rebate-received",
            "benefit-code",
        ):
            with self.subTest(key=key):
                self.assertEqual("requires-review", destination(facts[key])["kind"])


class MedicareAndSpouseDestinationGateTests(unittest.TestCase):
    def test_numeric_zero_spouse_answer_remains_visible_and_maps_as_false(self) -> None:
        contract = taxmate_handoff.build_row_contract(
            "spouse-review",
            "Used",
            [
                taxmate_handoff.fact(
                    "had-spouse",
                    "Had spouse",
                    0,
                    destination_key="spouse-had-question",
                    destination_context={
                        "had_spouse": 0,
                        "contradicted": False,
                        "conflicted": False,
                    },
                )
            ],
            income_year="2025-26",
            root=ROOT,
        )
        prepared = contract["facts"][0]
        self.assertEqual(0, prepared["value"])
        self.assertEqual("verified", destination(prepared)["kind"])

    def test_m1_true_exemption_maps_question_and_valid_days(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "medicare_levy": {
                        "reduction": False,
                        "exemption": True,
                        "full_exemption_days": 0,
                        "half_exemption_days": 10,
                        "evidence": "exemption evidence held",
                    }
                }
            )
        )
        facts = facts_by_key(row(payload, "MEDICARE-LEVY"))
        question = destination(facts["exemption-signal"])
        self.assertEqual("verified", question["kind"])
        self.assertEqual("verified", channel(question, "mytax")["kind"])
        self.assertEqual("requires-review", channel(question, "paper")["kind"])
        self.assertIn("ato-39155fe09d00", channel_source_ids(question, "paper"))
        self.assertEqual(0, facts["full-exemption-days"]["value"])
        self.assertEqual("verified", destination(facts["full-exemption-days"])["kind"])
        self.assertEqual("verified", destination(facts["half-exemption-days"])["kind"])

    def test_m1_false_exemption_zero_days_are_not_entered(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "medicare_levy": {
                        "reduction": False,
                        "exemption": False,
                        "full_exemption_days": 0,
                        "half_exemption_days": 0,
                        "evidence": "review facts held",
                    }
                }
            )
        )
        facts = facts_by_key(row(payload, "MEDICARE-LEVY"))
        for key in ("full-exemption-days", "half-exemption-days"):
            with self.subTest(key=key):
                self.assertEqual(0, facts[key]["value"])
                self.assertEqual("not-entered", destination(facts[key])["kind"])

    def test_m1_false_exemption_missing_category_and_days_are_not_entered(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "medicare_levy": {
                        "reduction": False,
                        "exemption": False,
                        "evidence": "review facts held",
                    }
                }
            )
        )
        facts = facts_by_key(row(payload, "MEDICARE-LEVY"))
        for key in ("exemption-category", "full-exemption-days", "half-exemption-days"):
            with self.subTest(key=key):
                self.assertEqual("not-entered", destination(facts[key])["kind"])

    def test_m1_conflicting_or_invalid_days_fail_closed(self) -> None:
        cases = (
            {"exemption": False, "full_exemption_days": 1},
            {"exemption": False, "exemption_category": "category supplied"},
            {"exemption": True, "full_exemption_days": -1},
            {"exemption": True, "full_exemption_days": "1e2"},
            {"exemption": True, "full_exemption_days": 367},
            {"exemption": True, "full_exemption_days": 0, "half_exemption_days": 0},
            {
                "exemption": True,
                "full_exemption_days": 300,
                "half_exemption_days": 100,
            },
            {"exemption": "unknown", "full_exemption_days": 1},
            {"exemption": True, "exemption_signal": False, "full_exemption_days": 1},
        )
        for levy in cases:
            with self.subTest(levy=levy):
                levy["evidence"] = "review facts held"
                payload = taxmate_intake.answers_to_pack_payload(
                    required_answers(private_health_medicare={"medicare_levy": levy})
                )
                facts = facts_by_key(row(payload, "MEDICARE-LEVY"))
                self.assertEqual(
                    "requires-review",
                    destination(facts["full-exemption-days"])["kind"],
                )
                if levy.get("full_exemption_days") != "1e2":
                    self.assertEqual(
                        "requires-review",
                        destination(facts["exemption-signal"])["kind"],
                    )

    def test_m2_cover_mapping_requires_explicit_local_full_year_answer(self) -> None:
        local = {
            "review": True,
            "full_year_appropriate_family_cover": True,
            "appropriate_hospital_cover": True,
            "hospital_cover_days": 365,
            "days_not_liable": 0,
            "evidence": "MLS review facts held",
        }
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(private_health_medicare={"mls": local})
        )
        facts = facts_by_key(row(payload, "MLS-REVIEW"))
        self.assertIn("full-year-family-cover", facts)
        self.assertEqual("verified", destination(facts["full-year-family-cover"])["kind"])
        self.assertEqual(
            "m2-cover-question-e",
            destination(facts["full-year-family-cover"])["mapping_id"],
        )

        inherited_only = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "private_health_cover": True,
                    "cover_period_start": "2025-07-01",
                    "cover_period_end": "2026-06-30",
                    "mls": {
                        "review": True,
                        "days_not_liable": 0,
                        "evidence": "MLS review facts held",
                    },
                }
            )
        )
        inherited_facts = facts_by_key(row(inherited_only, "MLS-REVIEW"))
        self.assertEqual(
            "requires-review",
            destination(inherited_facts["full-year-family-cover"])["kind"],
        )

        broad_local_only = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "mls": {
                        "review": True,
                        "appropriate_hospital_cover": True,
                        "hospital_cover_days": 365,
                        "evidence": "MLS review facts held",
                    }
                }
            )
        )
        broad_local_facts = facts_by_key(row(broad_local_only, "MLS-REVIEW"))
        self.assertEqual(
            "requires-review",
            destination(broad_local_facts["full-year-family-cover"])["kind"],
        )

    def test_m2_explicit_full_year_family_no_answer_maps_without_borrowing_cover(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "mls": {
                        "review": True,
                        "full_year_appropriate_family_cover": False,
                        "hospital_cover_days": 200,
                        "evidence": "MLS review facts held",
                    }
                }
            )
        )
        fact = facts_by_key(row(payload, "MLS-REVIEW"))["full-year-family-cover"]
        self.assertIs(False, fact["value"])
        self.assertEqual("verified", destination(fact)["kind"])
        self.assertEqual("m2-cover-question-e", destination(fact)["mapping_id"])

    def test_m2_semantic_conflicts_fail_closed(self) -> None:
        cases = (
            {
                "full_year_appropriate_family_cover": True,
                "appropriate_hospital_cover": True,
                "hospital_cover_days": 365,
                "cover_period_start": "2025-08-01",
                "cover_period_end": "2026-06-30",
            },
        )
        for mls in cases:
            with self.subTest(mls=mls):
                mls.update({"review": True, "evidence": "MLS review facts held"})
                payload = taxmate_intake.answers_to_pack_payload(
                    required_answers(private_health_medicare={"mls": mls})
                )
                facts = facts_by_key(row(payload, "MLS-REVIEW"))
                self.assertEqual(
                    "requires-review",
                    destination(facts["full-year-family-cover"])["kind"],
                )

    def test_m2_days_not_liable_validates_zero_and_invalid_values(self) -> None:
        cases = (
            (0, "verified"),
            (-1, "requires-review"),
            (367, "requires-review"),
            ("1e2", "requires-review"),
            ("unknown", "requires-review"),
        )
        for value, expected in cases:
            with self.subTest(value=value):
                payload = taxmate_intake.answers_to_pack_payload(
                    required_answers(
                        private_health_medicare={
                            "mls": {
                                "review": True,
                                "full_year_appropriate_family_cover": False,
                                "days_not_liable": value,
                                "evidence": "MLS review facts held",
                            }
                        }
                    )
                )
                fact = facts_by_key(row(payload, "MLS-REVIEW"))["days-not-liable"]
                self.assertEqual(value, fact["value"])
                self.assertEqual(expected, destination(fact)["kind"])
                if expected == "verified":
                    self.assertEqual("requires-review", channel(destination(fact), "mytax")["kind"])
                    self.assertEqual("verified", channel(destination(fact), "paper")["kind"])

        missing_cover = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "mls": {
                        "review": True,
                        "days_not_liable": 0,
                        "evidence": "MLS review facts held",
                    }
                }
            )
        )
        missing_fact = facts_by_key(row(missing_cover, "MLS-REVIEW"))["days-not-liable"]
        self.assertEqual("requires-review", destination(missing_fact)["kind"])

        full_year_cover = taxmate_intake.answers_to_pack_payload(
            required_answers(
                private_health_medicare={
                    "mls": {
                        "review": True,
                        "full_year_appropriate_family_cover": True,
                        "appropriate_hospital_cover": True,
                        "hospital_cover_days": 365,
                        "days_not_liable": 0,
                        "evidence": "MLS review facts held",
                    }
                }
            )
        )
        full_year_fact = facts_by_key(row(full_year_cover, "MLS-REVIEW"))["days-not-liable"]
        self.assertEqual("not-entered", destination(full_year_fact)["kind"])

        overlapping_periods = {
            "_income_year": "2025-26",
            "review": True,
            "full_year_appropriate_family_cover": False,
            "appropriate_hospital_cover": True,
            "hospital_cover_days": 200,
            "days_not_liable": 365,
            "evidence": "MLS review facts held",
        }
        self.assertFalse(
            any(
                "hospital cover days and days not liable exceed" in gap
                for gap in taxmate_intake.mls_review_gaps(overlapping_periods)
            )
        )

    def test_visible_mapped_value_must_match_destination_context(self) -> None:
        cases = (
            (
                "medicare-levy-review",
                "exemption-signal",
                "m1-exemption-question",
                {"exemption": True, "conflicted": False},
            ),
            (
                "medicare-surcharge-review",
                "full-year-family-cover",
                "m2-cover-question-e",
                {
                    "explicit_family_cover": True,
                    "explicit_local_days": 365,
                    "conflicted": False,
                },
            ),
            (
                "spouse-review",
                "had-spouse",
                "spouse-had-question",
                {"had_spouse": True, "contradicted": False, "conflicted": False},
            ),
        )
        for row_kind, fact_key, mapping_id, context in cases:
            with self.subTest(mapping_id=mapping_id):
                contract = taxmate_handoff.build_row_contract(
                    row_kind,
                    "Used",
                    [
                        taxmate_handoff.fact(
                            fact_key,
                            "Mapped question",
                            False,
                            destination_key=mapping_id,
                            destination_context=context,
                        )
                    ],
                    income_year="2025-26",
                    root=ROOT,
                )
                self.assertEqual(
                    "requires-review",
                    destination(contract["facts"][0])["kind"],
                )

    def test_spouse_question_has_verified_mytax_and_review_paper_provenance(self) -> None:
        for had_spouse in (True, False):
            with self.subTest(had_spouse=had_spouse):
                spouse = {"had_spouse": had_spouse}
                if had_spouse:
                    spouse["income_evidence"] = "income facts held"
                payload = taxmate_intake.answers_to_pack_payload(
                    required_answers(
                        private_health_medicare={
                            "spouse": spouse,
                        }
                    )
                )
                fact = facts_by_key(row(payload, "SPOUSE-REVIEW"))["had-spouse"]
                target = destination(fact)
                self.assertEqual("verified", target["kind"])
                self.assertEqual("verified", channel(target, "mytax")["kind"])
                self.assertEqual("requires-review", channel(target, "paper")["kind"])
                self.assertIn("ato-29a73bbec8f5", channel_source_ids(target, "paper"))

    def test_spouse_unknown_conflict_and_contradiction_fail_closed(self) -> None:
        spouse_cases = (
            {"had_spouse": "unknown"},
            {"had_spouse": True, "spouse_had": False},
            {"had_spouse": False, "income_for_tests": 100, "income_evidence": "held"},
        )
        for spouse in spouse_cases:
            with self.subTest(spouse=spouse):
                payload = taxmate_intake.answers_to_pack_payload(
                    required_answers(private_health_medicare={"spouse": spouse})
                )
                fact = facts_by_key(row(payload, "SPOUSE-REVIEW"))["had-spouse"]
                self.assertEqual("requires-review", destination(fact)["kind"])
                self.assertFalse(str(destination(fact).get("mapping_id", "")).strip())


class IncomeYearContractTests(unittest.TestCase):
    def test_destination_requires_explicit_supported_income_year(self) -> None:
        supported = taxmate_handoff.verified_destination(
            "m1-full-days-v",
            "2025-26",
            ROOT,
        )
        self.assertEqual("verified", supported["kind"])

        for income_year in (None, "", False, 0, "2024-25"):
            with self.subTest(income_year=income_year):
                unresolved = taxmate_handoff.verified_destination(
                    "m1-full-days-v",
                    income_year,
                    ROOT,
                )
                self.assertEqual("requires-review", unresolved["kind"])

        implicit = taxmate_handoff.verified_destination(
            "m1-full-days-v",
            root=ROOT,
        )
        self.assertEqual("requires-review", implicit["kind"])

    def test_payload_income_year_downgrades_stale_private_health_mapping(self) -> None:
        answers = required_answers(income_year="2024-25")
        answers["private_health_medicare"] = {
            "private_health_cover": True,
            "statements": [statement("C")],
        }
        payload = taxmate_intake.answers_to_pack_payload(answers)
        facts = facts_by_key(row(payload, "PHI-STMT-1"))
        for key in (
            "tax-claim-code",
            "premiums-eligible-for-rebate",
            "rebate-received",
            "benefit-code",
        ):
            with self.subTest(key=key):
                self.assertEqual("requires-review", destination(facts[key])["kind"])


class SharedExtractionNormalizationTests(unittest.TestCase):
    def test_shared_extraction_normalizer_is_idempotent(self) -> None:
        raw = {
            "document": "statement.pdf",
            "field": "Tax withheld",
            "value": 0,
            "confidence": 0,
            "confirmed": False,
        }
        first = taxmate_handoff.normalize_extraction_row(raw, "2025-26", index=1, root=ROOT)
        self.assertIsNotNone(first)
        assert first is not None
        second = taxmate_handoff.normalize_extraction_row(first, "2025-26", index=1, root=ROOT)
        self.assertEqual(first, second)

    def test_empty_extraction_dict_is_skipped_at_both_boundaries(self) -> None:
        self.assertEqual([], taxmate_intake.extraction_rows([{}]))
        self.assertEqual([], taxmate_taxpack.extracted_values([{}], "2025-26"))
        self.assertIsNone(
            taxmate_handoff.normalize_extraction_row({}, "2025-26", index=1)
        )

    def test_intake_and_taxpack_use_the_same_extraction_contract(self) -> None:
        raw = {
            "document": "statement.pdf",
            "page": 0,
            "field": "Tax withheld",
            "value": 0,
            "confidence": False,
            "target_label": "1 Salary or wages",
            "confirmed": True,
        }
        intake_rows = taxmate_intake.extraction_rows([raw])
        taxpack_rows = taxmate_taxpack.extracted_values([raw], "2025-26")
        self.assertEqual(intake_rows, taxpack_rows)
        self.assertEqual("answer", taxmate_handoff.effective_status_kind(intake_rows[0]["status"]))
        facts = facts_by_key(intake_rows[0])
        self.assertEqual(0, facts["page"]["value"])
        self.assertEqual(0, facts["extracted-value"]["value"])
        self.assertIs(False, facts["confidence"]["value"])
        self.assertEqual(
            "requires-review",
            destination(facts["suggested-target"])["kind"],
        )

    def test_explicit_evidence_is_not_upgraded_by_confirmed_true(self) -> None:
        raw = {
            "document": "statement.pdf",
            "field": "Tax withheld",
            "value": 10,
            "confirmed": True,
            "status": "Evidence",
        }
        normalized = taxmate_handoff.normalize_extraction_row(
            raw,
            "2025-26",
            index=1,
        )
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual("evidence", normalized["status_kind"])
        self.assertEqual("resolve-before-entry", normalized["handoff"]["kind"])

    def test_source_less_extraction_fails_closed_with_explicit_provenance_gap(self) -> None:
        normalized = taxmate_handoff.normalize_extraction_row(
            {
                "field": "Tax withheld",
                "value": 0,
                "confirmed": True,
            },
            "2025-26",
            index=1,
        )
        self.assertIsNotNone(normalized)
        assert normalized is not None
        self.assertEqual("evidence", normalized["status_kind"])
        self.assertEqual("Not supplied", normalized["document"])
        facts = facts_by_key(normalized)
        self.assertEqual("Not supplied", facts["document"]["value"])
        self.assertEqual("resolve-before-entry", normalized["handoff"]["kind"])
        self.assertEqual(
            normalized,
            taxmate_handoff.normalize_extraction_row(normalized, "2025-26", index=1),
        )

    def test_malformed_extraction_scalars_remain_visible_review_rows(self) -> None:
        for index, value in enumerate((False, 0, ["malformed"]), start=1):
            with self.subTest(value=value):
                normalized = taxmate_handoff.normalize_extraction_row(
                    value,
                    "2025-26",
                    index=index,
                )
                self.assertIsNotNone(normalized)
                assert normalized is not None
                self.assertEqual("review", normalized["status_kind"])
                self.assertIn(value, [fact["value"] for fact in normalized["facts"]])
                self.assertEqual("accountant-handoff-only", normalized["handoff"]["kind"])

    def test_supplied_extraction_facts_cannot_hide_or_verify_target_label(self) -> None:
        raw = {
            "document": "statement.pdf",
            "field": "Tax withheld",
            "value": 10,
            "target_label": "1 Salary or wages",
            "confirmed": True,
            "facts": [
                taxmate_handoff.fact(
                    "custom",
                    "Custom",
                    10,
                    action_kind="enter-reviewed-value",
                    destination_key="spouse-had-question",
                )
            ],
        }
        normalized = taxmate_handoff.normalize_extraction_row(
            raw,
            "2025-26",
            index=1,
        )
        self.assertIsNotNone(normalized)
        assert normalized is not None
        facts = facts_by_key(normalized)
        self.assertIn("suggested-target", facts)
        self.assertEqual(
            "requires-review",
            destination(facts["suggested-target"])["kind"],
        )
        self.assertEqual("requires-review", destination(facts["custom"])["kind"])


class ProducerAtomicFactContractTests(unittest.TestCase):
    def test_private_health_rows_keep_atomic_notes_source_lineage_and_checked_at(self) -> None:
        checked_at = "2026-06-30"
        sections = {
            "private_health": {
                "covered": True,
                "period_start": "2025-07-01",
                "period_end": "2026-06-30",
                "days_covered": 365,
                "evidence": "cover record held",
                "notes": ["overview note", {"review_basis": "overview nested note"}],
                "source_urls": ["https://records.example/overview"],
                "checked_at": checked_at,
            },
            "statements": [
                {
                    **statement("A"),
                    "notes": ["statement note", {"review_basis": "statement nested note"}],
                    "source_urls": ["https://records.example/statement"],
                    "checked_at": checked_at,
                }
            ],
            "medicare_levy": {
                "exemption": True,
                "full_exemption_days": 1,
                "half_exemption_days": 0,
                "evidence": "levy record held",
                "notes": ["levy note", {"review_basis": "levy nested note"}],
                "source_urls": ["https://records.example/levy"],
                "checked_at": checked_at,
            },
            "mls": {
                "review": True,
                "full_year_appropriate_family_cover": True,
                "appropriate_hospital_cover": True,
                "hospital_cover_days": 365,
                "days_not_liable": 0,
                "evidence": "surcharge record held",
                "notes": ["surcharge note", {"review_basis": "surcharge nested note"}],
                "source_urls": ["https://records.example/surcharge"],
                "checked_at": checked_at,
            },
            "spouse": {
                "had_spouse": True,
                "period_start": "2025-07-01",
                "period_end": "2026-06-30",
                "income_for_tests": 0,
                "income_evidence": "spouse record held",
                "notes": ["spouse note", {"review_basis": "spouse nested note"}],
                "source_urls": ["https://records.example/spouse"],
                "checked_at": checked_at,
            },
            "dependant_summary": {
                "count": 1,
                "notes": ["dependant summary note", {"review_basis": "dependant summary nested note"}],
                "source_urls": ["https://records.example/dependant-summary"],
                "checked_at": checked_at,
            },
            "dependants": [
                {
                    "name": "Synthetic dependant",
                    "type": "child",
                    "age": 10,
                    "maintained": True,
                    "evidence": "dependant record held",
                    "notes": ["dependant note", {"review_basis": "dependant nested note"}],
                    "source_urls": ["https://records.example/dependant"],
                    "checked_at": checked_at,
                }
            ],
        }
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(private_health_medicare=sections)
        )
        expected = {
            "PHI-OVERVIEW": ("overview nested note", "https://records.example/overview"),
            "PHI-STMT-1": ("statement nested note", "https://records.example/statement"),
            "MEDICARE-LEVY": ("levy nested note", "https://records.example/levy"),
            "MLS-REVIEW": ("surcharge nested note", "https://records.example/surcharge"),
            "SPOUSE-REVIEW": ("spouse nested note", "https://records.example/spouse"),
            "DEPENDANT-SUMMARY": (
                "dependant summary nested note",
                "https://records.example/dependant-summary",
            ),
            "DEPENDANT-1": ("dependant nested note", "https://records.example/dependant"),
        }
        for number, (note, source_url) in expected.items():
            with self.subTest(number=number):
                prepared = row(payload, number)
                values = [fact["value"] for fact in prepared["facts"]]
                self.assertIn(note, values)
                self.assertIn(checked_at, values)
                self.assertIn(source_url, values)
                self.assertIn(source_url, prepared["source_urls"])
                self.assertEqual(checked_at, prepared["checked_at"])
                self.assertFalse(any(isinstance(value, (dict, list)) for value in values))

    def test_abn_row_keeps_all_profile_review_and_item_facts(self) -> None:
        income_streams = [
            {"label": f"Income stream {index}", "amount": index * 10, "evidence": f"income record {index}"}
            for index in range(1, 7)
        ]
        expense_categories = [
            {"category": f"Expense category {index}", "amount": index, "invoice": f"expense record {index}"}
            for index in range(1, 7)
        ]
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(
                abn_business={
                    "abn": "12 345 678 901",
                    "business_name": "Synthetic Business",
                    "activity": "Software services",
                    "start_date": "2025-07-01",
                    "end_date": "2026-03-31",
                    "gst_registered": False,
                    "gst_registration_date": "2025-07-01",
                    "accounting_basis": "cash",
                    "record_system": "ledger",
                    "income_streams": income_streams,
                    "expense_categories": expense_categories,
                    "private_apportionment": 0,
                    "home_business": False,
                    "motor_vehicle": "mixed use review",
                    "depreciation": "asset schedule held",
                    "capital_expense": False,
                    "loss": 0,
                    "psi": {"income": 0, "results_test": False},
                    "business_vs_hobby": "business",
                    "non_commercial_loss": False,
                }
            )
        )
        prepared = row(payload, "ABN")
        facts = facts_by_key(prepared)
        for key, value in (
            ("end-date", "2026-03-31"),
            ("gst-registered", False),
            ("gst-registration-date", "2025-07-01"),
            ("accounting-basis", "cash"),
            ("private-apportionment", 0),
            ("home-business", False),
            ("loss", 0),
            ("psi-income", 0),
            ("psi-results-test", False),
        ):
            with self.subTest(key=key):
                self.assertEqual(value, facts[key]["value"])
        values = [fact["value"] for fact in prepared["facts"]]
        self.assertEqual("PSI - Income", facts["psi-income"]["label"])
        for index in range(1, 7):
            self.assertIn(f"Income stream {index}", values)
            self.assertIn(f"income record {index}", values)
            self.assertIn(f"Expense category {index}", values)
            self.assertIn(f"expense record {index}", values)
        self.assertNotIn("2 more", prepared["answer"])
        self.assertFalse(any(isinstance(value, (dict, list)) for value in values))

    def test_sample_extended_sections_use_item_level_atomic_facts(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        for number in ("FOREIGN-INCOME", "CRYPTO-CGT", "RENTAL-PROPERTY", "ESS"):
            with self.subTest(number=number):
                prepared = row(payload, number)
                self.assertNotIn("items", {fact["key"] for fact in prepared["facts"]})
                self.assertNotIn("properties", {fact["key"] for fact in prepared["facts"]})
                self.assertFalse(
                    any(isinstance(fact["value"], (dict, list)) for fact in prepared["facts"])
                )
                self.assertFalse(any(" | " in str(fact["value"]) for fact in prepared["facts"]))

    def test_extended_sections_preserve_more_than_four_items_without_dense_facts(self) -> None:
        count = 6
        payload = taxmate_intake.answers_to_pack_payload(
            required_answers(
                foreign_income_items=[
                    {
                        "statement": f"foreign statement {index}",
                        "country": f"Foreign country {index}",
                        "income_type": "employment",
                        "payer": f"Foreign payer {index}",
                        "amount": index * 100,
                        "foreign_tax_paid": 0,
                        "exchange_rate": 1,
                        "residency_status": "Australian resident",
                    }
                    for index in range(1, count + 1)
                ],
                crypto_items=[
                    {
                        "event_type": "sale",
                        "asset": f"Crypto asset {index}",
                        "exchange_or_wallet": f"Wallet {index}",
                        "quantity": index,
                        "acquired_date": "2025-07-01",
                        "disposed_date": "2026-01-01",
                        "cost_base": index * 10,
                        "capital_proceeds": index * 20,
                        "rewards_income": 0,
                        "wallet_records": f"wallet record {index}",
                        "ownership_entity": "individual",
                        "business_use": False,
                        "private_use": False,
                    }
                    for index in range(1, count + 1)
                ],
                rental_property_items=[
                    {
                        "address": f"Rental property {index}",
                        "ownership": "individual",
                        "income": index * 1000,
                        "interest": index * 100,
                        "repairs": 0,
                        "capital_works": 0,
                        "depreciation": 0,
                        "other_expenses": 0,
                        "private_use": False,
                        "private_use_days": 0,
                        "available_days": 365,
                        "records": f"rental record {index}",
                    }
                    for index in range(1, count + 1)
                ],
                ess_items=[
                    {
                        "statement": f"ESS statement {index}",
                        "employer": f"ESS employer {index}",
                        "scheme": f"ESS scheme {index}",
                        "taxed_upfront_discount": index,
                        "deferred_discount": 0,
                        "foreign_source_discount": 0,
                        "tfn_amount_withheld": 0,
                    }
                    for index in range(1, count + 1)
                ],
            )
        )
        expected = {
            "FOREIGN-INCOME": ("foreign-item-", "Foreign country"),
            "CRYPTO-CGT": ("crypto-item-", "Crypto asset"),
            "RENTAL-PROPERTY": ("rental-item-", "Rental property"),
            "ESS": ("ess-item-", "ESS employer"),
        }
        for number, (prefix, marker) in expected.items():
            with self.subTest(number=number):
                prepared = row(payload, number)
                item_facts = [fact for fact in prepared["facts"] if fact["key"].startswith(prefix)]
                values = [fact["value"] for fact in item_facts]
                for index in range(1, count + 1):
                    self.assertIn(f"{marker} {index}", values)
                self.assertFalse(any(isinstance(value, (dict, list)) for value in values))
                self.assertFalse(any(" | " in str(value) for value in values))


if __name__ == "__main__":
    unittest.main()
