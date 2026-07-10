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
import taxmate_taxpack  # noqa: E402


def simple_row(number: Any, status: str = "Evidence", source: str = "") -> dict[str, Any]:
    row: dict[str, Any] = {
        "number": number,
        "ato_area": "Other",
        "question": f"Question {number}",
        "answer": f"Answer {number}",
        "why_included": f"Reason {number}",
        "status": status,
        "row_kind": "test-row",
        "facts": [
            {
                "key": "value",
                "label": "Supplied value",
                "value": number,
            }
        ],
    }
    if source:
        row["source_urls"] = [source]
        row["checked_at"] = "2026-07-10"
    return row


def render(payload: dict[str, Any]) -> str:
    return taxmate_taxpack.render_html(taxmate_taxpack.load_guide_payload(payload))


def card_fragment(body: str, number: str) -> str:
    match = re.search(
        rf'<article class="handoff-card[^"]*"[^>]*id="[^"]*{re.escape(number)}"[\s\S]*?</article>',
        body,
    )
    if match is None:
        raise AssertionError(f"card not found: {number}")
    return match.group(0)


def card_fragments(body: str) -> list[str]:
    return re.findall(r'<article class="handoff-card[\s\S]*?</article>', body)


def card_anchors(body: str) -> list[str]:
    return re.findall(r'<article class="handoff-card[^"]*"[^>]*id="([^"]+)"', body)


def context_index_fragment(body: str) -> str:
    match = re.search(
        r'<nav[^>]*class="[^"]*context-index[\s\S]*?</nav>'
        r'|<details[^>]*class="[^"]*context-index[\s\S]*?</details>',
        body,
    )
    if match is None:
        raise AssertionError("context index not found")
    return match.group(0)


def review_queue_fragment(body: str) -> str:
    match = re.search(
        r'<section[^>]*class="[^"]*review-callout[\s\S]*?</section>',
        body,
    )
    if match is None:
        raise AssertionError("review-required queue not found")
    return match.group(0)


def all_payload_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("items", "abn_items", "bas_items", "missing_facts", "evidence_items"):
        raw_rows = payload.get(key, [])
        if isinstance(raw_rows, list):
            rows.extend(row for row in raw_rows if isinstance(row, dict))
    raw_extractions = payload.get("extracted_values", [])
    if isinstance(raw_extractions, list):
        rows.extend(row for row in raw_extractions if isinstance(row, dict))
    return rows


