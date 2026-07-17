import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import atodata
import taxmate_intake
import taxmate_entity_routing
import taxmate_entity_worksheet
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

        for url in taxmate_entity_worksheet.DETAILED_SOURCES:
            with self.subTest(url=url):
                self.assertIn(url, atodata.SEED_URLS)
                self.assertTrue(records[url]["content_verified"])
                self.assertEqual(64, len(records[url]["content_hash"]))
                self.assertEqual(records[url]["content_hash"], covered[url]["content_hash"])
                expected_status = (
                    "verified"
                    if url in (
                        *taxmate_entity_worksheet.COMPANY_REVIEW_SOURCES,
                        *taxmate_entity_worksheet.PARTNERSHIP_REVIEW_SOURCES,
                        *taxmate_entity_worksheet.TRUST_REVIEW_SOURCES,
                    )
                    else "metadata_only"
                )
                self.assertEqual(expected_status, covered[url]["status"])
                if url in (
                    *taxmate_entity_worksheet.COMPANY_REVIEW_SOURCES[2:],
                    *taxmate_entity_worksheet.TRUST_REVIEW_SOURCES,
                ):
                    self.assertIn("records-evidence", covered[url]["skills"])

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
        self.assertIn('"carried_losses": false', rendered)
        self.assertIn('"beneficiary": 0', rendered)
        self.assertIn('"cgt_details": []', rendered)
        franking = next(
            row for row in payload["company_items"]
            if row["row_kind"] == "entity-return-company-franking-account"
        )
        self.assertIn("credits 0", franking["answer"])
        self.assertTrue(all(row["status"] in {"Evidence", "Accountant review"} for row in evidence))

    def test_nested_alias_lists_keep_unsupported_and_route_partnership_losses(self):
        payload = self.payload({
            "company_intake": [{"name": "Alias Co", "dividends": False}],
            "trust_entity": {"name": "Alias Trust", "distributions": 0},
            "partnership_return_losses": {"carried_forward": 0},
        })
        rendered = " ".join(row["answer"] for row in payload["evidence_items"])
        self.assertIn('"distributions": 0', rendered)
        dividend = next(
            row for row in payload["company_items"]
            if row["row_kind"] == "entity-return-company-dividend"
        )
        self.assertIn("amount false", dividend["answer"])
        loss = next(
            row for row in payload["partnership_items"]
            if row["row_kind"] == "entity-return-partnership-loss"
        )
        self.assertIn("carried forward 0", loss["answer"])
        self.assertIn("finite partnership loss amount", rendered)

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

    def test_nested_and_flat_entity_sources_merge_without_missing_sentinel(self):
        nested_source = "https://example.invalid/nested-company"
        flat_source = "https://example.invalid/flat-company"
        payload = self.payload({
            "company_return": {"name": "Source Co", "source_url": nested_source},
            "company_return_source_url": flat_source,
        })
        sources = payload["company_items"][0]["source_urls"]
        self.assertIn(nested_source, sources)
        self.assertIn(flat_source, sources)
        self.assertNotIn(None, sources)
        self.assertFalse(any(
            "source provenance" in row["answer"]
            for row in payload["evidence_items"]
        ))

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

    def test_blank_repeater_objects_do_not_create_factless_rows(self):
        payload = self.payload({
            "trust_return_beneficiary_statements": [{}, {"notes": ""}, self.trust_statement()],
            "partnership_return_partner_statement_items": [{}, self.partner_statement()],
        })
        trust = [row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-")]
        partner = [row for row in payload["partnership_items"] if row["number"].startswith("PARTNER-DIST-")]
        self.assertEqual(1, len(trust))
        self.assertEqual(1, len(partner))
        self.assertTrue(trust[0]["facts"])
        self.assertTrue(partner[0]["facts"])

        unknown = self.payload({
            "trust_return_beneficiary_statements": [{}, {"statement_status": "unknown"}],
        })
        self.assertEqual(1, len([row for row in unknown["trust_items"] if row["number"].startswith("TRUST-BEN-")]))
        self.assertTrue(any("received statement" in row["answer"] for row in unknown["evidence_items"]))

        blank_only = self.payload({"partnership_return_partner_statements": [{}, {"notes": ""}]})
        self.assertFalse(any(row["number"].startswith("PARTNER-DIST-") for row in blank_only["partnership_items"]))
        self.assertTrue(any("statement facts required" in row["question"] for row in blank_only["evidence_items"]))

    def test_blank_nested_collection_does_not_mask_flat_statements(self):
        payload = self.payload({
            "trust_return": {"name": "Merged Trust", "beneficiary_statements": None},
            "trust_return_beneficiary_statements": [self.trust_statement()],
            "partnership_return": {"name": "Merged Partnership", "partner_statements": ""},
            "partnership_return_partner_statements": [self.partner_statement()],
        })
        trust = [row for row in payload["trust_items"] if row["number"].startswith("TRUST-BEN-")]
        partner = [row for row in payload["partnership_items"] if row["number"].startswith("PARTNER-DIST-")]
        self.assertEqual(["TRUST-BEN-1"], [row["number"] for row in trust])
        self.assertEqual(["PARTNER-DIST-1"], [row["number"] for row in partner])
        child_evidence = [row for row in payload["evidence_items"] if "statement" in row["row_kind"]]
        self.assertEqual([], child_evidence)

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

    def test_nested_component_amounts_validate_every_leaf(self):
        payload = self.payload({
            "trust_return": {
                "name": "Nested Amount Trust",
                "beneficiary_statements": [self.trust_statement(
                    income_components={"primary": "bad"},
                    credits=[{"franking": "bad"}],
                    tax_withheld={"amount": "bad"},
                )],
            },
            "partnership_return": {
                "name": "Nested Amount Partnership",
                "partner_statements": [self.partner_statement(
                    income_share={"primary": "bad"},
                    loss_share=[{"amount": "bad"}],
                    credits={"franking": "bad"},
                    withholding={"amount": "bad"},
                    drawings=["bad"],
                    distributions={"cash": "bad"},
                )],
            },
        })
        evidence = " ".join(row["answer"] for row in payload["evidence_items"] if "statement-evidence" in row["row_kind"])
        for field in (
            "income components", "credits", "tax withheld", "income share", "loss share",
            "drawings", "distributions",
        ):
            self.assertIn(f"valid {field}", evidence)

        valid = self.payload({
            "trust_return_beneficiary_statements": [self.trust_statement(
                income_components=[{"type": "primary", "amount": 0}],
                credits={"franking": {"label": "franking credit", "amount": 0}},
            )],
        })
        child_evidence = [row for row in valid["evidence_items"] if "statement-evidence" in row["row_kind"]]
        self.assertFalse(any("valid income components" in row["answer"] or "valid credits" in row["answer"] for row in child_evidence))

    def test_statement_amounts_reject_booleans_and_metadata_only_components(self):
        payload = self.payload({
            "trust_return": {
                "name": "Boolean Amount Trust",
                "beneficiary_statements": [self.trust_statement(
                    income_components=[{"type": "primary"}],
                    credits={"franking": True},
                    tax_withheld=False,
                )],
            },
            "partnership_return": {
                "name": "Boolean Amount Partnership",
                "partner_statements": [self.partner_statement(
                    income_share=True,
                    loss_share=False,
                    credits=[{"label": "franking credit"}],
                    withholding={"amount": True},
                    drawings=[False],
                    distributions={"cash": True},
                )],
            },
        })
        evidence = " ".join(
            row["answer"]
            for row in payload["evidence_items"]
            if "statement-evidence" in row["row_kind"]
        )
        for field in (
            "income components", "credits", "tax withheld", "income share", "loss share",
            "drawings", "distributions",
        ):
            self.assertIn(f"valid {field}", evidence)

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


class EntityWorksheetRoutingTests(unittest.TestCase):
    def payload(self, answers):
        return taxmate_intake.answers_to_pack_payload({"income_year": "2025-26", **answers})

    def income_item(self, **overrides):
        item = {
            "category": "interest",
            "description": "Business saver interest",
            "amount": 0,
            "evidence": ["interest-statement.pdf"],
            "gst_bas_interaction": False,
            "private_use": False,
            "source_urls": ["https://example.invalid/income"],
            "checked_at": "2026-07-15T10:00:00Z",
        }
        item.update(overrides)
        return item

    def deduction_item(self, **overrides):
        item = {
            "category": "repairs-maintenance",
            "description": "Equipment servicing",
            "amount": 125,
            "evidence": ["invoice.pdf"],
            "gst_bas_interaction": False,
            "non_deductible": False,
        }
        item.update(overrides)
        return item

    def test_company_and_partnership_rows_share_contract_and_stay_isolated(self):
        payload = self.payload({
            "company_return": {
                "name": "Worksheet Co",
                "abn": "11 222 333 444",
                "income_items": [self.income_item()],
                "expense_items": [self.deduction_item()],
                "income_total": 0,
                "expense_total": 125,
            },
            "partnership_return": {
                "name": "Worksheet Partnership",
                "abn": "55 666 777 888",
                "income_categories": [self.income_item(category="business-income")],
                "deduction_items": [self.deduction_item(category="interest")],
                "income_total": 0,
                "deduction_total": 125,
            },
        })
        company = [row for row in payload["company_items"] if "worksheet" in row["ato_area"].lower()]
        partnership = [row for row in payload["partnership_items"] if "worksheet" in row["ato_area"].lower()]
        self.assertEqual(4, len(company))
        self.assertEqual(4, len(partnership))
        self.assertIn("amount 0", company[0]["answer"])
        self.assertIn("gst bas interaction false", company[0]["answer"])
        self.assertTrue(all(row["status"] == "Accountant review" for row in company + partnership))
        self.assertFalse(any(
            row["row_kind"].startswith("entity-return-company")
            or row["row_kind"].startswith("entity-return-partnership")
            for row in payload["items"]
        ))
        self.assertFalse(any("total reconciliation" in row["answer"] for row in payload["evidence_items"]))

    def test_alias_collections_dedupe_and_conflicting_total_fails_closed(self):
        item = self.income_item(amount="1,000")
        payload = self.payload({
            "company_return": {
                "name": "Alias Co",
                "income_items": [item],
                "income_categories": [dict(item)],
                "income_total": 999,
            },
        })
        rows = [row for row in payload["company_items"] if row["row_kind"] == "entity-return-company-income"]
        self.assertEqual(2, len(rows))
        self.assertEqual(1, len([row for row in rows if "Supplied income total" not in row["question"]]))
        evidence = [row for row in payload["evidence_items"] if row["row_kind"] == "entity-return-company-income-evidence"]
        self.assertTrue(any("total reconciliation" in row["answer"] for row in evidence))

    def test_equivalent_monetary_aliases_do_not_create_conflicts(self):
        payload = self.payload({
            "company_return": {
                "name": "Equivalent Co",
                "deduction_items": [{
                    "category": "repairs-maintenance",
                    "description": "Service",
                    "amount": "1,000",
                    "value": 1000,
                    "evidence": ["invoice.pdf"],
                }],
                "deduction_total": "1,000",
                "expense_total": 1000,
            },
            "company_return_deduction_total": 1000,
        })
        rows = [row for row in payload["company_items"] if row["row_kind"] == "entity-return-company-deduction"]
        self.assertEqual(2, len(rows))
        self.assertFalse(any("conflicts" in row["answer"] for row in rows))
        self.assertFalse(any(
            row["row_kind"] == "entity-return-company-deduction-evidence"
            for row in payload["evidence_items"]
        ))

    def test_alias_collections_merge_complements_and_preserve_conflicts(self):
        payload = self.payload({
            "company_return": {
                "name": "Merged Co",
                "income_items": [{"category": "interest", "description": "Bank", "amount": 10}],
                "income_categories": [{
                    "category": "interest",
                    "description": "Bank",
                    "amount": 20,
                    "evidence": ["statement.pdf"],
                    "private_use": False,
                }],
            },
        })
        rows = [row for row in payload["company_items"] if row["row_kind"] == "entity-return-company-income"]
        self.assertEqual(1, len(rows))
        self.assertIn("evidence [\"statement.pdf\"]", rows[0]["answer"])
        self.assertIn("private use false", rows[0]["answer"])
        evidence = next(
            row for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-company-income-evidence"
        )
        self.assertEqual("Accountant review", evidence["status"])
        self.assertIn("conflicting item facts", evidence["answer"])

    def test_top_level_accounting_and_gst_context_is_not_dropped(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Context Partnership",
                "accounting_records": False,
                "gst_bas_interaction": False,
            },
        })
        row = next(
            row for row in payload["partnership_items"]
            if row["question"] == "Partnership accounting and GST/BAS context"
        )
        self.assertIn("accounting records false", row["answer"])
        self.assertIn("gst bas interaction false", row["answer"])
        evidence = next(
            row for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-partnership-deduction-evidence"
        )
        self.assertEqual("Evidence", evidence["status"])
        self.assertIn("accounting records", evidence["answer"])

    def test_partnership_category_uses_narrow_detailed_source(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Source Partnership",
                "income_items": [self.income_item(category="interest")],
            },
        })
        row = next(row for row in payload["partnership_items"] if row["row_kind"] == "entity-return-partnership-income")
        self.assertIn(taxmate_entity_worksheet.PARTNERSHIP_ITEMS_10_TO_15_SOURCE, row["source_urls"])
        self.assertNotIn(taxmate_entity_worksheet.PARTNERSHIP_ITEM_5_SOURCE, row["source_urls"])

    def test_blank_declined_and_malformed_collections_have_distinct_behavior(self):
        declined = self.payload({"company_return": {"name": "No Worksheet Co", "income_items": False}})
        self.assertFalse(any(row["row_kind"] == "entity-return-company-income" for row in declined["company_items"]))
        self.assertFalse(any(row["row_kind"] == "entity-return-company-income-evidence" for row in declined["evidence_items"]))

        blank = self.payload({"company_return": {"name": "Blank Co", "income_items": []}})
        self.assertTrue(any(
            row["row_kind"] == "entity-return-company-income-evidence"
            and "income items" in row["answer"]
            for row in blank["evidence_items"]
        ))

        blank_item = self.payload({"company_return": {"name": "Blank Item Co", "income_items": [{}]}})
        self.assertTrue(any(
            row["row_kind"] == "entity-return-company-income-evidence"
            and "income items" in row["answer"]
            for row in blank_item["evidence_items"]
        ))

        malformed = self.payload({"company_return": {"name": "Malformed Co", "income_items": [False, "bad"]}})
        rendered = json.dumps(malformed["evidence_items"])
        self.assertIn("false", rendered.lower())
        self.assertIn("bad", rendered)

    def test_flat_worksheet_only_records_are_not_malformed_entities(self):
        cases = (
            ("company", "company_return_income_items", [self.income_item()]),
            ("partnership", "partnership_return_expense_items", [self.deduction_item(category="interest")]),
        )
        for kind, key, value in cases:
            with self.subTest(kind=kind):
                payload = self.payload({key: value})
                self.assertTrue(any(
                    row["row_kind"] == f"entity-return-{kind}-{'income' if kind == 'company' else 'deduction'}"
                    for row in payload[f"{kind}_items"]
                ))
                self.assertTrue(any(
                    f"{kind} identity" in row["answer"]
                    for row in payload["evidence_items"]
                    if row["row_kind"].startswith(f"entity-return-{kind}-")
                ))
                self.assertFalse(any(
                    row["row_kind"] == "entity-return-malformed"
                    for row in payload["evidence_items"]
                ))

    def test_invalid_amount_evidence_and_provenance_are_preserved(self):
        for amount in (True, False, float("nan"), float("inf"), "NaN", "bad"):
            with self.subTest(amount=amount):
                payload = self.payload({
                    "company_return": {
                        "name": "Invalid Co",
                        "income_items": [self.income_item(
                            amount=amount,
                            evidence=False,
                            source_urls=["bad source", False],
                            checked_at="bad date",
                        )],
                    },
                })
                row = next(row for row in payload["company_items"] if row["row_kind"] == "entity-return-company-income")
                evidence = next(row for row in payload["evidence_items"] if row["row_kind"] == "entity-return-company-income-evidence")
                self.assertIn(str(amount).lower(), row["answer"].lower())
                self.assertIn("finite amount", evidence["answer"])
                self.assertIn("evidence", evidence["answer"])
                self.assertIn("source provenance", evidence["answer"])
                self.assertIn("checked-at provenance", evidence["answer"])
                self.assertNotIn("bad source", row["source_urls"])

        negative = self.payload({
            "company_return": {
                "name": "Negative Co",
                "income_items": [self.income_item(amount=-25)],
                "income_total": -25,
            },
        })
        negative_row = next(row for row in negative["company_items"] if row["number"] == "COMPANY-INCOME-1")
        self.assertIn("amount -25", negative_row["answer"])
        self.assertFalse(any(
            "finite amount" in row["answer"]
            for row in negative["evidence_items"]
            if row["row_kind"] == "entity-return-company-income-evidence"
        ))

    def test_unknown_company_categories_remain_review_and_dividends_migrate(self):
        payload = self.payload({
            "company_return": {
                "name": "Boundary Co",
                "income_items": [
                    self.income_item(category="dividends", amount=0),
                    self.income_item(category="mystery income"),
                ],
                "deduction_items": [self.deduction_item(category="depreciation")],
            },
        })
        evidence = [
            row for row in payload["evidence_items"]
            if row["row_kind"] in {
                "entity-return-company-income-evidence",
                "entity-return-company-deduction-evidence",
            }
        ]
        rendered = " ".join(row["answer"] for row in evidence)
        self.assertIn("supported category", rendered)
        self.assertTrue(all(row["status"] == "Accountant review" for row in evidence))
        dividend = next(
            row for row in payload["company_items"]
            if row["row_kind"] == "entity-return-company-dividend"
        )
        self.assertIn("amount 0", dividend["answer"])
        self.assertIn("dividend direction received", dividend["answer"])
        self.assertFalse(any(
            row["row_kind"] == "entity-return-company-income"
            and "category dividends" in row["answer"]
            for row in payload["company_items"]
        ))

        with_total = self.payload({
            "company_return": {
                "name": "Unsupported Total Co",
                "income_items": [self.income_item(category="mystery income", amount=10)],
                "income_total": 10,
            },
        })
        total = next(row for row in with_total["company_items"] if "TOTAL" in row["number"])
        self.assertIn("item reconciliation unavailable", total["answer"])

    def test_company_dividend_franking_and_division_7a_rows_preserve_review_facts(self):
        payload = self.payload({
            "company_return": {
                "name": "Review Benefits Co",
                "income_items": [{
                    "category": "dividends",
                    "amount": 0,
                    "franked_amount": 0,
                    "unfranked_amount": 0,
                    "franking_credit": 0,
                    "evidence": ["dividend-statement.pdf"],
                    "source_url": "https://example.invalid/dividend",
                    "checked_at": "2026-07-16T10:00:00Z",
                }],
                "franking_account": {
                    "opening_balance": 0,
                    "credits": 0,
                    "debits": 0,
                    "closing_balance": 0,
                    "deficit": False,
                    "franking_deficit_tax": 0,
                    "records": ["franking-account.csv"],
                },
                "division_7a": {
                    "shareholder": "Synthetic Shareholder",
                    "loan_amount": 0,
                    "asset_use": False,
                    "debt_forgiven": 0,
                    "complying_loan_agreement": False,
                    "minimum_repayment_made": False,
                    "distributable_surplus": 0,
                    "retained_earnings": 0,
                    "private_expense": False,
                    "interposed_entity": False,
                    "trust_upe": False,
                    "records": ["related-party-ledger.pdf"],
                },
            },
        })
        rows = {
            row["row_kind"]: row for row in payload["company_items"]
            if row["row_kind"] in {
                "entity-return-company-dividend",
                "entity-return-company-franking-account",
                "entity-return-company-division-7a",
            }
        }
        self.assertEqual(3, len(rows))
        rendered = json.dumps(rows)
        for expected in (
            "franked amount 0", "franking credit 0", "deficit false",
            "franking deficit tax 0", "loan amount 0", "asset use false",
            "debt forgiven 0", "complying loan agreement false",
            "minimum repayment made false", "distributable surplus 0",
            "retained earnings 0", "private expense false",
            "interposed entity false", "trust upe false",
        ):
            self.assertIn(expected, rendered)
        self.assertIn(
            taxmate_entity_worksheet.COMPANY_DIVIDEND_SOURCE,
            rows["entity-return-company-dividend"]["source_urls"],
        )
        self.assertTrue(taxmate_entity_worksheet.COMPANY_DIVIDEND_SOURCE.endswith(
            "dividend-and-interest-schedule-2026"
        ))
        self.assertNotIn(
            "https://www.ato.gov.au/forms-and-instructions/dividend-and-interest-schedule-2025",
            rows["entity-return-company-dividend"]["source_urls"],
        )
        self.assertIn(
            taxmate_entity_worksheet.COMPANY_FRANKING_SOURCE,
            rows["entity-return-company-franking-account"]["source_urls"],
        )
        self.assertIn(
            taxmate_entity_worksheet.COMPANY_DIVISION_7A_SOURCE,
            rows["entity-return-company-division-7a"]["source_urls"],
        )
        evidence = " ".join(
            row["answer"] for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-company-division-7a-evidence"
        )
        self.assertIn("complying loan agreement review", evidence)
        self.assertIn("repayment review", evidence)
        self.assertTrue(all(row["status"] == "Accountant review" for row in rows.values()))
        self.assertFalse(any(
            row["row_kind"].startswith("entity-return-company-")
            for row in payload["items"] + payload["trust_items"] + payload["partnership_items"]
        ))

    def test_company_review_flat_scalar_aliases_dedupe_and_fail_closed(self):
        payload = self.payload({
            "company_return": [{"name": "First Co"}, {"name": "Review Co", "abn": "22"}],
            "company_return_entity_name": "Review Co",
            "company_return_dividends": 0,
            "company_return_dividend_direction": "paid",
            "company_return_dividend_records": ["resolution.pdf"],
            "company_return_franking_account": 0,
            "company_return_franking_opening_balance": 0,
            "company_return_franking_records": ["franking.csv"],
            "company_return_division_7a": 0,
            "company_return_division_7a_loan_amount": 0,
            "company_return_division_7a_records": ["ledger.pdf"],
            "company_return_source_urls": [
                "bad source",
                "https://example.invalid/company-review",
            ],
            "company_return_checked_at": "bad date",
        })
        rows = [
            row for row in payload["company_items"]
            if row["row_kind"] in {
                "entity-return-company-dividend",
                "entity-return-company-franking-account",
                "entity-return-company-division-7a",
            }
        ]
        self.assertEqual(3, len(rows))
        self.assertTrue(all("company name Review Co" in row["answer"] for row in rows))
        self.assertEqual(
            1,
            sum(row["row_kind"] == "entity-return-company-dividend" for row in rows),
        )
        rendered = json.dumps(rows)
        self.assertIn("amount 0", rendered)
        self.assertIn("closing balance 0", rendered)
        self.assertIn("loan amount 0", rendered)
        evidence = " ".join(
            row["answer"] for row in payload["evidence_items"]
            if row["row_kind"].startswith("entity-return-company-")
        )
        self.assertIn("source provenance", evidence)
        self.assertIn("checked-at provenance", evidence)
        self.assertNotIn("parent entity", evidence)

    def test_company_deferred_and_direct_dividend_aliases_merge_once(self):
        shared = {
            "category": "dividends",
            "description": "Synthetic dividend",
            "amount": 0,
            "evidence": ["dividend.pdf"],
        }
        payload = self.payload({
            "company_return": {
                "name": "Dedupe Co",
                "income_items": [shared],
                "dividend_items": [{
                    **shared,
                    "franking_credit": 0,
                    "resolution": False,
                }],
                "income_total": 0,
            },
        })
        dividends = [
            row for row in payload["company_items"]
            if row["row_kind"] == "entity-return-company-dividend"
        ]
        self.assertEqual(1, len(dividends))
        self.assertIn("franking credit 0", dividends[0]["answer"])
        self.assertIn("resolution false", dividends[0]["answer"])
        self.assertIn("dividend direction received", dividends[0]["answer"])
        total = next(
            row for row in payload["company_items"]
            if row["number"] == "COMPANY-INCOME-TOTAL-1"
        )
        self.assertIn("matches supplied item total", total["answer"])

    def test_company_deferred_franking_amount_normalizes_to_account_credit(self):
        payload = self.payload({
            "company_return": {
                "name": "Franking Migration Co",
                "income_items": [{
                    "category": "franking",
                    "amount": 100,
                    "evidence": ["franking-ledger.csv"],
                }],
                "income_total": 100,
            },
        })
        row = next(
            row for row in payload["company_items"]
            if row["row_kind"] == "entity-return-company-franking-account"
        )
        self.assertIn("credits 100", row["answer"])
        evidence = " ".join(
            row["answer"] for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-company-franking-account-evidence"
        )
        self.assertNotIn("finite monetary fact", evidence)
        self.assertNotIn("franking account fact", evidence)
        self.assertFalse(any(
            row["row_kind"] == "entity-return-company-income"
            and "category franking" in row["answer"]
            for row in payload["company_items"]
        ))
        total = next(
            row for row in payload["company_items"]
            if row["number"] == "COMPANY-INCOME-TOTAL-1"
        )
        self.assertIn("matches supplied item total", total["answer"])

    def test_company_dividend_aliases_preserve_nested_flat_and_scalar_direction(self):
        nested = self.payload({
            "company_return": {
                "name": "Paid Alias Co",
                "dividends_paid": 0,
                "dividend_records": ["resolution.pdf"],
            },
        })
        paid = next(
            row for row in nested["company_items"]
            if row["row_kind"] == "entity-return-company-dividend"
        )
        self.assertIn("amount 0", paid["answer"])
        self.assertIn("dividend direction paid", paid["answer"])
        nested_evidence = " ".join(
            row["answer"] for row in nested["evidence_items"]
            if row["row_kind"] == "entity-return-company-dividend-evidence"
        )
        self.assertNotIn("dividend paid or received", nested_evidence)

        flat = self.payload({
            "company_return_name": "Received Alias Co",
            "company_return_dividends_received": {
                "amount": 25,
                "evidence": ["dividend-statement.pdf"],
            },
        })
        received = next(
            row for row in flat["company_items"]
            if row["row_kind"] == "entity-return-company-dividend"
        )
        self.assertIn("amount 25", received["answer"])
        self.assertIn("dividend direction received", received["answer"])
        flat_evidence = " ".join(
            row["answer"] for row in flat["evidence_items"]
            if row["row_kind"] == "entity-return-company-dividend-evidence"
        )
        self.assertNotIn("dividend paid or received", flat_evidence)

    def test_company_division_7a_boolean_signals_are_not_validated_as_money(self):
        denied = self.payload({
            "company_return": {
                "name": "Denied Loan Co",
                "division_7a": {
                    "payment": 100,
                    "loan": False,
                    "asset_use": False,
                    "private_expense": False,
                    "evidence": ["related-party-ledger.pdf"],
                },
            },
        })
        denied_row = next(
            row for row in denied["company_items"]
            if row["row_kind"] == "entity-return-company-division-7a"
        )
        self.assertIn("payment 100", denied_row["answer"])
        self.assertIn("loan false", denied_row["answer"])
        self.assertIn("asset use false", denied_row["answer"])
        denied_evidence = " ".join(
            row["answer"] for row in denied["evidence_items"]
            if row["row_kind"] == "entity-return-company-division-7a-evidence"
        )
        self.assertNotIn("finite monetary fact", denied_evidence)
        self.assertNotIn("loan agreement", denied_evidence)
        self.assertNotIn("repayment", denied_evidence)

        confirmed = self.payload({
            "company_return": {
                "name": "Confirmed Loan Co",
                "division_7a": {
                    "loan": True,
                    "evidence": ["related-party-ledger.pdf"],
                },
            },
        })
        confirmed_evidence = " ".join(
            row["answer"] for row in confirmed["evidence_items"]
            if row["row_kind"] == "entity-return-company-division-7a-evidence"
        )
        self.assertNotIn("finite monetary fact", confirmed_evidence)
        self.assertIn("loan agreement", confirmed_evidence)
        self.assertIn("repayment", confirmed_evidence)

    def test_company_division_7a_aliases_preserve_transaction_and_recipient_meaning(self):
        cases = (
            (
                "shareholder_loans",
                40,
                ("loan amount 40", "transaction type loan", "shareholder true"),
            ),
            (
                "director_loans",
                50,
                ("loan amount 50", "transaction type loan", "director true"),
            ),
            (
                "related_party_benefits",
                60,
                ("payment 60", "transaction type benefit", "related party true"),
            ),
        )
        for alias, value, expected in cases:
            with self.subTest(alias=alias):
                payload = self.payload({
                    "company_return": {
                        "name": "Alias Meaning Co",
                        alias: value,
                        "division_7a_records": ["related-party-ledger.pdf"],
                    },
                })
                row = next(
                    row for row in payload["company_items"]
                    if row["row_kind"] == "entity-return-company-division-7a"
                )
                for text in expected:
                    self.assertIn(text, row["answer"])

    def test_company_review_alias_conflicts_and_malformed_amounts_fail_closed(self):
        payload = self.payload({
            "company_return": {
                "name": "Conflict Co",
                "dividends": {
                    "amount": "unknown",
                    "dividend_direction": "paid",
                    "records": False,
                },
                "dividend_amount": 50,
                "franking_account": {
                    "opening_balance": "NaN",
                    "records": False,
                },
                "franking_opening_balance": 0,
                "division_7a": {
                    "loan_amount": "unknown",
                    "records": False,
                    "source_urls": ["bad source"],
                    "checked_at": "bad date",
                },
                "division_7a_loan_amount": 0,
            },
        })
        evidence = [
            row for row in payload["evidence_items"]
            if row["row_kind"] in {
                "entity-return-company-dividend-evidence",
                "entity-return-company-franking-account-evidence",
                "entity-return-company-division-7a-evidence",
            }
        ]
        rendered = json.dumps(evidence)
        for expected in (
            "finite monetary fact", "evidence", "conflicting review aliases",
            "source provenance", "checked-at provenance",
        ):
            self.assertIn(expected, rendered)
        self.assertTrue(all(row["status"] == "Accountant review" for row in evidence))

    def test_company_issue_131_flat_fact_matrix_preserves_negative_and_alias_values(self):
        payload = self.payload({
            "company_return_name": "Complete Review Co",
            "company_return_dividend_direction": "paid",
            "company_return_dividend_amount": -10,
            "company_return_dividend_franked_amount": -4,
            "company_return_dividend_unfranked_amount": -6,
            "company_return_dividend_franking_credits": -1,
            "company_return_dividend_resolution": "directors-resolution.pdf",
            "company_return_dividend_evidence_status": "partial",
            "company_return_dividend_records": ["dividend-ledger.pdf"],
            "company_return_franking_opening_balance": -100,
            "company_return_franking_credits": 0,
            "company_return_franking_debits": -5,
            "company_return_franking_closing_balance": -105,
            "company_return_franking_deficit": True,
            "company_return_franking_fdt_payable": -7,
            "company_return_franking_benchmark_percentage": 30,
            "company_return_franking_evidence_status": "review required",
            "company_return_franking_records": ["franking-account.csv"],
            "company_return_division_7a_transaction_type": "loan and benefit",
            "company_return_division_7a_related_party": True,
            "company_return_division_7a_shareholder_payment": -10,
            "company_return_division_7a_director_payment": 0,
            "company_return_division_7a_associate_payment": -5,
            "company_return_division_7a_loan_amount": -100,
            "company_return_division_7a_repayments": -1,
            "company_return_division_7a_complying_loan_agreement": True,
            "company_return_division_7a_loan_terms": "7-year written agreement",
            "company_return_division_7a_loan_term_years": 7,
            "company_return_division_7a_interest_rate": 8.77,
            "company_return_division_7a_benchmark_rate": 8.77,
            "company_return_division_7a_maturity_date": "2033-06-30",
            "company_return_division_7a_minimum_repayment": 0,
            "company_return_division_7a_repayment_made": False,
            "company_return_division_7a_distributable_surplus": -200,
            "company_return_division_7a_retained_profit": -300,
            "company_return_division_7a_interposed_entity": True,
            "company_return_division_7a_trust_upe": True,
            "company_return_division_7a_evidence_status": "partial",
            "company_return_division_7a_records": ["related-party-ledger.pdf"],
        })
        rows = {
            row["row_kind"]: row
            for row in payload["company_items"]
            if row["row_kind"] in {
                "entity-return-company-dividend",
                "entity-return-company-franking-account",
                "entity-return-company-division-7a",
            }
        }
        self.assertEqual(3, len(rows))
        rendered = json.dumps(rows)
        for expected in (
            "amount -10",
            "franked amount -4",
            "unfranked amount -6",
            "franking credit -1",
            "evidence status partial",
            "opening balance -100",
            "credits 0",
            "debits -5",
            "closing balance -105",
            "deficit true",
            "franking deficit tax -7",
            "shareholder payment -10",
            "director payment 0",
            "associate payment -5",
            "loan amount -100",
            "repayments -1",
            "loan terms 7-year written agreement",
            "loan term years 7",
            "interest rate 8.77",
            "benchmark interest rate 8.77",
            "minimum yearly repayment 0",
            "minimum repayment made false",
            "distributable surplus -200",
            "retained profit -300",
            "interposed entity true",
            "trust upe true",
        ):
            self.assertIn(expected, rendered)
        self.assertTrue(all(row["status"] == "Accountant review" for row in rows.values()))
        self.assertFalse(any(
            row["row_kind"].startswith("entity-return-company-")
            for row in payload["items"] + payload["trust_items"] + payload["partnership_items"]
        ))

    def test_company_issue_131_missing_documents_and_loan_terms_fail_closed(self):
        cases = (
            (
                {
                    "name": "Paid Dividend Co",
                    "dividends_paid": {
                        "amount": 10,
                        "records": ["dividend-ledger.pdf"],
                    },
                },
                "entity-return-company-dividend-evidence",
                "dividend resolution",
            ),
            (
                {
                    "name": "Received Dividend Co",
                    "dividends_received": {
                        "amount": 10,
                        "records": ["general-ledger.pdf"],
                    },
                },
                "entity-return-company-dividend-evidence",
                "dividend statement",
            ),
            (
                {
                    "name": "Loan Terms Co",
                    "division_7a": {
                        "loan_amount": 10,
                        "complying_loan_agreement": True,
                        "repayment": 0,
                        "records": ["related-party-ledger.pdf"],
                    },
                },
                "entity-return-company-division-7a-evidence",
                "loan terms",
            ),
            (
                {
                    "name": "Unknown Direction Co",
                    "dividends": {
                        "amount": 0,
                        "paid": False,
                        "received": False,
                        "records": ["dividend-ledger.pdf"],
                    },
                },
                "entity-return-company-dividend-evidence",
                "dividend paid or received",
            ),
            (
                {
                    "name": "Incomplete Franking Co",
                    "franking_account": {
                        "deficit": False,
                        "records": ["franking-account.csv"],
                    },
                },
                "entity-return-company-franking-account-evidence",
                "franking account fact",
            ),
        )
        for company, row_kind, expected in cases:
            with self.subTest(company=company["name"]):
                payload = self.payload({"company_return": company})
                evidence = " ".join(
                    row["answer"]
                    for row in payload["evidence_items"]
                    if row["row_kind"] == row_kind
                )
                self.assertIn(expected, evidence)
                review_rows = [
                    row for row in payload["company_items"]
                    if row["row_kind"] == row_kind.removesuffix("-evidence")
                ]
                self.assertTrue(review_rows)
                self.assertTrue(all(row["status"] == "Accountant review" for row in review_rows))

    def test_company_issue_131_flat_synonyms_conflict_instead_of_overwriting(self):
        payload = self.payload({
            "company_return_name": "Synonym Conflict Co",
            "company_return_dividend_direction": "received",
            "company_return_dividend_franking_credit": 1,
            "company_return_dividend_franking_credits": 2,
            "company_return_dividend_statement": "statement.pdf",
            "company_return_dividend_records": ["statement.pdf"],
            "company_return_franking_opening_balance": 0,
            "company_return_franking_fdt": 3,
            "company_return_franking_fdt_payable": 4,
            "company_return_franking_records": ["franking.csv"],
        })
        evidence = " ".join(
            row["answer"]
            for row in payload["evidence_items"]
            if row["row_kind"] in {
                "entity-return-company-dividend-evidence",
                "entity-return-company-franking-account-evidence",
            }
        )
        self.assertIn("conflicting review aliases", evidence)

    def test_company_issue_131_direct_item_alias_conflicts_fail_closed(self):
        payload = self.payload({
            "company_return": {
                "name": "Direct Conflict Co",
                "dividends": {
                    "direction": "paid",
                    "dividend_direction": "received",
                    "amount": 1,
                    "dividend_amount": 2,
                    "resolution": "resolution.pdf",
                    "statement": "statement.pdf",
                    "records": ["dividend-ledger.pdf"],
                },
                "franking_account": {
                    "opening_balance": 0,
                    "franking_deficit_tax": 3,
                    "fdt": 4,
                    "records": ["franking.csv"],
                },
            },
        })
        evidence = " ".join(
            row["answer"]
            for row in payload["evidence_items"]
            if row["row_kind"] in {
                "entity-return-company-dividend-evidence",
                "entity-return-company-franking-account-evidence",
            }
        )
        self.assertIn("conflicting review aliases", evidence)

    def test_company_issue_131_direct_and_flat_collections_are_equivalent(self):
        nested = self.payload({
            "company_return": {
                "name": "Equivalent Co",
                "dividend_items": {
                    "direction": "paid",
                    "amount": 0,
                    "franked_amount": 0,
                    "franking_credit": 0,
                    "resolution": "resolution.pdf",
                    "evidence_status": "partial",
                    "records": ["dividend-ledger.pdf"],
                },
                "franking_account_items": {
                    "opening_balance": 0,
                    "credits": 0,
                    "franking_deficit_tax": 0,
                    "evidence_status": "partial",
                    "records": ["franking.csv"],
                },
                "division_7a_items": {
                    "transaction_type": "loan",
                    "shareholder_payment": 0,
                    "loan_amount": 0,
                    "repayments": 0,
                    "complying_loan_agreement": True,
                    "loan_terms": "written terms",
                    "benchmark_interest_rate": 8.77,
                    "minimum_yearly_repayment": 0,
                    "retained_profit": 0,
                    "evidence_status": "partial",
                    "records": ["ledger.pdf"],
                },
            },
        })
        flat = self.payload({
            "company_return_name": "Equivalent Co",
            "company_return_dividend_direction": "paid",
            "company_return_dividend_amount": 0,
            "company_return_dividend_franked_amount": 0,
            "company_return_dividend_franking_credit": 0,
            "company_return_dividend_resolution": "resolution.pdf",
            "company_return_dividend_evidence_status": "partial",
            "company_return_dividend_records": ["dividend-ledger.pdf"],
            "company_return_franking_opening_balance": 0,
            "company_return_franking_credits": 0,
            "company_return_franking_fdt": 0,
            "company_return_franking_evidence_status": "partial",
            "company_return_franking_records": ["franking.csv"],
            "company_return_division_7a_transaction_type": "loan",
            "company_return_division_7a_shareholder_payment": 0,
            "company_return_division_7a_loan_amount": 0,
            "company_return_division_7a_repayments": 0,
            "company_return_division_7a_complying_loan_agreement": True,
            "company_return_division_7a_loan_terms": "written terms",
            "company_return_division_7a_benchmark_rate": 8.77,
            "company_return_division_7a_minimum_repayment": 0,
            "company_return_division_7a_retained_profit": 0,
            "company_return_division_7a_evidence_status": "partial",
            "company_return_division_7a_records": ["ledger.pdf"],
        })

        def review_facts(payload):
            return {
                row["row_kind"]: {
                    fact["key"]: fact["value"]
                    for fact in row["facts"]
                    if not fact["key"].startswith("company_")
                }
                for row in payload["company_items"]
                if row["row_kind"] in {
                    "entity-return-company-dividend",
                    "entity-return-company-franking-account",
                    "entity-return-company-division-7a",
                }
            }

        self.assertEqual(review_facts(nested), review_facts(flat))

    def test_out_of_scope_entity_worksheet_fields_are_preserved_as_unsupported(self):
        payload = self.payload({
            "company_return": {
                "name": "Capital Co",
                "capital_allowance_items": [{"asset": "Server", "amount": 10}],
            },
            "trust_return": {
                "name": "No Worksheet Trust",
                "income_items": [self.income_item()],
            },
        })
        unsupported = [
            row for row in payload["evidence_items"]
            if row["row_kind"] in {"entity-return-company-unsupported", "entity-return-trust-unsupported"}
        ]
        self.assertEqual(1, len(unsupported))
        self.assertIn("income_items", json.dumps(unsupported))
        self.assertTrue(any(
            row["row_kind"] == "entity-return-company-capital-allowance"
            for row in payload["company_items"]
        ))

    def test_trust_cgt_franking_streaming_and_allocations_stay_review_only(self):
        checked_at = "2026-07-17T10:00:00Z"
        source_url = "https://example.invalid/trust-workpaper"
        payload = self.payload({
            "trust_return": {
                "name": "Review Trust",
                "capital_gain_items": [{
                    "asset": "Synthetic shares",
                    "amount": 0,
                    "proceeds": 0,
                    "cost_base": 0,
                    "discount_eligible": False,
                    "discount_applied": False,
                    "records": ["cgt-register.csv"],
                    "source_url": source_url,
                    "checked_at": checked_at,
                }],
                "franked_distribution_items": [{
                    "payer": "Synthetic Co",
                    "amount": 0,
                    "franked_amount": 0,
                    "unfranked_amount": 0,
                    "franking_credit": 0,
                    "statement": "distribution-statement.pdf",
                    "records": ["distribution-statement.pdf"],
                    "source_url": source_url,
                    "checked_at": checked_at,
                }],
                "streaming_review": {
                    "streaming": False,
                    "deed_allows_streaming": False,
                    "specific_entitlement": False,
                    "recorded_in_character": False,
                    "resolution": "trustee-resolution.pdf",
                    "records": ["trustee-resolution.pdf", "trust-deed.pdf"],
                    "source_url": source_url,
                    "checked_at": checked_at,
                },
                "beneficiary_component_allocations": [{
                    "beneficiary_name": "Synthetic Beneficiary",
                    "component_type": "capital gain and franked distribution",
                    "beneficiary_capital_gain": 0,
                    "beneficiary_discounted_capital_gain": 0,
                    "beneficiary_franked_distribution": 0,
                    "beneficiary_franking_credits": 0,
                    "allocation_percentage": 0,
                    "allocation_basis": "trustee resolution",
                    "allocation_resolution": "trustee-resolution.pdf",
                    "records": ["beneficiary-ledger.csv"],
                    "source_url": source_url,
                    "checked_at": checked_at,
                }],
            },
        })
        rows = {
            row["row_kind"]: row for row in payload["trust_items"]
            if row["row_kind"].startswith("entity-return-trust-")
            and row["row_kind"] != "entity-return-trust"
        }
        expected = {
            "entity-return-trust-capital-gain",
            "entity-return-trust-franked-distribution",
            "entity-return-trust-streaming",
            "entity-return-trust-beneficiary-allocation",
        }
        self.assertEqual(expected, set(rows))
        rendered = json.dumps(rows)
        for value in (
            "amount 0", "proceeds 0", "cost base 0", "discount eligible false",
            "discount applied false", "franked amount 0", "unfranked amount 0",
            "franking credit 0", "streaming false", "specific entitlement false",
            "recorded in character false", "beneficiary capital gain 0",
            "beneficiary franking credits 0", "allocation percentage 0",
        ):
            self.assertIn(value, rendered)
        self.assertTrue(all(row["status"] == "Accountant review" for row in rows.values()))
        self.assertTrue(all(row["checked_at"] == checked_at for row in rows.values()))
        self.assertTrue(all(source_url in row["source_urls"] for row in rows.values()))
        self.assertTrue(all(
            taxmate_entity_worksheet.TRUST_STREAMING_SOURCE in row["source_urls"]
            for row in rows.values()
        ))
        self.assertFalse(any(
            row["row_kind"] in expected
            for row in payload["items"] + payload["company_items"] + payload["partnership_items"]
        ))

    def test_trust_unknown_amounts_missing_resolution_and_bad_allocations_fail_closed(self):
        payload = self.payload({
            "trust_return": {
                "name": "Incomplete Trust",
                "capital_gains": {
                    "description": "Unknown disposal",
                    "amount": "unknown",
                    "records": ["asset-list.csv"],
                },
                "franked_distributions": {
                    "amount": "bad",
                    "franking_credit": "unknown",
                    "records": ["general-ledger.csv"],
                },
                "beneficiary_allocations": {
                    "beneficiary_name": "Synthetic Beneficiary",
                    "component_type": "capital gain",
                    "component_amount": 10,
                    "allocation_percentage": 125,
                    "records": ["beneficiary-ledger.csv"],
                },
            },
        })
        evidence = {
            row["row_kind"]: row
            for row in payload["evidence_items"]
            if row["row_kind"].startswith("entity-return-trust-")
        }
        self.assertIn("finite component amount", evidence["entity-return-trust-capital-gain-evidence"]["answer"])
        self.assertIn("CGT discount signal", evidence["entity-return-trust-capital-gain-evidence"]["answer"])
        self.assertIn("streaming resolution evidence", evidence["entity-return-trust-capital-gain-evidence"]["answer"])
        self.assertIn("franking credit amount", evidence["entity-return-trust-franked-distribution-evidence"]["answer"])
        self.assertIn("franked distribution statement", evidence["entity-return-trust-franked-distribution-evidence"]["answer"])
        self.assertIn("supported allocation percentage", evidence["entity-return-trust-beneficiary-allocation-evidence"]["answer"])
        self.assertIn("allocation basis", evidence["entity-return-trust-beneficiary-allocation-evidence"]["answer"])
        self.assertTrue(all(
            evidence[row_kind]["status"] == "Accountant review"
            for row_kind in (
                "entity-return-trust-capital-gain-evidence",
                "entity-return-trust-franked-distribution-evidence",
                "entity-return-trust-beneficiary-allocation-evidence",
            )
        ))

    def test_trust_flat_review_fields_preserve_falsey_values_and_provenance_gaps(self):
        payload = self.payload({
            "trust_return_name": "Flat Trust",
            "trust_return_capital_gain_asset": "Synthetic asset",
            "trust_return_capital_gain_amount": 0,
            "trust_return_capital_gain_discount_eligible": False,
            "trust_return_capital_gain_records": ["cgt.csv"],
            "trust_return_franked_distribution_amount": 0,
            "trust_return_franked_amount": 0,
            "trust_return_franking_credits": 0,
            "trust_return_franked_distribution_statement": "statement.pdf",
            "trust_return_franked_distribution_records": ["statement.pdf"],
            "trust_return_streaming": False,
            "trust_return_deed_allows_streaming": False,
            "trust_return_specific_entitlement": False,
            "trust_return_recorded_in_character": False,
            "trust_return_streaming_resolution": "resolution.pdf",
            "trust_return_streaming_records": ["resolution.pdf"],
            "trust_return_source_urls": ["bad source", "https://example.invalid/trust"],
            "trust_return_checked_at": "bad date",
        })
        rows = [
            row for row in payload["trust_items"]
            if row["row_kind"] in {
                "entity-return-trust-capital-gain",
                "entity-return-trust-franked-distribution",
                "entity-return-trust-streaming",
            }
        ]
        self.assertEqual(3, len(rows))
        rendered = json.dumps(rows)
        self.assertIn("amount 0", rendered)
        self.assertIn("discount eligible false", rendered)
        self.assertIn("franking credit 0", rendered)
        self.assertIn("streaming false", rendered)
        evidence = " ".join(
            row["answer"] for row in payload["evidence_items"]
            if row["row_kind"].startswith("entity-return-trust-")
        )
        self.assertIn("source provenance", evidence)
        self.assertIn("checked-at provenance", evidence)
        self.assertNotIn("bad source", json.dumps(rows))

    def test_trust_flat_and_nested_conflicts_fail_closed_and_streaming_evidence_normalizes(self):
        payload = self.payload({
            "trust_return": {
                "name": "Conflict Trust",
                "capital_gain_items": {
                    "asset": "Synthetic asset",
                    "amount": 1,
                    "discount_eligible": False,
                    "records": ["cgt.csv"],
                },
            },
            "trust_return_capital_gain_amount": 2,
            "trust_return_streaming": False,
            "trust_return_deed_allows_streaming": False,
            "trust_return_specific_entitlement": False,
            "trust_return_recorded_in_character": False,
            "trust_return_streaming_resolution": "resolution.pdf",
            "trust_return_streaming_evidence": ["resolution.pdf"],
        })
        conflict = next(
            row for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-trust-capital-gain-evidence"
        )
        streaming = next(
            row for row in payload["trust_items"]
            if row["row_kind"] == "entity-return-trust-streaming"
        )
        streaming_evidence = [
            row for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-trust-streaming-evidence"
        ]
        self.assertIn("conflicting review aliases", conflict["answer"])
        self.assertIn('evidence ["resolution.pdf"]', streaming["answer"])
        self.assertFalse(any("Confirm evidence" in row["answer"] for row in streaming_evidence))
        self.assertFalse(any("worksheet" in row["ato_area"].lower() for row in payload["trust_items"]))

    def test_entity_review_conflict_merges_never_create_circular_payloads(self):
        cases = (
            (
                {
                    "company_return": {
                        "name": "Conflict Company",
                        "dividends": {
                            "direction": "received", "amount": 1,
                            "franking_credit": 1, "records": ["ledger.csv"],
                        },
                    },
                    "company_return_dividend_franking_credit": 2,
                    "company_return_dividend_franking_credits": 3,
                },
                "entity-return-company-dividend-evidence",
            ),
            (
                {
                    "trust_return": {
                        "name": "Conflict Trust",
                        "franked_distribution_items": {
                            "payer": "Synthetic Co", "amount": 1,
                            "franking_credit": 1, "records": ["ledger.csv"],
                        },
                    },
                    "trust_return_franking_credit": 2,
                    "trust_return_franking_credits": 3,
                },
                "entity-return-trust-franked-distribution-evidence",
            ),
            (
                {
                    "partnership_return": {
                        "name": "Conflict Partnership",
                        "loss_items": {
                            "category": "loss", "description": "same loss",
                            "current_year_loss": 1, "records": ["first.csv"],
                        },
                        "losses": {
                            "category": "loss", "description": "same loss",
                            "current_year_loss": 2, "records": ["second.csv"],
                        },
                    },
                    "partnership_return_current_year_loss": 3,
                },
                "entity-return-partnership-loss-evidence",
            ),
        )
        for answers, row_kind in cases:
            with self.subTest(row_kind=row_kind):
                payload = self.payload(answers)
                json.dumps(payload)
                evidence = next(
                    row for row in payload["evidence_items"]
                    if row["row_kind"] == row_kind
                )
                self.assertIn("conflicting review aliases", evidence["answer"])

    def test_trust_direct_item_alias_conflicts_fail_closed(self):
        cases = (
            (
                "capital_gain_items",
                {
                    "asset": "Synthetic asset", "amount": 1,
                    "capital_gain_amount": 2, "discount_eligible": False,
                    "resolution": "resolution.pdf", "records": ["cgt.csv"],
                },
                "entity-return-trust-capital-gain-evidence",
            ),
            (
                "franked_distribution_items",
                {
                    "payer": "Synthetic Co", "amount": 1,
                    "franking_credit": 1, "franking_credits": 2,
                    "statement": "statement.pdf", "resolution": "resolution.pdf",
                    "records": ["statement.pdf"],
                },
                "entity-return-trust-franked-distribution-evidence",
            ),
            (
                "streaming_review",
                {
                    "streaming": False, "streaming_applied": True,
                    "deed_allows_streaming": False, "resolution": "resolution.pdf",
                    "records": ["resolution.pdf"],
                },
                "entity-return-trust-streaming-evidence",
            ),
            (
                "beneficiary_allocations",
                {
                    "beneficiary_name": "Synthetic Beneficiary",
                    "component_type": "capital gain", "component_amount": 1,
                    "allocation": 1, "beneficiary_allocation": 2,
                    "allocation_percentage": 50, "allocation_basis": "percentage",
                    "allocation_resolution": "resolution.pdf",
                    "records": ["beneficiary.csv"],
                },
                "entity-return-trust-beneficiary-allocation-evidence",
            ),
        )
        for collection, item, row_kind in cases:
            with self.subTest(collection=collection):
                payload = self.payload({
                    "trust_return": {"name": "Direct Conflict Trust", collection: item},
                })
                evidence = next(
                    row for row in payload["evidence_items"]
                    if row["row_kind"] == row_kind
                )
                self.assertIn("conflicting review aliases", evidence["answer"])

    def test_trust_allocation_percentage_strings_use_percentage_semantics(self):
        for percentage, supported in (
            ("0%", True), ("50%", True), ("100%", True),
            ("-1%", False), ("101%", False), ("bad", False),
        ):
            with self.subTest(percentage=percentage):
                payload = self.payload({
                    "trust_return": {
                        "name": "Percentage Trust",
                        "beneficiary_allocations": {
                            "beneficiary_name": "Synthetic Beneficiary",
                            "component_type": "capital gain", "component_amount": 1,
                            "allocation_percentage": percentage,
                            "allocation_basis": "percentage",
                            "allocation_resolution": "resolution.pdf",
                            "records": ["beneficiary.csv"],
                        },
                    },
                })
                evidence = " ".join(
                    row["answer"] for row in payload["evidence_items"]
                    if row["row_kind"]
                    == "entity-return-trust-beneficiary-allocation-evidence"
                )
                self.assertEqual(
                    supported,
                    "supported allocation percentage" not in evidence,
                )

    def test_numeric_equivalent_review_aliases_do_not_create_false_conflicts(self):
        cases = (
            {
                "company_return_name": "Equivalent Company",
                "company_return_dividend_direction": "received",
                "company_return_dividend_franking_credit": 1,
                "company_return_dividend_franking_credits": "1.00",
                "company_return_dividend_statement": "statement.pdf",
                "company_return_dividend_records": ["statement.pdf"],
            },
            {
                "trust_return_name": "Equivalent Trust",
                "trust_return_franked_distribution_amount": 1,
                "trust_return_franking_credit": 1,
                "trust_return_franking_credits": "1.00",
                "trust_return_franked_distribution_statement": "statement.pdf",
                "trust_return_franked_distribution_records": ["statement.pdf"],
                "trust_return_streaming_resolution": "resolution.pdf",
            },
        )
        for answers in cases:
            name = next(value for key, value in answers.items() if key.endswith("_name"))
            with self.subTest(name=name):
                payload = self.payload(answers)
                evidence = " ".join(row["answer"] for row in payload["evidence_items"])
                self.assertNotIn("conflicting review aliases", evidence)

    def test_percent_alias_equivalence_is_limited_to_percentage_fields(self):
        conflict = self.payload({
            "trust_return_name": "Amount Percent Trust",
            "trust_return_franked_distribution_amount": 1,
            "trust_return_franking_credit": 1,
            "trust_return_franking_credits": "1%",
            "trust_return_franked_distribution_statement": "statement.pdf",
            "trust_return_franked_distribution_records": ["statement.pdf"],
            "trust_return_streaming_resolution": "resolution.pdf",
        })
        equivalent = self.payload({
            "trust_return": {
                "name": "Percentage Alias Trust",
                "beneficiary_allocations": {
                    "beneficiary_name": "Synthetic Beneficiary",
                    "component_type": "capital gain", "component_amount": 1,
                    "allocation_percentage": 50,
                    "beneficiary_allocation_percentage": "50%",
                    "allocation_basis": "percentage",
                    "allocation_resolution": "resolution.pdf",
                    "records": ["beneficiary.csv"],
                },
            },
        })
        conflict_evidence = " ".join(
            row["answer"] for row in conflict["evidence_items"]
        )
        equivalent_evidence = " ".join(
            row["answer"] for row in equivalent["evidence_items"]
        )
        self.assertIn("conflicting review aliases", conflict_evidence)
        self.assertNotIn("conflicting review aliases", equivalent_evidence)

    def test_claimed_trust_streaming_requires_ato_specific_entitlement_facts(self):
        incomplete = self.payload({
            "trust_return": {
                "name": "Incomplete Streaming Trust",
                "deed_evidence": False,
                "streaming_review": {
                    "streaming": True,
                    "specific_entitlement": True,
                    "deed_allows_streaming": False,
                    "recorded_in_character": False,
                    "resolution": "resolution.pdf",
                    "resolution_date": "not-a-date",
                    "records": ["resolution.pdf"],
                },
            },
        })
        answer = next(
            row["answer"] for row in incomplete["evidence_items"]
            if row["row_kind"] == "entity-return-trust-streaming-evidence"
        )
        for gap in (
            "trust deed streaming power", "trust deed evidence", "streamed component type",
            "financial benefit received or expected",
            "financial benefit referable to component",
            "specific-entitlement recording condition",
            "specific-entitlement recording date",
        ):
            self.assertIn(gap, answer)

        complete = self.payload({
            "trust_return": {
                "name": "Supported Streaming Review Trust",
                "deed_evidence": "trust-deed.pdf",
                "streaming_review": {
                    "streaming": True,
                    "specific_entitlement": True,
                    "deed_allows_streaming": True,
                    "component_type": "capital gain",
                    "financial_benefit_expected": True,
                    "benefit_referable_to_component": True,
                    "recorded_in_character": True,
                    "resolution": "resolution.pdf",
                    "recording_date": "2026-06-30",
                    "records": ["resolution.pdf"],
                },
            },
        })
        complete_evidence = " ".join(
            row["answer"] for row in complete["evidence_items"]
            if row["row_kind"] == "entity-return-trust-streaming-evidence"
        )
        for gap in (
            "trust deed streaming power", "trust deed evidence", "streamed component type",
            "financial benefit received or expected",
            "financial benefit referable to component",
            "specific-entitlement recording condition",
            "specific-entitlement recording date",
        ):
            self.assertNotIn(gap, complete_evidence)

        flat = self.payload({
            "trust_return_name": "Flat Supported Streaming Review Trust",
            "trust_return_deed_evidence": "trust-deed.pdf",
            "trust_return_streaming": True,
            "trust_return_specific_entitlement": True,
            "trust_return_deed_allows_streaming": True,
            "trust_return_component_type": "franked distribution",
            "trust_return_financial_benefit_received": True,
            "trust_return_benefit_referable_to_component": True,
            "trust_return_recorded_in_character": True,
            "trust_return_resolution": "resolution.pdf",
            "trust_return_resolution_date": "2026-06-30",
            "trust_return_streaming_records": ["resolution.pdf"],
        })
        flat_evidence = " ".join(
            row["answer"] for row in flat["evidence_items"]
            if row["row_kind"] == "entity-return-trust-streaming-evidence"
        )
        self.assertNotIn("streaming resolution evidence", flat_evidence)
        self.assertNotIn("specific-entitlement", flat_evidence)

    def test_positive_trust_franking_requires_integrity_review_facts(self):
        cases = (
            (
                "franked_distribution_items",
                {
                    "amount": 10, "franking_credit": 3,
                    "statement": "statement.pdf", "records": ["statement.pdf"],
                    "resolution": "resolution.pdf",
                },
                "entity-return-trust-franked-distribution-evidence",
                "trust_qualified_person",
            ),
            (
                "beneficiary_allocations",
                {
                    "beneficiary_name": "Synthetic Beneficiary",
                    "component_type": "franked distribution",
                    "beneficiary_franked_distribution": 10,
                    "beneficiary_franking_credits": 3,
                    "allocation_percentage": 100,
                    "allocation_basis": "percentage",
                    "allocation_resolution": "resolution.pdf",
                    "records": ["beneficiary.csv"],
                },
                "entity-return-trust-beneficiary-allocation-evidence",
                "beneficiary_qualified_person",
            ),
        )
        for collection, item, row_kind, integrity_field in cases:
            with self.subTest(collection=collection):
                missing = self.payload({
                    "trust_return": {"name": "Franking Review Trust", collection: item},
                })
                missing_answer = next(
                    row["answer"] for row in missing["evidence_items"]
                    if row["row_kind"] == row_kind
                )
                self.assertIn("franking credit integrity review", missing_answer)

                supplied_item = dict(item)
                supplied_item[integrity_field] = False
                supplied = self.payload({
                    "trust_return": {"name": "Franking Review Trust", collection: supplied_item},
                })
                supplied_answer = " ".join(
                    row["answer"] for row in supplied["evidence_items"]
                    if row["row_kind"] == row_kind
                )
                self.assertNotIn("franking credit integrity review", supplied_answer)

    def test_company_losses_assets_and_allowances_are_isolated_review_rows(self):
        payload = self.payload({
            "company_return": {
                "name": "Review Assets Co",
                "loss_items": [{
                    "income_year": "2024-25",
                    "prior_year_loss": 0,
                    "carried_forward_loss": 1250,
                    "records": ["loss-schedule.pdf"],
                }],
                "loss_continuity": {
                    "continuity_of_ownership": False,
                    "business_continuity": "unclear",
                    "control_change": False,
                    "evidence": ["share-register.pdf"],
                },
                "asset_items": [{
                    "asset": "Server",
                    "cost": 0,
                    "mixed_use": False,
                    "instant_asset_write_off": False,
                    "evidence": ["invoice.pdf"],
                }],
                "asset_pools": [{
                    "pool_type": "general small business pool",
                    "opening_value": 0,
                    "additions": 500,
                    "closing_value": 500,
                    "records": ["pool-register.csv"],
                }],
                "depreciation_items": [{
                    "asset": "Server",
                    "deduction_amount": 0,
                    "method": "decline in value supplied",
                    "evidence": ["asset-register.csv"],
                }],
                "capital_allowance_items": [{
                    "category": "software pool",
                    "adjustable_value": 0,
                    "method": "supplied method",
                    "evidence": ["capital-allowances.csv"],
                }],
            },
        })
        kinds = {
            row["row_kind"] for row in payload["company_items"]
            if row["row_kind"].startswith("entity-return-company-")
        }
        self.assertTrue({
            "entity-return-company-loss",
            "entity-return-company-loss-continuity",
            "entity-return-company-asset",
            "entity-return-company-asset-pool",
            "entity-return-company-depreciation",
            "entity-return-company-capital-allowance",
        }.issubset(kinds))
        rendered = json.dumps(payload["company_items"])
        self.assertIn("prior year loss 0", rendered)
        self.assertIn("continuity of ownership false", rendered)
        self.assertIn("instant asset write off false", rendered)
        self.assertTrue(all(row["status"] == "Accountant review" for row in payload["company_items"]))
        self.assertFalse(any(
            row["row_kind"].startswith("entity-return-company-")
            for row in payload["items"] + payload["partnership_items"]
        ))
        self.assertFalse(any(
            row["row_kind"] == "entity-return-company-unsupported"
            and "capital_allowance_items" in row["answer"]
            for row in payload["evidence_items"]
        ))

    def test_company_review_rows_fail_closed_without_amount_method_records_or_provenance(self):
        payload = self.payload({
            "company_return": {
                "name": "Incomplete Assets Co",
                "losses": [{"prior_year_loss": "unknown", "records": False}],
                "ownership_continuity": {"notes": "unknown", "evidence": False},
                "depreciation_items": [{
                    "asset": "Vehicle",
                    "deduction_amount": "NaN",
                    "method": "unknown",
                    "mixed_use": "unknown",
                    "source_urls": ["bad source"],
                    "checked_at": "bad date",
                }],
                "capital_allowance_items": [],
            },
        })
        evidence = [
            row for row in payload["evidence_items"]
            if row["row_kind"].startswith("entity-return-company-")
        ]
        rendered = " ".join(row["answer"] for row in evidence)
        for expected in (
            "finite monetary fact", "evidence", "ownership or business continuity signal",
            "method", "source provenance", "checked-at provenance", "capital allowance facts",
        ):
            self.assertIn(expected, rendered)
        self.assertTrue(any(row["status"] == "Accountant review" for row in evidence))
        expected_sources = {
            "entity-return-company-loss-evidence": taxmate_entity_worksheet.COMPANY_LOSSES_SOURCE,
            "entity-return-company-loss-continuity-evidence": taxmate_entity_worksheet.COMPANY_LOSSES_SOURCE,
            "entity-return-company-depreciation-evidence": taxmate_entity_worksheet.COMPANY_CAPITAL_ALLOWANCES_SOURCE,
            "entity-return-company-capital-allowance-evidence": taxmate_entity_worksheet.COMPANY_CAPITAL_ALLOWANCES_SOURCE,
        }
        for row_kind, source in expected_sources.items():
            with self.subTest(row_kind=row_kind):
                row = next(item for item in evidence if item["row_kind"] == row_kind)
                self.assertIn(source, row["source_urls"])
                self.assertNotIn(taxmate_entity_worksheet.COMPANY_DEDUCTION_SOURCE, row["source_urls"])

    def test_flat_company_review_aliases_keep_parent_association(self):
        payload = self.payload({
            "company_return": [{"name": "First Co"}, {"name": "Loss Co", "abn": "22"}],
            "company_return_entity_name": "Loss Co",
            "company_return_loss_items": [{
                "current_year_loss": 0,
                "evidence": ["accounts.pdf"],
            }],
        })
        row = next(row for row in payload["company_items"] if row["row_kind"] == "entity-return-company-loss")
        self.assertIn("company name Loss Co", row["answer"])
        self.assertFalse(any(
            "parent entity" in item["answer"]
            for item in payload["evidence_items"]
            if item["row_kind"] == "entity-return-company-loss-evidence"
        ))

    def test_scalar_company_review_aliases_preserve_numeric_and_false_facts(self):
        payload = self.payload({
            "company_return": {"name": "Scalar Facts Co"},
            "company_return_losses": 1250,
            "company_return_ownership_continuity": False,
            "company_return_depreciating_assets": "Server",
        })
        rows = {row["row_kind"]: row for row in payload["company_items"]}
        self.assertIn("amount 1250", rows["entity-return-company-loss"]["answer"])
        self.assertIn(
            "continuity of ownership false",
            rows["entity-return-company-loss-continuity"]["answer"],
        )
        self.assertIn("asset Server", rows["entity-return-company-asset"]["answer"])
        evidence = json.dumps(payload["evidence_items"])
        self.assertIn("entity-return-company-loss-evidence", evidence)
        self.assertIn("entity-return-company-loss-continuity-evidence", evidence)

    def test_partnership_loss_gst_bas_psi_structure_rows_are_isolated(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Review Partners",
                "loss_items": [{
                    "current_year_loss": 0,
                    "records": ["accounts.pdf"],
                }],
                "loss_allocations": [{
                    "allocation_percentages": {"Partner A": 60, "Partner B": 40},
                    "evidence": ["agreement.pdf"],
                }],
                "gst_bas_review": {
                    "gst_registered": False,
                    "bas_period": "quarterly",
                    "bas_overlap": False,
                    "records": ["bas-workpaper.pdf"],
                },
                "psi_review": {
                    "psi": False,
                    "income_amount": 0,
                    "evidence": ["contracts.pdf"],
                },
                "business_structure_review": {
                    "business_structure": "partnership",
                    "structure_indicator": False,
                    "evidence": ["agreement.pdf"],
                },
            },
        })
        rows = {
            row["row_kind"]: row for row in payload["partnership_items"]
            if row["row_kind"].startswith("entity-return-partnership-")
        }
        expected = {
            "entity-return-partnership-loss",
            "entity-return-partnership-loss-allocation",
            "entity-return-partnership-gst-bas",
            "entity-return-partnership-psi",
            "entity-return-partnership-business-structure",
        }
        self.assertTrue(expected.issubset(rows))
        rendered = json.dumps(list(rows.values()))
        self.assertIn("current year loss 0", rendered)
        self.assertIn("gst registered false", rendered)
        self.assertIn("psi false", rendered)
        self.assertIn("structure indicator false", rendered)
        self.assertTrue(all(rows[kind]["status"] == "Accountant review" for kind in expected))
        self.assertFalse(any(
            row["row_kind"] in expected for row in payload["items"] + payload["company_items"]
        ))

    def test_partnership_review_gaps_fail_closed_with_narrow_sources(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Incomplete Partners",
                "losses": {"amount": "unknown", "records": False},
                "loss_allocation": [
                    {"partner": "Partner A", "allocation_percentage": 60, "evidence": False},
                    {"partner": "Partner B", "allocation_percentage": 50, "evidence": False},
                ],
                "gst_bas_details": {"gst_registered": "unknown", "bas_overlap": True},
                "psi_details": {"psi": "unknown", "source_urls": ["bad source"]},
                "structure_indicators": {},
            },
        })
        evidence = [
            row for row in payload["evidence_items"]
            if row["row_kind"].startswith("entity-return-partnership-")
        ]
        rendered = " ".join(row["answer"] for row in evidence)
        for expected in (
            "finite partnership loss amount", "conflicting loss allocation", "evidence",
            "BAS reporting period", "BAS overlap review", "PSI uncertainty",
            "source provenance", "business structure facts",
        ):
            self.assertIn(expected, rendered)
        sources = {row["row_kind"]: row["source_urls"] for row in evidence}
        self.assertIn(
            taxmate_entity_worksheet.PARTNERSHIP_LOSSES_SOURCE,
            sources["entity-return-partnership-loss-evidence"],
        )
        self.assertIn(
            taxmate_entity_worksheet.PARTNERSHIP_BAS_SOURCE,
            sources["entity-return-partnership-gst-bas-evidence"],
        )
        self.assertIn(
            taxmate_entity_worksheet.PARTNERSHIP_PSI_SOURCE,
            sources["entity-return-partnership-psi-evidence"],
        )

    def test_flat_scalar_partnership_review_aliases_preserve_falsey_facts(self):
        payload = self.payload({
            "partnership_return": {"name": "Scalar Partners"},
            "partnership_return_losses": 0,
            "partnership_return_gst_bas_review": False,
            "partnership_return_personal_services_income": False,
            "partnership_return_business_structure": "partnership",
        })
        rendered = json.dumps(payload["partnership_items"])
        self.assertIn("amount 0", rendered)
        self.assertIn("bas overlap false", rendered)
        self.assertIn("personal services income false", rendered)
        self.assertIn("business structure partnership", rendered)
        self.assertEqual(1, sum(
            row["row_kind"] == "entity-return-partnership-gst-bas"
            for row in payload["partnership_items"]
        ))

    def test_documented_flat_partnership_review_fields_are_grouped(self):
        payload = self.payload({
            "partnership_return": {"name": "Flat Review Partners"},
            "partnership_return_current_year_loss": 0,
            "partnership_return_loss_records": ["accounts.pdf"],
            "partnership_return_gst_registered": False,
            "partnership_return_bas_period": "quarterly",
            "partnership_return_bas_overlap": True,
            "partnership_return_gst_bas_records": ["bas.pdf"],
            "partnership_return_psi": False,
            "partnership_return_psi_evidence": ["contracts.pdf"],
            "partnership_return_business_structure": "partnership",
            "partnership_return_business_structure_records": ["agreement.pdf"],
            "partnership_return_source_url": "https://www.ato.gov.au/example-review",
            "partnership_return_checked_at": "2026-07-15T10:00:00Z",
        })
        rows = {row["row_kind"]: row for row in payload["partnership_items"]}
        gst = rows["entity-return-partnership-gst-bas"]
        self.assertEqual(1, sum(
            row["row_kind"] == "entity-return-partnership-gst-bas"
            for row in payload["partnership_items"]
        ))
        self.assertIn("gst registered false", gst["answer"])
        self.assertIn("bas period quarterly", gst["answer"])
        self.assertIn("bas overlap true", gst["answer"])
        self.assertIn("https://www.ato.gov.au/example-review", gst["source_urls"])
        self.assertEqual("2026-07-15T10:00:00Z", gst["checked_at"])
        self.assertIn("psi false", rows["entity-return-partnership-psi"]["answer"])
        self.assertIn(
            "business structure partnership",
            rows["entity-return-partnership-business-structure"]["answer"],
        )
        self.assertIn("current year loss 0", rows["entity-return-partnership-loss"]["answer"])
        unsupported = " ".join(
            row["answer"] for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-partnership-unsupported"
        )
        for field in ("gst_registered", "bas_period", "bas_overlap", "psi", "business_structure"):
            self.assertNotIn(field, unsupported)

    def test_flat_allocation_percentage_maps_are_grouped(self):
        for field in ("allocation_percentages", "partner_percentages", "share_percentages"):
            for percentages in (
                {"Partner A": 60, "Partner B": 40},
                {"Partner A": "60%", "Partner B": "40%"},
            ):
                with self.subTest(field=field, percentages=percentages):
                    payload = self.payload({
                        "partnership_return": {"name": "Flat Allocation Partners"},
                        f"partnership_return_{field}": percentages,
                        "partnership_return_loss_allocation_records": ["agreement.pdf"],
                    })
                    allocation = next(
                        row for row in payload["partnership_items"]
                        if row["row_kind"] == "entity-return-partnership-loss-allocation"
                    )
                    self.assertIn(field.replace("_", " "), allocation["answer"])
                    unsupported = " ".join(
                        row["answer"] for row in payload["evidence_items"]
                        if row["row_kind"] == "entity-return-partnership-unsupported"
                    )
                    self.assertNotIn(field, unsupported)
                    self.assertFalse(any(
                        row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                        for row in payload["evidence_items"]
                    ))

    def test_core_share_map_does_not_create_loss_allocation_review(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Ordinary Partners",
                "share_percentages": {"Partner A": 60, "Partner B": 40},
            },
        })
        self.assertFalse(any(
            row["row_kind"] == "entity-return-partnership-loss-allocation"
            for row in payload["partnership_items"]
        ))
        partnership_gaps = " ".join(
            row["answer"] for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-partnership-evidence"
        )
        self.assertNotIn("partner share percentages", partnership_gaps)

    def test_share_percentage_list_joins_real_allocation_context(self):
        payload = self.payload({
            "partnership_return": {"name": "Share List Partners"},
            "partnership_return_share_percentages": [60, 40],
            "partnership_return_loss_allocation_records": ["agreement.pdf"],
        })
        allocation = next(
            row for row in payload["partnership_items"]
            if row["row_kind"] == "entity-return-partnership-loss-allocation"
        )
        self.assertIn("share percentages [60, 40]", allocation["answer"])
        self.assertFalse(any(
            row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
            for row in payload["evidence_items"]
        ))

    def test_nested_overlapping_review_aliases_preserve_objects(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Nested Alias Partners",
                "personal_services_income": {
                    "psi": False,
                    "evidence": ["contracts.pdf"],
                },
                "business_structure": {
                    "structure": "partnership",
                    "evidence": ["agreement.pdf"],
                },
            },
        })
        rows = {row["row_kind"]: row for row in payload["partnership_items"]}
        self.assertIn("psi false", rows["entity-return-partnership-psi"]["answer"])
        self.assertIn(
            "structure partnership",
            rows["entity-return-partnership-business-structure"]["answer"],
        )
        self.assertFalse(any(
            row["row_kind"] in {
                "entity-return-partnership-psi-evidence",
                "entity-return-partnership-business-structure-evidence",
            }
            for row in payload["evidence_items"]
        ))

    def test_review_alias_conflicts_queue_every_partnership_section(self):
        cases = (
            (
                "loss_items", {"current_year_loss": 0, "records": ["accounts.pdf"]},
                "current_year_loss", 100,
                "entity-return-partnership-loss-evidence",
            ),
            (
                "gst_bas_review", {
                    "gst_registered": False, "bas_period": "quarterly",
                    "bas_overlap": False, "records": ["bas.pdf"],
                },
                "gst_registered", True,
                "entity-return-partnership-gst-bas-evidence",
            ),
            (
                "psi_review", {"psi": False, "evidence": ["contracts.pdf"]},
                "psi", True,
                "entity-return-partnership-psi-evidence",
            ),
            (
                "business_structure_review", {
                    "business_structure": "partnership", "evidence": ["agreement.pdf"],
                },
                "business_structure", "company",
                "entity-return-partnership-business-structure-evidence",
            ),
        )
        for collection, nested, flat_field, flat_value, row_kind in cases:
            with self.subTest(collection=collection):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Conflicting Alias Partners",
                        collection: nested,
                    },
                    f"partnership_return_{flat_field}": flat_value,
                })
                evidence = next(
                    row for row in payload["evidence_items"]
                    if row["row_kind"] == row_kind
                )
                self.assertIn("conflicting review aliases", evidence["answer"])

    def test_bare_loss_allocation_alias_maps_reconcile_as_amounts(self):
        for alias in ("loss_allocations", "partner_loss_allocations"):
            with self.subTest(alias=alias):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Bare Map Partners",
                        alias: {"Partner A": 600, "Partner B": 400},
                    },
                    "partnership_return_current_year_loss": 1000,
                    "partnership_return_loss_allocation_records": ["agreement.pdf"],
                })
                allocation = next(
                    row for row in payload["partnership_items"]
                    if row["row_kind"] == "entity-return-partnership-loss-allocation"
                )
                self.assertIn("allocation", allocation["answer"])
                self.assertFalse(any(
                    row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                    for row in payload["evidence_items"]
                ))

    def test_bare_loss_allocation_map_without_metadata_is_normalized(self):
        for alias in ("loss_allocations", "partner_loss_allocations"):
            with self.subTest(alias=alias):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Bare Only Partners",
                        alias: {"Partner A": 600, "Partner B": 400},
                    },
                })
                allocation = next(
                    row for row in payload["partnership_items"]
                    if row["row_kind"] == "entity-return-partnership-loss-allocation"
                )
                self.assertIn('allocation {"Partner A": 600, "Partner B": 400}', allocation["answer"])
                evidence = " ".join(
                    row["answer"] for row in payload["evidence_items"]
                    if row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                )
                self.assertNotIn("Confirm loss allocation;", evidence)
                self.assertIn("loss amount for allocation reconciliation", evidence)
                self.assertIn("evidence", evidence)

    def test_partner_identity_does_not_replace_allocation_value(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Partner Only Allocation",
                "loss_allocation": {
                    "partner": "Partner A",
                    "evidence": ["agreement.pdf"],
                },
            },
        })
        evidence = next(
            row for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
        )
        self.assertIn("loss allocation", evidence["answer"])

        valued = self.payload({
            "partnership_return": {
                "name": "Valued Partner Allocation",
                "loss_allocation": {
                    "partner": "Partner A",
                    "allocation_percentage": "100%",
                    "evidence": ["agreement.pdf"],
                },
            },
        })
        self.assertFalse(any(
            row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
            for row in valued["evidence_items"]
        ))

    def test_per_partner_allocation_values_require_partner_identity(self):
        for item in (
            {"allocation_percentage": "100%", "evidence": ["agreement.pdf"]},
            {"allocated_loss": 1000, "loss_amount": 1000, "evidence": ["agreement.pdf"]},
            {"allocation": 100, "allocation_basis": "percentage", "evidence": ["agreement.pdf"]},
        ):
            with self.subTest(item=item):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Unidentified Allocation",
                        "loss_allocation": item,
                    },
                })
                evidence = next(
                    row for row in payload["evidence_items"]
                    if row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                )
                self.assertIn("allocation partner", evidence["answer"])

        keyed = self.payload({
            "partnership_return": {
                "name": "Keyed Allocation",
                "loss_allocation": {
                    "allocation": {"Partner A": 60, "Partner B": 40},
                    "allocation_basis": "percentage",
                    "evidence": ["agreement.pdf"],
                },
            },
        })
        self.assertFalse(any(
            row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
            for row in keyed["evidence_items"]
        ))

    def test_percentage_strings_reconcile_in_rows_and_generic_maps(self):
        for allocation in (
            [
                {"partner": "Partner A", "allocation_percentage": "60%", "evidence": ["agreement.pdf"]},
                {"partner": "Partner B", "allocation_percentage": "40%", "evidence": ["agreement.pdf"]},
            ],
            {
                "allocation": {"Partner A": "60%", "Partner B": "40%"},
                "allocation_basis": "percentage",
                "evidence": ["agreement.pdf"],
            },
        ):
            with self.subTest(allocation=allocation):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Percentage String Partners",
                        "loss_allocation": allocation,
                    },
                })
                self.assertFalse(any(
                    row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                    for row in payload["evidence_items"]
                ))

    def test_review_aliases_union_nested_and_flat_provenance(self):
        nested_source = "https://www.ato.gov.au/nested-review"
        flat_source = "https://www.ato.gov.au/flat-review"
        payload = self.payload({
            "partnership_return": {
                "name": "Source Union Partners",
                "losses": [{
                    "amount": 0,
                    "records": ["accounts.pdf"],
                    "source_url": nested_source,
                }],
            },
            "partnership_return_source_url": flat_source,
        })
        loss = next(
            row for row in payload["partnership_items"]
            if row["row_kind"] == "entity-return-partnership-loss"
        )
        self.assertIn(nested_source, loss["source_urls"])
        self.assertIn(flat_source, loss["source_urls"])
        source_gaps = [
            row for row in payload["evidence_items"]
            if "source provenance" in row["answer"]
        ]
        self.assertEqual([], source_gaps)

    def test_flat_gst_bas_interaction_has_one_context_and_one_review_row(self):
        payload = self.payload({
            "partnership_return": {"name": "GST Context Partners"},
            "partnership_return_gst_bas_interaction": False,
            "partnership_return_gst_bas_records": ["bas.pdf"],
        })
        partnership = payload["partnership_items"]
        self.assertEqual(1, sum(
            row["question"] == "Partnership accounting and GST/BAS context"
            for row in partnership
        ))
        self.assertEqual(1, sum(
            row["row_kind"] == "entity-return-partnership-gst-bas" for row in partnership
        ))
        self.assertEqual(1, sum(
            row["row_kind"] == "entity-return-partnership-gst-bas-evidence"
            for row in payload["evidence_items"]
        ))

    def test_psi_amount_and_records_do_not_replace_psi_indicator(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Amount Only PSI Partners",
                "psi_review": {
                    "income_amount": 0,
                    "records": ["contracts.pdf"],
                },
            },
        })
        evidence = next(
            row for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-partnership-psi-evidence"
        )
        self.assertIn("PSI indicator", evidence["answer"])
        psi = next(
            row for row in payload["partnership_items"]
            if row["row_kind"] == "entity-return-partnership-psi"
        )
        self.assertIn("income amount 0", psi["answer"])

    def test_flat_scalar_review_aliases_merge_group_specific_evidence(self):
        payload = self.payload({
            "partnership_return": {"name": "Evidence Merge Partners"},
            "partnership_return_losses": 0,
            "partnership_return_loss_records": ["accounts.pdf"],
            "partnership_return_personal_services_income": False,
            "partnership_return_psi_evidence": ["contracts.pdf"],
            "partnership_return_business_structure": "partnership",
            "partnership_return_business_structure_records": ["agreement.pdf"],
        })
        rows = {row["row_kind"]: row for row in payload["partnership_items"]}
        self.assertIn("amount 0", rows["entity-return-partnership-loss"]["answer"])
        self.assertIn("records", rows["entity-return-partnership-loss"]["answer"])
        self.assertIn(
            "personal services income false",
            rows["entity-return-partnership-psi"]["answer"],
        )
        self.assertIn("evidence", rows["entity-return-partnership-psi"]["answer"])
        self.assertFalse(any(
            row["row_kind"] in {
                "entity-return-partnership-loss-evidence",
                "entity-return-partnership-psi-evidence",
                "entity-return-partnership-business-structure-evidence",
            }
            for row in payload["evidence_items"]
        ))

    def test_empty_review_alias_preserves_group_specific_evidence(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Empty Alias Partners",
                "losses": [],
            },
            "partnership_return_loss_records": ["accounts.pdf"],
        })
        loss = next(
            row for row in payload["partnership_items"]
            if row["row_kind"] == "entity-return-partnership-loss"
        )
        self.assertIn("records", loss["answer"])
        self.assertTrue(any(
            row["row_kind"] == "entity-return-partnership-loss-evidence"
            for row in payload["evidence_items"]
        ))

    def test_generic_loss_allocation_maps_and_rows_require_reconciliation(self):
        for allocation in (
            {"allocation": {"Partner A": 60, "Partner B": 50}, "evidence": ["agreement.pdf"]},
            [
                {"partner": "Partner A", "allocation": 60, "evidence": ["agreement.pdf"]},
                {"partner": "Partner B", "allocation": 50, "evidence": ["agreement.pdf"]},
            ],
        ):
            with self.subTest(allocation=allocation):
                payload = self.payload({
                    "partnership_return": {
                        "name": "Allocation Partners",
                        "loss_allocation": allocation,
                    },
                })
                evidence = " ".join(
                    row["answer"] for row in payload["evidence_items"]
                    if row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                )
                self.assertIn("conflicting loss allocation", evidence)
                self.assertIn("loss allocation basis", evidence)

        reconciled = self.payload({
            "partnership_return": {
                "name": "Amount Allocation Partners",
                "loss_allocation": {
                    "allocation": {"Partner A": 600, "Partner B": 400},
                    "allocation_basis": "amount",
                    "loss_amount": 1000,
                    "evidence": ["agreement.pdf"],
                },
            },
        })
        self.assertFalse(any(
            row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
            for row in reconciled["evidence_items"]
        ))

        for second_amount, conflict_expected in ((400, False), (500, True)):
            with self.subTest(second_amount=second_amount):
                rows = self.payload({
                    "partnership_return": {
                        "name": "Partner Row Allocations",
                        "loss_allocation": [
                            {
                                "partner": "Partner A", "allocated_loss": 600,
                                "loss_amount": 1000, "evidence": ["agreement.pdf"],
                            },
                            {
                                "partner": "Partner B", "allocated_loss": second_amount,
                                "loss_amount": 1000, "evidence": ["agreement.pdf"],
                            },
                        ],
                    },
                })
                evidence = " ".join(
                    row["answer"] for row in rows["evidence_items"]
                    if row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                )
                self.assertEqual(conflict_expected, "conflicting loss allocation" in evidence)

        for second_amount, conflict_expected in ((400, False), (500, True)):
            with self.subTest(flat_current_year_loss=second_amount):
                rows = self.payload({
                    "partnership_return": {
                        "name": "Flat Loss Allocation Partners",
                        "loss_allocations": [
                            {
                                "partner": "Partner A", "allocated_loss": 600,
                                "evidence": ["agreement.pdf"],
                            },
                            {
                                "partner": "Partner B", "allocated_loss": second_amount,
                                "evidence": ["agreement.pdf"],
                            },
                        ],
                    },
                    "partnership_return_current_year_loss": 1000,
                })
                evidence = " ".join(
                    row["answer"] for row in rows["evidence_items"]
                    if row["row_kind"] == "entity-return-partnership-loss-allocation-evidence"
                )
                self.assertEqual(conflict_expected, "conflicting loss allocation" in evidence)
                self.assertNotIn("loss amount for allocation reconciliation", evidence)

    def test_other_category_requires_description_and_review_signals_win(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Review Partnership",
                "income_items": [self.income_item(
                    category="other",
                    description="",
                    gst_bas_interaction="unknown",
                    psi=True,
                    status="Evidence",
                    review_status="Accountant review",
                )],
            },
        })
        evidence = next(row for row in payload["evidence_items"] if row["row_kind"] == "entity-return-partnership-income-evidence")
        self.assertEqual("Accountant review", evidence["status"])
        self.assertIn("other category description", evidence["answer"])

    def test_partnership_stock_and_capital_allowance_rows_preserve_falsey_values(self):
        payload = self.payload({
            "partnership_return": {
                "name": "Special Partnership",
                "trading_stock": {
                    "opening_stock": 0,
                    "purchases": 125,
                    "closing_stock": 0,
                    "valuation_method": "cost",
                    "election": False,
                    "evidence": ["stocktake.pdf"],
                },
                "capital_allowance_items": [{
                    "asset": "Server",
                    "deduction_amount": 0,
                    "adjustable_value": 0,
                    "method": "decline in value supplied",
                    "balancing_adjustment": False,
                    "evidence": ["asset-register.csv"],
                }],
            },
        })
        stock = next(row for row in payload["partnership_items"] if row["row_kind"] == "entity-return-partnership-trading-stock")
        capital = next(row for row in payload["partnership_items"] if row["row_kind"] == "entity-return-partnership-capital-allowance")
        self.assertIn("opening stock 0", stock["answer"])
        self.assertIn("election false", stock["answer"])
        self.assertIn("deduction amount 0", capital["answer"])
        self.assertIn("balancing adjustment false", capital["answer"])
        self.assertFalse(any(
            row["row_kind"] in {
                "entity-return-partnership-trading-stock-evidence",
                "entity-return-partnership-capital-allowance-evidence",
            }
            for row in payload["evidence_items"]
        ))

    def test_multiple_parent_flat_items_require_unique_association(self):
        payload = self.payload({
            "company_return": [{"name": "First Co", "abn": "11"}, {"name": "Second Co", "abn": "22"}],
            "company_return_entity_name": "Second Co",
            "company_return_income_items": [self.income_item()],
        })
        row = next(row for row in payload["company_items"] if row["row_kind"] == "entity-return-company-income")
        self.assertIn("company name Second Co", row["answer"])
        self.assertFalse(any(
            "parent entity" in row["answer"]
            for row in payload["evidence_items"]
            if row["row_kind"] == "entity-return-company-income-evidence"
        ))

        ambiguous = self.payload({
            "company_return": [{"name": "First Co"}, {"name": "Second Co"}],
            "company_return_income_items": [self.income_item()],
        })
        evidence = next(row for row in ambiguous["evidence_items"] if row["row_kind"] == "entity-return-company-income-evidence")
        self.assertIn("parent entity identity", evidence["answer"])

    def test_direct_renderer_keeps_all_new_row_subtypes(self):
        subtypes = (
            "entity-return-company-income",
            "entity-return-company-deduction",
            "entity-return-partnership-income",
            "entity-return-partnership-deduction",
            "entity-return-partnership-trading-stock",
            "entity-return-partnership-capital-allowance",
            "entity-return-company-loss",
            "entity-return-company-loss-continuity",
            "entity-return-company-asset",
            "entity-return-company-asset-pool",
            "entity-return-company-depreciation",
            "entity-return-company-capital-allowance",
        )
        for row_kind in subtypes:
            kind = "company" if "company" in row_kind else "partnership"
            with self.subTest(row_kind=row_kind):
                data = taxmate_taxpack.load_guide_payload({
                    f"{kind}_items": [{
                        "number": "DIRECT",
                        "row_kind": row_kind,
                        "status": "Evidence",
                        "review_status": "Accountant review",
                        "facts": [{"key": "amount", "label": "Amount", "value": 0}],
                    }],
                })
                item = getattr(data, f"{kind}_items")[0]
                self.assertEqual(row_kind, item.row_kind)
                self.assertEqual("Accountant review", item.status)


if __name__ == "__main__":
    unittest.main()
