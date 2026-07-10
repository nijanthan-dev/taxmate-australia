from __future__ import annotations

import html
import re
import sys
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import taxmate_handoff  # noqa: E402
import taxmate_intake  # noqa: E402
import taxmate_review_guardrails  # noqa: E402
import taxmate_taxpack  # noqa: E402
import taxmate_validate  # noqa: E402


EXPECTED_TAXONOMY = {
    "enter-reviewed-value",
    "answer-guided-question",
    "retain-evidence",
    "resolve-before-entry",
    "accountant-handoff-only",
    "not-entered-directly",
    "destination-requires-review",
}


class HandoffTaxonomyTests(unittest.TestCase):
    def test_taxonomy_is_small_documented_and_complete(self) -> None:
        self.assertEqual(EXPECTED_TAXONOMY, set(taxmate_handoff.TAXONOMY))
        for kind, entry in taxmate_handoff.TAXONOMY.items():
            with self.subTest(kind=kind):
                self.assertTrue(str(entry["label"]).strip())
                self.assertTrue(str(entry["description"]).strip())

    def test_destination_mappings_match_verified_source_state(self) -> None:
        self.assertEqual([], taxmate_handoff.destination_mapping_errors(ROOT))
        manifest = taxmate_handoff.load_destination_manifest(ROOT)

        self.assertEqual("2025-26", manifest["income_year"])
        self.assertTrue(
            {
                "phi-tax-claim-code",
                "phi-premiums-j",
                "phi-rebate-k",
                "phi-benefit-code-l",
                "m1-exemption-question",
                "m1-full-days-v",
                "m1-half-days-w",
                "m2-cover-question-e",
                "m2-days-not-liable-a",
                "spouse-had-question",
            }.issubset(manifest["destinations"])
        )

    def test_each_taxonomy_category_normalizes_for_a_non_review_row(self) -> None:
        for kind in EXPECTED_TAXONOMY:
            with self.subTest(kind=kind):
                if kind in {"enter-reviewed-value", "answer-guided-question"}:
                    destination = {
                        "kind": "verified",
                        "label": "Verified destination",
                        "mapping_id": "spouse-had-question",
                    }
                elif kind in {"retain-evidence", "not-entered-directly"}:
                    destination = {
                        "kind": "not-entered",
                        "label": "Not entered directly.",
                    }
                else:
                    destination = {
                        "kind": "requires-review",
                        "label": "Destination requires review.",
                    }
                normalized = taxmate_handoff.normalize_handoff(
                    {
                        "kind": kind,
                        "next_action": f"Action for {kind}",
                        "destination": destination,
                    },
                    status_kind="answer",
                    income_year="2025-26",
                    root=ROOT,
                )

                self.assertEqual(kind, normalized["kind"])
                self.assertTrue(normalized["next_action"].strip())
                self.assertTrue(normalized["destination"]["label"].strip())

    def test_entry_actions_without_verified_destination_fail_closed(self) -> None:
        for kind in ("enter-reviewed-value", "answer-guided-question"):
            with self.subTest(kind=kind):
                normalized = taxmate_handoff.normalize_handoff(
                    {
                        "kind": kind,
                        "next_action": "Use this value.",
                        "destination": {
                            "kind": "requires-review",
                            "label": "Destination requires review.",
                        },
                    },
                    status_kind="answer",
                    income_year="2025-26",
                    root=ROOT,
                )

                self.assertEqual("destination-requires-review", normalized["kind"])
                self.assertEqual("requires-review", normalized["destination"]["kind"])