class CompactHandoffCardTests(unittest.TestCase):
    def test_uniform_review_card_renders_each_fact_and_action_once(self) -> None:
        body = render(
            {
                "items": [
                    {
                        "number": "COMPACT-1",
                        "ato_area": "Other",
                        "question": "Compact review",
                        "answer": "legacy; answer; must not render",
                        "why_included": "Review reason.",
                        "status": "Accountant review",
                        "row_kind": "test-row",
                        "facts": [
                            {"key": "zero", "label": "Zero supplied", "value": 0},
                            {"key": "false", "label": "False supplied", "value": False},
                            {
                                "key": "record",
                                "label": "Record held",
                                "value": "yes",
                                "action_kind": "retain-evidence",
                            },
                        ],
                    }
                ]
            }
        )
        card = card_fragment(body, "COMPACT-1")

        self.assertIn('class="fact-list"', card)
        self.assertEqual(3, card.count('class="fact-item"'))
        for label in ("Zero supplied", "False supplied", "Record held"):
            with self.subTest(label=label):
                self.assertEqual(1, card.count(label))
        self.assertEqual(
            1,
            card.count(taxmate_handoff.ACTION_TEXT["accountant-handoff-only"]),
        )
        self.assertNotIn("Destination mapping", card)
        self.assertNotIn('class="destination-item"', card)
        self.assertNotIn('class="provenance-block"', card)
        self.assertNotIn("legacy; answer; must not render", card)
        self.assertIn('<span class="fact-value">0</span>', card)
        self.assertIn('<span class="fact-value">false</span>', card)

    def test_renderer_deduplicates_only_exact_duplicate_facts(self) -> None:
        duplicate = {"key": "same", "label": "Same fact", "value": 0}
        row = simple_row("DEDUP-1")
        row["facts"] = [
            duplicate,
            dict(duplicate),
            {"key": "same", "label": "Same fact", "value": 1},
        ]

        card = card_fragment(render({"items": [row]}), "DEDUP-1")

        self.assertEqual(2, card.count('class="fact-item"'))
        self.assertEqual(1, card.count('<span class="fact-value">0</span>'))
        self.assertEqual(1, card.count('<span class="fact-value">1</span>'))

    def test_phi_statement_keeps_field_destinations_with_fact_bullets(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        statement = next(row for row in payload["items"] if row["number"] == "PHI-STMT-1")
        body = render({"income_year": payload["income_year"], "items": [statement]})
        card = card_fragment(body, "PHI-STMT-1")

        self.assertEqual(len(statement["facts"]), card.count('class="fact-item"'))
        for fact in statement["facts"]:
            with self.subTest(key=fact["key"]):
                label = html.escape(str(fact["label"]), quote=True)
                self.assertEqual(
                    1,
                    card.count(f'<span class="fact-label">{label}</span>'),
                )
        self.assertEqual(
            1,
            card.count(taxmate_handoff.ACTION_TEXT["accountant-handoff-only"]),
        )
        self.assertRegex(
            card,
            r'Benefit code[\s\S]*Private health insurance policy details &gt; label L',
        )
        self.assertRegex(card, r'Days covered[\s\S]*Not entered directly')
        self.assertRegex(card, r'Insurer or health fund[\s\S]*Destination requires review')
        self.assertNotIn('class="destination-item"', card)

    def test_phone_output_uses_neutral_duplicate_claim_wording(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(
            {
                "phone": {
                    "context": "employee",
                    "paid_by_user": True,
                    "wfh_method": "fixed-rate",
                    "incidental": {
                        "claim_amount": 0,
                        "work_calls": 10,
                        "work_texts": 5,
                        "basic_records": "held",
                    },
                }
            }
        )
        body = render(payload)

        self.assertIn("duplicate-claim", body.lower())
        self.assertNotIn("double-dip", body.lower())


class GroupedSourceAppendixTests(unittest.TestCase):
    def test_source_appendix_groups_one_url_with_all_row_contexts(self) -> None:
        source = "https://www.ato.gov.au/example-source"
        evidence = simple_row("SRC-2", source=source)
        evidence["checked_at"] = "2026-07-11"

        body = render(
            {
                "items": [simple_row("SRC-1", source=source)],
                "evidence_items": [evidence],
            }
        )
        cards = "".join(card_fragments(body))

        self.assertNotIn(source, cards)
        self.assertEqual(
            1,
            len(re.findall(rf'<span class="source-url">{re.escape(source)}</span>', body)),
        )
        self.assertEqual(1, body.count('class="source-group"'))
        self.assertIn("2026-07-10", body)
        self.assertIn("2026-07-11", body)
        self.assertIn('href="#row-main-1-SRC-1"', body)
        self.assertIn('href="#row-evidence-1-SRC-2"', body)
        self.assertIn("Supporting source", body)

    def test_source_role_does_not_cross_supporting_and_destination_boundaries(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        original = next(row for row in payload["items"] if row["number"] == "PHI-STMT-1")
        mapped_source = next(
            source
            for fact in original["facts"]
            for source in fact["handoff"]["destination"].get("sources", [])
            if source.get("url")
        )
        row = dict(original)
        row["source_urls"] = [mapped_source["url"]]

        body = render({"items": [row]})

        self.assertEqual(
            1,
            len(
                re.findall(
                    rf'<span class="source-url">{re.escape(mapped_source["url"])}</span>',
                    body,
                )
            ),
        )
        destination_urls = {
            str(source["url"])
            for fact in row["facts"]
            for source in fact["handoff"]["destination"].get("sources", [])
            if source.get("url")
        }
        self.assertEqual(len(destination_urls), body.count('class="source-group"'))
        self.assertIn("Supporting source", body)
        self.assertIn("Destination mapping", body)

    def test_source_appendix_is_collapsed_on_screen_and_expanded_for_print(self) -> None:
        body = render(
            {
                "items": [
                    simple_row(
                        "SRC-DETAILS",
                        source="https://www.ato.gov.au/source-details",
                    )
                ]
            }
        )
        tag = re.search(r'<details[^>]*class="[^"]*source-appendix[^"]*"[^>]*>', body)

        self.assertIsNotNone(tag)
        self.assertNotRegex(tag.group(0), r'\sopen(?:\s|=|>)')
        compact = re.sub(r"\s+", "", body)
        self.assertRegex(
            compact,
            r'@mediaprint[\s\S]*details\.source-appendix:not\(\[open\]\)[^}]*display:block',
        )

    def test_source_labels_are_global_and_visible_in_print_markup(self) -> None:
        body = render(
            {
                "items": [
                    simple_row("SOURCE-A", source="https://www.ato.gov.au/source-a"),
                    simple_row("SOURCE-B", source="https://www.ato.gov.au/source-b"),
                ]
            }
        )
        second_card = card_fragment(body, "SOURCE-B")
        second_group = re.search(
            r'<li class="source-group" id="source-2">[\s\S]*?</li></ul></li>',
            body,
        )

        self.assertIn('<a class="source-ref" href="#source-2">Source 2</a>', second_card)
        self.assertNotIn('href="#source-2">Source 1</a>', second_card)
        self.assertIsNotNone(second_group)
        self.assertIn('<span class="source-id">Source 2</span>', second_group.group(0))

    def test_source_context_labels_disambiguate_duplicate_rows_across_sections(self) -> None:
        source = "https://www.ato.gov.au/shared-source"
        duplicate = simple_row("DUP", source=source)
        body = render({"items": [duplicate], "abn_items": [duplicate]})
        group = re.search(
            r'<li class="source-group" id="source-1">[\s\S]*?</li></ul></li>',
            body,
        )

        self.assertIsNotNone(group)
        self.assertIn(
            'href="#row-main-1-DUP">Prepared return items #1: DUP - Question DUP</a>',
            group.group(0),
        )
        self.assertIn(
            'href="#row-abn-1-DUP">ABN preparation #1: DUP - Question DUP</a>',
            group.group(0),
        )


class RendererAnchorAndFallbackTests(unittest.TestCase):
    def test_blank_numbers_fail_closed_to_nonblank_section_context(self) -> None:
        section_keys = {
            "items": "main",
            "abn_items": "abn",
            "bas_items": "bas",
            "missing_facts": "missing",
            "evidence_items": "evidence",
        }
        for payload_key, anchor_key in section_keys.items():
            with self.subTest(section=payload_key):
                row = simple_row("TEMP")
                row.pop("number")
                try:
                    body = render({payload_key: [row]})
                except Exception as exc:  # pragma: no cover - red contract diagnostic
                    self.fail(f"blank {payload_key} number raised {type(exc).__name__}: {exc}")
                badge = re.search(r'<span class="row-number">([^<]+)</span>', body)
                self.assertIsNotNone(badge)
                self.assertTrue(badge.group(1).strip())
                self.assertRegex(body, rf'id="row-{anchor_key}-1-[A-Za-z0-9_-]+"')

    def test_direct_blank_number_uses_visible_fallback_but_falsey_numbers_survive(self) -> None:
        blank = taxmate_taxpack.GuideItem(
            number="",
            ato_area="",
            question="",
            answer=0,
            why_included="",
            source_urls=[],
            checked_at="",
            status="Evidence",
            status_kind="evidence",
            tab_title="",
            tab_text="",
            tab_kind="evidence",
        )
        blank_body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="10 Jul 2026",
                summary_note="Blank row.",
                items=[blank],
            )
        )
        self.assertNotIn('<span class="row-number"></span>', blank_body)
        self.assertNotIn('class="tab-text"></span>', blank_body)
        self.assertIn('id="row-main-1-item"', blank_body)
        self.assertIn('<span class="fact-value">0</span>', blank_body)

        zero_body = render({"items": [simple_row(0)]})
        false_body = render({"items": [simple_row(False)]})
        self.assertIn('id="row-main-1-0"', zero_body)
        self.assertIn('<span class="row-number">0</span>', zero_body)
        self.assertIn('id="row-main-1-false"', false_body)
        self.assertIn('<span class="row-number">false</span>', false_body)

    def test_section_anchors_scale_without_magic_offset_collisions(self) -> None:
        main = [simple_row(f"MAIN-{index}") for index in range(1, 202)]
        main[-1]["number"] = "DUP"
        body = render({"items": main, "abn_items": [simple_row("DUP")]})
        anchors = card_anchors(body)

        self.assertEqual(len(anchors), len(set(anchors)))
        self.assertIn("row-main-201-DUP", anchors)
        self.assertIn("row-abn-1-DUP", anchors)

    def test_item_index_order_matches_card_dom_order(self) -> None:
        body = render(
            {
                "items": [simple_row("MAIN-1")],
                "extracted_values": [
                    {
                        "number": "AI-1",
                        "field": "Gross",
                        "value": 0,
                        "confirmed": False,
                    }
                ],
                "evidence_items": [simple_row("EVID-1")],
            }
        )

        card_order = card_anchors(body)
        index_order = re.findall(r'href="#([^"]+)"', context_index_fragment(body))
        self.assertEqual(card_order, index_order)

    def test_every_internal_link_has_a_unique_valid_target(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = render(payload)
        identifiers = re.findall(r'id="([A-Za-z][A-Za-z0-9_-]*)"', body)
        targets = re.findall(r'href="#([A-Za-z][A-Za-z0-9_-]*)"', body)

        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(set(targets).issubset(set(identifiers)))


class DirectMalformedAndExtendedPathTests(unittest.TestCase):
    def test_direct_constructor_defaults_to_external_row_contract(self) -> None:
        direct = taxmate_taxpack.GuideItem(
            number="DIRECT-DEFAULT",
            ato_area="Other",
            question="Direct item",
            answer=0,
            why_included="Direct constructor.",
            source_urls=[],
            checked_at="",
            status="Evidence",
            status_kind="evidence",
            tab_title="",
            tab_text="",
            tab_kind="evidence",
        )

        self.assertEqual("external-row", direct.row_kind)
        contract = taxmate_taxpack.item_contract(direct, "2025-26")
        self.assertEqual("external-row", contract["row_kind"])

    def test_runtime_status_precedence_controls_direct_and_parsed_rows(self) -> None:
        parsed = taxmate_taxpack.guide_item(
            {
                "number": "PARSED-STATUS",
                "ato_area": "Other",
                "question": "Parsed status",
                "answer": 0,
                "status": "N/A skipped",
                "status_kind": "ATO label",
                "tab_kind": "Used",
            }
        )
        self.assertEqual("answer", parsed.status_kind)
        self.assertEqual("answer", parsed.tab_kind)

        direct = taxmate_taxpack.GuideItem(
            number="DIRECT-STATUS",
            ato_area="Other",
            question="Direct status",
            answer=False,
            why_included="Direct precedence.",
            source_urls=[],
            checked_at="",
            status="N/A skipped",
            status_kind="answer",
            tab_title="",
            tab_text="",
            tab_kind="evidence",
        )
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="10 Jul 2026",
                summary_note="Status precedence.",
                items=[direct],
            )
        )
        card = card_fragment(body, "DIRECT-STATUS")
        self.assertIn('data-status="evidence"', card)
        self.assertIn('data-review-required="false"', card)
        self.assertIn('<span class="status gap">Evidence</span>', card)
        self.assertIn("Resolve before entry", card)

    def test_direct_malformed_extractions_use_shared_fail_closed_contract(self) -> None:
        body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="10 Jul 2026",
                summary_note="Direct malformed extractions.",
                items=[],
                extracted_values=[False, 0, ["bad extraction"]],
            )
        )
        cards = card_fragments(body)

        self.assertEqual(3, len(cards))
        for index, card in enumerate(cards, start=1):
            with self.subTest(index=index):
                self.assertIn(f'id="row-ai-{index}-AI-MALFORMED-{index}"', card)
                self.assertIn('data-status="review"', card)
                self.assertIn('data-review-required="true"', card)
                self.assertIn("Accountant handoff only", card)
                self.assertIn("Destination requires review", card)
        self.assertIn('<span class="fact-value">false</span>', body)
        self.assertIn('<span class="fact-value">0</span>', body)
        self.assertIn('<span class="fact-value">bad extraction</span>', body)

    def test_direct_malformed_queue_and_extended_rows_share_the_card_contract(self) -> None:
        direct = taxmate_taxpack.GuideItem(
            number="DIRECT-1",
            ato_area="Other",
            question="Direct item",
            answer=False,
            why_included="Direct construction stays visible.",
            source_urls=[],
            checked_at="",
            status="Accountant review",
            status_kind="review",
            tab_title="Direct",
            tab_text="Direct construction stays visible.",
            tab_kind="review",
        )
        direct_body = taxmate_taxpack.render_html(
            taxmate_taxpack.GuideData(
                income_year="2025-26",
                generated_date="10 Jul 2026",
                summary_note="Direct path.",
                items=[direct],
            )
        )
        direct_card = card_fragment(direct_body, "DIRECT-1")
        self.assertIn("Next action", direct_card)
        self.assertIn('class="fact-list"', direct_card)
        self.assertIn('<span class="fact-value">false</span>', direct_card)

        malformed_body = render({"items": ["bad row"]})
        malformed_cards = card_fragments(malformed_body)
        self.assertEqual(1, len(malformed_cards))
        malformed_card = malformed_cards[0]
        self.assertIn("Accountant handoff only", malformed_card)
        self.assertIn("bad row", malformed_card)

        extended_body = render(
            {
                "abn_items": [simple_row("ABN-X", "Accountant review")],
                "bas_items": [simple_row("BAS-X", "Accountant review")],
                "missing_facts": [simple_row("MISS-X")],
                "evidence_items": [simple_row("EVID-X")],
                "extracted_values": [
                    {
                        "number": "AI-X",
                        "field": "Withheld",
                        "value": 0,
                        "confirmed": False,
                    }
                ],
            }
        )
        for anchor in (
            "row-abn-1-ABN-X",
            "row-bas-1-BAS-X",
            "row-missing-1-MISS-X",
            "row-evidence-1-EVID-X",
            "row-ai-1-AI-X",
        ):
            with self.subTest(anchor=anchor):
                self.assertIn(f'id="{anchor}"', extended_body)
        for card in card_fragments(extended_body):
            self.assertIn("Next action", card)
            self.assertIn('class="fact-list"', card)

    def test_queue_only_payload_renders_without_primary_or_empty_sections(self) -> None:
        body = render({"evidence_items": [simple_row("QUEUE-ONLY")]})

        self.assertIn('id="row-evidence-1-QUEUE-ONLY"', body)
        self.assertIn("Evidence queue", body)
        self.assertIn("Resolve before entry", body)


