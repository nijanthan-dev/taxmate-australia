from __future__ import annotations

import re
import sys
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import taxmate_intake  # noqa: E402
import taxmate_taxpack  # noqa: E402


class PrivateHealthMedicareWorkflowTests(unittest.TestCase):
    def statement(self, **updates: Any) -> dict[str, Any]:
        statement: dict[str, Any] = {
            "insurer": "Example Health Fund",
            "membership_id": "MEM-001",
            "benefit_code": "30",
            "premiums_eligible_for_rebate": 0,
            "rebate_received": 0,
            "tax_claim_code": "A",
            "days_covered": 365,
            "period_start": "2025-07-01",
            "period_end": "2026-06-30",
            "evidence": "statement held",
        }
        statement.update(updates)
        return statement

    def dependant(self, name: str = "Example Child", **updates: Any) -> dict[str, Any]:
        dependant: dict[str, Any] = {
            "name": name,
            "type": "child",
            "student": False,
            "age": 12,
            "period_start": "2025-07-01",
            "period_end": "2026-06-30",
            "maintained": True,
            "income_for_tests": 0,
            "shared_care": 0,
            "evidence": "maintenance records held",
        }
        dependant.update(updates)
        return dependant

    def private_health(self, **updates: Any) -> dict[str, Any]:
        private_health: dict[str, Any] = {
            "private_health_cover": True,
            "cover_start": "2025-07-01",
            "cover_end": "2026-06-30",
            "days_covered": 365,
            "statements": [self.statement()],
            "medicare_levy_exemption": False,
            "medicare_levy_reduction": False,
            "medicare_levy_evidence": "no exemption or reduction claimed",
            "mls_review": True,
            "mls_income_for_surcharge": 120000,
            "mls_income_tier": "review from supplied income facts",
            "mls_hospital_cover_days": 365,
            "spouse_had": False,
            "dependant_children": 0,
            "dependants": [],
        }
        private_health.update(updates)
        return private_health

    def payload(self, answers: dict[str, Any]) -> dict[str, Any]:
        return taxmate_intake.answers_to_pack_payload({"income_year": "2025-26", **answers})

    def rows(self, payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {str(row["number"]): row for row in payload["items"]}

    def private_health_rows(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        numbers = {"PHI-OVERVIEW", "MEDICARE-LEVY", "MLS-REVIEW", "SPOUSE-REVIEW"}
        return [
            row
            for row in payload["items"]
            if str(row["number"]) in numbers
            or str(row["number"]).startswith(("PHI-STMT-", "DEPENDANT-"))
        ]

    def phi_evidence(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        return [row for row in payload["evidence_items"] if str(row["number"]).startswith("PHI-EVID-")]

    def phi_evidence_text(self, payload: dict[str, Any]) -> str:
        return "\n".join(str(row.get("answer", "")) for row in self.phi_evidence(payload)).lower()

    def private_health_text(self, payload: dict[str, Any]) -> str:
        fields = ("question", "answer", "why_included", "tab_text")
        return "\n".join(
            str(row.get(field, ""))
            for row in [*self.private_health_rows(payload), *self.phi_evidence(payload)]
            for field in fields
        ).lower()

    def assert_contains_any(self, text: str, *terms: str) -> None:
        self.assertTrue(any(term.lower() in text.lower() for term in terms), (text, terms))

    def test_runtime_helpers_and_canonical_answer_shape(self) -> None:
        for name in (
            "private_health_medicare_answers",
            "private_health_medicare_rows",
            "private_health_medicare_evidence_rows",
        ):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(taxmate_intake, name, None)))

        raw = taxmate_intake.private_health_medicare_answers(
            {"private_health_medicare": self.private_health()}
        )

        self.assertIs(raw["private_health_cover"], True)
        self.assertIs(raw["spouse_had"], False)
        self.assertEqual(0, raw["dependant_children"])
        self.assertEqual(1, len(raw["statements"]))
        self.assertEqual("Example Health Fund", raw["statements"][0]["insurer"])

    def test_structured_rows_preserve_falsey_values_and_sources(self) -> None:
        payload = self.payload({"private_health_medicare": self.private_health()})
        rows = self.rows(payload)

        for number in ("PHI-OVERVIEW", "PHI-STMT-1", "MEDICARE-LEVY", "MLS-REVIEW", "SPOUSE-REVIEW"):
            with self.subTest(number=number):
                self.assertEqual("Accountant review", rows[number]["status"])
                self.assertEqual(taxmate_intake.generation_checked_at(), rows[number]["checked_at"])

        self.assertIn("0.00", rows["PHI-STMT-1"]["answer"])
        self.assertIn("false", rows["MEDICARE-LEVY"]["answer"].lower())
        self.assertIn("false", rows["SPOUSE-REVIEW"]["answer"].lower())
        self.assertIn("0", rows["PHI-OVERVIEW"]["answer"])
        self.assertEqual(
            {
                taxmate_intake.ATO_PRIVATE_HEALTH_STATEMENT_SOURCE,
                taxmate_intake.ATO_PRIVATE_HEALTH_REBATE_CLAIM_SOURCE,
            },
            set(rows["PHI-STMT-1"]["source_urls"]),
        )
        self.assertEqual(
            {taxmate_intake.ATO_MEDICARE_LEVY_SOURCE},
            set(rows["MEDICARE-LEVY"]["source_urls"]),
        )
        self.assertEqual(
            {
                taxmate_intake.ATO_MLS_RETURN_SOURCE,
                taxmate_intake.ATO_MLS_THRESHOLDS_SOURCE,
                taxmate_intake.ATO_MLS_PAYING_SOURCE,
            },
            set(rows["MLS-REVIEW"]["source_urls"]),
        )
        self.assertIn(
            taxmate_intake.ATO_MLS_FAMILY_DEPENDANTS_SOURCE,
            rows["SPOUSE-REVIEW"]["source_urls"],
        )

    def test_no_cover_false_spouse_zero_dependants_are_review_facts(self) -> None:
        payload = self.payload(
            {
                "private_health_cover": False,
                "spouse_had": False,
                "dependant_children": 0,
            }
        )
        rows = self.rows(payload)
        evidence = self.phi_evidence_text(payload)

        self.assertIn("PHI-OVERVIEW", rows)
        self.assertIn("MLS-REVIEW", rows)
        self.assertIn("SPOUSE-REVIEW", rows)
        self.assertIn("false", rows["PHI-OVERVIEW"]["answer"].lower())
        self.assertIn("false", rows["SPOUSE-REVIEW"]["answer"].lower())
        self.assertIn("0", rows["PHI-OVERVIEW"]["answer"])
        for legacy in ("private_health_cover", "spouse_had", "dependant_children"):
            self.assertNotIn(legacy, rows)
        self.assertNotIn("missing private health statement", evidence)
        self.assertNotIn("spouse income", evidence)
        self.assertNotIn("dependant", evidence)

    def test_nested_facts_satisfy_required_long_checklist_questions(self) -> None:
        payload = self.payload({"private_health_medicare": self.private_health()})
        missing_text = "\n".join(
            f"{row.get('question', '')} {row.get('answer', '')} {row.get('tab_text', '')}"
            for row in payload["missing_facts"]
        ).lower()

        self.assertNotIn("had spouse during income year", missing_text)
        self.assertNotIn("dependent children/students count", missing_text)
        self.assertNotIn("private hospital cover", missing_text)

    def test_container_and_statement_alias_shapes_normalize(self) -> None:
        cases = (
            {"private_health": self.private_health()},
            {"medicare_private_health": self.private_health()},
            {
                "private_health_cover": True,
                "spouse_had": False,
                "dependant_children": 0,
                "private_health_statements": [self.statement()],
            },
            {
                "private_health_cover": True,
                "spouse_had": False,
                "dependant_children": 0,
                "private_health_insurance_statements": self.statement(),
            },
        )
        for answers in cases:
            with self.subTest(answers=answers):
                payload = self.payload(answers)
                rows = self.rows(payload)

                self.assertIn("PHI-STMT-1", rows)
                self.assertIn("Example Health Fund", rows["PHI-STMT-1"]["answer"])
                self.assertNotIn("private_health", rows)
                self.assertNotIn("medicare_private_health", rows)

    def test_flat_statement_fields_build_structured_row(self) -> None:
        payload = self.payload(
            {
                "private_health_cover": True,
                "spouse_had": False,
                "dependant_children": 0,
                "private_health_insurer": "Flat Health",
                "private_health_membership_id": "FLAT-1",
                "private_health_benefit_code": "30",
                "private_health_premiums_eligible_for_rebate": 0,
                "private_health_rebate_received": 0,
                "private_health_tax_claim_code": "A",
                "private_health_days_covered": 365,
                "private_health_statement_evidence": "statement held",
            }
        )
        statement = self.rows(payload)["PHI-STMT-1"]

        self.assertIn("Flat Health", statement["answer"])
        self.assertIn("FLAT-1", statement["answer"])
        self.assertGreaterEqual(statement["answer"].count("0.00"), 2)

    def test_scalar_note_only_and_unknown_sibling_facts_stay_visible(self) -> None:
        cases = (
            ({"private_health_medicare": "policy statement pending"}, "policy statement pending"),
            (
                {
                    "private_health_medicare": {
                        "notes": "policy statement pending",
                        "visa_medical_status": "unclear",
                    }
                },
                "visa_medical_status",
            ),
            ({"private_health_statements": ["insurer statement pending"]}, "insurer statement pending"),
            (
                {
                    "private_health_medicare": {
                        "private_health_cover": True,
                        "statements": [
                            {
                                **self.statement(),
                                "insurer_portal_note": "manual statement only",
                            }
                        ],
                    }
                },
                "insurer_portal_note",
            ),
        )
        for answers, expected in cases:
            with self.subTest(expected=expected):
                payload = self.payload(answers)

                self.assertIn(expected.lower(), self.private_health_text(payload))
                self.assertTrue(self.phi_evidence(payload))

    def test_empty_and_false_only_review_defaults_do_not_create_blank_rows(self) -> None:
        cases = (
            {"private_health_medicare": {}},
            {"private_health_medicare": {"statements": []}},
            {
                "private_health_medicare": {
                    "mls_review": False,
                    "medicare_levy_exemption": False,
                    "medicare_levy_reduction": False,
                }
            },
        )
        for answers in cases:
            with self.subTest(answers=answers):
                payload = self.payload(answers)

                self.assertEqual([], self.private_health_rows(payload))
                self.assertEqual([], self.phi_evidence(payload))

    def test_unknown_and_ambiguous_answers_are_not_noops(self) -> None:
        cases = (
            {"private_health_medicare": {"private_health_cover": "unknown"}},
            {"private_health_medicare": "not sure whether I had hospital cover"},
            {"private_health_medicare": {"mls_review": "unclear"}},
        )
        for answers in cases:
            with self.subTest(answers=answers):
                payload = self.payload(answers)

                self.assertTrue(self.private_health_rows(payload))
                self.assertTrue(self.phi_evidence(payload))
                self.assertFalse(any(row["status"] == "Used" for row in self.private_health_rows(payload)))

    def test_statement_denials_stay_in_evidence_queue(self) -> None:
        for denial in (False, "no statement", "statement not received", "not available"):
            with self.subTest(denial=denial):
                private_health = self.private_health(
                    statements=[self.statement(evidence=denial)]
                )
                payload = self.payload({"private_health_medicare": private_health})
                statement = self.rows(payload)["PHI-STMT-1"]
                evidence = self.phi_evidence_text(payload)

                self.assertEqual("Accountant review", statement["status"])
                self.assertIn(str(denial).lower(), statement["answer"].lower())
                self.assertIn("statement", evidence)
                statement_evidence = next(row for row in self.phi_evidence(payload) if "statement" in row["answer"].lower())
                self.assertIn(
                    taxmate_intake.ATO_PRIVATE_HEALTH_STATEMENT_SOURCE,
                    statement_evidence["source_urls"],
                )

    def test_statement_missing_field_matrix_routes_evidence(self) -> None:
        cases = (
            ("benefit_code", "benefit code"),
            ("premiums_eligible_for_rebate", "premium"),
            ("rebate_received", "rebate"),
            ("tax_claim_code", "tax claim code"),
        )
        for field, expected in cases:
            with self.subTest(field=field):
                statement = self.statement()
                statement.pop(field)
                payload = self.payload(
                    {"private_health_medicare": self.private_health(statements=[statement])}
                )

                self.assertIn(expected, self.phi_evidence_text(payload))
                self.assertEqual("Accountant review", self.rows(payload)["PHI-STMT-1"]["status"])

        complete = self.payload({"private_health_medicare": self.private_health()})
        complete_evidence = self.phi_evidence_text(complete)
        self.assertNotIn("premium amount", complete_evidence)
        self.assertNotIn("rebate amount", complete_evidence)

    def test_no_cover_does_not_create_fake_missing_statement_evidence(self) -> None:
        payload = self.payload(
            {
                "private_health_medicare": {
                    "private_health_cover": False,
                    "days_covered": 0,
                    "spouse_had": False,
                    "dependant_children": 0,
                }
            }
        )

        self.assertIn("MLS-REVIEW", self.rows(payload))
        self.assertNotIn("statement", self.phi_evidence_text(payload))

    def test_partial_cover_and_period_conflicts_stay_evidence(self) -> None:
        cases = (
            self.private_health(
                days_covered=180,
                cover_end="2025-12-27",
                statements=[
                    self.statement(
                        days_covered=180,
                        period_end="2025-12-27",
                    )
                ],
            ),
            self.private_health(cover_start="2026-06-30", cover_end="2025-07-01"),
            self.private_health(private_health_cover=False, days_covered=365),
            self.private_health(private_health_cover=True, days_covered=0),
        )
        for private_health in cases:
            with self.subTest(private_health=private_health):
                payload = self.payload({"private_health_medicare": private_health})
                evidence = self.phi_evidence_text(payload)

                self.assert_contains_any(evidence, "partial", "period", "cover", "days")

    def test_medicare_spouse_dependant_and_mls_gap_matrix(self) -> None:
        cases = (
            (
                {
                    "private_health_medicare": {
                        "medicare_levy_exemption": True,
                        "medicare_levy_evidence": "unknown",
                    }
                },
                ("exemption", "medicare levy"),
            ),
            (
                {"private_health_medicare": {"mls_review": "unknown"}},
                ("surcharge", "mls"),
            ),
            (
                {
                    "private_health_medicare": {
                        "spouse_had": True,
                        "dependant_children": 0,
                    }
                },
                ("spouse income", "spouse period"),
            ),
            (
                {
                    "private_health_medicare": {
                        "spouse_had": False,
                        "dependant_children": 1,
                        "dependants": [],
                    }
                },
                ("dependant", "student"),
            ),
        )
        for answers, expected_terms in cases:
            with self.subTest(answers=answers):
                evidence = self.phi_evidence_text(self.payload(answers))

                self.assert_contains_any(evidence, *expected_terms)

    def test_malformed_amount_date_code_and_count_values_stay_evidence(self) -> None:
        malformed = self.statement(
            benefit_code="unsupported-code",
            premiums_eligible_for_rebate="about 100",
            rebate_received=-1,
            tax_claim_code="??",
            days_covered=-1,
            period_start="31/06/2025",
            period_end="2025-01-01",
        )
        payload = self.payload(
            {"private_health_medicare": self.private_health(statements=[malformed])}
        )
        text = self.private_health_text(payload)
        evidence = self.phi_evidence_text(payload)

        for supplied in ("unsupported-code", "about 100", "-1", "??", "31/06/2025"):
            self.assertIn(supplied.lower(), text)
        self.assert_contains_any(evidence, "amount", "premium")
        self.assertIn("code", evidence)
        self.assert_contains_any(evidence, "date", "period", "days")

    def test_alias_values_use_field_specific_canonicalization(self) -> None:
        statement = self.statement(
            premiums="0.00",
            rebate="0",
            benefit=" 30 ",
            claim_code=" a ",
        )
        payload = self.payload(
            {"private_health_medicare": self.private_health(statements=[statement])}
        )

        self.assertNotIn("alias conflict", self.private_health_text(payload))

    def test_alias_conflicts_preserve_values_and_queue_evidence(self) -> None:
        statement = self.statement(
            premiums=10,
            benefit="31",
            claim_code="B",
        )
        private_health = self.private_health(
            private_health_cover=False,
            cover=True,
            statements=[statement],
        )
        payload = self.payload(
            {
                "private_health_cover": True,
                "private_health_medicare": private_health,
            }
        )
        text = self.private_health_text(payload)
        evidence = self.phi_evidence_text(payload)

        self.assertIn("conflict", evidence)
        self.assertIn("0.00", text)
        self.assertIn("10", text)
        self.assertIn("30", text)
        self.assertIn("31", text)
        self.assertRegex(text, r"(?:tax )?claim code[^\n]*(?:a[^\n]*b|b[^\n]*a)")

    def test_statement_alias_lists_merge_complementary_items_and_preserve_extras(self) -> None:
        private_health = self.private_health(
            statements=[
                {
                    "insurer": "Merged Health",
                    "membership_id": "MERGED-1",
                    "benefit_code": "30",
                    "tax_claim_code": "A",
                }
            ],
            statement_rows=[
                {
                    "premiums": 100,
                    "rebate": 20,
                    "days_covered": 365,
                    "evidence": "statement held",
                },
                self.statement(insurer="Extra Health", membership_id="EXTRA-2"),
            ],
        )
        payload = self.payload({"private_health_medicare": private_health})
        rows = self.rows(payload)

        self.assertIn("PHI-STMT-1", rows)
        self.assertIn("PHI-STMT-2", rows)
        self.assertIn("Merged Health", rows["PHI-STMT-1"]["answer"])
        self.assertIn("100.00", rows["PHI-STMT-1"]["answer"])
        self.assertIn("20.00", rows["PHI-STMT-1"]["answer"])
        self.assertIn("Extra Health", rows["PHI-STMT-2"]["answer"])

    def test_dependant_rows_preserve_false_student_and_sources(self) -> None:
        private_health = self.private_health(
            spouse_had=True,
            spouse_period_start="2025-07-01",
            spouse_period_end="2026-06-30",
            spouse_income_for_tests=0,
            spouse_income_evidence="income statement held",
            dependant_children=1,
            dependants=[
                {
                    "name": "Example Child",
                    "type": "child",
                    "student": False,
                    "age": 12,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "evidence": "birth certificate held",
                    "notes": "lived with taxpayer",
                }
            ],
        )
        dependant = self.rows(
            self.payload({"private_health_medicare": private_health})
        )["DEPENDANT-1"]

        self.assertEqual("Accountant review", dependant["status"])
        self.assertIn("Example Child", dependant["answer"])
        self.assertIn("false", dependant["answer"].lower())
        self.assertIn("lived with taxpayer", dependant["answer"])
        self.assertIn(
            taxmate_intake.ATO_MLS_FAMILY_DEPENDANTS_SOURCE,
            dependant["source_urls"],
        )

    def test_evidence_review_queue_html_and_provenance_stay_in_parity(self) -> None:
        incomplete_statement = self.statement()
        incomplete_statement.pop("tax_claim_code")
        private_health = self.private_health(
            statements=[incomplete_statement],
            spouse_had=True,
            spouse_period_start=None,
            spouse_period_end=None,
            spouse_income_for_tests=None,
            spouse_income_evidence=None,
        )
        payload = self.payload({"private_health_medicare": private_health})
        rows = self.rows(payload)
        evidence_rows = self.phi_evidence(payload)

        self.assertEqual("Accountant review", rows["PHI-STMT-1"]["status"])
        self.assertEqual("Accountant review", rows["SPOUSE-REVIEW"]["status"])
        self.assertTrue(evidence_rows)
        self.assertTrue(all(row["status"] == "Evidence" for row in evidence_rows))
        statement_evidence = next(
            row for row in evidence_rows if "tax claim code" in row["answer"].lower()
        )
        self.assertEqual(
            {
                taxmate_intake.ATO_PRIVATE_HEALTH_STATEMENT_SOURCE,
                taxmate_intake.ATO_PRIVATE_HEALTH_REBATE_CLAIM_SOURCE,
            },
            set(statement_evidence["source_urls"]),
        )

        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))
        self.assertIn("PHI-STMT-1", body)
        self.assertIn("SPOUSE-REVIEW", body)
        self.assertIn("Evidence queue", body)
        self.assertIn("Accountant review queue", body)
        self.assertIn("tax claim code", body.lower())
        self.assertIn(taxmate_intake.ATO_PRIVATE_HEALTH_STATEMENT_SOURCE, body)
        self.assertIn(taxmate_intake.ATO_MLS_FAMILY_DEPENDANTS_SOURCE, body)
        self.assertRegex(body, r"Checked\s+\d{4}-\d{2}-\d{2}")
        self.assertNotRegex(
            body.lower(),
            re.compile(r"\b(lodgment-ready|claimable|calculated (?:levy|surcharge|rebate)|final tax advice)\b"),
        )

    def test_unrelated_top_level_generic_fields_do_not_create_workflow(self) -> None:
        payload = self.payload(
            {
                "period_start": "2025-07-01",
                "period_end": "2026-06-30",
                "period": "foreign employment period",
                "evidence": "foreign income statement held",
                "records": "foreign income records held",
                "notes": "foreign income only",
                "source_url": "https://example.test/foreign-income",
                "checked_at": "2026-07-10",
                "foreign_income": {
                    "statement": "foreign income statement held",
                    "country": "NZ",
                    "amount": 5000,
                },
            }
        )

        self.assertEqual([], self.private_health_rows(payload))
        self.assertEqual([], self.phi_evidence(payload))

    def test_sample_foreign_income_does_not_leak_into_spouse(self) -> None:
        answers = taxmate_intake.sample_answers()
        raw = taxmate_intake.private_health_medicare_answers(answers)
        payload = taxmate_intake.answers_to_pack_payload(answers)
        spouse = self.rows(payload)["SPOUSE-REVIEW"]

        self.assertNotIn("foreign_income", raw["spouse"])
        self.assertNotIn("Example NZ Employer", spouse["answer"])
        self.assertNotIn("foreign income statement held", spouse["answer"].lower())
        self.assertNotIn("Example NZ Employer", self.phi_evidence_text(payload))

    def test_generic_fields_inside_typed_sections_stay_in_their_section(self) -> None:
        payload = self.payload(
            {
                "private_health_medicare": {
                    "private_health": {
                        "covered": True,
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "evidence": "cover-only evidence",
                    },
                    "medicare_levy": {
                        "reduction": True,
                        "evidence": "levy-only evidence",
                    },
                    "mls": {
                        "appropriate_hospital_cover": False,
                        "income_for_surcharge": 0,
                        "income_tier": "base tier",
                        "evidence": "mls-only evidence",
                    },
                    "spouse": {
                        "had_spouse": True,
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "income_for_tests": 0,
                        "income_evidence": "spouse-only evidence",
                    },
                    "dependant_count": 0,
                }
            }
        )
        rows = self.rows(payload)
        expected = {
            "PHI-OVERVIEW": "cover-only evidence",
            "MEDICARE-LEVY": "levy-only evidence",
            "MLS-REVIEW": "mls-only evidence",
            "SPOUSE-REVIEW": "spouse-only evidence",
        }

        for number, marker in expected.items():
            with self.subTest(number=number):
                self.assertIn(marker, rows[number]["answer"])
                for other_marker in set(expected.values()).difference({marker}):
                    self.assertNotIn(other_marker, rows[number]["answer"])

    def test_scalar_false_typed_sections_and_zero_dependants_are_preserved(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependant_count": 0,
            }
        }
        raw = taxmate_intake.private_health_medicare_answers(answers)
        rows = self.rows(self.payload(answers))

        self.assertIs(raw["private_health_cover"], False)
        self.assertIs(raw["spouse_had"], False)
        self.assertEqual(0, raw["dependant_children"])
        self.assertIn("false", rows["PHI-OVERVIEW"]["answer"].lower())
        self.assertIn("false", rows["SPOUSE-REVIEW"]["answer"].lower())
        self.assertIn("count 0", rows["DEPENDANT-SUMMARY"]["answer"].lower())

    def test_workflow_list_merges_typed_records(self) -> None:
        answers = {
            "private_health_medicare": [
                {
                    "private_health": {
                        "covered": True,
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "days_covered": 365,
                    }
                },
                {"statements": [self.statement()]},
                {"spouse": {"had_spouse": False}},
                {"dependant_count": 0},
            ]
        }
        raw = taxmate_intake.private_health_medicare_answers(answers)
        rows = self.rows(self.payload(answers))

        self.assertIs(raw["private_health_cover"], True)
        self.assertIs(raw["spouse_had"], False)
        self.assertEqual(0, raw["dependant_children"])
        self.assertEqual(1, len(raw["statements"]))
        self.assertIn("PHI-STMT-1", rows)
        self.assertIn("SPOUSE-REVIEW", rows)
        self.assertIn("DEPENDANT-SUMMARY", rows)
        self.assertNotIn("supplemental facts", rows["PHI-OVERVIEW"]["answer"].lower())

    def test_nested_private_health_accepts_flat_statement_and_dependants(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": {
                    "covered": True,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "days_covered": 365,
                    "evidence": "policy held",
                    "private_health_insurer": "Nested Flat Health",
                    "private_health_membership_id": "NESTED-1",
                    "private_health_benefit_code": "30",
                    "private_health_premiums_eligible_for_rebate": 100,
                    "private_health_rebate_received": 20,
                    "private_health_tax_claim_code": "A",
                    "private_health_statement_evidence": "statement held",
                    "dependant_count": 1,
                    "dependants": [self.dependant("Nested Child")],
                },
                "spouse": {"had_spouse": False},
            }
        }
        rows = self.rows(self.payload(answers))

        self.assertIn("Nested Flat Health", rows["PHI-STMT-1"]["answer"])
        self.assertIn("Nested Child", rows["DEPENDANT-1"]["answer"])
        self.assertIn("count 1", rows["DEPENDANT-SUMMARY"]["answer"].lower())

    def test_dependant_dictionary_preserves_count_items_and_provenance_without_phantoms(self) -> None:
        source_url = "https://example.test/dependant-evidence"
        answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependants": {
                    "count": 1,
                    "items": [
                        self.dependant(
                            "Dictionary Child",
                            source_url=source_url,
                            source_checked_at="2026-07-09",
                        )
                    ],
                },
            }
        }
        raw = taxmate_intake.private_health_medicare_answers(answers)
        payload = self.payload(answers)
        rows = self.rows(payload)
        dependant_numbers = sorted(number for number in rows if number.startswith("DEPENDANT-"))

        self.assertEqual(1, raw["dependant_children"])
        self.assertEqual(["DEPENDANT-1", "DEPENDANT-SUMMARY"], dependant_numbers)
        self.assertIn(source_url, rows["DEPENDANT-1"]["source_urls"])
        self.assertIn("2026-07-09", rows["DEPENDANT-1"]["answer"])
        self.assertNotIn("confirm dependant count", self.phi_evidence_text(payload))
        self.assertNotIn("reconcile dependant count", self.phi_evidence_text(payload))

    def test_distinct_statement_alias_items_are_not_index_collapsed(self) -> None:
        alpha = self.statement(insurer="Alpha Health", membership_id="ALPHA-1")
        beta = self.statement(insurer="Beta Health", membership_id="BETA-1")
        answers = {
            "private_health_medicare": {
                "private_health_cover": True,
                "cover_period_start": "2025-07-01",
                "cover_period_end": "2026-06-30",
                "days_covered": 365,
                "statements": [alpha],
                "policy_lines": [beta],
            }
        }
        payload = self.payload(answers)
        rows = self.rows(payload)

        self.assertIn("Alpha Health", rows["PHI-STMT-1"]["answer"])
        self.assertIn("Beta Health", rows["PHI-STMT-2"]["answer"])
        self.assertNotIn("alias conflict", self.private_health_text(payload))

    def test_reordered_statement_aliases_merge_by_identity(self) -> None:
        alpha = self.statement(insurer="Alpha Health", membership_id="ALPHA-1", premiums_eligible_for_rebate=100)
        beta = self.statement(insurer="Beta Health", membership_id="BETA-1", premiums_eligible_for_rebate=200)
        answers = {
            "private_health_medicare": {
                "private_health_cover": True,
                "cover_period_start": "2025-07-01",
                "cover_period_end": "2026-06-30",
                "days_covered": 365,
                "statements": [alpha, beta],
                "statement_rows": [
                    {"insurer": "Beta Health", "membership_id": "BETA-1", "notes": "beta secondary"},
                    {"insurer": "Alpha Health", "membership_id": "ALPHA-1", "notes": "alpha secondary"},
                ],
            }
        }
        payload = self.payload(answers)
        rows = self.rows(payload)

        self.assertIn("Alpha Health", rows["PHI-STMT-1"]["answer"])
        self.assertIn("100.00", rows["PHI-STMT-1"]["answer"])
        self.assertIn("alpha secondary", rows["PHI-STMT-1"]["answer"])
        self.assertNotIn("beta secondary", rows["PHI-STMT-1"]["answer"])
        self.assertIn("Beta Health", rows["PHI-STMT-2"]["answer"])
        self.assertIn("200.00", rows["PHI-STMT-2"]["answer"])
        self.assertIn("beta secondary", rows["PHI-STMT-2"]["answer"])
        self.assertNotIn("alpha secondary", rows["PHI-STMT-2"]["answer"])
        self.assertNotIn("alias conflict", self.private_health_text(payload))

    def test_statement_partial_reconciliation_preserves_unmatched_items(self) -> None:
        alpha = self.statement(insurer="Alpha Health", membership_id="ALPHA-1")
        beta = self.statement(insurer="Beta Health", membership_id="BETA-1")
        answers = {
            "private_health_medicare": {
                "private_health_cover": True,
                "cover_period_start": "2025-07-01",
                "cover_period_end": "2026-06-30",
                "days_covered": 365,
                "statements": [alpha, beta],
                "policy_lines": [
                    {
                        "insurer": "Beta Health",
                        "membership_id": "BETA-1",
                        "notes": "matched partial record",
                    }
                ],
            }
        }
        rows = self.rows(self.payload(answers))

        self.assertIn("Alpha Health", rows["PHI-STMT-1"]["answer"])
        self.assertNotIn("matched partial record", rows["PHI-STMT-1"]["answer"])
        self.assertIn("Beta Health", rows["PHI-STMT-2"]["answer"])
        self.assertIn("matched partial record", rows["PHI-STMT-2"]["answer"])

    def test_distinct_dependant_alias_items_are_not_index_collapsed(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependant_count": 2,
                "dependants": [self.dependant("Alice")],
                "dependents": [self.dependant("Bob")],
            }
        }
        payload = self.payload(answers)
        rows = self.rows(payload)

        self.assertIn("Alice", rows["DEPENDANT-1"]["answer"])
        self.assertIn("Bob", rows["DEPENDANT-2"]["answer"])
        self.assertNotIn("alias conflict", self.private_health_text(payload))

    def test_reordered_dependant_aliases_merge_by_identity(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependant_count": 2,
                "dependants": [self.dependant("Alice"), self.dependant("Bob")],
                "dependents": [
                    {"name": "Bob", "notes": "bob secondary"},
                    {"name": "Alice", "notes": "alice secondary"},
                ],
            }
        }
        payload = self.payload(answers)
        rows = self.rows(payload)

        self.assertIn("Alice", rows["DEPENDANT-1"]["answer"])
        self.assertIn("alice secondary", rows["DEPENDANT-1"]["answer"])
        self.assertNotIn("bob secondary", rows["DEPENDANT-1"]["answer"])
        self.assertIn("Bob", rows["DEPENDANT-2"]["answer"])
        self.assertIn("bob secondary", rows["DEPENDANT-2"]["answer"])
        self.assertNotIn("alice secondary", rows["DEPENDANT-2"]["answer"])
        self.assertNotIn("alias conflict", self.private_health_text(payload))

    def test_complementary_dependant_aliases_still_merge(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependant_count": 1,
                "dependants": [
                    {
                        "name": "Alice",
                        "type": "child",
                        "student": False,
                        "age": 12,
                    }
                ],
                "dependents": [
                    {
                        "name": "Alice",
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "maintained": True,
                        "evidence": "maintenance records held",
                    }
                ],
            }
        }
        payload = self.payload(answers)
        rows = self.rows(payload)
        dependant_numbers = sorted(number for number in rows if re.fullmatch(r"DEPENDANT-\d+", number))

        self.assertEqual(["DEPENDANT-1"], dependant_numbers)
        self.assertIn("Alice", rows["DEPENDANT-1"]["answer"])
        self.assertIn("false", rows["DEPENDANT-1"]["answer"].lower())
        self.assertIn("2025-07-01 to 2026-06-30", rows["DEPENDANT-1"]["answer"])
        self.assertIn("maintenance records held", rows["DEPENDANT-1"]["answer"])
        self.assertNotIn("alias conflict", self.private_health_text(payload))

    def test_statement_denial_phrases_and_numeric_zero_need_evidence(self) -> None:
        denials: tuple[Any, ...] = (
            "do not have statement",
            "don't have statement",
            "dont have statement",
            "statement not provided",
            "statement not supplied",
            0,
        )
        for denial in denials:
            with self.subTest(denial=denial):
                payload = self.payload(
                    {
                        "private_health_medicare": self.private_health(
                            statements=[self.statement(evidence=denial)]
                        )
                    }
                )
                statement = self.rows(payload)["PHI-STMT-1"]
                evidence = self.phi_evidence_text(payload)

                self.assertIn(str(denial).lower(), statement["answer"].lower())
                self.assertIn("statement evidence", evidence)

    def test_evidence_denials_apply_to_cover_spouse_and_dependant_fields(self) -> None:
        cases = (
            (
                {
                    "private_health_medicare": {
                        "private_health": {
                            "covered": True,
                            "period_start": "2025-07-01",
                            "period_end": "2026-06-30",
                            "days_covered": 365,
                            "evidence": 0,
                        },
                        "statements": [self.statement(evidence=0)],
                    }
                },
                "private hospital cover evidence",
            ),
            (
                {
                    "private_health_medicare": {
                        "spouse": {
                            "had_spouse": True,
                            "period_start": "2025-07-01",
                            "period_end": "2026-06-30",
                            "income_for_tests": 0,
                            "income_evidence": "do not have spouse income statement",
                        }
                    }
                },
                "spouse income evidence",
            ),
            (
                {
                    "private_health_medicare": {
                        "private_health": False,
                        "spouse": False,
                        "dependant_count": 1,
                        "dependants": [
                            self.dependant(
                                "Evidence Child",
                                evidence="dependant records not provided",
                            )
                        ],
                    }
                },
                "dependant or student evidence",
            ),
        )
        for answers, expected in cases:
            with self.subTest(expected=expected):
                evidence = self.phi_evidence_text(self.payload(answers))

                self.assertIn(expected, evidence)

    def test_supported_benefit_code_set_accepts_known_codes_and_rejects_99(self) -> None:
        supported = ("30", "31", "35", "36", "40", "41")
        for benefit_code in supported:
            with self.subTest(benefit_code=benefit_code):
                payload = self.payload(
                    {
                        "private_health_medicare": self.private_health(
                            statements=[self.statement(benefit_code=benefit_code)]
                        )
                    }
                )
                statement_gaps = "\n".join(
                    row["answer"].lower()
                    for row in self.phi_evidence(payload)
                    if "private health statement" in row["answer"].lower()
                )

                self.assertNotIn("confirm benefit code", statement_gaps)

        unsupported = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements=[self.statement(benefit_code="99")]
                )
            }
        )
        self.assertIn("confirm benefit code (99)", self.phi_evidence_text(unsupported))

    def test_arbitrary_period_text_requires_evidence(self) -> None:
        statement = self.statement()
        statement.pop("period_start")
        statement.pop("period_end")
        statement.pop("days_covered")
        statement["period"] = "whenever the policy applied"
        cases = (
            (
                self.private_health(
                    cover_start=None,
                    cover_end=None,
                    days_covered=None,
                    cover_period="some custom policy period",
                    statements=[self.statement()],
                ),
                "private hospital cover period",
                "some custom policy period",
            ),
            (
                self.private_health(statements=[statement]),
                "statement cover period",
                "whenever the policy applied",
            ),
        )
        for private_health, expected_gap, supplied in cases:
            with self.subTest(expected_gap=expected_gap):
                evidence = self.phi_evidence_text(
                    self.payload({"private_health_medicare": private_health})
                )

                self.assertIn(expected_gap, evidence)
                self.assertIn(supplied, evidence)

    def test_ambiguous_levy_and_mls_flags_remain_visible_evidence(self) -> None:
        answers = {
            "private_health_medicare": {
                "medicare_levy": {
                    "reduction": "not sure if reduction applies",
                    "exemption": "not sure whether exempt",
                    "evidence": "unknown",
                },
                "mls": {
                    "review": "not sure whether surcharge applies",
                    "appropriate_hospital_cover": "not sure whether covered",
                    "evidence": "unknown",
                },
            }
        }
        payload = self.payload(answers)
        rows = self.rows(payload)
        evidence = self.phi_evidence_text(payload)

        self.assertIn("MEDICARE-LEVY", rows)
        self.assertIn("MLS-REVIEW", rows)
        self.assertIn("not sure if reduction applies", rows["MEDICARE-LEVY"]["answer"])
        self.assertIn("not sure whether surcharge applies", rows["MLS-REVIEW"]["answer"])
        self.assertIn("reduction uncertainty", evidence)
        self.assertIn("exemption uncertainty", evidence)
        self.assertIn("surcharge review uncertainty", evidence)
        self.assertIn("appropriate private patient hospital cover", evidence)

    def test_full_year_cover_has_no_partial_gap(self) -> None:
        payload = self.payload({"private_health_medicare": self.private_health()})
        evidence = self.phi_evidence_text(payload)

        self.assertNotIn("partial-year", evidence)
        self.assertNotIn("date order", evidence)
        self.assertNotIn("confirm private hospital cover period", evidence)
        self.assertNotIn("confirm hospital cover period", evidence)

    def test_partial_dates_days_and_text_have_specific_evidence(self) -> None:
        cases = (
            self.private_health(
                cover_end="2025-12-31",
                days_covered=184,
                mls_hospital_cover_days=184,
            ),
            self.private_health(
                cover_start=None,
                cover_end=None,
                days_covered=None,
                cover_period="partial year",
            ),
            self.private_health(
                cover_start=None,
                cover_end=None,
                days_covered=180,
            ),
        )
        for private_health in cases:
            with self.subTest(private_health=private_health):
                evidence = self.phi_evidence_text(
                    self.payload({"private_health_medicare": private_health})
                )

                self.assertIn("partial-year", evidence)

    def test_false_statement_collection_is_noop_with_no_cover(self) -> None:
        cases = (
            {"statements": False},
            {"private_health_statements": False},
            {"private_health_insurance_statements": False},
        )
        for collection in cases:
            with self.subTest(collection=collection):
                private_health = {
                    "private_health_cover": False,
                    "spouse_had": False,
                    "dependant_count": 0,
                    **collection,
                }
                payload = self.payload({"private_health_medicare": private_health})
                rows = self.rows(payload)

                self.assertFalse(any(number.startswith("PHI-STMT-") for number in rows))
                self.assertNotIn("statement evidence", self.phi_evidence_text(payload))

    def test_metadata_only_and_noop_inputs_do_not_create_phantoms(self) -> None:
        cases = (
            {
                "private_health_medicare": {
                    "source_url": "https://example.test/workflow-metadata",
                    "checked_at": "2026-07-10",
                }
            },
            {
                "private_health_medicare": {
                    "private_health": {
                        "source_urls": ["https://example.test/cover-metadata"],
                        "source_checked_at": "2026-07-10",
                    }
                }
            },
            {
                "private_health_medicare": {
                    "statements": [
                        {
                            "source_url": "https://example.test/statement-metadata",
                            "checked_at": "2026-07-10",
                        }
                    ]
                }
            },
            {
                "private_health_medicare": {
                    "mls": {
                        "sources": ["https://example.test/mls-metadata"],
                        "checked_at": "2026-07-10",
                    }
                }
            },
            {"private_health_medicare": {"notes": "n/a", "statements": []}},
            {"private_health_medicare": [None, False, "not applicable", {}, []]},
        )
        for answers in cases:
            with self.subTest(answers=answers):
                payload = self.payload(answers)

                self.assertEqual([], self.private_health_rows(payload))
                self.assertEqual([], self.phi_evidence(payload))

    def test_recursive_noop_containers_do_not_create_phantoms(self) -> None:
        noop: Any = ["N/A", {"note": ["not applicable", None, ""]}, [["none"]]]
        cases = (
            {"private_health_medicare": {"notes": noop}},
            {"private_health_medicare": {"notes": [False]}},
            {"private_health_medicare": {"custom": noop}},
            {
                "private_health_medicare": {
                    "private_health": {"covered": noop, "notes": noop, "custom": noop}
                }
            },
            {
                "private_health_medicare": {
                    "medicare_levy": {"exemption": noop, "notes": noop, "custom": noop}
                }
            },
            {
                "private_health_medicare": {
                    "mls": {"review": noop, "notes": noop, "custom": noop}
                }
            },
            {
                "private_health_medicare": {
                    "spouse": {"had_spouse": noop, "notes": noop, "custom": noop}
                }
            },
            {
                "private_health_medicare": {
                    "statements": {
                        "items": [{"insurer": noop}],
                        "notes": noop,
                        "source_urls": [False],
                        "checked_at": [False],
                    }
                }
            },
            {
                "private_health_medicare": {
                    "dependants": {
                        "count": noop,
                        "items": [{"name": noop}],
                        "notes": noop,
                        "source_urls": [False],
                        "checked_at": [False],
                    }
                }
            },
            {
                "private_health_medicare": {
                    "medicare": {
                        "levy": {"exemption": noop},
                        "mls": {"review": noop},
                    }
                }
            },
            {
                "private_health_medicare": {
                    "source_urls": [False],
                    "checked_at": [False],
                }
            },
        )
        for answers in cases:
            with self.subTest(answers=answers):
                payload = self.payload(answers)

                self.assertEqual([], self.private_health_rows(payload))
                self.assertEqual([], self.phi_evidence(payload))

        direct = {
            "private_health": {
                "covered": noop,
                "source_urls": [False],
                "checked_at": [False],
            },
            "statements": [{"insurer": noop}],
            "medicare_levy": {"exemption": noop},
            "mls": {"review": noop},
            "spouse": {"had_spouse": noop},
            "dependant_summary": {"count": noop},
            "dependants": [{"name": noop}],
            "notes": [*noop, False],
        }
        self.assertEqual([], taxmate_intake.private_health_medicare_rows(direct))
        self.assertEqual([], taxmate_intake.private_health_medicare_evidence_rows(direct))

        body = taxmate_taxpack.render_html(
            taxmate_taxpack.load_guide_payload(self.payload({"private_health_medicare": {"notes": noop}}))
        )
        for row_id in ("PHI-OVERVIEW", "PHI-STMT-", "MEDICARE-LEVY", "MLS-REVIEW", "SPOUSE-REVIEW"):
            self.assertNotIn(row_id, body)

    def test_noop_aliases_do_not_shadow_real_private_health_facts(self) -> None:
        noop: Any = ["n/a", {"note": "not applicable"}]
        custom_source = "https://example.test/noop-filter-source"
        answers = {
            "private_health_medicare": {
                "private_health": {
                    "covered": noop,
                    "private_health_cover": True,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "days_covered": 365,
                    "evidence": "policy held",
                    "notes": ["none", "manual cover check retained"],
                    "source_urls": ["n/a", custom_source],
                    "checked_at": ["none", "2026-07-10"],
                },
                "statements": [
                    self.statement(insurer=noop, health_fund="Real Health Fund")
                ],
                "medicare_levy": {
                    "exemption": noop,
                    "medicare_levy_exemption": True,
                    "exemption_category": "supplied review category",
                    "full_exemption_days": 0,
                    "evidence": "certificate held",
                },
                "mls": {
                    "review": noop,
                    "mls_review": True,
                    "appropriate_hospital_cover": True,
                    "income_for_surcharge": 0,
                    "income_tier": "base tier",
                    "evidence": "review records held",
                },
                "spouse": {
                    "had_spouse": noop,
                    "spouse_had": True,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "income_for_tests": 0,
                    "income_evidence": "statement held",
                },
                "dependant_count": 1,
                "dependants": [
                    self.dependant(name=noop, label="Real Child")
                ],
            }
        }
        payload = self.payload(answers)
        rows = self.rows(payload)
        text = self.private_health_text(payload)
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        self.assertIn("true", rows["PHI-OVERVIEW"]["answer"].lower())
        self.assertIn("Real Health Fund", rows["PHI-STMT-1"]["answer"])
        self.assertIn("true", rows["MEDICARE-LEVY"]["answer"].lower())
        self.assertIn("true", rows["MLS-REVIEW"]["answer"].lower())
        self.assertIn("true", rows["SPOUSE-REVIEW"]["answer"].lower())
        self.assertIn("Real Child", rows["DEPENDANT-1"]["answer"])
        self.assertIn("manual cover check retained", text)
        self.assertIn(custom_source, rows["PHI-OVERVIEW"]["source_urls"])
        self.assertIn("2026-07-10", rows["PHI-OVERVIEW"]["answer"])
        for suppressed in ("n/a", "not applicable", "alias conflict"):
            self.assertNotIn(suppressed, text)
        for suppressed in ("insurer/fund n/a", "notes n/a", "not applicable", "alias conflict"):
            self.assertNotIn(suppressed, body.lower())

    def test_mixed_containers_preserve_real_notes_falsey_facts_and_denials(self) -> None:
        nested = self.payload({"private_health_medicare": [["policy pending"]]})
        self.assertIn("policy pending", self.private_health_text(nested))
        self.assertIn("policy pending", self.phi_evidence_text(nested))

        mixed_section = self.payload(
            {
                "private_health_medicare": {
                    "private_health": [
                        {
                            "covered": True,
                            "period_start": "2025-07-01",
                            "period_end": "2026-06-30",
                            "days_covered": 365,
                            "evidence": "policy held",
                        },
                        "policy split pending",
                    ],
                    "notes": ["n/a", {"detail": "manual mapping unclear"}],
                    "custom": {"noop": "none", "zero": 0, "flag": False},
                }
            }
        )
        mixed_text = self.private_health_text(mixed_section)
        self.assertIn("policy split pending", mixed_text)
        self.assertIn("manual mapping unclear", mixed_text)
        self.assertIn("zero", mixed_text)
        self.assertIn("0", mixed_text)
        self.assertIn("false", mixed_text)
        self.assertNotIn("n/a", mixed_text)

        denial = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements={"evidence": ["none", False]}
                )
            }
        )
        self.assertFalse(
            any(number.startswith("PHI-STMT-") for number in self.rows(denial))
        )
        self.assertIn("false", self.phi_evidence_text(denial))

        direct = {
            "private_health": {"source_urls": [False], "checked_at": [False]},
            "statements": [],
            "medicare_levy": {},
            "mls": {},
            "spouse": {
                "had_spouse": True,
                "period_start": "2025-07-01",
                "period_end": "2026-06-30",
                "income_for_tests": 0,
                "income_evidence": "statement held",
            },
            "dependant_summary": {},
            "dependants": [],
            "notes": [],
        }
        direct_rows = {
            str(row["number"]): row
            for row in taxmate_intake.private_health_medicare_rows(direct)
        }
        self.assertNotIn("PHI-OVERVIEW", direct_rows)
        self.assertIn("SPOUSE-REVIEW", direct_rows)

    def test_dependant_non_item_facts_route_to_summary_without_phantom_items(self) -> None:
        cases = (
            ([{"notes": "child facts unclear"}], "child facts unclear"),
            ([{"custom": "maintenance arrangement unclear"}], "maintenance arrangement unclear"),
            (["student status pending"], "student status pending"),
            ({"items": [{"notes": "child period unclear"}]}, "child period unclear"),
            ({"items": [], "evidence": "family records pending"}, "family records pending"),
        )
        for dependants, expected in cases:
            with self.subTest(dependants=dependants):
                payload = self.payload(
                    {
                        "private_health_medicare": {
                            "dependants": dependants,
                        }
                    }
                )
                rows = self.rows(payload)

                self.assertIn("DEPENDANT-SUMMARY", rows)
                self.assertFalse(
                    any(re.fullmatch(r"DEPENDANT-\d+", number) for number in rows)
                )
                self.assertIn(expected, rows["DEPENDANT-SUMMARY"]["answer"])
                self.assertIn(expected, self.phi_evidence_text(payload))

        wrapped = self.payload(
            {
                "private_health_medicare": {
                    "dependant_count": 1,
                    "dependants": {
                        "items": [self.dependant()],
                        "family_arrangement": "shared arrangement unclear",
                    },
                }
            }
        )
        wrapped_rows = self.rows(wrapped)
        self.assertIn("DEPENDANT-1", wrapped_rows)
        self.assertNotIn("shared arrangement unclear", wrapped_rows["DEPENDANT-1"]["answer"])
        self.assertIn("shared arrangement unclear", wrapped_rows["DEPENDANT-SUMMARY"]["answer"])
        self.assertIn("shared arrangement unclear", self.phi_evidence_text(wrapped))

    def test_typed_scalar_lists_preserve_true_status_without_false_defaults(self) -> None:
        true_payload = self.payload(
            {
                "private_health_medicare": {
                    "private_health": [True],
                    "spouse": [True],
                }
            }
        )
        true_rows = self.rows(true_payload)

        self.assertIn("true", true_rows["PHI-OVERVIEW"]["answer"].lower())
        self.assertIn("true", true_rows["SPOUSE-REVIEW"]["answer"].lower())

        false_payload = self.payload(
            {
                "private_health_medicare": {
                    "private_health": [False],
                    "spouse": [False],
                }
            }
        )
        self.assertEqual([], self.private_health_rows(false_payload))
        self.assertEqual([], self.phi_evidence(false_payload))

    def test_no_cover_with_statement_and_no_spouse_with_income_are_contradictions(self) -> None:
        cases = (
            (
                {
                    "private_health_medicare": {
                        "private_health": {
                            "covered": False,
                            "days_covered": 0,
                        },
                        "statements": [self.statement()],
                        "spouse": False,
                        "dependant_count": 0,
                    }
                },
                ("no-cover", "statement"),
            ),
            (
                {
                    "private_health_medicare": {
                        "private_health": False,
                        "spouse": {
                            "had_spouse": False,
                            "period_start": "2025-07-01",
                            "period_end": "2026-06-30",
                            "income_for_tests": 50000,
                            "income_evidence": "spouse statement held",
                        },
                        "dependant_count": 0,
                    }
                },
                ("no-spouse", "income"),
            ),
        )
        for answers, expected_terms in cases:
            with self.subTest(expected_terms=expected_terms):
                evidence = self.phi_evidence_text(self.payload(answers))

                for expected in expected_terms:
                    self.assertIn(expected, evidence)

    def test_day_count_ranges_are_enforced(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": {
                    "covered": True,
                    "days_covered": 367,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                },
                "statements": [self.statement(days_covered=367)],
                "medicare_levy": {
                    "exemption": True,
                    "exemption_category": "supplied review category",
                    "full_exemption_days": 367,
                    "evidence": "certificate held",
                },
                "mls": {
                    "appropriate_hospital_cover": True,
                    "hospital_cover_days": 367,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "evidence": "policy held",
                },
                "spouse": False,
                "dependant_count": 0,
            }
        }
        evidence = self.phi_evidence_text(self.payload(answers))

        self.assertIn("367", evidence)
        self.assertIn("full exemption days", evidence)
        self.assert_contains_any(
            evidence,
            "cover days",
            "hospital cover days",
            "hospital cover period days",
        )

    def test_mls_cover_and_not_liable_days_must_reconcile(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": {
                    "covered": True,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "days_covered": 300,
                    "evidence": "policy held",
                },
                "mls": {
                    "appropriate_hospital_cover": True,
                    "hospital_cover_days": 300,
                    "days_not_liable": 100,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "evidence": "policy held",
                },
                "spouse": False,
                "dependant_count": 0,
            }
        }
        evidence = self.phi_evidence_text(self.payload(answers))

        self.assert_contains_any(evidence, "reconcile", "days not liable", "total cover")

    def test_dependant_count_age_and_shared_care_ranges_are_enforced(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependant_count": -1,
                "dependants": [
                    self.dependant(
                        "Range Child",
                        age=-1,
                        shared_care=101,
                    )
                ],
            }
        }
        evidence = self.phi_evidence_text(self.payload(answers))

        self.assert_contains_any(evidence, "dependant count", "dependant_count")
        self.assertIn("dependant age (-1)", evidence)
        self.assertIn("shared care", evidence)

    def test_dependant_type_labels_are_validated(self) -> None:
        allowed_dependant_types = ("child", "student", "full-time student", "dependent child")
        for dependant_type in allowed_dependant_types:
            with self.subTest(dependant_type=dependant_type):
                answers = {
                    "private_health_medicare": {
                        "private_health": False,
                        "spouse": False,
                        "dependant_count": 1,
                        "dependants": [self.dependant(type=dependant_type)],
                    }
                }
                evidence = self.phi_evidence_text(self.payload(answers))

                self.assertNotIn("confirm dependant child or student type", evidence)

        invalid_dependant = self.payload(
            {
                "private_health_medicare": {
                    "private_health": False,
                    "spouse": False,
                    "dependant_count": 1,
                    "dependants": [self.dependant(type="housemate")],
                }
            }
        )
        self.assertIn("dependant child or student type", self.phi_evidence_text(invalid_dependant))

    def test_mls_tier_labels_are_validated(self) -> None:
        for tier in ("base tier", "tier 1", "tier 2", "tier 3"):
            with self.subTest(tier=tier):
                answers = {
                    "private_health_medicare": {
                        "mls": {
                            "appropriate_hospital_cover": False,
                            "income_for_surcharge": 0,
                            "income_tier": tier,
                            "evidence": "review records held",
                        }
                    }
                }
                evidence = self.phi_evidence_text(self.payload(answers))

                self.assertNotIn("confirm medicare levy surcharge income tier", evidence)

        invalid_tier = self.payload(
            {
                "private_health_medicare": {
                    "mls": {
                        "appropriate_hospital_cover": False,
                        "income_for_surcharge": 0,
                        "income_tier": "platinum tier",
                        "evidence": "review records held",
                    }
                }
            }
        )
        self.assertIn("medicare levy surcharge income tier", self.phi_evidence_text(invalid_tier))

    def test_all_source_url_aliases_and_mls_paying_source_render_in_html(self) -> None:
        for alias in ("source_url", "source_urls", "sources"):
            with self.subTest(alias=alias):
                custom_url = f"https://example.test/{alias.replace('_', '-')}"
                supplied: Any = [custom_url] if alias in {"source_urls", "sources"} else custom_url
                answers = {
                    "private_health_medicare": {
                        "mls": {
                            "appropriate_hospital_cover": False,
                            "income_for_surcharge": 0,
                            "income_tier": "base tier",
                            "evidence": "review records held",
                            alias: supplied,
                        }
                    }
                }
                payload = self.payload(answers)
                row = self.rows(payload)["MLS-REVIEW"]
                body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

                self.assertIn(custom_url, row["source_urls"])
                self.assertIn(taxmate_intake.ATO_MLS_PAYING_SOURCE, row["source_urls"])
                self.assertIn(custom_url, body)
                self.assertIn(taxmate_intake.ATO_MLS_PAYING_SOURCE, body)

        statement_source = "https://example.test/statement-source"
        levy_source = "https://example.test/levy-source"
        spouse_source = "https://example.test/spouse-source"
        dependant_source = "https://example.test/dependant-source"
        private_health = self.private_health(
            statements=[self.statement(source_url=statement_source)],
            medicare_levy={
                "reduction": True,
                "evidence": "certificate held",
                "sources": [levy_source],
            },
            spouse={
                "had_spouse": True,
                "period_start": "2025-07-01",
                "period_end": "2026-06-30",
                "income_for_tests": 0,
                "income_evidence": "statement held",
                "source_urls": [spouse_source],
            },
            dependant_count=1,
            dependants=[self.dependant(source_url=dependant_source)],
        )
        payload = self.payload({"private_health_medicare": private_health})
        rows = self.rows(payload)
        body = taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))

        expected = {
            "PHI-STMT-1": statement_source,
            "MEDICARE-LEVY": levy_source,
            "SPOUSE-REVIEW": spouse_source,
            "DEPENDANT-1": dependant_source,
        }
        for number, url in expected.items():
            with self.subTest(number=number):
                self.assertIn(url, rows[number]["source_urls"])
                self.assertIn(url, body)

    def test_recursive_provenance_values_reach_matching_row(self) -> None:
        nested_source = "https://example.test/nested-cover-source"
        nested_source_two = "https://example.test/nested-cover-source-two"
        nested_payload = self.payload(
            {
                "private_health_medicare": {
                    "private_health": {
                        "covered": True,
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "days_covered": 365,
                        "evidence": "policy held",
                        "source_urls": [
                            "n/a",
                            [nested_source],
                            {"value": nested_source_two},
                        ],
                        "checked_at": ["none", ["2026-07-10"]],
                    }
                }
            }
        )
        nested_overview = self.rows(nested_payload)["PHI-OVERVIEW"]
        self.assertTrue(
            {nested_source, nested_source_two}.issubset(set(nested_overview["source_urls"]))
        )
        self.assertIn("2026-07-10", nested_overview["answer"])
        self.assertNotIn("n/a", nested_overview["answer"].lower())

    def test_supplemental_provenance_reaches_matching_rows(self) -> None:
        statement_cases = (
            (
                {
                    "items": [],
                    "annual_split": "statement split unclear",
                    "source_url": "https://example.test/statement-supplement",
                    "checked_at": "2026-07-10",
                },
                "https://example.test/statement-supplement",
            ),
            (
                {
                    "items": [
                        {
                            "notes": "statement facts unclear",
                            "source_url": "https://example.test/statement-item-supplement",
                            "checked_at": "2026-07-10",
                        }
                    ]
                },
                "https://example.test/statement-item-supplement",
            ),
        )
        for statements, source in statement_cases:
            with self.subTest(statements=statements):
                payload = self.payload(
                    {
                        "private_health_medicare": {
                            "statements": statements,
                        }
                    }
                )
                rows = self.rows(payload)

                self.assertFalse(any(number.startswith("PHI-STMT-") for number in rows))
                self.assertIn(source, rows["PHI-OVERVIEW"]["source_urls"])
                self.assertIn("2026-07-10", rows["PHI-OVERVIEW"]["answer"])
                self.assertTrue(
                    any(source in row["source_urls"] for row in self.phi_evidence(payload))
                )

        dependant_cases = (
            (
                {
                    "items": [],
                    "family_arrangement": "family arrangement unclear",
                    "source_url": "https://example.test/dependant-supplement",
                    "checked_at": "2026-07-10",
                },
                "https://example.test/dependant-supplement",
            ),
            (
                [
                    {
                        "notes": "child facts unclear",
                        "source_url": "https://example.test/dependant-item-supplement",
                        "checked_at": "2026-07-10",
                    }
                ],
                "https://example.test/dependant-item-supplement",
            ),
        )
        for dependants, source in dependant_cases:
            with self.subTest(dependants=dependants):
                payload = self.payload(
                    {
                        "private_health_medicare": {
                            "dependants": dependants,
                        }
                    }
                )
                rows = self.rows(payload)

                self.assertFalse(any(re.fullmatch(r"DEPENDANT-\d+", number) for number in rows))
                self.assertIn(source, rows["DEPENDANT-SUMMARY"]["source_urls"])
                self.assertIn("2026-07-10", rows["DEPENDANT-SUMMARY"]["answer"])
                self.assertTrue(
                    any(source in row["source_urls"] for row in self.phi_evidence(payload))
                )

    def test_supplemental_provenance_isolated_by_branch(self) -> None:
        statement_item_source = "https://example.test/statement-item"
        statement_supplement_source = "https://example.test/statement-supplement-only"
        statement_payload = self.payload(
            {
                "private_health_medicare": {
                    "statements": [
                        self.statement(
                            source_url=statement_item_source,
                            checked_at="2026-07-09",
                        ),
                        {
                            "notes": "separate statement facts unclear",
                            "source_url": statement_supplement_source,
                            "checked_at": "2026-07-10",
                        },
                    ]
                }
            }
        )
        statement_rows = self.rows(statement_payload)
        self.assertIn(statement_item_source, statement_rows["PHI-STMT-1"]["source_urls"])
        self.assertNotIn(
            statement_supplement_source,
            statement_rows["PHI-STMT-1"]["source_urls"],
        )
        self.assertIn(
            statement_supplement_source,
            statement_rows["PHI-OVERVIEW"]["source_urls"],
        )
        self.assertNotIn(
            statement_item_source,
            statement_rows["PHI-OVERVIEW"]["source_urls"],
        )
        self.assertIn("2026-07-10", statement_rows["PHI-OVERVIEW"]["answer"])
        self.assertNotIn("2026-07-09", statement_rows["PHI-OVERVIEW"]["answer"])

        dependant_item_source = "https://example.test/dependant-item"
        dependant_supplement_source = "https://example.test/dependant-supplement-only"
        dependant_payload = self.payload(
            {
                "private_health_medicare": {
                    "dependants": [
                        self.dependant(
                            source_url=dependant_item_source,
                            checked_at="2026-07-09",
                        ),
                        {
                            "notes": "separate dependant facts unclear",
                            "source_url": dependant_supplement_source,
                            "checked_at": "2026-07-10",
                        },
                    ]
                }
            }
        )
        dependant_rows = self.rows(dependant_payload)
        self.assertIn(dependant_item_source, dependant_rows["DEPENDANT-1"]["source_urls"])
        self.assertNotIn(
            dependant_supplement_source,
            dependant_rows["DEPENDANT-1"]["source_urls"],
        )
        self.assertIn(
            dependant_supplement_source,
            dependant_rows["DEPENDANT-SUMMARY"]["source_urls"],
        )
        self.assertNotIn(
            dependant_item_source,
            dependant_rows["DEPENDANT-SUMMARY"]["source_urls"],
        )
        self.assertIn("2026-07-10", dependant_rows["DEPENDANT-SUMMARY"]["answer"])
        self.assertNotIn("2026-07-09", dependant_rows["DEPENDANT-SUMMARY"]["answer"])

    def test_medicare_wrapper_metadata_follows_nested_or_supplemental_facts(self) -> None:
        source = "https://example.test/medicare-wrapper"
        checked_at = "2026-07-10"
        cases = (
            (
                {
                    "levy": {
                        "exemption": True,
                        "exemption_category": "supplied review category",
                        "full_exemption_days": 0,
                        "evidence": "certificate held",
                    },
                    "source_url": source,
                    "checked_at": checked_at,
                },
                "MEDICARE-LEVY",
                False,
            ),
            (
                {
                    "mls": {
                        "review": True,
                        "appropriate_hospital_cover": False,
                        "income_for_surcharge": 0,
                        "income_tier": "base tier",
                        "evidence": "review records held",
                    },
                    "source_url": source,
                    "checked_at": checked_at,
                },
                "MLS-REVIEW",
                False,
            ),
            (
                {
                    "custom": "Medicare wrapper facts unclear",
                    "source_url": source,
                    "checked_at": checked_at,
                },
                "PHI-OVERVIEW",
                True,
            ),
        )
        for medicare, number, overview_expected in cases:
            with self.subTest(number=number):
                payload = self.payload(
                    {
                        "private_health_medicare": {
                            "medicare": medicare,
                        }
                    }
                )
                rows = self.rows(payload)

                self.assertEqual(overview_expected, "PHI-OVERVIEW" in rows)
                self.assertIn(source, rows[number]["source_urls"])
                self.assertIn(checked_at, rows[number]["answer"])

        false_metadata = self.payload(
            {
                "private_health_medicare": {
                    "medicare": {
                        "custom": "Medicare wrapper facts unclear",
                        "source_url": [False],
                        "checked_at": [False],
                    }
                }
            }
        )
        false_answer = self.rows(false_metadata)["PHI-OVERVIEW"]["answer"].lower()
        self.assertIn("medicare wrapper facts unclear", false_answer)
        self.assertNotIn("source_url", false_answer)
        self.assertNotIn("checked_at", false_answer)
        self.assertNotIn("false", false_answer)

    def test_workflow_metadata_is_preserved_only_with_substantive_facts(self) -> None:
        source_url = "https://example.test/workflow-source"
        checked_at = "2026-07-10"
        substantive = {
            "private_health_medicare": {
                "private_health_cover": True,
                "cover_start": "2025-07-01",
                "cover_end": "2026-06-30",
                "days_covered": 365,
                "cover_evidence": "policy held",
                "source_url": source_url,
                "checked_at": checked_at,
            }
        }
        overview = self.rows(self.payload(substantive))["PHI-OVERVIEW"]

        self.assertIn(source_url, overview["source_urls"])
        self.assertIn(checked_at, overview["answer"])
        self.assertNotIn("supplemental facts", overview["answer"])

        metadata_only = self.payload(
            {
                "private_health_medicare": {
                    "source_url": source_url,
                    "checked_at": checked_at,
                }
            }
        )
        self.assertEqual([], self.private_health_rows(metadata_only))
        self.assertEqual([], self.phi_evidence(metadata_only))

    def test_recursive_and_wrapped_statement_denials_stay_in_evidence(self) -> None:
        cases: tuple[tuple[Any, tuple[str, ...], bool], ...] = (
            (
                [["statement not received", ["do not have statement"]]],
                ("statement not received", "do not have statement"),
                False,
            ),
            (
                [self.statement(insurer="Valid Health"), ["statement not supplied"]],
                ("statement not supplied",),
                True,
            ),
            (
                {"items": ["statement not available"]},
                ("statement not available",),
                False,
            ),
            (
                {"rows": [["dont have statement"]]},
                ("dont have statement",),
                False,
            ),
        )
        for statements, denials, has_valid_statement in cases:
            with self.subTest(statements=statements):
                private_health = self.private_health(statements=statements)
                payload = self.payload({"private_health_medicare": private_health})
                evidence = self.phi_evidence_text(payload)

                for denial in denials:
                    self.assertIn(denial, evidence)
                valid_rows = [
                    row
                    for row in self.private_health_rows(payload)
                    if str(row["number"]).startswith("PHI-STMT-")
                    and "Valid Health" in row["answer"]
                ]
                self.assertEqual(has_valid_statement, bool(valid_rows))

    def test_tied_statement_identity_supplement_is_preserved_separately(self) -> None:
        first = self.statement(
            insurer="Twin Health",
            membership_id="TWIN-1",
            premiums_eligible_for_rebate=100,
            rebate_received=10,
        )
        second = self.statement(
            insurer="Twin Health",
            membership_id="TWIN-1",
            premiums_eligible_for_rebate=200,
            rebate_received=20,
        )
        answers = {
            "private_health_medicare": self.private_health(
                statements=[first, second],
                statement_rows=[
                    {
                        "insurer": "Twin Health",
                        "membership_id": "TWIN-1",
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "notes": "ambiguous statement supplement",
                    }
                ],
            )
        }
        rows = self.rows(self.payload(answers))
        statement_rows = [
            rows[number]
            for number in sorted(rows)
            if number.startswith("PHI-STMT-")
        ]

        self.assertEqual(3, len(statement_rows))
        self.assertNotIn("ambiguous statement supplement", statement_rows[0]["answer"])
        self.assertNotIn("ambiguous statement supplement", statement_rows[1]["answer"])
        self.assertIn("ambiguous statement supplement", statement_rows[2]["answer"])

    def test_tied_dependant_identity_supplement_is_preserved_separately(self) -> None:
        answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependant_count": 3,
                "dependants": [
                    self.dependant("Twin Child", age=10),
                    self.dependant("Twin Child", age=12),
                ],
                "dependents": [
                    {
                        "name": "Twin Child",
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "notes": "ambiguous dependant supplement",
                    }
                ],
            }
        }
        rows = self.rows(self.payload(answers))
        dependant_rows = [
            rows[number]
            for number in sorted(rows)
            if re.fullmatch(r"DEPENDANT-\d+", number)
        ]

        self.assertEqual(3, len(dependant_rows))
        self.assertNotIn("ambiguous dependant supplement", dependant_rows[0]["answer"])
        self.assertNotIn("ambiguous dependant supplement", dependant_rows[1]["answer"])
        self.assertIn("ambiguous dependant supplement", dependant_rows[2]["answer"])

    def test_statement_interval_overlap_gap_wrong_year_and_overview_bounds_are_evidence(self) -> None:
        def covered_period(statements: list[dict[str, Any]], **updates: Any) -> dict[str, Any]:
            private_health: dict[str, Any] = {
                "private_health_cover": True,
                "cover_start": "2025-07-01",
                "cover_end": "2026-06-30",
                "days_covered": 365,
                "cover_evidence": "policy held",
                "statements": statements,
                "spouse_had": False,
                "dependant_children": 0,
            }
            private_health.update(updates)
            return private_health

        cases = (
            (
                "overlap",
                covered_period(
                    [
                        self.statement(
                            insurer="Overlap One",
                            membership_id="OVERLAP-1",
                            period_start="2025-07-01",
                            period_end="2026-01-31",
                            days_covered=215,
                        ),
                        self.statement(
                            insurer="Overlap Two",
                            membership_id="OVERLAP-2",
                            period_start="2026-01-01",
                            period_end="2026-06-30",
                            days_covered=181,
                        ),
                    ]
                ),
                "overlap",
            ),
            (
                "gap",
                covered_period(
                    [
                        self.statement(
                            insurer="Gap One",
                            membership_id="GAP-1",
                            period_start="2025-07-01",
                            period_end="2025-12-31",
                            days_covered=184,
                        ),
                        self.statement(
                            insurer="Gap Two",
                            membership_id="GAP-2",
                            period_start="2026-01-02",
                            period_end="2026-06-30",
                            days_covered=180,
                        ),
                    ]
                ),
                "gap",
            ),
            (
                "wrong income year",
                covered_period(
                    [
                        self.statement(
                            period_start="2024-07-01",
                            period_end="2025-06-30",
                            days_covered=365,
                        )
                    ]
                ),
                "income year",
            ),
            (
                "outside overview",
                covered_period(
                    [self.statement()],
                    cover_start="2025-09-01",
                    cover_end="2026-06-30",
                    days_covered=303,
                ),
                "outside",
            ),
        )
        for label, private_health, expected in cases:
            with self.subTest(label=label):
                evidence = self.phi_evidence_text(
                    self.payload({"private_health_medicare": private_health})
                )

                self.assertIn(expected, evidence)

    def test_explicit_period_dates_and_day_counts_must_match(self) -> None:
        cases = (
            {
                "private_health_cover": True,
                "cover_start": "2025-07-01",
                "cover_end": "2026-06-30",
                "days_covered": 364,
                "cover_evidence": "policy held",
                "statements": [self.statement()],
                "spouse_had": False,
                "dependant_children": 0,
            },
            {
                "private_health_cover": True,
                "cover_start": "2025-07-01",
                "cover_end": "2026-06-30",
                "days_covered": 365,
                "cover_evidence": "policy held",
                "statements": [self.statement(days_covered=364)],
                "spouse_had": False,
                "dependant_children": 0,
            },
        )
        for private_health in cases:
            with self.subTest(private_health=private_health):
                evidence = self.phi_evidence_text(
                    self.payload({"private_health_medicare": private_health})
                )

                self.assertRegex(
                    evidence,
                    r"(?:mismatch|do(?:es)? not match|reconcile[^\n]*(?:date|day))",
                )

    def test_malformed_reversed_nonadjacent_and_impossible_free_text_periods_are_evidence(self) -> None:
        periods = (
            "July 2025 through",
            "2026-25",
            "2025-27",
            "2025-02-30 to 2025-06-30",
            "2026-06-30 to 2025-07-01",
        )
        for period in periods:
            with self.subTest(period=period):
                statement = self.statement()
                statement.pop("period_start")
                statement.pop("period_end")
                statement.pop("days_covered")
                statement["period"] = period
                evidence = self.phi_evidence_text(
                    self.payload(
                        {
                            "private_health_medicare": self.private_health(
                                statements=[statement]
                            )
                        }
                    )
                )

                self.assertIn("statement cover period", evidence)
                self.assertIn(period.lower(), evidence)

    def test_uncertain_statement_evidence_words_require_confirmation(self) -> None:
        for uncertain in (
            "maybe statement held",
            "perhaps statement held",
            "statement evidence unclear",
        ):
            with self.subTest(uncertain=uncertain):
                payload = self.payload(
                    {
                        "private_health_medicare": self.private_health(
                            statements=[self.statement(evidence=uncertain)]
                        )
                    }
                )
                statement = self.rows(payload)["PHI-STMT-1"]

                self.assertIn(uncertain, statement["answer"].lower())
                self.assertIn("statement evidence", self.phi_evidence_text(payload))

    def test_global_generic_aliases_are_isolated_but_workflow_shorthand_is_allowed(self) -> None:
        generic = {
            "covered": True,
            "period_start": "2025-07-01",
            "period_end": "2026-06-30",
            "days_covered": 365,
            "evidence": "generic policy evidence sentinel",
            "statements": [
                self.statement(
                    insurer="Generic Health Sentinel",
                    membership_id="GENERIC-1",
                )
            ],
        }
        global_payload = self.payload(generic)

        self.assertEqual([], self.private_health_rows(global_payload))
        self.assertEqual([], self.phi_evidence(global_payload))

        workflow_payload = self.payload({"private_health_medicare": deepcopy(generic)})
        rows = self.rows(workflow_payload)

        self.assertIn("PHI-OVERVIEW", rows)
        self.assertIn("Private hospital cover true", rows["PHI-OVERVIEW"]["answer"])
        self.assertIn("2025-07-01", rows["PHI-OVERVIEW"]["answer"])
        self.assertIn("365", rows["PHI-OVERVIEW"]["answer"])
        self.assertIn("generic policy evidence sentinel", rows["PHI-OVERVIEW"]["answer"])
        self.assertIn("Generic Health Sentinel", rows["PHI-STMT-1"]["answer"])

    def test_private_health_periods_must_match_requested_income_year(self) -> None:
        prior_year_statement = self.statement(
            period_start="2024-07-01",
            period_end="2025-06-30",
            days_covered=365,
        )
        private_health = self.private_health(
            cover_start="2024-07-01",
            cover_end="2025-06-30",
            days_covered=365,
            statements=[prior_year_statement],
            mls_hospital_cover_days=365,
        )
        payload = self.payload({"private_health_medicare": private_health})
        overview = self.rows(payload)["PHI-OVERVIEW"]["answer"]

        self.assertIn("2024-07-01", overview)
        self.assertIn("income year", self.phi_evidence_text(payload))

    def test_period_representations_and_free_text_intervals_must_reconcile(self) -> None:
        conflicting = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements=[self.statement(period="2024-25")]
                )
            }
        )
        conflicting_text = self.private_health_text(conflicting)

        self.assertIn("2024-25", conflicting_text)
        self.assertIn("period", self.phi_evidence_text(conflicting))

        def text_period_statement(insurer: str, period: str) -> dict[str, Any]:
            statement = self.statement(insurer=insurer, membership_id=insurer, period=period)
            for field in ("period_start", "period_end", "days_covered"):
                statement.pop(field)
            return statement

        cases = (
            (
                "overlap",
                [
                    text_period_statement("Overlap One", "July 2025 to December 2025"),
                    text_period_statement("Overlap Two", "December 2025 to June 2026"),
                ],
            ),
            (
                "gap",
                [
                    text_period_statement("Gap One", "July 2025 to December 2025"),
                    text_period_statement("Gap Two", "February 2026 to June 2026"),
                ],
            ),
        )
        for expected, statements in cases:
            with self.subTest(expected=expected):
                payload = self.payload(
                    {
                        "private_health_medicare": self.private_health(
                            statements=statements
                        )
                    }
                )

                self.assertIn(expected, self.phi_evidence_text(payload))

    def test_unknown_typed_section_facts_remain_in_rows_and_evidence(self) -> None:
        cases = (
            ("private_health", "cover_status_note", "policy lapsed mid-year", "PHI-OVERVIEW"),
            ("medicare_levy", "eligibility", "levy eligibility unclear", "MEDICARE-LEVY"),
            ("mls", "family_status", "MLS family status unclear", "MLS-REVIEW"),
            ("spouse", "relationship_status", "separated during income year", "SPOUSE-REVIEW"),
        )
        for section, key, marker, number in cases:
            with self.subTest(section=section):
                payload = self.payload(
                    {
                        "private_health_medicare": {
                            section: {key: marker},
                        }
                    }
                )
                rows = self.rows(payload)

                self.assertIn(number, rows)
                self.assertIn(marker.lower(), rows[number]["answer"].lower())
                self.assertIn(marker.lower(), self.phi_evidence_text(payload))

    def test_collection_wrappers_preserve_metadata_without_phantom_items(self) -> None:
        statement_source = "https://example.test/statement-wrapper"
        dependant_source = "https://example.test/dependant-wrapper"
        checked_at = "2026-07-10"
        wrapped_statement = self.statement()
        wrapped_statement.pop("insurer")
        wrapped_statement.pop("membership_id")
        private_health = self.private_health(
            statements={
                "insurer": "Wrapper Health",
                "membership_id": "WRAP-1",
                "items": [wrapped_statement],
                "notes": "annual statement wrapper note",
                "source_url": statement_source,
                "checked_at": checked_at,
            },
            dependant_children=1,
            dependants={
                "items": [self.dependant()],
                "source_url": dependant_source,
                "checked_at": checked_at,
            },
        )
        payload = self.payload({"private_health_medicare": private_health})
        rows = self.rows(payload)
        statement_numbers = sorted(number for number in rows if number.startswith("PHI-STMT-"))
        dependant_numbers = sorted(number for number in rows if re.fullmatch(r"DEPENDANT-\d+", number))

        self.assertEqual(["PHI-STMT-1"], statement_numbers)
        self.assertEqual(["DEPENDANT-1"], dependant_numbers)
        self.assertIn("Wrapper Health", rows["PHI-STMT-1"]["answer"])
        self.assertIn("WRAP-1", rows["PHI-STMT-1"]["answer"])
        self.assertIn(statement_source, rows["PHI-STMT-1"]["source_urls"])
        self.assertIn(dependant_source, rows["DEPENDANT-1"]["source_urls"])
        self.assertIn(checked_at, rows["PHI-STMT-1"]["answer"])
        self.assertIn(checked_at, rows["DEPENDANT-1"]["answer"])
        self.assertIn("annual statement wrapper note", self.private_health_text(payload))

    def test_structured_denials_do_not_create_statement_or_dependant_items(self) -> None:
        statement_payload = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements={"evidence": "no statement held"}
                )
            }
        )
        statement_rows = self.rows(statement_payload)

        self.assertFalse(any(number.startswith("PHI-STMT-") for number in statement_rows))
        self.assertIn("no statement held", self.phi_evidence_text(statement_payload))

        dependant_answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependants": {"status": "no dependants"},
            }
        }
        raw = taxmate_intake.private_health_medicare_answers(dependant_answers)
        dependant_payload = self.payload(dependant_answers)
        dependant_rows = self.rows(dependant_payload)

        self.assertFalse(any(re.fullmatch(r"DEPENDANT-\d+", number) for number in dependant_rows))
        self.assertTrue(
            raw["dependant_children"] == 0
            or "no dependants" in self.private_health_text(dependant_payload)
        )

        contradictory_answers = {
            "private_health_medicare": {
                "private_health": False,
                "spouse": False,
                "dependants": {
                    "status": "no dependants",
                    "items": [self.dependant()],
                },
            }
        }
        contradictory_payload = self.payload(contradictory_answers)

        self.assertIn("DEPENDANT-1", self.rows(contradictory_payload))
        self.assertIn("reconcile dependant count 0 with 1 item rows", self.phi_evidence_text(contradictory_payload))

    def test_conflicting_checked_at_aliases_remain_visible_and_queued(self) -> None:
        statement = self.statement(
            checked_at="2026-07-10",
            source_checked_at="2026-07-09",
            source_url="https://example.test/checked-at-conflict",
        )
        payload = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements=[statement]
                )
            }
        )
        text = self.private_health_text(payload)
        evidence = self.phi_evidence_text(payload)

        self.assertIn("2026-07-10", text)
        self.assertIn("2026-07-09", text)
        self.assertIn("checked", evidence)
        self.assertIn("conflict", evidence)

    def test_zero_exemption_days_do_not_conflict_with_no_exemption(self) -> None:
        payload = self.payload(
            {
                "private_health_medicare": {
                    "medicare_levy": {
                        "reduction": False,
                        "exemption": False,
                        "full_exemption_days": 0,
                        "half_exemption_days": 0,
                        "evidence": "Medicare levy review facts held",
                    }
                }
            }
        )
        row = self.rows(payload)["MEDICARE-LEVY"]

        self.assertIn("full exemption days 0", row["answer"].lower())
        self.assertIn("half exemption days 0", row["answer"].lower())
        self.assertNotIn(
            "no-exemption answer conflicts with exemption days",
            self.phi_evidence_text(payload),
        )

    def test_pending_or_requested_statement_evidence_remains_unresolved(self) -> None:
        for evidence_value in (
            "statement pending",
            "awaiting statement",
            "statement requested",
        ):
            with self.subTest(evidence=evidence_value):
                payload = self.payload(
                    {
                        "private_health_medicare": self.private_health(
                            statements=[self.statement(evidence=evidence_value)]
                        )
                    }
                )

                self.assertIn(evidence_value, self.rows(payload)["PHI-STMT-1"]["answer"])
                self.assertIn("statement evidence", self.phi_evidence_text(payload))

    def test_private_health_overview_fields_do_not_create_statement_rows(self) -> None:
        cases = (
            (
                {
                    "covered": False,
                    "days_covered": 0,
                },
                False,
            ),
            (
                {
                    "covered": True,
                    "period_start": "2025-07-01",
                    "period_end": "2026-06-30",
                    "days_covered": 365,
                    "evidence": "policy held",
                },
                True,
            ),
        )
        for private_health, statement_missing in cases:
            with self.subTest(private_health=private_health):
                answers = {
                    "private_health_medicare": {
                        "private_health": private_health,
                    }
                }
                raw = taxmate_intake.private_health_medicare_answers(
                    {"income_year": "2025-26", **answers}
                )
                payload = self.payload(answers)
                rows = self.rows(payload)
                evidence = self.phi_evidence_text(payload)

                self.assertEqual([], raw["statements"])
                self.assertFalse(any(number.startswith("PHI-STMT-") for number in rows))
                self.assertNotIn("supplied private health statement lines", evidence)
                if statement_missing:
                    self.assertIn("missing private health statement", evidence)

        for covered, days in ((True, 365), (False, 0)):
            with self.subTest(scope="top-level", covered=covered, days=days):
                payload = self.payload(
                    {
                        "private_health_cover": covered,
                        "private_health_days_covered": days,
                        "spouse_had": False,
                        "dependant_children": 0,
                    }
                )
                rows = self.rows(payload)

                self.assertFalse(any(number.startswith("PHI-STMT-") for number in rows))
                self.assertNotIn("supplied private health statement lines", self.phi_evidence_text(payload))

    def test_qualified_or_negative_full_year_periods_remain_unresolved(self) -> None:
        for period in (
            "not full year",
            "full year except June",
            "previous income year",
        ):
            with self.subTest(period=period):
                statement = self.statement(period=period)
                for field in ("period_start", "period_end", "days_covered"):
                    statement.pop(field)
                payload = self.payload(
                    {
                        "private_health_medicare": self.private_health(
                            statements=[statement]
                        )
                    }
                )
                evidence = self.phi_evidence_text(payload)

                self.assertIn(period, self.rows(payload)["PHI-STMT-1"]["answer"])
                self.assertIn("statement cover period", evidence)
                self.assertIn(period.lower(), evidence)

    def test_2025_26_day_counts_and_sums_cannot_exceed_365(self) -> None:
        with self.subTest(area="cover and statement"):
            statement = self.statement(days_covered=366)
            statement.pop("period_start")
            statement.pop("period_end")
            payload = self.payload(
                {
                    "private_health_medicare": {
                        "private_health_cover": True,
                        "days_covered": 366,
                        "cover_evidence": "policy held",
                        "statements": [statement],
                        "spouse_had": False,
                        "dependant_children": 0,
                    }
                }
            )
            evidence = self.phi_evidence_text(payload)

            self.assertIn("366", evidence)
            self.assertIn("private hospital cover", evidence)
            self.assertIn("private health statement", evidence)

        with self.subTest(area="Medicare levy"):
            payload = self.payload(
                {
                    "private_health_medicare": {
                        "medicare_levy": {
                            "exemption": True,
                            "exemption_category": "supplied review category",
                            "full_exemption_days": 365,
                            "half_exemption_days": 1,
                            "evidence": "certificate held",
                        }
                    }
                }
            )

            self.assertIn("exemption days exceed", self.phi_evidence_text(payload))

        with self.subTest(area="Medicare levy surcharge"):
            payload = self.payload(
                {
                    "private_health_medicare": {
                        "mls": {
                            "appropriate_hospital_cover": True,
                            "income_for_surcharge": 100000,
                            "income_tier": "base tier",
                            "hospital_cover_days": 365,
                            "days_not_liable": 1,
                            "period_start": "2025-07-01",
                            "period_end": "2026-06-30",
                            "evidence": "policy held",
                        }
                    }
                }
            )

            self.assertIn(
                "hospital cover days and days not liable exceed",
                self.phi_evidence_text(payload),
            )

    def test_evidence_only_statement_wrapper_preserves_unresolved_value(self) -> None:
        for unresolved in (False, "not held", "statement pending"):
            with self.subTest(unresolved=unresolved):
                payload = self.payload(
                    {
                        "private_health_medicare": self.private_health(
                            statements={"evidence": unresolved}
                        )
                    }
                )
                rows = self.rows(payload)
                evidence = self.phi_evidence_text(payload)

                self.assertFalse(any(number.startswith("PHI-STMT-") for number in rows))
                self.assertIn("missing private health statement", evidence)
                self.assertIn(str(unresolved).lower(), evidence)

    def test_statement_wrapper_notes_survive_without_phantom_rows(self) -> None:
        cases = (
            (True, {"notes": "annual statement split unclear"}, "annual statement split unclear"),
            (True, {"evidence": "statement held"}, "statement held"),
            (False, {"evidence": "statement held"}, "statement held"),
        )
        for covered, statements, expected in cases:
            with self.subTest(covered=covered, statements=statements):
                private_health = {
                    "private_health_cover": covered,
                    "statements": statements,
                    "spouse_had": False,
                    "dependant_children": 0,
                }
                if covered:
                    private_health.update(
                        {
                            "cover_start": "2025-07-01",
                            "cover_end": "2026-06-30",
                            "days_covered": 365,
                        }
                    )
                payload = self.payload({"private_health_medicare": private_health})
                rows = self.rows(payload)

                self.assertFalse(any(number.startswith("PHI-STMT-") for number in rows))
                self.assertIn(expected, self.private_health_text(payload))
                self.assertIn(expected, self.phi_evidence_text(payload))

    def test_statement_wrapper_parent_facts_are_represented_or_reviewed(self) -> None:
        empty_wrapper = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements={"insurer": "Wrapper Health", "items": []}
                )
            }
        )
        self.assertFalse(
            any(number.startswith("PHI-STMT-") for number in self.rows(empty_wrapper))
        )
        self.assertIn("wrapper health", self.private_health_text(empty_wrapper))
        self.assertIn("wrapper health", self.phi_evidence_text(empty_wrapper))

        child = self.statement()
        child.pop("insurer")
        wrapped_child = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements={
                        "insurer": "Wrapper Health",
                        "statement_status": "annual split unclear",
                        "benefit_code": "31",
                        "items": [child],
                    }
                )
            }
        )
        rows = self.rows(wrapped_child)
        statement_numbers = [number for number in rows if number.startswith("PHI-STMT-")]
        self.assertEqual(["PHI-STMT-1"], statement_numbers)
        self.assertIn("Wrapper Health", rows["PHI-STMT-1"]["answer"])
        self.assertIn("annual split unclear", self.phi_evidence_text(wrapped_child))
        self.assertIn("31", self.phi_evidence_text(wrapped_child))

        denied_wrapper = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements={"evidence": False, "items": [self.statement()]}
                )
            }
        )
        self.assertIn("false", self.phi_evidence_text(denied_wrapper))

        unknown_only = self.payload(
            {
                "private_health_medicare": self.private_health(
                    statements={"statement_status": "annual split unclear"}
                )
            }
        )
        self.assertFalse(
            any(number.startswith("PHI-STMT-") for number in self.rows(unknown_only))
        )
        self.assertIn("annual split unclear", self.phi_evidence_text(unknown_only))

    def test_prefixed_partial_statement_fields_survive_typed_private_health_section(self) -> None:
        payload = self.payload(
            {
                "private_health_medicare": {
                    "private_health": {
                        "covered": True,
                        "period_start": "2025-07-01",
                        "period_end": "2026-06-30",
                        "days_covered": 365,
                        "private_health_statement_days_covered": 365,
                        "private_health_statement_period": "2025-26",
                        "private_health_statement_evidence": "statement pending",
                    }
                }
            }
        )
        statement = self.rows(payload)["PHI-STMT-1"]

        self.assertIn("days covered 365", statement["answer"].lower())
        self.assertIn("period 2025-26", statement["answer"].lower())
        self.assertIn("statement pending", statement["answer"].lower())
        self.assertIn("statement evidence", self.phi_evidence_text(payload))

    def test_prefixed_evidence_only_statement_fact_is_preserved_without_phantom_row(self) -> None:
        payload = self.payload(
            {
                "private_health_cover": True,
                "private_health_days_covered": 365,
                "private_health_statement_evidence": "statement pending",
                "spouse_had": False,
                "dependant_children": 0,
            }
        )
        rows = self.rows(payload)

        self.assertFalse(any(number.startswith("PHI-STMT-") for number in rows))
        self.assertIn("statement pending", self.private_health_text(payload))
        self.assertIn("statement pending", self.phi_evidence_text(payload))

        scalar_payload = self.payload(
            {
                "private_health_cover": True,
                "private_health_days_covered": 365,
                "private_health_statements": ["insurer statement pending"],
                "spouse_had": False,
                "dependant_children": 0,
            }
        )

        self.assertFalse(
            any(number.startswith("PHI-STMT-") for number in self.rows(scalar_payload))
        )
        self.assertIn("insurer statement pending", self.phi_evidence_text(scalar_payload))


if __name__ == "__main__":
    unittest.main()