class RuntimeHandoffContractTests(unittest.TestCase):
    def payload(self) -> dict[str, Any]:
        return taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())

    def guide_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for key in ("items", "abn_items", "bas_items", "missing_facts", "evidence_items"):
            rows.extend(payload[key])
        return rows

    def row(self, payload: dict[str, Any], number: str) -> dict[str, Any]:
        return next(row for row in self.guide_rows(payload) if str(row["number"]) == number)

    def assert_handoff(self, handoff: dict[str, Any]) -> None:
        self.assertIn(handoff["kind"], EXPECTED_TAXONOMY)
        self.assertTrue(str(handoff["next_action"]).strip())
        self.assertIsInstance(handoff["destination"], dict)
        self.assertTrue(str(handoff["destination"]["label"]).strip())

    def test_every_runtime_row_fact_queue_and_extraction_has_handoff(self) -> None:
        payload = self.payload()

        for row in self.guide_rows(payload):
            with self.subTest(number=row["number"]):
                self.assertTrue(str(row["row_kind"]).strip())
                self.assert_handoff(row["handoff"])
                self.assertIsInstance(row["facts"], list)
                self.assertTrue(row["facts"])
                for fact in row["facts"]:
                    self.assertTrue(str(fact["key"]).strip())
                    self.assertTrue(str(fact["label"]).strip())
                    self.assertIn("value", fact)
                    self.assert_handoff(fact["handoff"])

        self.assertTrue(payload["extracted_values"])
        for row in payload["extracted_values"]:
            self.assertEqual("ai-extraction", row["row_kind"])
            self.assert_handoff(row["handoff"])
            self.assertTrue(row["facts"])

    def test_runtime_structures_sample_facts_without_semicolon_paragraphs(self) -> None:
        payload = self.payload()
        for row in self.guide_rows(payload):
            with self.subTest(number=row["number"]):
                for fact in row["facts"]:
                    self.assertNotIn(";", str(fact["value"]))

        rows = {row["number"]: row for row in self.guide_rows(payload)}
        phone_facts = {fact["key"]: fact for fact in rows["PHONE-DEVICE"]["facts"]}
        self.assertEqual("Decline-in-value review", phone_facts["treatment"]["value"])
        self.assertEqual(
            "Not a full immediate claim",
            phone_facts["treatment-boundary"]["value"],
        )
        asset_facts = {fact["key"]: fact for fact in rows["ASSET-1"]["facts"]}
        self.assertEqual(320.0, asset_facts["work-use-amount"]["value"])
        self.assertEqual(
            "Selected method candidate, not a full immediate claim",
            asset_facts["prepared-treatment"]["value"],
        )

    def test_accountant_review_blocks_entry_and_copy_wording(self) -> None:
        payload = self.payload()
        for row in self.guide_rows(payload):
            if str(row["status"]).strip().lower() != "accountant review":
                continue
            with self.subTest(number=row["number"]):
                self.assertEqual("accountant-handoff-only", row["handoff"]["kind"])
                self.assertNotRegex(row["handoff"]["next_action"].lower(), r"\b(?:enter|copy)\b")
                for fact in row["facts"]:
                    self.assertNotEqual("enter-reviewed-value", fact["handoff"]["kind"])
                    self.assertNotRegex(fact["handoff"]["next_action"].lower(), r"\b(?:enter|copy)\b")

    def test_private_health_statement_uses_field_level_destinations(self) -> None:
        row = self.row(self.payload(), "PHI-STMT-1")
        facts = {fact["key"]: fact for fact in row["facts"]}

        self.assertEqual(
            {
                "insurer",
                "membership-id",
                "benefit-code",
                "premiums-eligible-for-rebate",
                "rebate-received",
                "tax-claim-code",
                "days-covered",
                "cover-period",
                "statement-evidence",
            },
            set(facts),
        )
        self.assertEqual("requires-review", facts["insurer"]["handoff"]["destination"]["kind"])
        self.assertEqual("not-entered", facts["days-covered"]["handoff"]["destination"]["kind"])
        self.assertEqual("not-entered", facts["cover-period"]["handoff"]["destination"]["kind"])
        self.assertEqual("not-entered", facts["statement-evidence"]["handoff"]["destination"]["kind"])
        self.assertEqual(
            "phi-premiums-j",
            facts["premiums-eligible-for-rebate"]["handoff"]["destination"]["mapping_id"],
        )
        self.assertEqual("phi-rebate-k", facts["rebate-received"]["handoff"]["destination"]["mapping_id"])
        self.assertEqual("phi-benefit-code-l", facts["benefit-code"]["handoff"]["destination"]["mapping_id"])
        self.assertEqual("phi-tax-claim-code", facts["tax-claim-code"]["handoff"]["destination"]["mapping_id"])

    def test_medicare_levy_uses_exact_field_actions(self) -> None:
        row = self.row(self.payload(), "MEDICARE-LEVY")
        facts = {fact["key"]: fact for fact in row["facts"]}

        self.assertEqual("not-entered", facts["reduction-signal"]["handoff"]["destination"]["kind"])
        self.assertEqual(
            "m1-exemption-question",
            facts["exemption-signal"]["handoff"]["destination"]["mapping_id"],
        )
        self.assertEqual("not-entered", facts["exemption-category"]["handoff"]["destination"]["kind"])
        for key in ("full-exemption-days", "half-exemption-days"):
            self.assertEqual("Not supplied", facts[key]["value"])
            self.assertEqual("not-entered", facts[key]["handoff"]["destination"]["kind"])
            self.assertFalse(facts[key]["handoff"]["destination"]["mapping_id"])

    def test_mls_uses_exact_field_actions_without_calculation(self) -> None:
        row = self.row(self.payload(), "MLS-REVIEW")
        facts = {fact["key"]: fact for fact in row["facts"]}

        self.assertEqual("not-entered", facts["income-for-surcharge"]["handoff"]["destination"]["kind"])
        self.assertEqual("not-entered", facts["income-tier"]["handoff"]["destination"]["kind"])
        self.assertEqual("requires-review", facts["appropriate-hospital-cover"]["handoff"]["destination"]["kind"])
        self.assertEqual("not-entered", facts["hospital-cover-days"]["handoff"]["destination"]["kind"])
        self.assertEqual("Not supplied", facts["days-not-liable"]["value"])
        self.assertEqual("not-entered", facts["days-not-liable"]["handoff"]["destination"]["kind"])
        self.assertFalse(facts["days-not-liable"]["handoff"]["destination"]["mapping_id"])
        self.assertNotRegex(row["handoff"]["next_action"].lower(), r"\bcalculat(?:e|ed|ion)\b")

    def test_spouse_row_does_not_force_one_destination(self) -> None:
        row = self.row(self.payload(), "SPOUSE-REVIEW")
        facts = {fact["key"]: fact for fact in row["facts"]}

        self.assertEqual("spouse-had-question", facts["had-spouse"]["handoff"]["destination"]["mapping_id"])
        self.assertEqual("requires-review", facts["spouse-period"]["handoff"]["destination"]["kind"])
        self.assertEqual("requires-review", facts["income-for-tests"]["handoff"]["destination"]["kind"])
        self.assertEqual("requires-review", facts["reportable-fringe-benefits"]["handoff"]["destination"]["kind"])
        self.assertEqual("requires-review", facts["reportable-super"]["handoff"]["destination"]["kind"])
        self.assertEqual("requires-review", facts["net-investment-loss"]["handoff"]["destination"]["kind"])

    def test_ai_target_label_is_not_destination_verification(self) -> None:
        row = self.payload()["extracted_values"][0]

        self.assertEqual("resolve-before-entry", row["handoff"]["kind"])
        self.assertEqual("requires-review", row["handoff"]["destination"]["kind"])
        self.assertNotEqual(row["target_label"], row["handoff"]["destination"]["label"])
        facts = {fact["key"]: fact for fact in row["facts"]}
        self.assertEqual(
            "resolve-before-entry",
            facts["suggested-target"]["handoff"]["kind"],
        )
        self.assertEqual(
            "requires-review",
            facts["suggested-target"]["handoff"]["destination"]["kind"],
        )


