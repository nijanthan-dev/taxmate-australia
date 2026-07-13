import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import taxmate_intake
import taxmate_taxpack


class EntityReturnRoutingTests(unittest.TestCase):
    def payload(self, answers):
        return taxmate_intake.answers_to_pack_payload({"income_year": "2025-26", **answers})

    def test_no_entity_has_no_entity_sections(self):
        payload = self.payload({"company_return": False, "trust_return": "no", "partnership_return": None})
        self.assertEqual([], payload["company_items"])
        self.assertEqual([], payload["trust_items"])
        self.assertEqual([], payload["partnership_items"])

    def test_three_nested_entities_route_to_isolated_sections(self):
        payload = self.payload({
            "company_return": {"name": "Zero Co", "abn": "12 345 678 901", "income_year": "2025-26", "residency": "Australian", "business_activity": "Design", "directors": 0, "shareholders": False, "source_url": "https://example.invalid/company", "checked_at": "2026-07-13"},
            "trust_return": {"name": "Example Trust", "tfn": "123", "trustee": "Example Pty Ltd", "trust_type": "discretionary", "income_year": "2025-26", "residency": "Australian", "deed_evidence": False, "beneficiaries": 0},
            "partnership_return": {"name": "Example Partnership", "abn": "98 765 432 109", "income_year": "2025-26", "partners": 0, "share_percentages": False, "business_activity": "Consulting", "accounting_basis": "unknown"},
        })
        self.assertEqual("COMPANY-1", payload["company_items"][0]["number"])
        self.assertEqual("TRUST-1", payload["trust_items"][0]["number"])
        self.assertEqual("PARTNERSHIP-1", payload["partnership_items"][0]["number"])
        self.assertIn("directors 0", payload["company_items"][0]["answer"])
        self.assertIn("beneficiaries 0", payload["trust_items"][0]["answer"])
        self.assertIn("partners 0", payload["partnership_items"][0]["answer"])
        self.assertTrue(all(row["status"] == "Accountant review" for key in ("company_items", "trust_items", "partnership_items") for row in payload[key]))
        self.assertFalse(any(row["row_kind"] == "entity-return-company" for row in payload["items"]))

    def test_itemized_aliases_malformed_and_conflicts_fail_closed(self):
        payload = self.payload({"entities": [
            {"entity_type": "company", "name": "Item Co", "residency": "Australian"},
            {"type": "trust", "name": "Item Trust", "deed_evidence": "missing"},
            {"entity_type": "partnership", "name": "Item Partnership", "share_percentages": [50, 40]},
            {"entity_type": "individual", "name": "Person"},
            {"entity_type": "company", "name": "Conflict Co", "status": "Ready", "review_status": "Accountant review"},
            "bad entity",
        ]})
        self.assertEqual(2, len(payload["company_items"]))
        self.assertEqual(1, len(payload["trust_items"]))
        self.assertEqual(1, len(payload["partnership_items"]))
        evidence = " ".join(row["answer"] for row in payload["evidence_items"])
        self.assertIn("Malformed entity item", evidence)
        self.assertIn("deed evidence", evidence)
        self.assertIn("partner share percentages", evidence)
        self.assertEqual("Accountant review", payload["company_items"][1]["status"])

    def test_partner_share_percentages_require_numeric_list_totalling_100(self):
        for value in (False, 0, "50/50", {}, [], [False, 100], [50, 40]):
            with self.subTest(value=value):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Example Partnership",
                        "partners": 2,
                        "share_percentages": value,
                    }
                })
                evidence = " ".join(row["answer"] for row in payload["evidence_items"])
                self.assertIn("partner share percentages", evidence)

        valid = self.payload({
            "partnership_return": {
                "name": "Example Partnership",
                "partners": 2,
                "share_percentages": [0, 100],
            }
        })
        evidence = " ".join(row["answer"] for row in valid["evidence_items"])
        self.assertNotIn("partner share percentages", evidence)

    def test_flat_aliases_and_renderer_sections_sources_and_anchors(self):
        payload = self.payload({
            "company_return": True, "company_name": "Flat Co", "company_acn": 0, "company_residency": "unclear",
            "trust_return": True, "trust_name": "Flat Trust", "trust_deed_evidence": False,
            "partnership_return": True, "partnership_name": "Flat Partnership", "partnership_accounting_basis": False,
        })
        data = taxmate_taxpack.load_guide_payload(payload)
        body = taxmate_taxpack.render_html(data)
        for title in ("Company return preparation", "Trust return preparation", "Partnership return preparation"):
            self.assertIn(title, body)
        self.assertIn("Source/provenance appendix", body)
        self.assertEqual(len(set(row.anchor for row in taxmate_taxpack.build_render_rows(data))), len(taxmate_taxpack.build_render_rows(data)))
        self.assertFalse(any(row["number"].startswith(("TRUST-SHARE-", "PART-SHARE-")) for row in payload["items"]))
        self.assertFalse(any(row["number"].startswith("PT-EVID-") for row in payload["evidence_items"]))

    def test_identical_alias_records_do_not_duplicate_routes(self):
        record = {"name": "Same Co", "income_year": "2025-26", "residency": "Australian", "business_activity": "Design", "directors": 0, "shareholders": 0}
        payload = self.payload({"company_return": record, "company_intake": dict(record)})
        self.assertEqual(1, len(payload["company_items"]))

    def test_file_backed_fixture_routes_all_entity_sections(self):
        fixture = Path(__file__).parent / "fixtures" / "entity-routing-answers.json"
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.read_json(str(fixture)))
        self.assertTrue(payload["company_items"])
        self.assertTrue(payload["trust_items"])
        self.assertTrue(payload["partnership_items"])

    def test_empty_required_containers_fail_closed_but_falsey_scalars_survive(self):
        payload = self.payload({
            "company_return": {"name": "Empty Co", "directors": [], "shareholders": {}},
            "trust_return": {"name": "Empty Trust", "beneficiaries": [], "deed_evidence": False},
            "partnership_return": {"name": "Empty Partnership", "partners": {}, "share_percentages": [], "accounting_basis": False},
        })
        evidence = " ".join(row["answer"] for row in payload["evidence_items"])
        for required in ("directors", "shareholders", "beneficiaries", "partners", "share percentages"):
            self.assertIn(required, evidence)
        self.assertIn("deed evidence false", payload["trust_items"][0]["answer"])
        self.assertIn("accounting basis false", payload["partnership_items"][0]["answer"])

    def test_nested_empty_required_structures_fail_closed(self):
        payload = self.payload({
            "company_return": {"name": "Nested Co", "directors": [{}], "shareholders": {"owners": []}},
            "trust_return": {"name": "Nested Trust", "beneficiaries": [{"owners": []}]},
            "partnership_return": {"name": "Nested Partnership", "partners": [{"owners": []}], "share_percentages": [{}]},
        })
        evidence = " ".join(row["answer"] for row in payload["evidence_items"])
        for required in ("directors", "shareholders", "beneficiaries", "partners", "share percentages"):
            self.assertIn(required, evidence)

        falsey = self.payload({
            "company_return": {"name": "Falsey Co", "directors": [0], "shareholders": [False]},
            "trust_return": {"name": "Falsey Trust", "beneficiaries": [0]},
            "partnership_return": {"name": "Falsey Partnership", "partners": [False], "share_percentages": [0, 100]},
        })
        evidence = " ".join(row["answer"] for row in falsey["evidence_items"])
        for required in ("directors", "shareholders", "beneficiaries", "partners", "share percentages"):
            self.assertNotIn(required, evidence)

    def test_both_itemized_collection_aliases_are_merged(self):
        payload = self.payload({
            "entities": [{"entity_type": "company", "name": "Collection Co"}],
            "entity_returns": [{"entity_type": "trust", "name": "Collection Trust"}],
        })
        self.assertEqual(1, len(payload["company_items"]))
        self.assertEqual(1, len(payload["trust_items"]))

        fallback = self.payload({
            "entities": [],
            "entity_returns": [{"entity_type": "partnership", "name": "Fallback Partnership"}],
        })
        self.assertEqual(1, len(fallback["partnership_items"]))

    def test_empty_primary_type_and_source_aliases_do_not_mask_fallbacks(self):
        payload = self.payload({"entities": [{
            "entity_type": "", "type": "company", "name": "Alias Co",
            "source_urls": [], "source_url": "https://example.invalid/alias-company",
        }]})
        self.assertEqual(1, len(payload["company_items"]))
        self.assertIn("https://example.invalid/alias-company", payload["company_items"][0]["source_urls"])

    def test_direct_entity_sections_force_fail_closed_status_and_kind(self):
        payload = {
            "company_items": [{"number": "DIRECT-C", "status": "Used", "facts": [], "answer": "empty"}],
            "trust_items": [{"number": "DIRECT-T", "status": "Used", "facts": [{"key": "beneficiaries", "value": 0}]}],
            "partnership_items": [{"number": "DIRECT-P", "status": "N/A skipped", "facts": [{"key": "partners", "value": False}]}],
        }
        data = taxmate_taxpack.load_guide_payload(payload)
        self.assertEqual("Evidence", data.company_items[0].status)
        self.assertEqual("Accountant review", data.trust_items[0].status)
        self.assertEqual("Accountant review", data.partnership_items[0].status)
        self.assertEqual("entity-return-company", data.company_items[0].row_kind)
        self.assertEqual("entity-return-trust", data.trust_items[0].row_kind)
        self.assertEqual("entity-return-partnership", data.partnership_items[0].row_kind)

        for key in ("company_items", "trust_items", "partnership_items"):
            with self.subTest(key=key):
                explicit = taxmate_taxpack.load_guide_payload({
                    key: [{"number": "DIRECT-REVIEW", "status": "Accountant review", "facts": [{}]}],
                })
                self.assertEqual("Accountant review", getattr(explicit, key)[0].status)

        empty = taxmate_taxpack.load_guide_payload({
            "company_items": [{"number": "DIRECT-EMPTY", "status": "Used", "facts": [{}]}],
        })
        self.assertEqual("Evidence", empty.company_items[0].status)

    def test_explicit_share_items_remain_separate_from_marked_entity_flat_fields(self):
        payload = self.payload({
            "trust_return": True, "trust_name": "Entity Trust",
            "trust_share_items": [{"entity_name": "Share Trust", "statement": "held", "income": 1}],
            "partnership_return": True, "partnership_name": "Entity Partnership",
            "partnership_share_items": [{"entity_name": "Share Partnership", "statement": "held", "income": 2}],
        })
        trust_share = next(row for row in payload["items"] if row["number"].startswith("TRUST-SHARE-"))
        partnership_share = next(row for row in payload["items"] if row["number"].startswith("PART-SHARE-"))
        self.assertIn("Share Trust", trust_share["answer"])
        self.assertNotIn("Entity Trust", trust_share["answer"])
        self.assertIn("Share Partnership", partnership_share["answer"])
        self.assertNotIn("Entity Partnership", partnership_share["answer"])

    def test_individual_share_statement_aliases_do_not_activate_entity_returns(self):
        payload = self.payload({
            "trust_name": "Individual Review Trust", "trust_share_income": 1,
            "trust_source_url": "https://example.invalid/trust-share", "trust_checked_at": "2026-07-13",
            "trust_status": "Accountant review",
            "partnership_name": "Individual Partnership", "partnership_abn": "12 345 678 901",
            "partnership_tfn": "123", "partnership_share_income": 0,
            "partnership_source_urls": ["https://example.invalid/partnership-share"],
            "partnership_checked_at": "2026-07-13", "partnership_status": "Accountant review",
        })
        self.assertEqual([], payload["trust_items"])
        self.assertEqual([], payload["partnership_items"])
        self.assertTrue(any(row["number"].startswith("TRUST-SHARE-") for row in payload["items"]))
        self.assertTrue(any(row["number"].startswith("PART-SHARE-") for row in payload["items"]))
        self.assertFalse(any(row["number"].startswith("ENTITY-EVID-") for row in payload["evidence_items"]))

    def test_nonoverlapping_return_flat_aliases_route_without_legacy_collision(self):
        payload = self.payload({
            "company_return_name": "Return Co",
            "trust_return_name": "Return Trust",
            "trust_return_trustee": "Return Trustee",
            "partnership_return_name": "Return Partnership",
            "partnership_return_partners": 0,
        })
        self.assertEqual(1, len(payload["company_items"]))
        self.assertEqual(1, len(payload["trust_items"]))
        self.assertEqual(1, len(payload["partnership_items"]))


if __name__ == "__main__":
    unittest.main()
