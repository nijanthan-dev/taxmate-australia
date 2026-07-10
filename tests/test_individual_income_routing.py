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
        self.assertEqual("Accountant review", uncommon[2]["status"])
        self.assertEqual([], evidence)

    def test_blank_and_generic_uncommon_rows_do_not_render_blank_review_items(self):
        items, evidence = self.rows({"uncommon_income": [{}, {"category": "other income"}, "unknown"]})
        uncommon = [row for row in items if row["number"].startswith("UNC-")]
        self.assertEqual(2, len(uncommon))
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