class TaxpackHandoffRenderingTests(unittest.TestCase):
    def test_renderer_uses_cards_and_labelled_fact_bullets(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))
        statement = next(row for row in payload["items"] if row["number"] == "PHI-STMT-1")

        self.assertIn('class="handoff-card', body)
        self.assertIn('class="fact-list"', body)
        self.assertIn("Next action", body)
        self.assertIn("Where it belongs", body)
        self.assertIn("Why this action", body)
        self.assertIn("Destination mapping", body)
        self.assertIn("Source/provenance appendix", body)
        self.assertNotIn(html.escape(statement["answer"], quote=True), body)
        self.assertNotIn("min-width:700px", body.replace(" ", ""))
        self.assertIn("break-inside:avoid-page", body.replace(" ", ""))

    def test_cards_preserve_unique_anchor_and_context_targets(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))
        anchors = re.findall(r'id="(row-[^"]+)"', body)
        targets = re.findall(r'href="#(row-[^"]+)"', body)

        self.assertEqual(len(anchors), len(set(anchors)))
        self.assertTrue(set(targets).issubset(set(anchors)))
        self.assertTrue(set(anchors).issubset(set(targets)))

    def test_queue_only_payload_uses_the_same_handoff_card(self) -> None:
        data = taxmate_taxpack.load_guide_payload(
            {
                "income_year": "2025-26",
                "items": [],
                "evidence_items": [
                    {
                        "number": "EVID-ONLY",
                        "ato_area": "Evidence",
                        "question": "Retain statement",
                        "answer": 0,
                        "why_included": "Statement supports later review.",
                        "status": "Evidence",
                    }
                ],
            }
        )
        body = taxmate_taxpack.render_html(data)

        self.assertIn('id="row-evidence-1-EVID-ONLY"', body)
        self.assertIn("Resolve before entry", body)
        self.assertIn('<span class="fact-value">0</span>', body)
        self.assertIn("Statement supports later review.", body)

    def test_missing_malformed_and_direct_handoffs_fail_closed(self) -> None:
        malformed = taxmate_taxpack.load_guide_payload(
            {
                "items": [
                    {
                        "number": "MALFORMED-HANDOFF",
                        "ato_area": "Other",
                        "question": "Malformed handoff",
                        "answer": False,
                        "why_included": "Malformed contract stays visible.",
                        "status": "Used",
                        "handoff": {"kind": "enter-reviewed-value"},
                    }
                ]
            }
        )
        malformed_body = taxmate_taxpack.render_html(malformed)
        self.assertIn("Destination requires review", malformed_body)
        self.assertNotIn('<p class="action-name">Enter reviewed value</p>', malformed_body)
        self.assertIn('<span class="fact-value">false</span>', malformed_body)

        direct = taxmate_taxpack.GuideItem(
            number=0,
            ato_area="Other",
            question="Direct row",
            answer=0,
            why_included="Direct construction stays visible.",
            source_urls=[],
            checked_at="",
            status="Accountant review",
            status_kind="review",
            tab_title="",
            tab_text="",
            tab_kind="review",
        )
        direct_body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="10 Jul 2026",
                summary_note="Direct handoff check.",
                items=[direct],
            )
        )
        self.assertIn("Accountant handoff only", direct_body)
        self.assertIn("Destination requires review", direct_body)
        self.assertIn('<span class="fact-value">0</span>', direct_body)

    def test_falsey_structured_fact_values_remain_visible(self) -> None:
        item = taxmate_taxpack.guide_item(
            {
                "number": "FALSEY-HANDOFF",
                "ato_area": "Other",
                "question": "Falsey facts",
                "answer": "Compatibility value",
                "why_included": "Falsey values are valid facts.",
                "status": "Evidence",
                "row_kind": "test-row",
                "facts": [
                    {"key": "zero", "label": "Zero", "value": 0},
                    {"key": "false", "label": "False", "value": False},
                ],
            }
        )
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="10 Jul 2026",
                summary_note="Falsey handoff check.",
                items=[item],
            )
        )

        self.assertIn('<span class="fact-value">0</span>', body)
        self.assertIn('<span class="fact-value">false</span>', body)


class HandoffValidationCheckTests(unittest.TestCase):
    def test_repository_validation_checks_cover_the_handoff_contract(self) -> None:
        self.assertTrue(taxmate_validate.handoff_destination_contract())
        self.assertEqual([], taxmate_review_guardrails.check_handoff_contract(ROOT))


if __name__ == "__main__":
    unittest.main()