class OutputOnlyRendererTests(unittest.TestCase):
    def test_taxpack_does_not_construct_handoff_actions_or_destinations(self) -> None:
        source = (ROOT / "scripts/taxmate_taxpack.py").read_text(encoding="utf-8")

        for forbidden in (
            "taxmate_handoff.fact(",
            "action_kind=",
            "destination_key=",
            '"suggested-target"',
            'raw.get("confirmed")',
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        manifest = taxmate_handoff.load_destination_manifest(ROOT)
        for mapping_id in manifest["destinations"]:
            with self.subTest(mapping_id=mapping_id):
                self.assertNotIn(mapping_id, source)
        self.assertIn("taxmate_handoff.normalize_row_contract(", source)
        self.assertIn("taxmate_handoff.normalize_extraction_row(", source)
        self.assertIn("taxmate_handoff.effective_status_kind(", source)
        self.assertNotIn("def is_review_like_key(", source)

    def test_renderer_preserves_runtime_fact_count_without_adding_facts(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        row = next(row for row in payload["items"] if row["number"] == "PHI-STMT-1")
        data = taxmate_taxpack.load_guide_payload({"items": [row]})
        body = taxmate_taxpack.render_html(data)

        self.assertEqual(len(row["facts"]), card_fragment(body, "PHI-STMT-1").count('class="fact-item"'))
        self.assertEqual(
            {fact["key"] for fact in row["facts"]},
            {fact["key"] for fact in data.items[0].facts},
        )


class FilterAndResponsiveContractTests(unittest.TestCase):
    def filter_fixture(self) -> str:
        source = "https://www.ato.gov.au/shared-source"
        return render(
            {
                "items": [
                    simple_row("REV-1", "Accountant review", source),
                    simple_row("DEST-REVIEW-1", "Used", source),
                ],
                "abn_items": [simple_row("SKIP-1", "N/A skipped", source)],
                "evidence_items": [simple_row("EVID-1", "Evidence", source)],
            }
        )

    def test_filters_propagate_to_every_row_context_and_report_count(self) -> None:
        body = self.filter_fixture()

        self.assertRegex(
            body,
            r'<div class="toolbar"[^>]*role="group"[^>]*aria-label="Worksheet filters"',
        )
        self.assertRegex(body, r'class="filter-summary"[^>]*aria-live="polite"')
        buttons = re.findall(r'<button[^>]*data-filter=[^>]+>', body)
        self.assertEqual(3, len(buttons))
        self.assertTrue(all('aria-controls="guide-content"' in button for button in buttons))
        self.assertGreaterEqual(body.count("data-filter-section"), 3)

        destination_review = card_fragment(body, "DEST-REVIEW-1")
        self.assertIn('data-status="answer"', destination_review)
        self.assertIn('data-review-required="true"', destination_review)
        self.assertIn('<span class="status used">Used</span>', destination_review)
        self.assertIn("Destination requires review", destination_review)

        review = review_queue_fragment(body)
        self.assertIn('data-status="review"', review)
        self.assertIn('data-status="answer"', review)
        self.assertNotIn('data-status="evidence"', review)
        self.assertIn("Accountant review queue", review)
        self.assertIn("Destination review queue", review)
        for status in ("review", "evidence", "skipped"):
            with self.subTest(status=status):
                self.assertRegex(
                    body,
                    rf'class="[^"]*source-context[^"]*"[^>]*data-status="{status}"',
                )

        script = re.search(r'<script>([\s\S]*)</script>', body)
        self.assertIsNotNone(script)
        for marker in (
            "data-filter-section",
            "review-list",
            "source-context",
            "source-group",
            "filter-summary",
            "reviewRequired",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, script.group(1))

    def test_review_queue_items_render_status_action_and_destination_contract(self) -> None:
        body = self.filter_fixture()
        queue = review_queue_fragment(body)
        items = re.findall(r'<li class="queue-item"[\s\S]*?</li>', queue)

        self.assertEqual(2, len(items))
        for item in items:
            self.assertIn('data-review-required="true"', item)
            self.assertRegex(item, r'class="queue-action"[^>]*>[\s\S]*\S+[\s\S]*</p>')
            self.assertRegex(item, r'class="queue-destination"[^>]*>[\s\S]*\S+[\s\S]*</div>')
        accountant = next(item for item in items if "REV-1" in item)
        destination = next(item for item in items if "DEST-REVIEW-1" in item)
        self.assertIn('<span class="status review-badge">Accountant review</span>', accountant)
        self.assertIn("Accountant handoff only", accountant)
        self.assertIn('<span class="status used">Used</span>', destination)
        self.assertIn("Destination requires review", destination)

    def test_hash_navigation_reveals_filtered_target_by_id(self) -> None:
        body = self.filter_fixture()
        script = re.search(r'<script>([\s\S]*)</script>', body).group(1)
        compact = re.sub(r"\s+", "", script)

        self.assertIn("document.getElementById", script)
        self.assertIn("hashchange", script)
        self.assertRegex(compact, r'location\.hash[\s\S]*getElementById')
        self.assertNotIn("querySelector(window.location.hash", compact)
        self.assertNotIn("querySelector(location.hash", compact)

    def test_mobile_layout_contract_is_contained_at_375px_and_headless_500px(self) -> None:
        compact = re.sub(r"\s+", "", self.filter_fixture())

        self.assertRegex(
            compact,
            r'@mediascreenand\(max-width:520px\)[\s\S]*?grid-template-columns:repeat\(3,minmax\(0,1fr\)\)',
        )
        self.assertRegex(compact, r'\.toolbarbutton\{[^}]*min-width:0[^}]*width:100%')
        self.assertIn("min-height:44px", compact)
        self.assertRegex(
            compact,
            r'\.toolbarstrong,\.filter-summary\{[^}]*grid-column:1/-1',
        )
        self.assertRegex(compact, r'\.queue-item-head\{[^}]*display:block')
        self.assertRegex(compact, r'\.book\{[^}]*width:100%')
        self.assertRegex(compact, r'\.header\{[^}]*display:block')
        self.assertRegex(compact, r'\.steps,\.taxonomy-list,\.context-indexul\{[^}]*grid-template-columns:1fr')
        self.assertRegex(compact, r'\.handoff-summary\{[^}]*grid-template-columns:1fr')
        self.assertRegex(compact, r'\.meta\{[^}]*min-width:0')
        self.assertRegex(compact, r'\.fact-value[^}]*min-width:0')
        self.assertNotIn("overflow-x:hidden", compact)


class PrintAndEmptySectionContractTests(unittest.TestCase):
    def test_print_restores_filter_and_splits_only_dense_cards(self) -> None:
        dense = simple_row("DENSE-1", "Accountant review")
        dense["facts"] = [
            {"key": f"fact-{index}", "label": f"Fact {index}", "value": index}
            for index in range(1, 13)
        ]
        compact_row = simple_row("SHORT-1", "Accountant review")
        body = render({"items": [dense, compact_row]})
        dense_card = card_fragment(body, "DENSE-1")
        short_card = card_fragment(body, "SHORT-1")
        compact = re.sub(r"\s+", "", body)

        self.assertIn("allow-page-split", dense_card)
        self.assertNotIn("allow-page-split", short_card)
        self.assertIn("print-color-adjust:exact", compact)
        self.assertRegex(
            compact,
            r'\.handoff-card\.allow-page-split\{[^}]*break-inside:auto',
        )
        self.assertRegex(compact, r'\.fact-item\{[^}]*break-inside:avoid')
        self.assertRegex(compact, r'\.queue-item\{[^}]*break-inside:avoid')
        self.assertIn("beforeprint", compact)
        self.assertIn("afterprint", compact)
        self.assertRegex(compact, r'beforeprint[\s\S]*applyFilter\(["\']all["\']\)')
        self.assertRegex(compact, r'afterprint[\s\S]*applyFilter')

    def test_queue_only_output_omits_every_empty_optional_section(self) -> None:
        body = render({"evidence_items": [simple_row("ONLY-EVID")]})

        for absent in (
            "AI extraction confirmation",
            "Prepared return items",
            "ABN preparation",
            "BAS preparation",
            "Missing facts queue",
            "Accountant review queue",
            "Source/provenance appendix",
            "No rows supplied",
            "No items supplied",
            "No review-only items supplied",
        ):
            with self.subTest(absent=absent):
                self.assertNotIn(absent, body)
        self.assertIn("Evidence queue", body)
        self.assertIn("ONLY-EVID", body)

    def test_source_appendix_starts_a_print_page_only_when_present(self) -> None:
        no_source = render({"evidence_items": [simple_row("NO-SOURCE")]})
        with_source = render(
            {
                "items": [
                    simple_row(
                        "WITH-SOURCE",
                        source="https://www.ato.gov.au/print-source",
                    )
                ]
            }
        )

        self.assertNotIn("source-appendix", no_source)
        self.assertIn("source-appendix", with_source)
        compact = re.sub(r"\s+", "", with_source)
        self.assertRegex(compact, r'\.source-appendix\{[^}]*break-before:page')


class TaxonomyLegendAndDensityTests(unittest.TestCase):
    def test_taxonomy_legend_uses_shared_runtime_labels_and_descriptions(self) -> None:
        body = render({"items": [simple_row("LEGEND-1")]})
        legend = re.search(
            r'<details[^>]*class="[^"]*taxonomy-legend[\s\S]*?</details>',
            body,
        )

        self.assertIsNotNone(legend)
        for kind, entry in taxmate_handoff.TAXONOMY.items():
            with self.subTest(kind=kind):
                self.assertIn(entry["label"], legend.group(0))
                self.assertIn(entry["description"], legend.group(0))

    def test_synthetic_output_density_matches_runtime_records(self) -> None:
        payload = taxmate_intake.answers_to_pack_payload(taxmate_intake.sample_answers())
        body = render(payload)
        rows = all_payload_rows(payload)
        expected_facts = sum(len(row["facts"]) for row in rows)
        review_rows = sum(
            taxmate_handoff.status_kind(row.get("status")) == "review"
            for row in rows
        )
        cards = card_fragments(body)

        self.assertEqual(len(rows), len(cards))
        self.assertEqual(expected_facts, body.count('class="fact-item"'))
        self.assertNotIn('class="destination-item"', body)
        self.assertEqual(
            review_rows,
            sum(
                card.count(taxmate_handoff.ACTION_TEXT["accountant-handoff-only"])
                for card in cards
            ),
        )
        lowered = body.lower()
        for forbidden in (
            "manual copy",
            "copy-ready",
            "copy ready",
            "double-dip",
            "double dip",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)
        self.assertIn("user-supplied intake value", body)
        displayed_sources = re.findall(r'<span class="source-url">([^<]*)</span>', body)
        self.assertEqual(len(displayed_sources), len(set(displayed_sources)))
        self.assertLess(len(body.encode("utf-8")), 300_000)
        self.assertLess(max(len(card.encode("utf-8")) for card in cards), 12_000)


if __name__ == "__main__":
    unittest.main()
