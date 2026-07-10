import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import taxmate_intake
import taxmate_taxpack


class IndividualIncomeRoutingTests(unittest.TestCase):
    def rows(self, answers):
        payload = taxmate_intake.answers_to_pack_payload({"income_year": "2025-26", **answers})
        return payload["items"], payload["evidence_items"]

    def test_partnership_statement_preserves_falsey_and_provenance(self):
        items, evidence = self.rows({
            "partnership_share_items": [{
                "entity_name": "Example Partnership", "abn": "12 345 678 901",
                "statement": "statement held", "income": 0, "loss": 250,
                "tax_withheld": 0, "credits": 0, "entity_return_context": False,
                "source_url": "https://example.invalid/statement", "checked_at": "2026-07-11",
            }]
        })
        row = next(row for row in items if row["number"] == "PART-SHARE-1")
        self.assertFalse(any(row["number"] == "partnership_share_items" for row in items))
        self.assertEqual("Accountant review", row["status"])
        self.assertIn("income 0.00", row["answer"])
        self.assertIn("loss 250.00", row["answer"])
        self.assertIn("entity return context false", row["answer"])
        self.assertIn("https://example.invalid/statement", row["source_urls"])
        self.assertEqual("2026-07-11", row["checked_at"])
        self.assertEqual([], evidence)

    def test_missing_statement_and_malformed_amount_fail_to_evidence(self):
        items, evidence = self.rows({
            "trust_share_items": [{
                "entity_name": "Example Trust", "statement": False,
                "income": "unknown", "credits": "not numeric",
            }]
        })
        row = next(row for row in items if row["number"] == "TRUST-SHARE-1")
        self.assertEqual("Evidence", row["status"])
        self.assertTrue(any(item["number"] == "PT-EVID-1" for item in evidence))

    def test_investment_trust_distribution_is_not_duplicated(self):
        items, _ = self.rows({
            "investment_income": {"trust_distribution_items": [{
                "trust": "Investment Trust", "beneficiary_type": "individual beneficiary",
                "statement": "statement held", "distribution_amount": 100,
            }]}
        })
        numbers = [row["number"] for row in items]
        self.assertEqual(1, sum(number.startswith("TRUST-DIST-") for number in numbers))
        self.assertFalse(any(number.startswith("TRUST-SHARE-") for number in numbers))

    def test_flat_and_nested_aliases_share_the_same_contract(self):
        items, evidence = self.rows({
            "partnership_name": "Flat Partnership",
            "partnership_statement": "statement held",
            "partnership_share_income": 0,
            "supplementary_income": {"trust_beneficiary_share_items": [{
                "entity_name": "Nested Trust", "statement": "missing statement", "income": 10,
            }]},
        })
        partnership = next(row for row in items if row["number"] == "PART-SHARE-1")
        trust = next(row for row in items if row["number"] == "TRUST-SHARE-1")
        self.assertEqual("Accountant review", partnership["status"])
        self.assertIn("income 0.00", partnership["answer"])
        self.assertEqual("Evidence", trust["status"])
        self.assertTrue(any(row["number"] == "PT-EVID-1" for row in evidence))

    def test_nested_flat_aliases_preserve_identity_provenance_and_review(self):
        items, evidence = self.rows({"individual_income": {
            "trust_name": "Nested Flat Trust",
            "trust_share_statement": False,
            "trust_share_income": 0,
            "trust_share_source_url": "https://example.invalid/nested-trust",
            "trust_share_checked_at": "2026-07-11",
            "trust_share_status": "Accountant review",
            "trust_share_mixed_components": False,
        }})
        row = next(row for row in items if row["number"] == "TRUST-SHARE-1")
        self.assertIn("entity Nested Flat Trust", row["answer"])
        self.assertIn("mixed components false", row["answer"])
        self.assertIn("https://example.invalid/nested-trust", row["source_urls"])
        self.assertEqual("2026-07-11", row["checked_at"])
        self.assertEqual("Accountant review", row["status"])
        self.assertFalse(any(item["number"].startswith("PT-EVID-") for item in evidence))

    def test_malformed_and_identical_statement_items_are_not_dropped_or_collapsed(self):
        statement = {"entity_name": "Same Partnership", "statement": "statement held", "income": 10}
        items, evidence = self.rows({"partnership_share_items": [statement, statement.copy(), "bad row", {}]})
        partnership = [row for row in items if row["number"].startswith("PART-SHARE-")]
        self.assertEqual(4, len(partnership))
        self.assertEqual(2, sum("entity Same Partnership" in row["answer"] for row in partnership))
        self.assertTrue(all(row["answer"].strip() for row in partnership))
        self.assertEqual(2, sum(row["number"].startswith("PT-EVID-") for row in evidence))

    def test_empty_earlier_statement_aliases_do_not_mask_later_aliases(self):
        for placeholder in (None, "", "   ", [], {}):
            with self.subTest(placeholder=placeholder):
                items, evidence = self.rows({
                    "partnership_share_items": placeholder,
                    "partnership_statement_items": [{
                        "entity_name": "Later Partnership", "statement": "statement held", "income": 0,
                    }],
                })
                partnership = [row for row in items if row["number"].startswith("PART-SHARE-")]
                self.assertEqual(1, len(partnership))
                self.assertIn("Later Partnership", partnership[0]["answer"])
                self.assertFalse(any(row["number"].startswith("PT-EVID-") for row in evidence))

    def test_populated_statement_aliases_merge_without_collapsing_rows(self):
        items, _ = self.rows({
            "trust_share_items": [{"entity_name": "First Trust", "statement": "statement held", "income": 1}],
            "trust_beneficiary_statement_items": [{"entity_name": "Second Trust", "statement": "statement held", "income": 2}],
        })
        trust = [row for row in items if row["number"].startswith("TRUST-SHARE-")]
        self.assertEqual(2, len(trust))
        self.assertIn("First Trust", trust[0]["answer"])
        self.assertIn("Second Trust", trust[1]["answer"])

    def test_empty_structured_fields_do_not_mask_identity_evidence_or_provenance(self):
        items, evidence = self.rows({"trust_share_items": [{
            "entity_name": {}, "trust": "Fallback Trust",
            "statement": [], "evidence": "statement held", "income": 0,
            "checked_at": {}, "source_checked_at": "2026-07-11",
        }], "trust_source_urls": [], "trust_share_source_urls": ["https://example.invalid/fallback"]})
        row = next(row for row in items if row["number"] == "TRUST-SHARE-1")
        self.assertIn("Fallback Trust", row["answer"])
        self.assertIn("https://example.invalid/fallback", row["source_urls"])
        self.assertEqual("2026-07-11", row["checked_at"])
        self.assertEqual("Evidence", row["status"])
        self.assertTrue(any(item["number"].startswith("PT-EVID-") for item in evidence))

    def test_narrow_and_unsupported_uncommon_income_routes(self):
        items, evidence = self.rows({"uncommon_income": [
            {"category": "compensation payment", "amount": 0, "statement": "statement held", "source_url": "https://example.invalid/comp"},
            {"type": "scholarship", "amount": 500, "statement": "award letter held", "checked_at": "2026-07-11"},
            {"category": "mystery receipt", "amount": 25, "notes": "preserve this"},
        ]})
        uncommon = [row for row in items if row["number"].startswith("UNC-")]
        self.assertEqual(["Compensation or insurance payment review", "Scholarship, prize or award review", "Uncommon income review"], [row["question"] for row in uncommon])
        self.assertIn("amount 0.00", uncommon[0]["answer"])
        self.assertIn(taxmate_intake.ATO_COMPENSATION_INCOME_SOURCE, uncommon[0]["source_urls"])
        self.assertIn("preserve this", uncommon[2]["answer"])
        self.assertEqual("Evidence", uncommon[2]["status"])
        self.assertTrue(any(row["number"].startswith("UNC-EVID-") for row in evidence))

    def test_insurance_phrases_and_later_specific_fields_use_verified_route(self):
        phrases = [
            "insurance payout", "insurance settlement", "general insurance",
            "insurance proceeds", "insurance claim payout", "insurance-payment",
        ]
        answers = {"supplementary_income": {"uncommon_income_items": [
            {"category": "other income", "notes": phrase, "amount": 1}
            for phrase in phrases
        ]}}
        items, _ = self.rows(answers)
        uncommon = [row for row in items if row["number"].startswith("UNC-")]
        self.assertEqual(len(phrases), len(uncommon))
        self.assertTrue(all(row["question"] == "Compensation or insurance payment review" for row in uncommon))
        self.assertTrue(all(taxmate_intake.ATO_COMPENSATION_INCOME_SOURCE in row["source_urls"] for row in uncommon))

    def test_nested_malformed_uncommon_income_is_visible_in_evidence_and_html(self):
        items, evidence = self.rows({"individual_income": {"other_income_items": [42, {}]}})
        uncommon = [row for row in items if row["number"].startswith("UNC-")]
        self.assertEqual(2, len(uncommon))
        self.assertEqual(2, sum(row["number"].startswith("UNC-EVID-") for row in evidence))
        payload = taxmate_intake.answers_to_pack_payload({
            "income_year": "2025-26",
            "individual_income": {"other_income_items": [42, {}]},
        })
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))
        self.assertIn("Uncommon income evidence required", body)
        self.assertIn("Empty other_income_items item", body)

    def test_empty_earlier_uncommon_aliases_do_not_mask_or_drop_later_rows(self):
        for placeholder in (None, "", "   ", [], {}):
            with self.subTest(placeholder=placeholder):
                items, _ = self.rows({"supplementary_income": {
                    "uncommon_income": placeholder,
                    "uncommon_income_items": [{"category": "insurance payout", "amount": 0}],
                    "other_income_items": [{"category": "scholarship", "amount": 1}],
                }})
                uncommon = [row for row in items if row["number"].startswith("UNC-")]
                self.assertEqual(2, len(uncommon))
                self.assertEqual(
                    ["Compensation or insurance payment review", "Scholarship, prize or award review"],
                    [row["question"] for row in uncommon],
                )

    def test_empty_uncommon_statement_does_not_mask_held_evidence(self):
        items, evidence = self.rows({"uncommon_income": [{
            "category": "insurance settlement", "amount": 0,
            "statement": [], "evidence": "statement held",
        }]})
        row = next(row for row in items if row["number"] == "UNC-1")
        self.assertEqual("Accountant review", row["status"])
        self.assertFalse(any(item["number"].startswith("UNC-EVID-") for item in evidence))

    def test_flat_identity_enriches_structured_row_without_duplicate(self):
        items, evidence = self.rows({
            "trust_share_items": [{"statement": "statement held", "income": 1}],
            "trust_name": "Enriched Trust", "trust_share_abn": "12 345 678 901",
        })
        trust = [row for row in items if row["number"].startswith("TRUST-SHARE-")]
        self.assertEqual(1, len(trust))
        self.assertIn("Enriched Trust", trust[0]["answer"])
        self.assertIn("12 345 678 901", trust[0]["answer"])
        self.assertFalse(any(row["number"].startswith("PT-EVID-") for row in evidence))

    def test_empty_structured_alias_yields_to_valid_flat_statement(self):
        items, evidence = self.rows({
            "trust_share_items": {}, "trust_name": "Flat Trust",
            "trust_share_statement": "statement held", "trust_share_income": 0,
        })
        trust = [row for row in items if row["number"].startswith("TRUST-SHARE-")]
        self.assertEqual(1, len(trust))
        self.assertIn("Flat Trust", trust[0]["answer"])
        self.assertFalse(any(row["number"].startswith("PT-EVID-") for row in evidence))

    def test_alias_conflicts_and_review_precedence_fail_closed(self):
        items, evidence = self.rows({
            "partnership_name": "Conflict Partnership",
            "partnership_statement": "statement held",
            "partnership_income": 0, "partnership_share_income": 100,
            "partnership_status": "Evidence", "partnership_share_status": "Accountant review",
        })
        row = next(row for row in items if row["number"] == "PART-SHARE-1")
        self.assertEqual("Accountant review", row["status"])
        self.assertIn("alias conflicts", row["answer"])
        self.assertFalse(any(item["number"].startswith("PT-EVID-") for item in evidence))

    def test_boolean_and_numeric_alias_values_conflict(self):
        for left, right in ((0, False), (1, True)):
            with self.subTest(left=left, right=right):
                items, evidence = self.rows({
                    "partnership_name": "Typed Conflict Partnership",
                    "partnership_statement": "statement held",
                    "partnership_income": left,
                    "partnership_share_income": right,
                })
                row = next(row for row in items if row["number"] == "PART-SHARE-1")
                self.assertEqual("Evidence", row["status"])
                self.assertIn("alias conflicts", row["answer"])
                self.assertTrue(any(item["number"].startswith("PT-EVID-") for item in evidence))

    def test_malformed_structured_row_survives_valid_flat_statement(self):
        items, evidence = self.rows({
            "partnership_share_items": ["bad structured row"],
            "partnership_name": "Flat Partnership",
            "partnership_statement": "statement held",
            "partnership_income": 1,
        })
        partnership = [row for row in items if row["number"].startswith("PART-SHARE-")]
        self.assertEqual(2, len(partnership))
        self.assertTrue(any("bad structured row" in row["answer"] for row in partnership))
        self.assertTrue(any(item["number"].startswith("PT-EVID-") for item in evidence))

    def test_flat_identity_does_not_contaminate_multiple_structured_rows(self):
        items, evidence = self.rows({
            "trust_share_items": [
                {"statement": "statement held", "income": 1},
                {"statement": "statement held", "income": 2},
            ],
            "trust_name": "Ambiguous Flat Trust",
        })
        trust = [row for row in items if row["number"].startswith("TRUST-SHARE-")]
        self.assertEqual(3, len(trust))
        self.assertEqual(1, sum("Ambiguous Flat Trust" in row["answer"] for row in trust))
        self.assertTrue(any("structured_row_assignment" in row["answer"] for row in trust))
        self.assertFalse(any("entity ;" in row["answer"] for row in trust))
        self.assertTrue(any(item["number"].startswith("PT-EVID-") for item in evidence))

    def test_source_aliases_merge_and_malformed_provenance_fails_closed(self):
        items, evidence = self.rows({
            "trust_name": "Source Trust", "trust_share_statement": "statement held", "trust_share_income": 1,
            "trust_source_url": "https://example.invalid/one",
            "trust_share_source_urls": ["https://example.invalid/two", "https://example.invalid/one"],
            "trust_beneficiary_source_urls": {"bad": "shape"},
            "trust_checked_at": False, "trust_share_checked_at": "2026-07-11",
        })
        row = next(row for row in items if row["number"] == "TRUST-SHARE-1")
        self.assertEqual(
            [taxmate_intake.ATO_PARTNERSHIP_TRUST_INCOME_SOURCE, "https://example.invalid/one", "https://example.invalid/two"],
            row["source_urls"],
        )
        self.assertEqual("2026-07-11", row["checked_at"])
        self.assertEqual("Evidence", row["status"])
        self.assertNotIn("{'bad': 'shape'}", row["source_urls"])
        self.assertTrue(any(item["number"].startswith("PT-EVID-") for item in evidence))

    def test_evidence_source_urls_are_stably_deduplicated(self):
        cases = (
            ({
                "trust_name": "Duplicate Source Trust",
                "trust_share_income": 1,
                "trust_share_source_url": taxmate_intake.ATO_PARTNERSHIP_TRUST_INCOME_SOURCE,
            }, "PT-EVID-", taxmate_intake.ATO_PARTNERSHIP_TRUST_INCOME_SOURCE),
            ({"uncommon_income": [{
                "category": "scholarship",
                "amount": 1,
                "source_url": taxmate_intake.ATO_SCHOLARSHIP_PRIZE_SOURCE,
            }]}, "UNC-EVID-", taxmate_intake.ATO_SCHOLARSHIP_PRIZE_SOURCE),
        )
        for answers, prefix, source in cases:
            with self.subTest(prefix=prefix):
                _items, evidence = self.rows(answers)
                row = next(item for item in evidence if item["number"].startswith(prefix))
                self.assertEqual(1, row["source_urls"].count(source))

    def test_payload_generation_does_not_mutate_input_and_is_idempotent(self):
        answers = {
            "income_year": "2025-26",
            "partnership_share_items": [{"entity_name": "Stable Partnership", "statement": "statement held", "income": 1}],
            "partnership_source_url": "https://example.invalid/stable",
        }
        original = json.loads(json.dumps(answers))
        first = taxmate_intake.answers_to_pack_payload(answers)
        second = taxmate_intake.answers_to_pack_payload(answers)
        self.assertEqual(original, answers)
        self.assertEqual(first, second)

    def test_non_payment_insurance_phrases_remain_unsupported(self):
        items, _ = self.rows({"uncommon_income": [
            {"category": "income protection insurance premium", "amount": 1, "statement": "record held"},
            {"category": "private health insurance rebate", "amount": 1, "statement": "record held"},
            {"category": "insurance policy", "amount": 1, "statement": "record held"},
        ]})
        uncommon = [row for row in items if row["number"].startswith("UNC-")]
        self.assertTrue(all(row["question"] == "Uncommon income review" for row in uncommon))

    def test_metadata_only_flat_share_inputs_do_not_create_blank_rows_or_queues(self):
        for answers in (
            {"trust_share_source_urls": ["https://example.invalid/source"]},
            {"trust_share_status": "Accountant review"},
            {"partnership_checked_at": "2026-07-11"},
        ):
            with self.subTest(answers=answers):
                items, evidence = self.rows(answers)
                self.assertFalse(any(row["number"].startswith(("TRUST-SHARE-", "PART-SHARE-")) for row in items))
                self.assertFalse(any(row["number"].startswith("PT-EVID-") for row in evidence))

    def test_blank_and_generic_uncommon_rows_do_not_render_blank_review_items(self):
        items, evidence = self.rows({"uncommon_income": [{}, {"category": "other income"}, "unknown"]})
        uncommon = [row for row in items if row["number"].startswith("UNC-")]
        self.assertEqual(3, len(uncommon))
        self.assertTrue(all(row["answer"].strip() for row in uncommon))
        self.assertTrue(all(row["tab_text"].strip() for row in uncommon))
        self.assertTrue(any(row["number"].startswith("UNC-EVID-") for row in evidence))

    def test_file_backed_payload_and_direct_constructor_keep_review_precedence(self):
        answers = {"income_year": "2025-26", "partnership_share_items": [{
            "entity_name": "Example Partnership", "statement": False, "income": 0,
            "status": "Accountant review", "source_url": "https://example.invalid/source",
        }]}
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json") as handle:
            json.dump(answers, handle)
            handle.flush()
            payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.read_json(handle.name))
        row = next(row for row in payload["items"] if row["number"] == "PART-SHARE-1")
        self.assertEqual("Accountant review", row["status"])
        self.assertFalse(any(item["number"].startswith("PT-EVID-") for item in payload["evidence_items"]))
        direct = taxmate_taxpack.guide_item({
            **row, "status": "Accountant review", "status_kind": "evidence",
            "tab_kind": "answer", "answer": 0, "checked_at": "2026-07-11",
        })
        self.assertEqual("review", direct.status_kind)
        self.assertEqual("0", direct.answer)
        self.assertEqual("2026-07-11", direct.checked_at)


if __name__ == "__main__":
    unittest.main()
