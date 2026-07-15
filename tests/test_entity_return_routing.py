import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import atodata
import taxmate_intake
import taxmate_entity_routing
import taxmate_taxpack


class EntityReturnRoutingTests(unittest.TestCase):
    def payload(self, answers):
        return taxmate_intake.answers_to_pack_payload({"income_year": "2025-26", **answers})

    def trust_statement(self, **overrides):
        row = {
            "beneficiary_name": "Synthetic Beneficiary",
            "beneficiary_tfn": "111222333",
            "beneficiary_type": "individual",
            "residency_status": "Australian resident",
            "beneficiary_status": "presently entitled beneficiary",
            "present_entitlement": False,
            "statement_status": "received",
            "income_components": {"primary": 0, "non_primary": 125},
            "credits": {"franking": 0},
            "tax_withheld": 0,
            "statement_files": ["synthetic-trust-statement.pdf"],
        }
        row.update(overrides)
        return row

    def partner_statement(self, **overrides):
        row = {
            "partner_name": "Synthetic Partner",
            "partner_abn": "11 222 333 444",
            "partner_type": "company",
            "partner_residency": "Australian resident",
            "ownership_percentage": 0,
            "statement_received": True,
            "income_share": 0,
            "loss_share": -25,
            "credits": {"franking": 0},
            "withholding": 0,
            "drawings": 0,
            "distributions": False,
            "documents": ["synthetic-partner-statement.pdf"],
        }
        row.update(overrides)
        return row

    def test_entity_sources_are_registered_with_hashes_and_coverage(self):
        root = Path(__file__).resolve().parents[1]
        registry = json.loads((root / "data/ato_knowledge_base/source_registry.json").read_text())
        coverage = json.loads((root / "data/ato_knowledge_base/source_coverage.json").read_text())
        records = {row["url"]: row for row in registry["records"]}
        covered = {row["original_url"]: row for row in coverage["sources"]}
        for kind, url in taxmate_entity_routing.SOURCES.items():
            with self.subTest(kind=kind):
                self.assertIn(url, atodata.SEED_URLS)
                self.assertTrue(records[url]["content_verified"])
                self.assertEqual(64, len(records[url]["content_hash"]))
                self.assertIn(kind.title(), records[url]["title"])
                self.assertEqual(records[url]["content_hash"], covered[url]["content_hash"])
                self.assertEqual("metadata_only", covered[url]["status"])

    def test_no_entity_has_no_entity_sections(self):
        payload = self.payload({
            "company_return": False,
            "trust_return": "no",
            "partnership_return": None,
            "company_intake": "n/a",
            "trust_intake": "unknown",
            "partnership_intake": "",
        })
        self.assertEqual([], payload["company_items"])
        self.assertEqual([], payload["trust_items"])
        self.assertEqual([], payload["partnership_items"])
        self.assertFalse(any(row["row_kind"].startswith("entity-return-") for row in payload["evidence_items"]))

    def test_declined_entity_collections_are_no_entity_answers(self):
        for key in ("entities", "entity_returns"):
            for value in (False, 0, "no", "not applicable", "n/a", [], {}):
                with self.subTest(key=key, value=value):
                    payload = self.payload({key: value})
                    self.assertEqual([], payload["company_items"])
                    self.assertEqual([], payload["trust_items"])
                    self.assertEqual([], payload["partnership_items"])
                    self.assertFalse(any(
                        row["row_kind"] == "entity-return-malformed"
                        for row in payload["evidence_items"]
                    ))

    def test_marker_only_aliases_preserve_request_and_fail_closed(self):
        aliases = {
            "company": ("company_return", "company_intake", "company_entity"),
            "trust": ("trust_return", "trust_intake", "trust_entity"),
            "partnership": ("partnership_return", "partnership_intake", "partnership_entity"),
        }
        for kind, kind_aliases in aliases.items():
            for alias in kind_aliases:
                for marker in (True, "yes", "true", "on", "checked"):
                    with self.subTest(kind=kind, alias=alias, marker=marker):
                        payload = self.payload({alias: marker})
                        rows = [
                            row for row in payload["evidence_items"]
                            if row["row_kind"] == f"entity-return-{kind}-request"
                        ]
                        self.assertEqual(1, len(rows))
                        self.assertEqual(marker, rows[0]["facts"][0]["value"])
                        self.assertIn("intake facts required", rows[0]["question"])

            payload = self.payload({alias: True for alias in kind_aliases})
            rows = [
                row for row in payload["evidence_items"]
                if row["row_kind"] == f"entity-return-{kind}-request"
            ]
            self.assertEqual(1, len(rows))

            payload = self.payload({kind_aliases[0]: True, f"{kind}_return_name": "Named"})
            self.assertEqual(1, len(payload[f"{kind}_items"]))
            self.assertFalse(any(
                row["row_kind"] == f"entity-return-{kind}-request"
                for row in payload["evidence_items"]
            ))

            nested = self.payload({kind_aliases[0]: True, kind_aliases[1]: {"name": "Nested"}})
            self.assertEqual(1, len(nested[f"{kind}_items"]))
            self.assertFalse(any(
                row["row_kind"] == f"entity-return-{kind}-request"
                for row in nested["evidence_items"]
            ))

        declined = self.payload({"company_return": False, "trust_return": "no"})
        self.assertFalse(any("-request" in row["row_kind"] for row in declined["evidence_items"]))

        for token in ("0", "off", "unchecked", 0, 0.0):
            payload = self.payload({f"{kind}_return": token for kind in aliases})
            self.assertFalse(any(payload[f"{kind}_items"] for kind in aliases))
            self.assertFalse(any(
                row["row_kind"].startswith("entity-return-")
                for row in payload["evidence_items"]
            ))

        shares = self.payload({
            "trust_return": 0,
            "trust_name": "Individual Trust",
            "trust_share_income": 1,
            "partnership_return": 0.0,
            "partnership_name": "Individual Partnership",
            "partnership_share_income": 2,
        })
        self.assertTrue(any(row["number"].startswith("TRUST-SHARE-") for row in shares["items"]))
        self.assertTrue(any(row["number"].startswith("PART-SHARE-") for row in shares["items"]))

        for kind in aliases:
            for blank in ({}, []):
                with self.subTest(kind=kind, blank=blank):
                    payload = self.payload({f"{kind}_return": blank})
                    rows = [
                        row for row in payload["evidence_items"]
                        if row["row_kind"] == f"entity-return-{kind}-request"
                    ]
                    self.assertEqual(1, len(rows))
                    self.assertEqual(blank, rows[0]["facts"][0]["value"])

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

    def test_untyped_and_unsupported_entity_facts_are_preserved_for_review(self):
        payload = self.payload({
            "entities": [
                {"name": "Untyped Trust", "tfn": "123"},
                {
                    "entity_type": "company",
                    "name": "Scoped Co",
                    "franking_credits": 0,
                    "carried_losses": False,
                },
                {
                    "type": "trust",
                    "name": "Scoped Trust",
                    "distributions": {"beneficiary": 0},
                },
                {
                    "entity_type": "partnership",
                    "name": "Scoped Partnership",
                    "cgt_details": [],
                },
            ]
        })
        evidence = [
            row for row in payload["evidence_items"]
            if row["row_kind"].startswith("entity-return-")
        ]
        rendered = " ".join(row["answer"] for row in evidence)
        self.assertIn("Untyped Trust", rendered)
        self.assertIn('"franking_credits": 0', rendered)
        self.assertIn('"carried_losses": false', rendered)
        self.assertIn('"beneficiary": 0', rendered)
        self.assertIn('"cgt_details": []', rendered)
        self.assertTrue(all(row["status"] in {"Evidence", "Accountant review"} for row in evidence))
        self.assertFalse(any("franking" in row["answer"].lower() for row in payload["company_items"]))

    def test_nested_alias_lists_and_flat_unsupported_facts_are_evidence_only(self):
        payload = self.payload({
            "company_intake": [{"name": "Alias Co", "dividends": False}],
            "trust_entity": {"name": "Alias Trust", "distributions": 0},
            "partnership_return_losses": {"carried_forward": 0},
        })
        rendered = " ".join(row["answer"] for row in payload["evidence_items"])
        self.assertIn('"dividends": false', rendered)
        self.assertIn('"distributions": 0', rendered)
        self.assertIn('"losses": {"carried_forward": 0}', rendered)
        self.assertEqual([], payload["partnership_items"])

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

    def test_legacy_bare_names_promote_only_for_explicit_entity_markers(self):
        payload = self.payload({
            "trust_return": True,
            "trust": "Bare Trust",
            "partnership_return": "yes",
            "partnership": "Bare Partnership",
        })
        self.assertIn("name Bare Trust", payload["trust_items"][0]["answer"])
        self.assertIn("name Bare Partnership", payload["partnership_items"][0]["answer"])
        self.assertFalse(any(row["number"].startswith(("TRUST-SHARE-", "PART-SHARE-")) for row in payload["items"]))

    def test_malformed_checked_at_fails_closed_and_uses_verified_default(self):
        for kind in ("company", "trust", "partnership"):
            with self.subTest(kind=kind):
                payload = self.payload({
                    f"{kind}_return": {"name": "Entity", "checked_at": "not-a-date"},
                })
                self.assertEqual(taxmate_entity_routing.CHECKED_AT, payload[f"{kind}_items"][0]["checked_at"])
                evidence = " ".join(row["answer"] for row in payload["evidence_items"])
                self.assertIn("checked-at provenance (not-a-date)", evidence)

                direct = taxmate_taxpack.load_guide_payload({
                    f"{kind}_items": [{
                        "number": "DIRECT", "checked_at": "not-a-date",
                        "facts": [{"key": "name", "value": "Entity"}],
                    }],
                })
                self.assertEqual(
                    taxmate_entity_routing.CHECKED_AT,
                    getattr(direct, f"{kind}_items")[0].checked_at,
                )

    def test_iso_timestamp_and_direct_source_provenance_are_normalized(self):
        timestamp = "2026-06-23T09:04:57Z"
        payload = self.payload({
            "company_return": {"name": "Entity", "checked_at": timestamp},
        })
        self.assertEqual(timestamp, payload["company_items"][0]["checked_at"])
        self.assertNotIn(
            "checked-at provenance",
            " ".join(row["answer"] for row in payload["evidence_items"]),
        )

        direct = taxmate_taxpack.load_guide_payload({
            "company_items": [{
                "number": "DIRECT", "checked_at": timestamp,
                "source_urls": ["not a url", "https://example.invalid/entity"],
                "facts": [{"key": "name", "value": "Entity"}],
            }],
        })
        item = direct.company_items[0]
        self.assertEqual(timestamp, item.checked_at)
        self.assertNotIn("not a url", item.source_urls)
        self.assertIn("https://example.invalid/entity", item.source_urls)
        self.assertTrue(any(fact["key"] == "unresolved-source-provenance" for fact in item.facts))
        body = taxmate_taxpack.render_html(direct)
        self.assertNotIn('href="not a url"', body)
        self.assertIn("Unresolved source provenance", body)

        invalid_by_kind = {
            "company": "not a url",
            "trust": "https://example.invalid/bad path",
            "partnership": ["bad", 0, False],
        }
        for kind, invalid in invalid_by_kind.items():
            with self.subTest(kind=kind):
                routed = self.payload({f"{kind}_return": {"name": "Entity", "source_urls": invalid}})
                evidence = next(
                    row for row in routed["evidence_items"]
                    if row["row_kind"] == f"entity-return-{kind}-evidence"
                )
                unresolved = next(
                    fact for fact in evidence["facts"]
                    if fact["key"] == "unresolved-source-provenance"
                )
                self.assertEqual(invalid if isinstance(invalid, list) else [invalid], unresolved["value"])

        scalar = taxmate_taxpack.load_guide_payload({
            "trust_items": [{
                "number": "DIRECT", "source_url": "not a url",
                "facts": [{"key": "name", "value": "Entity"}],
            }],
        })
        scalar_body = taxmate_taxpack.render_html(scalar)
        self.assertNotIn('href="not a url"', scalar_body)
        self.assertIn("Unresolved source provenance", scalar_body)

        no_facts = taxmate_taxpack.load_guide_payload({
            "partnership_items": [{
                "number": "DIRECT-NO-FACTS",
                "source_url": "not a url",
                "answer": "Preserve provenance gap",
            }],
        })
        no_facts_body = taxmate_taxpack.render_html(no_facts)
        self.assertNotIn('href="not a url"', no_facts_body)
        self.assertIn("Unresolved source provenance", no_facts_body)

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

    def test_not_applicable_required_facts_fail_closed(self):
        payload = self.payload({
            "company_return": {"name": "Company", "directors": "not applicable"},
            "trust_return": {"name": "Trust", "beneficiaries": "Not Applicable"},
            "partnership_return": {"name": "Partnership", "partners": "not applicable"},
        })
        evidence = " ".join(row["answer"] for row in payload["evidence_items"])
        for required in ("directors", "beneficiaries", "partners"):
            self.assertIn(required, evidence)

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
        for kind in ("company", "trust", "partnership"):
            item = getattr(data, f"{kind}_items")[0]
            self.assertIn(taxmate_entity_routing.SOURCES[kind], item.source_urls)
            self.assertEqual(taxmate_entity_routing.CHECKED_AT, item.checked_at)
        body = taxmate_taxpack.render_html(data)
        self.assertIn("Source/provenance appendix", body)
        self.assertIn(taxmate_entity_routing.SOURCES["company"], body)

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

    def test_nested_and_list_entity_aliases_isolate_flat_share_fields(self):
        for kind, nested in (
            ("trust", {"name": "Nested Trust"}),
            ("partnership", [{"name": "List Partnership"}]),
        ):
            with self.subTest(kind=kind):
                payload = self.payload({
                    f"{kind}_return": nested,
                    f"{kind}_name": "Entity-only flat name",
                    f"{kind}_statement": "missing",
                    f"{kind}_share_income": 0,
                })
                self.assertFalse(any(
                    row["number"].startswith(("TRUST-SHARE-", "PART-SHARE-"))
                    for row in payload["items"]
                ))
                self.assertFalse(any(
                    row["number"].startswith("PT-EVID-")
                    for row in payload["evidence_items"]
                ))
                self.assertEqual(1, len(payload[f"{kind}_items"]))

        trust = self.payload({
            "trust_return": {"name": "Entity Trust"},
            "trust_entity_return_context": "entity-only",
        })
        self.assertFalse(any(row["number"].startswith("TRUST-SHARE-") for row in trust["items"]))
        self.assertFalse(any(row["number"].startswith("PT-EVID-") for row in trust["evidence_items"]))

    def test_flat_and_blank_entity_requests_block_individual_share_routing(self):
        for kind, request in (
            ("trust", {"trust_return_name": "Flat Trust"}),
            ("trust", {"trust_return": {}}),
            ("partnership", {"partnership_return_name": "Flat Partnership"}),
            ("partnership", {"partnership_return": []}),
        ):
            with self.subTest(kind=kind, request=request):
                payload = self.payload({
                    **request,
                    f"{kind}_name": "Must stay entity-only",
                    f"{kind}_statement": "held",
                    f"{kind}_share_income": 1,
                })
                self.assertFalse(any(
                    row["number"].startswith(("TRUST-SHARE-", "PART-SHARE-"))
                    for row in payload["items"]
                ))
                self.assertTrue(payload[f"{kind}_items"] or any(
                    row["row_kind"] == f"entity-return-{kind}-request"
                    for row in payload["evidence_items"]
                ))

    def test_singleton_nested_and_return_flat_facts_merge_with_conflicts_preserved(self):
        cases = {
            "company": ("residency", "Australian"),
            "trust": ("trustee", "Example Trustee"),
            "partnership": ("partners", 2),
        }
        for kind, (field, value) in cases.items():
            with self.subTest(kind=kind):
                payload = self.payload({
                    f"{kind}_return": {"name": "Nested Name"},
                    f"{kind}_return_{field}": value,
                })
                self.assertEqual(1, len(payload[f"{kind}_items"]))
                facts = {fact["key"]: fact["value"] for fact in payload[f"{kind}_items"][0]["facts"]}
                self.assertEqual(value, facts[field.replace("_", "-")])

                conflict = self.payload({
                    f"{kind}_return": {"name": "Nested Name"},
                    f"{kind}_return_name": "Flat Name",
                })
                self.assertEqual(1, len(conflict[f"{kind}_items"]))
                evidence = " ".join(row["answer"] for row in conflict["evidence_items"])
                self.assertIn("Nested Name", evidence)
                self.assertIn("Flat Name", evidence)

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

    def test_nested_distribution_statements_route_to_entity_subtypes(self):
        payload = self.payload({
            "trust_return": {
                "name": "Synthetic Trust",
                "beneficiary_statements": [self.trust_statement()],
            },
            "partnership_return": {
                "name": "Synthetic Partnership",
                "partner_statements": [self.partner_statement()],
            },
        })
        trust = next(row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-"))
        partner = next(row for row in payload["partnership_items"] if row["number"].startswith("PARTNER-DIST-"))
        self.assertEqual("entity-return-trust-beneficiary-statement", trust["row_kind"])
        self.assertEqual("entity-return-partnership-partner-statement", partner["row_kind"])
        self.assertIn("present entitlement false", trust["answer"])
        self.assertIn("tax withheld 0", trust["answer"])
        self.assertIn("share percentage 0", partner["answer"])
        self.assertIn("loss share -25", partner["answer"])
        self.assertIn("distributions false", partner["answer"])
        child_evidence = [row for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"]]
        self.assertEqual([], child_evidence)

    def test_collection_aliases_merge_and_empty_alias_does_not_mask_populated_alias(self):
        payload = self.payload({
            "trust_return": {
                "name": "Alias Trust",
                "beneficiary_statements": [],
                "beneficiary_statement_items": [self.trust_statement()],
                "beneficiary_distribution_statements": [
                    self.trust_statement(credits={"franking": 0}, notes="merged note"),
                ],
            },
            "partnership_return": {
                "name": "Alias Partnership",
                "partner_statements": {},
                "partner_statement_items": [self.partner_statement()],
                "partner_distribution_statements": [self.partner_statement(notes="merged note")],
            },
        })
        trust = [row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-")]
        partner = [row for row in payload["partnership_items"] if row["number"].startswith("PARTNER-DIST-")]
        self.assertEqual(1, len(trust))
        self.assertEqual(1, len(partner))
        self.assertIn("merged note", trust[0]["answer"])
        self.assertIn("merged note", partner[0]["answer"])
        self.assertFalse(any("statement facts required" in row["question"] for row in payload["evidence_items"]))

    def test_flat_prefixed_collections_attach_to_single_entity(self):
        payload = self.payload({
            "trust_return": {"name": "Flat Trust"},
            "trust_return_beneficiary_statements": [self.trust_statement()],
            "partnership_return": {"name": "Flat Partnership"},
            "partnership_return_partner_statements": [self.partner_statement()],
        })
        trust = next(row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-"))
        partner = next(row for row in payload["partnership_items"] if row["number"].startswith("PARTNER-DIST-"))
        self.assertIn("trust name Flat Trust", trust["answer"])
        self.assertIn("partnership name Flat Partnership", partner["answer"])

    def test_multiple_parent_flat_statements_require_unique_matching(self):
        payload = self.payload({
            "trust_return": [{"name": "First Trust", "abn": "11"}, {"name": "Second Trust", "abn": "22"}],
            "trust_return_beneficiary_statements": [
                self.trust_statement(trust_abn="22"),
                self.trust_statement(beneficiary_name="Unmatched", beneficiary_tfn="999", trust_abn="99"),
            ],
            "partnership_return": [{"name": "First Partnership"}, {"name": "Second Partnership"}],
            "partnership_return_partner_statements": [
                self.partner_statement(partnership_name="Second Partnership"),
                self.partner_statement(partner_name="Ambiguous", partner_abn="99"),
            ],
        })
        trust_rows = [row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-")]
        partner_rows = [row for row in payload["partnership_items"] if row["number"].startswith("PARTNER-DIST-")]
        self.assertIn("trust name Second Trust", trust_rows[0]["answer"])
        self.assertIn("partnership name Second Partnership", partner_rows[0]["answer"])
        evidence = " ".join(row["answer"] for row in payload["evidence_items"])
        self.assertIn("unmatched parent entity association", evidence)
        self.assertIn("parent entity identity", evidence)

    def test_nested_statement_parent_reference_conflict_fails_closed(self):
        payload = self.payload({
            "trust_return": {
                "name": "Parent Trust",
                "abn": "11",
                "beneficiary_statements": [self.trust_statement(trust_abn="22")],
            },
            "partnership_return": {
                "name": "Parent Partnership",
                "partner_statements": [self.partner_statement(partnership_name="Other Partnership")],
            },
        })
        evidence = " ".join(row["answer"] for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"])
        self.assertEqual(2, evidence.count("conflicting parent entity association"))

    def test_missing_malformed_and_unsupported_statement_facts_fail_closed(self):
        payload = self.payload({
            "trust_return": {
                "name": "Incomplete Trust",
                "beneficiary_statements": [
                    {"beneficiary_name": "Incomplete", "statement_status": "missing", "mystery": 0},
                    "bad trust row",
                ],
            },
            "partnership_return": {
                "name": "Incomplete Partnership",
                "partner_statements": [
                    self.partner_statement(ownership_percentage=101, income_share="bad", mystery=False),
                    False,
                ],
            },
        })
        evidence = [row for row in payload["evidence_items"] if "statement" in row["row_kind"]]
        rendered = " ".join(row["answer"] + json.dumps(row["facts"]) for row in evidence)
        self.assertIn("received statement", rendered)
        self.assertIn("partner share percentage between 0 and 100", rendered)
        self.assertIn("valid income share", rendered)
        self.assertIn("bad trust row", rendered)
        self.assertIn("false", rendered.lower())
        self.assertIn("mystery", rendered)

    def test_review_status_wins_for_ambiguous_or_conflicting_statement_facts(self):
        payload = self.payload({
            "trust_return": {
                "name": "Review Trust",
                "beneficiary_statements": [
                    self.trust_statement(present_entitlement="unclear", accountant_review=True),
                ],
            },
            "partnership_return": {
                "name": "Review Partnership",
                "partner_statements": [
                    self.partner_statement(share_percentage=25, ownership_percentage=50),
                ],
            },
        })
        evidence = [row for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"]]
        self.assertTrue(evidence)
        self.assertTrue(all(row["status"] == "Accountant review" for row in evidence))
        rendered = " ".join(row["answer"] + json.dumps(row["facts"]) for row in evidence)
        self.assertIn("present entitlement", rendered)
        self.assertIn("conflicting statement facts", rendered)

    def test_complementary_identity_aliases_merge_and_identity_conflicts_are_retained(self):
        payload = self.payload({
            "trust_return": {
                "name": "Merge Trust",
                "beneficiary_statements": [self.trust_statement(beneficiary_tfn="111")],
                "beneficiary_statement_items": [
                    self.trust_statement(beneficiary_tfn="222", notes="same name different TFN"),
                ],
            },
            "partnership_return": {
                "name": "Merge Partnership",
                "partner_statements": [self.partner_statement(partner_abn="111")],
                "partner_statement_items": [
                    self.partner_statement(partner_abn="222", notes="same name different ABN"),
                ],
            },
        })
        self.assertEqual(1, len([row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-")]))
        self.assertEqual(1, len([row for row in payload["partnership_items"] if row["number"].startswith("PARTNER-DIST-")]))
        evidence = [row for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"]]
        self.assertTrue(all(row["status"] == "Accountant review" for row in evidence))
        rendered = json.dumps(evidence)
        self.assertIn("111", rendered)
        self.assertIn("222", rendered)

    def test_nonfinite_amounts_and_percentages_fail_closed(self):
        for value in (float("nan"), float("inf"), "NaN", "Infinity"):
            with self.subTest(value=value):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Finite Partnership",
                        "partner_statements": [self.partner_statement(
                            ownership_percentage=value,
                            income_share=value,
                        )],
                    },
                })
                evidence = " ".join(row["answer"] for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"])
                self.assertIn("valid income share", evidence)
                self.assertIn("partner share percentage between 0 and 100", evidence)

    def test_explicit_evidence_denial_is_preserved_and_requires_evidence(self):
        payload = self.payload({
            "trust_return": {
                "name": "Evidence Trust",
                "beneficiary_statements": [self.trust_statement(statement_files=False)],
            },
            "partnership_return": {
                "name": "Evidence Partnership",
                "partner_statements": [self.partner_statement(documents=False)],
            },
        })
        rows = [
            row
            for key in ("trust_items", "partnership_items")
            for row in payload[key]
            if row["number"].startswith(("TRUST-BEN-", "PARTNER-DIST-"))
        ]
        self.assertTrue(all("evidence [false]" in row["answer"].lower() for row in rows))
        evidence = [row for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"]]
        self.assertEqual(2, len(evidence))
        self.assertTrue(all("evidence" in row["answer"] for row in evidence))

    def test_invalid_statement_provenance_is_retained_without_links(self):
        payload = self.payload({
            "trust_return": {
                "name": "Source Trust",
                "beneficiary_statements": [self.trust_statement(
                    source_urls=["https://example.invalid/trust", "bad source"],
                    checked_at="not-a-date",
                )],
            },
        })
        trust = next(row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-"))
        self.assertIn("https://example.invalid/trust", trust["source_urls"])
        self.assertNotIn("bad source", trust["source_urls"])
        evidence = next(row for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"])
        self.assertIn("source provenance", evidence["answer"])
        self.assertIn("checked-at provenance", evidence["answer"])

    def test_entity_statements_never_duplicate_individual_share_rows(self):
        payload = self.payload({
            "trust_return": {"name": "Entity Trust", "beneficiary_statements": [self.trust_statement()]},
            "partnership_return": {"name": "Entity Partnership", "partner_statements": [self.partner_statement()]},
            "trust_beneficiary_statement_items": [{"entity_name": "Individual Trust", "statement": "held", "income": 1}],
            "partnership_share_items": [{"entity_name": "Individual Partnership", "statement": "held", "income": 2}],
        })
        individual = [row for row in payload["items"] if row["number"].startswith(("TRUST-SHARE-", "PART-SHARE-"))]
        self.assertEqual(2, len(individual))
        rendered = " ".join(row["answer"] for row in individual)
        self.assertIn("Individual Trust", rendered)
        self.assertIn("Individual Partnership", rendered)
        self.assertNotIn("Entity Trust", rendered)
        self.assertNotIn("Entity Partnership", rendered)

    def test_direct_renderer_preserves_valid_statement_subtypes(self):
        data = taxmate_taxpack.load_guide_payload({
            "trust_items": [{
                "number": "DIRECT-T",
                "row_kind": "entity-return-trust-beneficiary-statement",
                "facts": [{"key": "present-entitlement", "value": False}],
            }],
            "partnership_items": [{
                "number": "DIRECT-P",
                "row_kind": "entity-return-partnership-partner-statement",
                "facts": [{"key": "share-percentage", "value": 0}],
            }],
        })
        self.assertEqual("entity-return-trust-beneficiary-statement", data.trust_items[0].row_kind)
        self.assertEqual("entity-return-partnership-partner-statement", data.partnership_items[0].row_kind)
        self.assertIn(taxmate_entity_routing.SOURCES["trust"], data.trust_items[0].source_urls)
        self.assertIn(taxmate_entity_routing.SOURCES["partnership"], data.partnership_items[0].source_urls)

        invalid = taxmate_taxpack.load_guide_payload({
            "trust_items": [{
                "number": "DIRECT-INVALID",
                "row_kind": "entity-return-partnership-partner-statement",
                "facts": [{"key": "name", "value": "Wrong namespace"}],
            }],
        })
        self.assertEqual("entity-return-trust", invalid.trust_items[0].row_kind)

    def test_empty_statement_collections_fail_closed(self):
        payload = self.payload({
            "trust_return": {"name": "Empty Trust", "beneficiary_statements": []},
            "partnership_return": {"name": "Empty Partnership", "partner_statements": None},
        })
        evidence = [row for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"]]
        self.assertEqual(2, len(evidence))
        self.assertTrue(all(row["status"] == "Evidence" for row in evidence))


if __name__ == "__main__":
    unittest.main()
