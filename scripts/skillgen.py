#!/usr/bin/env python3
"""TaxMate skill generation and source coverage (Python replacement)."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, Iterable, List, Optional, Union

import atodata

GENERATED_MARKER = "Generated from TaxMate Australia source metadata. Verify volatile values before relying on them."
JURISDICTION = "Australia"
EMPTY_CONTENT_HASH_V2 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SOURCE_COVERAGE_FILE = "source_coverage.json"
SKILL_GUARDRAIL_NEEDLES = [
    "Accountant review",
    "Claim candidate",
    "Do not hide income",
    "metadata-only sources",
    "Supported record",
    "Insufficient evidence",
    "Not claimable",
    "Do not lodge",
]

# Statuses
StatusVerified = "verified"
StatusMetadataOnly = "metadata_only"
StatusDuplicate = "duplicate"
StatusExcluded = "excluded"
StatusNeedsReview = "needs_review"


@dataclass
class Topic:
    slug: str
    title: str
    description: str
    signals: List[str]
    use: str
    avoid: str
    keywords: List[str]
    review: List[str]


@dataclass
class Source:
    source_id: str
    url: str
    final_url: str
    title: str
    last_updated: str = ""
    checked_at: str = ""
    content_hash: str = ""
    assigned_skill: str = ""
    reference: str = ""
    duplicate_of: str = ""
    status: str = ""
    reason: str = ""
    assignment_reason: str = ""

    @property
    def SourceID(self) -> str: return self.source_id
    @SourceID.setter
    def SourceID(self, value: str) -> None: self.source_id = value

    @property
    def URL(self) -> str: return self.url
    @URL.setter
    def URL(self, value: str) -> None: self.url = value

    @property
    def FinalURL(self) -> str: return self.final_url
    @FinalURL.setter
    def FinalURL(self, value: str) -> None: self.final_url = value

    @property
    def Title(self) -> str: return self.title
    @Title.setter
    def Title(self, value: str) -> None: self.title = value

    @property
    def LastUpdated(self) -> str: return self.last_updated
    @LastUpdated.setter
    def LastUpdated(self, value: str) -> None: self.last_updated = value

    @property
    def CheckedAt(self) -> str: return self.checked_at
    @CheckedAt.setter
    def CheckedAt(self, value: str) -> None: self.checked_at = value

    @property
    def ContentHash(self) -> str: return self.content_hash
    @ContentHash.setter
    def ContentHash(self, value: str) -> None: self.content_hash = value

    @property
    def AssignedSkill(self) -> str: return self.assigned_skill
    @AssignedSkill.setter
    def AssignedSkill(self, value: str) -> None: self.assigned_skill = value

    @property
    def Reference(self) -> str: return self.reference
    @Reference.setter
    def Reference(self, value: str) -> None: self.reference = value

    @property
    def DuplicateOf(self) -> str: return self.duplicate_of
    @DuplicateOf.setter
    def DuplicateOf(self, value: str) -> None: self.duplicate_of = value

    @property
    def Status(self) -> str: return self.status
    @Status.setter
    def Status(self, value: str) -> None: self.status = value

    @property
    def Reason(self) -> str: return self.reason
    @Reason.setter
    def Reason(self, value: str) -> None: self.reason = value

    @property
    def AssignmentReason(self) -> str: return self.assignment_reason
    @AssignmentReason.setter
    def AssignmentReason(self, value: str) -> None: self.assignment_reason = value


@dataclass
class ValueFact:
    topic: str
    value: str
    unit: str
    context: str
    jurisdiction: str
    income_year: str = ""
    effective_from: str = ""
    effective_to: str = ""
    source_url: str = ""
    source_title: str = ""
    last_updated: str = ""
    checked_at: str = ""
    content_hash: str = ""
    reuse_warning: str = ""

    @property
    def Topic(self) -> str: return self.topic
    @Topic.setter
    def Topic(self, value: str) -> None: self.topic = value

    @property
    def SourceURL(self) -> str: return self.source_url
    @SourceURL.setter
    def SourceURL(self, value: str) -> None: self.source_url = value

    @property
    def SourceTitle(self) -> str: return self.source_title
    @SourceTitle.setter
    def SourceTitle(self, value: str) -> None: self.source_title = value

    @property
    def CheckedAt(self) -> str: return self.checked_at
    @CheckedAt.setter
    def CheckedAt(self, value: str) -> None: self.checked_at = value

    @property
    def ContentHash(self) -> str: return self.content_hash
    @ContentHash.setter
    def ContentHash(self, value: str) -> None: self.content_hash = value

    @property
    def Jurisdiction(self) -> str: return self.jurisdiction
    @Jurisdiction.setter
    def Jurisdiction(self, value: str) -> None: self.jurisdiction = value

    @property
    def IncomeYear(self) -> str: return self.income_year
    @IncomeYear.setter
    def IncomeYear(self, value: str) -> None: self.income_year = value

    @property
    def EffectiveFrom(self) -> str: return self.effective_from
    @EffectiveFrom.setter
    def EffectiveFrom(self, value: str) -> None: self.effective_from = value

    @property
    def EffectiveTo(self) -> str: return self.effective_to
    @EffectiveTo.setter
    def EffectiveTo(self, value: str) -> None: self.effective_to = value

    @property
    def Context(self) -> str: return self.context
    @Context.setter
    def Context(self, value: str) -> None: self.context = value

    @property
    def ReuseWarning(self) -> str: return self.reuse_warning
    @ReuseWarning.setter
    def ReuseWarning(self, value: str) -> None: self.reuse_warning = value


@dataclass
class GenerationReport:
    generated_at: str
    sources: List[Source]

    @property
    def GeneratedAt(self) -> str: return self.generated_at
    @GeneratedAt.setter
    def GeneratedAt(self, value: str) -> None: self.generated_at = value

    @property
    def Sources(self) -> List[Source]: return self.sources
    @Sources.setter
    def Sources(self, value: List[Source]) -> None: self.sources = value


@dataclass
class Options:
    root: str
    output_root: str = ""
    checked_at: str = ""

    @property
    def OutputRoot(self) -> str: return self.output_root
    @OutputRoot.setter
    def OutputRoot(self, value: str) -> None: self.output_root = value

    @property
    def CheckedAt(self) -> str: return self.checked_at
    @CheckedAt.setter
    def CheckedAt(self, value: str) -> None: self.checked_at = value


@dataclass
class SourceCoverageEntry:
    source_id: str
    original_url: str
    canonical_url: str
    title: str
    last_updated: str = ""
    checked_at: str = ""
    content_hash: str = ""
    status: str = ""
    skills: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    covered_concepts: List[str] = field(default_factory=list)
    duplicate_of: str = ""
    duplicate_evidence: str = ""
    reason: str = ""

    @property
    def SourceID(self) -> str: return self.source_id
    @SourceID.setter
    def SourceID(self, value: str) -> None: self.source_id = value

    @property
    def OriginalURL(self) -> str: return self.original_url
    @OriginalURL.setter
    def OriginalURL(self, value: str) -> None: self.original_url = value

    @property
    def CanonicalURL(self) -> str: return self.canonical_url
    @CanonicalURL.setter
    def CanonicalURL(self, value: str) -> None: self.canonical_url = value

    @property
    def Title(self) -> str: return self.title
    @Title.setter
    def Title(self, value: str) -> None: self.title = value

    @property
    def LastUpdated(self) -> str: return self.last_updated
    @LastUpdated.setter
    def LastUpdated(self, value: str) -> None: self.last_updated = value

    @property
    def CheckedAt(self) -> str: return self.checked_at
    @CheckedAt.setter
    def CheckedAt(self, value: str) -> None: self.checked_at = value

    @property
    def ContentHash(self) -> str: return self.content_hash
    @ContentHash.setter
    def ContentHash(self, value: str) -> None: self.content_hash = value

    @property
    def Status(self) -> str: return self.status
    @Status.setter
    def Status(self, value: str) -> None: self.status = value

    @property
    def Skills(self) -> List[str]: return self.skills
    @Skills.setter
    def Skills(self, value: List[str]) -> None: self.skills = value

    @property
    def References(self) -> List[str]: return self.references
    @References.setter
    def References(self, value: List[str]) -> None: self.references = value

    @property
    def CoveredConcepts(self) -> List[str]: return self.covered_concepts
    @CoveredConcepts.setter
    def CoveredConcepts(self, value: List[str]) -> None: self.covered_concepts = value

    @property
    def DuplicateOf(self) -> str: return self.duplicate_of
    @DuplicateOf.setter
    def DuplicateOf(self, value: str) -> None: self.duplicate_of = value

    @property
    def DuplicateEvidence(self) -> str: return self.duplicate_evidence
    @DuplicateEvidence.setter
    def DuplicateEvidence(self, value: str) -> None: self.duplicate_evidence = value

    @property
    def Reason(self) -> str: return self.reason
    @Reason.setter
    def Reason(self, value: str) -> None: self.reason = value


@dataclass
class SourceCoverage:
    sources: List[SourceCoverageEntry] = field(default_factory=list)

    @property
    def Sources(self) -> List[SourceCoverageEntry]:
        return self.sources

    @Sources.setter
    def Sources(self, value: List[SourceCoverageEntry]) -> None:
        self.sources = value


@dataclass
class CoverageSkillState:
    assigned_sources: int = 0
    verified_sources: int = 0
    metadata_only_sources: int = 0
    coverage_status: str = ""

    @property
    def AssignedSources(self) -> int: return self.assigned_sources
    @AssignedSources.setter
    def AssignedSources(self, value: int) -> None: self.assigned_sources = value

    @property
    def VerifiedSources(self) -> int: return self.verified_sources
    @VerifiedSources.setter
    def VerifiedSources(self, value: int) -> None: self.verified_sources = value

    @property
    def MetadataOnlySources(self) -> int: return self.metadata_only_sources
    @MetadataOnlySources.setter
    def MetadataOnlySources(self, value: int) -> None: self.metadata_only_sources = value

    @property
    def CoverageStatus(self) -> str: return self.coverage_status
    @CoverageStatus.setter
    def CoverageStatus(self, value: str) -> None: self.coverage_status = value


@dataclass
class CoverageSummary:
    Total: int = 0
    Verified: int = 0
    MetadataOnly: int = 0
    Duplicate: int = 0
    Excluded: int = 0
    NeedsReview: int = 0
    by_skill: Dict[str, CoverageSkillState] = field(default_factory=dict)
    missing_destination_files: List[str] = field(default_factory=list)
    missing_reverse_provenance: List[str] = field(default_factory=list)
    invalid_hashes: List[str] = field(default_factory=list)
    duplicate_evidence_issues: List[str] = field(default_factory=list)
    duplicate_chain_issues: List[str] = field(default_factory=list)
    required_assignment_missing: List[str] = field(default_factory=list)
    required_verified_missing: List[str] = field(default_factory=list)
    volatile_missing_periods: List[str] = field(default_factory=list)
    skills_missing_guardrail: List[str] = field(default_factory=list)
    not_used_entries: List[str] = field(default_factory=list)
    review_entries: List[str] = field(default_factory=list)
    cgt_coverage: Dict[str, bool] = field(default_factory=dict)

    @property
    def BySkill(self) -> Dict[str, CoverageSkillState]:
        return self.by_skill
    @BySkill.setter
    def BySkill(self, value: Dict[str, CoverageSkillState]) -> None:
        self.by_skill = value

    @property
    def MissingDestinationFiles(self) -> List[str]:
        return self.missing_destination_files
    @MissingDestinationFiles.setter
    def MissingDestinationFiles(self, value: List[str]) -> None:
        self.missing_destination_files = value

    @property
    def MissingReverseProvenance(self) -> List[str]:
        return self.missing_reverse_provenance
    @MissingReverseProvenance.setter
    def MissingReverseProvenance(self, value: List[str]) -> None:
        self.missing_reverse_provenance = value

    @property
    def InvalidHashes(self) -> List[str]:
        return self.invalid_hashes
    @InvalidHashes.setter
    def InvalidHashes(self, value: List[str]) -> None:
        self.invalid_hashes = value

    @property
    def DuplicateEvidenceIssues(self) -> List[str]:
        return self.duplicate_evidence_issues
    @DuplicateEvidenceIssues.setter
    def DuplicateEvidenceIssues(self, value: List[str]) -> None:
        self.duplicate_evidence_issues = value

    @property
    def DuplicateChainIssues(self) -> List[str]:
        return self.duplicate_chain_issues
    @DuplicateChainIssues.setter
    def DuplicateChainIssues(self, value: List[str]) -> None:
        self.duplicate_chain_issues = value

    @property
    def RequiredAssignmentMissing(self) -> List[str]:
        return self.required_assignment_missing
    @RequiredAssignmentMissing.setter
    def RequiredAssignmentMissing(self, value: List[str]) -> None:
        self.required_assignment_missing = value

    @property
    def RequiredVerifiedMissing(self) -> List[str]:
        return self.required_verified_missing
    @RequiredVerifiedMissing.setter
    def RequiredVerifiedMissing(self, value: List[str]) -> None:
        self.required_verified_missing = value

    @property
    def VolatileMissingPeriods(self) -> List[str]:
        return self.volatile_missing_periods
    @VolatileMissingPeriods.setter
    def VolatileMissingPeriods(self, value: List[str]) -> None:
        self.volatile_missing_periods = value

    @property
    def SkillsMissingGuardrail(self) -> List[str]:
        return self.skills_missing_guardrail
    @SkillsMissingGuardrail.setter
    def SkillsMissingGuardrail(self, value: List[str]) -> None:
        self.skills_missing_guardrail = value

    @property
    def NotUsedEntries(self) -> List[str]:
        return self.not_used_entries
    @NotUsedEntries.setter
    def NotUsedEntries(self, value: List[str]) -> None:
        self.not_used_entries = value

    @property
    def ReviewEntries(self) -> List[str]:
        return self.review_entries
    @ReviewEntries.setter
    def ReviewEntries(self, value: List[str]) -> None:
        self.review_entries = value

    @property
    def CGTCoverage(self) -> Dict[str, bool]:
        return self.cgt_coverage
    @CGTCoverage.setter
    def CGTCoverage(self, value: Dict[str, bool]) -> None:
        self.cgt_coverage = value


ApprovedHosts = {
    "ato.gov.au": True,
    "www.ato.gov.au": True,
    "abr.gov.au": True,
    "www.abr.gov.au": True,
}


_topic_cache: Optional[List[Topic]] = None


def topic(slug: str, title: str, desc: str, signals: List[str], use: str, avoid: str, keywords: List[str], review: List[str]) -> Topic:
    return Topic(slug=slug, title=title, description=desc, signals=signals, use=use, avoid=avoid, keywords=keywords, review=review)


def Topics() -> List[Topic]:
    global _topic_cache
    if _topic_cache is not None:
        return _topic_cache
    _topic_cache = [
        topic(
            "employment-deductions",
            "Employment Deductions",
            "Employee income, work-related expenses, records, exclusions, and conservative claim review.",
            ["employee", "salary", "wages", "work-related", "deduction", "allowance", "deductions-you-can-claim", "occupancy"],
            "employee income and work-related deductions",
            "ABN business, GST credits, CGT, FBT, or payroll obligations",
            ["employee", "salary", "wages", "work-related", "deduction", "allowance", "deductions-you-can-claim", "occupancy", "allowances", "travel", "tools", "education", "meals", "records-you-need-to-keep"],
            ["mixed business/private use", "missing evidence", "allowances", "capital items"],
        ),
        topic(
            "work-from-home",
            "Work From Home",
            "Employee and home-business WFH records, fixed/actual methods, covered costs, and conservative review flags.",
            ["work from home", "WFH", "home office", "fixed rate", "actual cost", "occupancy"],
            "work-from-home expenses and evidence",
            "general business deductions not tied to home use",
            ["working-from-home-expenses", "fixed-rate-method", "actual-cost-method", "occupancy-expenses", "home-based-business"],
            ["home occupancy", "main residence", "mixed private use", "method conflicts"],
        ),
        topic(
            "abn-business",
            "ABN Business",
            "Sole trader and small business income, deductions, PSI, business-versus-hobby, losses, and evidence.",
            ["ABN", "sole trader", "business expense", "PSI", "business loss", "hobby"],
            "ABN and business income or expenses",
            "employee-only expenses, GST/BAS lodgment, or CGT disposal calculations",
            ["income-and-deductions-for-business", "assessable-income", "business-deductions", "personal-services-income", "business-losses", "non-commercial", "motor-vehicle"],
            ["pre-revenue", "PSI", "business versus hobby", "non-commercial losses", "capital versus revenue"],
        ),
        topic(
            "gst-bas",
            "GST BAS",
            "GST registration, credits, tax invoices, BAS reporting, PAYG instalment intersections, and guardrails.",
            ["GST", "BAS", "tax invoice", "GST credit", "PAYG instalment"],
            "GST registration, credits, tax invoices, and BAS preparation",
            "income-tax-only employee deductions",
            ["gst", "business-activity-statements-bas", "claiming-gst-credits", "tax-invoices", "when-to-charge-gst", "payg-instalments"],
            ["GST registration", "creditable purpose", "mixed use", "missing tax invoice", "disputed credits"],
        ),
        topic(
            "payg-employer",
            "PAYG Employer",
            "PAYG withholding, STP, TPAR, and employer reporting obligations.",
            ["PAYG withholding", "payroll", "STP", "income statement", "TPAR", "employee"],
            "employer withholding and reporting obligations",
            "personal deduction classification or BAS-only questions",
            ["payg-withholding", "single-touch-payroll", "tax-table", "taxable-payments-annual-report", "super-for-employers", "ordinary-time-earnings"],
            ["payroll obligations", "employee status", "late super", "withholding tables"],
        ),
        topic(
            "capital-gains-tax",
            "Capital Gains Tax",
            "General CGT events, dates, ownership, proceeds, cost base, losses, discounts, and complex review flags.",
            ["CGT", "capital gain", "capital loss", "cost base", "disposal", "CGT event"],
            "general CGT concepts and records",
            "routine employee deductions or GST credits",
            ["capital-gains-tax", "cgt-events", "calculating-your-cgt", "acquiring-cgt-assets", "cost-base", "capital-proceeds", "cgt-discount", "market-valuation"],
            ["main residence", "inherited asset", "rollover", "foreign resident", "related party", "market value substitution"],
        ),
        topic(
            "shares-etfs-managed-funds",
            "Shares ETFs Managed Funds",
            "Shares, ETFs, managed funds, DRP, AMIT, distributions, and investment CGT records.",
            ["shares", "ETF", "managed fund", "AMIT", "DRP", "dividend", "distribution"],
            "shares, ETFs, managed funds, investment income and related CGT records",
            "crypto, rental property, or non-investment CGT",
            ["shares", "similar-investments", "investing-in-shares", "managed-investment", "dividend", "distribution", "trust-non-assessable", "share-buy-backs", "demergers"],
            ["DRP", "AMIT", "trust adjustments", "capital losses", "share trading versus investing"],
        ),
        topic(
            "crypto-assets",
            "Crypto Assets",
            "Crypto disposals, swaps, rewards, transfers, records, and CGT review boundaries.",
            ["crypto", "bitcoin", "wallet", "exchange", "staking", "swap"],
            "crypto asset events and records",
            "shares, ETFs, or non-crypto CGT",
            ["crypto-asset", "keeping-crypto-records", "crypto", "wallet", "staking"],
            ["swaps", "rewards", "lost records", "private wallet transfers", "trader versus investor"],
        ),
        topic(
            "property-rental-cgt",
            "Property Rental CGT",
            "Rental property records, repairs versus capital works, private use, disposal, and property CGT review.",
            ["rental", "property", "holiday home", "main residence", "capital works"],
            "rental property records and property-related CGT",
            "non-property investments or routine employment expenses",
            ["property-and-capital-gains-tax", "residential-rental-properties", "rental-properties", "holiday-homes", "main-residence", "capital-works"],
            ["main residence", "private use", "repairs versus improvements", "inherited property", "related-party transfer"],
        ),
        topic(
            "superannuation",
            "Superannuation",
            "Personal super contributions, caps, SG touchpoints, deductions, and contribution records.",
            ["super", "superannuation", "SG", "contribution", "notice of intent"],
            "super contribution and record questions",
            "BAS, employee deductions, or CGT calculations",
            ["super", "superannuation", "personal-super-contributions", "concessional-contributions", "super-guarantee", "ordinary-time-earnings"],
            ["caps", "SG rates", "payment date", "notice of intent", "Division 293"],
        ),
        topic(
            "private-health-medicare",
            "Private Health Medicare",
            "Private health rebate, Medicare levy, Medicare levy surcharge, and insurer statement records.",
            ["private health", "Medicare", "MLS", "rebate", "health statement"],
            "private health and Medicare levy questions",
            "deductibility of business or employment expenses",
            ["medicare", "private-health-insurance", "medicare-levy", "medicare-levy-surcharge", "private-health-insurance-rebate"],
            ["thresholds", "family status", "dependants", "insurer statement"],
        ),
        topic(
            "records-evidence",
            "Records Evidence",
            "Cross-topic records, receipts, substantiation, logbooks, and evidence gaps.",
            ["receipt", "record", "evidence", "logbook", "invoice", "substantiation"],
            "records and proof standards",
            "topic-specific current rates without source refresh",
            ["records", "records-you-need-to-keep", "tax-invoices", "keeping-good-investment-records", "keeping-crypto-records"],
            ["missing evidence", "altered records", "estimates", "duplicate claims"],
        ),
    ]
    return _topic_cache


def requiredSkillSlugs() -> List[str]:
    return sorted([t.slug for t in Topics()])


@dataclass
class _GenerationRow:
    sources: List[Source] = field(default_factory=list)
    grouped: Dict[str, List[Source]] = field(default_factory=dict)
    values: Dict[str, List[ValueFact]] = field(default_factory=dict)


def Generate(opts: Union[Options, dict]) -> GenerationReport:
    if isinstance(opts, dict):
        opts = Options(**opts)
    if not opts.root:
        raise RuntimeError("missing root")
    if not opts.output_root:
        opts.output_root = opts.root

    previous_coverage: Optional[SourceCoverage] = None
    previous_loaded = False
    try:
        previous_coverage = LoadSourceCoverage(opts.root)
        previous_loaded = True
    except Exception:
        previous_coverage = None

    registry = atodata.LoadRegistry(opts.root)
    checked_at = firstNonEmpty(opts.checked_at, registry.RefreshedAt, registry.FetchedAt)
    if checked_at == "":
        checked_at = "1970-01-01T00:00:00Z"

    report_sources, grouped, values, _ = _build(opts.root, registry, checked_at, previous_loaded, previous_coverage)
    for t in Topics():
        sources = grouped.get(t.slug, [])
        if writeTopic(opts.output_root, opts.root, t, sources, values.get(t.slug, [])) is not None:
            pass

    if writeOutputLayers(opts.output_root) is not None:
        pass

    coverage = BuildSourceCoverage(report_sources)
    WriteSourceCoverage(opts.output_root, coverage)
    if opts.output_root != opts.root:
        src = os.path.join(opts.root, "data", "ato_knowledge_base", "source_registry.json")
        dst = os.path.join(opts.output_root, "data", "ato_knowledge_base", "source_registry.json")
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(src, dst)
    err = ValidateSourceCoverage(opts.output_root)
    if err is not None:
        raise err
    return GenerationReport(generated_at=checked_at, sources=report_sources)


def Validate(root: str) -> None:
    for topic in Topics():
        path = os.path.join(root, "skills", topic.slug, "SKILL.md")
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        for needle in SKILL_GUARDRAIL_NEEDLES:
            if needle not in text:
                raise RuntimeError(f"{topic.slug} missing guardrail {needle!r}")
        if "<html" in text or "<script" in text or "Skip to main content" in text:
            raise RuntimeError(f"{topic.slug} contains webpage shell")
    if (
        os.path.exists(os.path.join(root, "data", "ato_knowledge_base", "raw"))
        or os.path.exists(os.path.join(root, "data", "ato_knowledge_base", "text"))
    ):
        raise RuntimeError("committed raw/text ATO snapshots must be removed")
    err = ValidateSourceCoverage(root)
    if err is not None:
        raise err
    return None


def Top(s: str) -> str:
    return s


def _build(
    root: str,
    registry: atodata.SourceRegistry,
    checked_at: str,
    use_previous: bool,
    previous: Optional[SourceCoverage],
) -> tuple[List[Source], Dict[str, List[Source]], Dict[str, List[ValueFact]], Optional[Exception]]:
    if registry is None:
        return None, {}, {}, RuntimeError("nil registry")

    seen_canonical: Dict[str, str] = {}
    previous_by_id: Dict[str, SourceCoverageEntry] = {}
    if use_previous and previous is not None:
        for entry in previous.sources:
            previous_by_id[entry.source_id] = entry

    sources: List[Source] = []
    grouped: Dict[str, List[Source]] = {}
    values: Dict[str, List[ValueFact]] = {}

    for rec in registry.records:
        canonical = canonicalURL(firstNonEmpty(rec.final_url, rec.url))
        if canonical == "":
            canonical = rec.url
        record_id = sourceID(rec.url, canonical)
        record_text = atodata.RecordText(root, rec).strip()
        record_hash = (rec.content_hash or "").strip()
        text_hash = ""
        content_verified = False
        if record_text != "":
            text_hash = atodata.HashText(record_text)
            content_verified = text_hash != "" and text_hash.lower() != EMPTY_CONTENT_HASH_V2
        content_hash = record_hash
        if text_hash != "":
            content_hash = text_hash

        preserved_verified = False
        if not content_verified and use_previous:
            prev = previous_by_id.get(record_id)
            if prev is not None:
                preserved_verified = (
                    prev.status == StatusVerified
                    and prev.canonical_url.strip() == canonical.strip()
                    and validContentHash(prev.content_hash)
                    and prev.content_hash.strip() == content_hash.strip()
                )

        src = Source(
            source_id=record_id,
            url=rec.url,
            final_url=canonical,
            title=rec.title,
            last_updated=rec.last_updated,
            checked_at=firstNonEmpty(rec.last_checked, checked_at),
            content_hash=content_hash,
            reference="references/rules.md",
        )

        if not HostApproved(canonical):
            src.status = StatusExcluded
            src.reason = "unsupported source host"
            sources.append(src)
            continue

        topic_match, score = assignTopic(rec, record_text)
        if canonical in seen_canonical:
            src.status = StatusDuplicate
            src.duplicate_of = seen_canonical[canonical]
            evidence = "identical canonical URL"
            if validContentHash(content_hash):
                prior = foundInRegistry(registry, src.duplicate_of)
                if prior is not None and prior.content_hash == content_hash:
                    evidence = "identical non-empty content hash"
            src.assignment_reason = evidence
            sources.append(src)
            continue

        seen_canonical[canonical] = record_id

        if score == 0 or firstNonEmpty(topic_match.slug if topic_match else "") == "":
            src.status = StatusMetadataOnly
            src.assignment_reason = "source topic not assigned from metadata"
        elif content_verified:
            src.status = StatusVerified
            src.assigned_skill = topic_match.slug
            src.assignment_reason = "topic match + verified source content"
            grouped.setdefault(topic_match.slug, []).append(src)
            if record_text != "":
                values.setdefault(topic_match.slug, []).extend(detectValues(topic_match.slug, record_text, src))
        elif preserved_verified:
            src.status = StatusVerified
            src.assigned_skill = topic_match.slug
            prev = previous_by_id.get(record_id)
            src.assignment_reason = firstNonEmpty(prev.assignment_reason if prev else "", "verified from previous coverage and unchanged hash")
            grouped.setdefault(topic_match.slug, []).append(src)
        else:
            src.status = StatusMetadataOnly
            src.assigned_skill = topic_match.slug
            src.assignment_reason = "matched topic metadata; source content not extracted"
            grouped.setdefault(topic_match.slug, []).append(src)

        sources.append(src)

    for key in requiredSkillSlugs():
        if key in grouped:
            grouped[key].sort(key=lambda s: s.source_id)
        if key in values:
            values[key].sort(key=lambda x: x.source_url + x.value + x.context)

    for src in sources:
        if src.status != StatusDuplicate:
            seen_canonical[src.final_url] = src.source_id

    return sources, grouped, values, None


def writeTopic(root: str, source_root: str, topic_obj: Topic, sources: List[Source], values: List[ValueFact]) -> None:
    dir_path = os.path.join(root, "skills", topic_obj.slug)
    ref_dir = os.path.join(dir_path, "references")
    os.makedirs(ref_dir, exist_ok=True)
    writeText(os.path.join(dir_path, "SKILL.md"), skillMarkdown(topic_obj))
    writeText(os.path.join(ref_dir, "rules.md"), rulesMarkdown(topic_obj, sources))
    writeText(os.path.join(ref_dir, "evidence.md"), evidenceMarkdown(topic_obj, sources))
    writeJSON(os.path.join(ref_dir, "sources.json"), [_source_to_json(src) for src in sources])

    values = mergeAndFilterValues(source_root, topic_obj.slug, values)
    if len(values) > 0:
        writeJSON(os.path.join(ref_dir, "current-values.json"), [_value_to_json(v) for v in values])
    else:
        try:
            os.remove(os.path.join(ref_dir, "current-values.json"))
        except FileNotFoundError:
            pass


def writeOutputLayers(root: str) -> None:
    for slug in ["workbook", "taxpack"]:
        ref_dir = os.path.join(root, "skills", slug, "references")
        os.makedirs(ref_dir, exist_ok=True)
        body = "# Generated Topic Inputs\n\n"
        body += "Workbook and taxpack are output layers only. They must consume reviewed classifications from topic skills and must not invent tax treatment.\n\n"
        body += "- Preserve `Accountant review` flags.\n- Preserve source URLs and checked-at dates.\n- Do not turn raw transactions into lodging-ready claims from source extracts alone.\n"
        writeText(os.path.join(ref_dir, "topic-inputs.md"), body)


def skillMarkdown(topic_obj: Topic) -> str:
    lines = [
        "---",
        f"name: {topic_obj.slug}",
        f"description: {topic_obj.description}",
        "---",
        "",
        f"# {topic_obj.title}",
        "",
        GENERATED_MARKER,
        "",
        f"Use for {topic_obj.use}. Do not use for {topic_obj.avoid}.",
        "",
        "## Source workflow",
        "",
        "1. Read `references/rules.md` before classifying tax treatment.",
        "2. Read `references/evidence.md` before deciding record status.",
        "3. Check `references/sources.json` for source URLs, checked-at dates, and metadata-only sources.",
        "4. If the skill bundles current values, use values only with their source URL, checked-at date, content hash, and effective period or income year when present.",
        "5. Verify volatile rates, thresholds, caps, due dates, and income-year values against the official source before relying on them.",
        "",
        "## Safety rules",
        "",
        "- Do not fabricate records, source support, source checks, or evidence.",
        "- Do not hide income, omit private use, suppress missing evidence, or remove `Accountant review` flags.",
        "- Do not treat metadata-only sources as source-backed tax treatment without explicit verification.",
        "- Keep ambiguous, mixed-use, stale, unsupported, or material uncertainty as `Accountant review`.",
        "- Do not lodge, submit, or present outputs as lodging-ready advice.",
        "",
        "## Output states",
        "",
        "- Supported record",
        "- Claim candidate",
        "- Not claimable",
        "- Insufficient evidence",
        "- Accountant review",
        "",
        "## Required facts",
        "",
    ]
    facts = [
        "income year or effective period",
        "taxpayer/entity and ownership",
        "business/private/employment purpose",
        "amounts excluding and including GST where relevant",
        "dates acquired, used, paid, received, and disposed",
        "records held and missing evidence",
        "prior claims, reimbursements, and duplicate-risk factors",
    ]
    for fact in facts:
        lines.append(f"- {fact}")
    return "\n".join(lines) + "\n"


def rulesMarkdown(topic_obj: Topic, sources: List[Source]) -> str:
    lines = ["# Rules", "", GENERATED_MARKER, "", "These are conservative topic summaries from official sources, not copied ATO pages.", ""]
    verified = [src for src in sources if src.status == StatusVerified]
    metadata = [src for src in sources if src.status == StatusMetadataOnly]

    lines.append("## Verified official-source content")
    lines.append("")
    if not verified:
        lines.append("- No verified official-source summaries for this topic.")
    else:
        for src in verified:
            lines.extend(
                [
                    f"- {src.title}",
                    f"  - Source ID: {src.source_id}",
                    f"  - URL: {src.final_url}",
                    *( [f"  - Source last updated: {src.last_updated}"] if src.last_updated else [] ),
                    f"  - Checked at: {src.checked_at}",
                ]
            )
            if src.content_hash:
                lines.append(f"  - Content hash: {src.content_hash}")
            lines.append("")
    lines.append("## Metadata-only official-source links")
    lines.append("")
    if not metadata:
        lines.append("- No metadata-only assigned sources for this topic.")
    else:
        for src in metadata:
            lines.extend(
                [
                    f"- {src.title}",
                    f"  - Source ID: {src.source_id}",
                    f"  - URL: {src.final_url}",
                    *( [f"  - Source last updated: {src.last_updated}"] if src.last_updated else [] ),
                    f"  - Checked at: {src.checked_at}",
                    "  - Source content status: not verified this run. treat claims as metadata-only and verify before relying",
                ]
            )
            lines.append("")
    lines.extend(
        [
            "## TaxMate conservative summary",
            "",
            "- Use official URLs plus source hashes to support treatment guidance.",
            "- Values, rates, thresholds, caps, and due dates are volatile. Verify against listed source URL and official income year/effective period before use.",
            "- If official support is unavailable or stale, classify as `Accountant review`.",
            "- Do not claim source-backed treatment from metadata-only sources without explicit validation.",
            "",
            "## Accountant-review boundaries",
        ]
    )
    for review in topic_obj.review:
        lines.append(f"- {review}")
    lines.extend(["- mixed business/private use", "- missing ownership or entity details", "- missing evidence", "- pre-revenue expenses", "- capital versus revenue treatment", "- GST/BAS, FBT, payroll, or complex CGT uncertainty"])
    return "\n".join(lines) + "\n"


def evidenceMarkdown(topic_obj: Topic, sources: List[Source]) -> str:
    lines = ["# Evidence", "", "Collect records before classifying anything as `Claim candidate`.", ""]
    for item in [
        "receipts, invoices, statements, contracts, or official payment summaries",
        "date, amount, supplier, entity, ownership, and tax period",
        "business/employment purpose and apportionment basis",
        "GST registration and creditable-purpose evidence where relevant",
        "CGT acquisition, disposal, proceeds, cost-base, and adjustment records where relevant",
        "logbooks, diaries, rosters, timesheets, or usage records where relevant",
    ]:
        lines.append(f"- {item}")
    lines.extend(["", "Missing or altered evidence means `Insufficient evidence` or `Accountant review`, never a confirmed claim."])
    if len(sources) > 0:
        lines.append("\n### Topic source coverage\n")
        for src in sources:
            status = src.status or StatusMetadataOnly
            lines.append(f"- {src.source_id} from {src.final_url} ({status})")
    return "\n".join(lines) + "\n"


def assignTopic(rec: atodata.SourceRecord, text: str) -> tuple[Topic, int]:
    hay = (rec.url + " " + rec.final_url + " " + rec.title + " " + firstN(text, 12000)).lower()
    for rule in [
        ("working-from-home-expenses", "work-from-home"),
        ("home-based-business-expenses", "work-from-home"),
        ("business-activity-statements-bas", "gst-bas"),
        ("gst-excise-and-indirect-taxes/gst", "gst-bas"),
        ("fringe-benefits-tax", "payg-employer"),
        ("payg-withholding", "payg-employer"),
        ("single-touch-payroll", "payg-employer"),
        ("taxable-payments-annual-report", "payg-employer"),
        ("tax-rates-and-codes", "payg-employer"),
        ("crypto-asset", "crypto-assets"),
        ("shares-and-similar-investments", "shares-etfs-managed-funds"),
        ("shares-funds-and-trusts", "shares-etfs-managed-funds"),
        ("property-and-capital-gains-tax", "property-rental-cgt"),
        ("residential-rental-properties", "property-rental-cgt"),
        ("medicare-and-private-health-insurance", "private-health-medicare"),
        ("super-for-individuals-and-families", "superannuation"),
        ("super-for-employers", "superannuation"),
        ("foreign-resident-investments", "capital-gains-tax"),
        ("capital-gains-tax", "capital-gains-tax"),
        ("income-and-deductions-for-business", "abn-business"),
        ("personal-services-income", "abn-business"),
        ("records-you-need-to-keep", "records-evidence"),
    ]:
        if rule[0] in hay:
            for t in Topics():
                if t.slug == rule[1]:
                    return t, 100

    best = Topic("", "", "", [], "", "", [], [])
    best_score = 0
    for topic_obj in Topics():
        score = 0
        lower_keywords = [kw.lower() for kw in topic_obj.keywords]
        for kw in lower_keywords:
            if kw in hay:
                score += 3
        for signal in [s.lower() for s in topic_obj.signals]:
            if signal in hay:
                score += 1
        if score > best_score:
            best_score = score
            best = topic_obj
    return best, best_score


def HostApproved(raw: str) -> bool:
    u = urlparse(raw)
    if not u.hostname:
        return False
    return u.hostname.lower() in ApprovedHosts


def ExtractMainText(src: bytes) -> str:
    s = src.decode("utf-8", errors="ignore")
    for pattern in [
        re.compile(r"(?is)<script.*?</script>"),
        re.compile(r"(?is)<style.*?</style>"),
        re.compile(r"(?is)<nav.*?</nav>"),
        re.compile(r"(?is)<footer.*?</footer>"),
        re.compile(r"(?is)<header.*?</header>"),
    ]:
        s = pattern.sub(" ", s)
    m = re.search(r"(?is)<main[^>]*>(.*?)</main>", s)
    if m:
        s = m.group(1)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    s = html.unescape(s)
    s = s.replace("\r", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


valueRE = re.compile(r"(?i)(\b\d{4}[-–]\d{2}\b|\b\d{1,2}\s+[A-Za-z]+\s+\d{4}\b|[$]\s?\d[\d,]*(?:\.\d+)?|\b\d+(?:\.\d+)?\s?(?:cents?|%|per cent|percent)\b)")


def detectValues(topic: str, text: str, src: Source) -> List[ValueFact]:
    out: List[ValueFact] = []
    seen = set()
    for match in valueRE.finditer(text):
        value = text[match.start() : match.end()].strip()
        if value in seen:
            continue
        seen.add(value)
        start = max(0, match.start() - 90)
        end = min(len(text), match.end() + 120)
        context = text[start:end].strip()
        out.append(
            ValueFact(
                topic=topic,
                value=value,
                unit=inferUnit(value),
                context=context,
                jurisdiction=JURISDICTION,
                income_year=incomeYear(context),
                source_url=src.final_url,
                source_title=src.title,
                last_updated=src.last_updated,
                checked_at=src.checked_at,
                content_hash=src.content_hash,
                reuse_warning="Do not reuse outside the stated income year or effective period without refreshing the official source.",
            )
        )
        if len(out) >= 20:
            break
    return out


def mergeAndFilterValues(root: str, topic: str, values: List[ValueFact]) -> List[ValueFact]:
    if len(values) == 0:
        path = os.path.join(root, "skills", topic, "references", "current-values.json")
        try:
            body = Path(path).read_text(encoding="utf-8")
            raw = json.loads(body)
            values = [value_from_json(item) for item in raw]
        except Exception:
            values = []
    return filterValuesWithPeriods(values)


def filterValuesWithPeriods(values: List[ValueFact]) -> List[ValueFact]:
    out: List[ValueFact] = []
    seen: set[str] = set()
    for value in values:
        if value.income_year == "" and (value.effective_from == "" or value.effective_to == ""):
            continue
        if value.source_url == "" or value.source_title == "" or value.checked_at == "" or value.content_hash == "" or value.unit == "" or value.context == "":
            continue
        key = value.topic + "|" + value.value + "|" + value.context + "|" + value.source_url
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    out.sort(key=lambda x: x.source_url + x.value + x.context)
    return out


def inferUnit(value: str) -> str:
    lower = value.lower()
    if "$" in lower:
        return "AUD"
    if "cent" in lower:
        return "cents"
    if "%" in lower or "per cent" in lower or "percent" in lower:
        return "percent"
    return ""


def incomeYear(text: str) -> str:
    match = re.search(r"\b(20\d{2}[-–]\d{2})\b", text)
    if match:
        return match.group(1).replace("–", "-")
    return ""


def ValidateCurrentValue(value: ValueFact, requiredIncomeYear: str, sourceVerified: bool) -> bool:
    if value.source_url == "":
        raise RuntimeError("missing source URL")
    if value.source_title == "":
        raise RuntimeError("missing source title")
    if value.checked_at == "" or value.content_hash == "" or not validContentHash(value.content_hash):
        raise RuntimeError("missing or invalid source provenance")
    if value.context == "" or value.unit == "":
        raise RuntimeError("missing context/unit")
    if not sourceVerified:
        raise RuntimeError("source content not verified")
    if requiredIncomeYear == "":
        if value.income_year == "" and (value.effective_from == "" or value.effective_to == ""):
            raise RuntimeError("missing income-year or effective period")
        return
    if value.income_year and value.income_year != requiredIncomeYear:
        raise RuntimeError("income-year mismatch")
    if value.income_year == "" and (value.effective_from == "" or value.effective_to == ""):
        raise RuntimeError("missing income-year and effective period")


def canonicalURL(raw: str) -> str:
    try:
        u = urlparse(raw)
    except Exception:
        return raw
    if not u.path and not u.hostname:
        return raw
    path = u.path.rstrip("/")
    host = u.hostname.lower() if u.hostname else ""
    rebuilt = u._replace(fragment="", query="", path=path, netloc=host)
    # keep scheme/host/path only
    return rebuilt.geturl()


def BuildSourceCoverage(report: Union[GenerationReport, List[Source]]) -> SourceCoverage:
    if isinstance(report, GenerationReport):
        sources = report.sources
    else:
        sources = report
    coverage_by_canonical: Dict[str, str] = {}
    for src in sources:
        canonical = coverageCanonicalURL(src.url, src.final_url)
        source_id = sourceID(src.url, canonical)
        if src.status not in (StatusDuplicate, StatusNeedsReview):
            coverage_by_canonical[canonical] = source_id

    out = SourceCoverage()
    for src in sources:
        canonical = coverageCanonicalURL(src.url, src.final_url)
        entry = SourceCoverageEntry(
            source_id=sourceID(src.url, canonical),
            original_url=src.url,
            canonical_url=canonical,
            title=src.title,
            last_updated=src.last_updated,
            checked_at=src.checked_at,
            content_hash=src.content_hash,
            status=src.status,
            covered_concepts=conceptsFor(src.assigned_skill),
            reason=firstNonEmpty(src.assignment_reason, src.reason),
        )
        if entry.canonical_url == "":
            entry.canonical_url = src.url

        if entry.status in (StatusVerified, StatusMetadataOnly):
            if src.assigned_skill:
                entry.skills.append(src.assigned_skill)
                entry.references.extend([
                    os.path.join("skills", src.assigned_skill, "references", "rules.md"),
                    os.path.join("skills", src.assigned_skill, "references", "sources.json"),
                ])
        elif entry.status == StatusDuplicate:
            entry.duplicate_of = firstNonEmpty(src.duplicate_of, coverage_by_canonical.get(canonical, ""))
            entry.duplicate_evidence = firstNonEmpty(src.assignment_reason, "identical canonical URL")
            if entry.duplicate_of == "":
                entry.duplicate_of = sourceID(src.url, canonical)
        elif entry.status == StatusExcluded:
            entry.reason = firstNonEmpty(src.reason, "excluded")
        out.sources.append(entry)

    out.sources.sort(key=lambda item: item.source_id)
    return out


def coverageCanonicalURL(primaryURL: str, fallbackURL: str) -> str:
    canonical = canonicalURL(fallbackURL)
    if canonical == "":
        canonical = canonicalURL(primaryURL)
    if canonical == "":
        return primaryURL
    return canonical


def WriteSourceCoverage(root: str, coverage: SourceCoverage) -> None:
    writeJSON(os.path.join(root, "data", "ato_knowledge_base", SOURCE_COVERAGE_FILE), {
        "sources": [_coverage_entry_to_json(entry) for entry in coverage.sources]
    })


def LoadSourceCoverage(root: str) -> SourceCoverage:
    path = os.path.join(root, "data", "ato_knowledge_base", SOURCE_COVERAGE_FILE)
    body = Path(path).read_text(encoding="utf-8")
    payload = json.loads(body)
    sources = [_coverage_entry_from_json(item) for item in payload.get("sources", [])]
    return SourceCoverage(sources=sources)


def WriteCoverageReport(root: str, format: str) -> bytes:
    coverage = LoadSourceCoverage(root)
    summary = Audit(root, coverage)
    if format == "json":
        body = json.dumps({"summary": asdict(summary), "source_coverage": {"sources": [_coverage_entry_to_json(e) for e in coverage.sources]}}, indent=2)
        return (body + "\n").encode("utf-8")
    if format == "":
        format = "markdown"
    if format != "markdown":
        raise RuntimeError(f"unsupported format {format!r}")
    lines = ["# Source Coverage Report", "", f"Checked sources: {summary.Total}", "", "## Coverage counts", "", f"- total: {summary.Total}", f"- verified: {summary.Verified}", f"- metadata_only: {summary.MetadataOnly}", f"- duplicate: {summary.Duplicate}", f"- excluded: {summary.Excluded}", f"- needs_review: {summary.NeedsReview}", "", "## Coverage by skill", ""]
    for skill in sorted(summary.by_skill.keys()):
        state = summary.by_skill[skill]
        lines.append(f"- {skill}: assigned={state.assigned_sources} verified={state.verified_sources} metadata_only={state.metadata_only_sources} coverage_status={state.coverage_status}")
    lines.extend(["", "## Required topics", "", *_list_section("required tax areas with no source assignment", summary.required_assignment_missing), *_list_section("required tax areas with no verified source content", summary.required_verified_missing), *_list_section("missing destination files", summary.missing_destination_files), *_list_section("missing reverse provenance", summary.missing_reverse_provenance), *_list_section("invalid hashes", summary.invalid_hashes), *_list_section("unsupported duplicate evidence", summary.duplicate_evidence_issues), *_list_section("duplicate chain issues", summary.duplicate_chain_issues), *_list_section("volatile values missing effective periods", summary.volatile_missing_periods), *_list_section("skills missing guardrails", summary.skills_missing_guardrail), "", "## Source state", "", *_list_section("unassigned sources", summary.not_used_entries), *_list_section("review required sources", summary.review_entries), "", "## CGT coverage", ""])
    for key in ["general", "shares_etfs_managed_funds", "crypto", "property_rental"]:
        lines.append(f"- {key}: {'covered' if summary.cgt_coverage.get(key) else 'missing'}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _list_section(title: str, values: List[str]) -> List[str]:
    out = [f"## {title}", ""]
    if len(values) == 0:
        out.append("- none")
    else:
        out.extend([f"- {v}" for v in values])
    out.append("")
    return out


def Audit(root: str, coverage: SourceCoverage) -> CoverageSummary:
    summary = CoverageSummary()
    summary.Total = len(coverage.sources)
    summary.by_skill = {}
    summary.cgt_coverage = {}
    by_id: Dict[str, SourceCoverageEntry] = {}

    for entry in coverage.sources:
        if entry.source_id.strip() == "":
            continue
        by_id[entry.source_id] = entry
        if entry.status == StatusVerified:
            summary.Verified += 1
            for skill in entry.skills:
                st = summary.by_skill.setdefault(skill, CoverageSkillState())
                st.assigned_sources += 1
                st.verified_sources += 1
                summary.by_skill[skill] = st
                summary = cgtMark(summary, skill)
            if not validContentHash(entry.content_hash):
                summary.invalid_hashes.append(f"{entry.source_id}:{entry.canonical_url}")
            summary.missing_destination_files.extend(checkReferences(root, entry))
            summary.missing_reverse_provenance.extend(checkReverseProvenance(root, entry))
        elif entry.status == StatusMetadataOnly:
            summary.MetadataOnly += 1
            for skill in entry.skills:
                st = summary.by_skill.setdefault(skill, CoverageSkillState())
                st.assigned_sources += 1
                st.metadata_only_sources += 1
                summary.by_skill[skill] = st
            summary.missing_destination_files.extend(checkReferences(root, entry))
            summary.missing_reverse_provenance.extend(checkReverseProvenance(root, entry))
        elif entry.status == StatusDuplicate:
            summary.Duplicate += 1
            try:
                validateDuplicateEvidence(entry)
            except Exception as e:
                summary.duplicate_evidence_issues.append(str(e))
        elif entry.status == StatusExcluded:
            summary.Excluded += 1
        elif entry.status == StatusNeedsReview:
            summary.NeedsReview += 1
            summary.review_entries.append(entry.source_id)
        else:
            summary.NeedsReview += 1
            summary.review_entries.append(entry.source_id)

    for skill in sorted(summary.by_skill.keys()):
        st = summary.by_skill.setdefault(skill, CoverageSkillState())
    for skill in requiredSkillSlugs():
        state = summary.by_skill.get(skill, CoverageSkillState())
        if state.verified_sources > 0:
            state.coverage_status = "verified"
        elif state.metadata_only_sources > 0:
            state.coverage_status = "metadata_only"
            summary.required_verified_missing.append(skill)
        else:
            state.coverage_status = "missing"
            summary.required_assignment_missing.append(skill)
        summary.by_skill[skill] = state

    for entry in coverage.sources:
        if entry.status == StatusNeedsReview:
            continue
        if len(entry.skills) == 0:
            summary.not_used_entries.append(entry.source_id)
    summary.not_used_entries = sorted(summary.not_used_entries)

    summary.volatile_missing_periods = valuesMissingPeriods(root)
    for skill in sorted(summary.by_skill.keys()):
        if missingGuardrail(root, skill):
            summary.skills_missing_guardrail.append(skill)

    summary.duplicate_chain_issues = validateDuplicateChainsAsList(by_id)

    for arr in [
        summary.missing_destination_files,
        summary.missing_reverse_provenance,
        summary.invalid_hashes,
        summary.duplicate_evidence_issues,
        summary.duplicate_chain_issues,
        summary.required_assignment_missing,
        summary.required_verified_missing,
        summary.volatile_missing_periods,
        summary.skills_missing_guardrail,
    ]:
        arr.sort()

    return summary


def cgtMark(summary: CoverageSummary, skill: str) -> CoverageSummary:
    if skill == "capital-gains-tax":
        summary.cgt_coverage["general"] = True
    elif skill == "shares-etfs-managed-funds":
        summary.cgt_coverage["shares_etfs_managed_funds"] = True
    elif skill == "crypto-assets":
        summary.cgt_coverage["crypto"] = True
    elif skill == "property-rental-cgt":
        summary.cgt_coverage["property_rental"] = True
    return summary


def checkReferences(root: str, entry: SourceCoverageEntry) -> List[str]:
    out = []
    for ref in entry.references:
        rel = Path(ref)
        path = os.path.join(root, rel.as_posix())
        if not os.path.exists(path):
            out.append(f"{entry.source_id}:{ref}")
    return out


def checkReverseProvenance(root: str, entry: SourceCoverageEntry) -> List[str]:
    missing = []
    for ref in entry.references:
        path = os.path.join(root, os.path.normpath(ref))
        try:
            body = Path(path).read_bytes()
        except OSError:
            continue
        if len(body) == 0:
            missing.append(f"{entry.source_id}:{ref}")
            continue
        if entry.source_id.encode("utf-8") not in body and entry.canonical_url.encode("utf-8") not in body:
            missing.append(f"{entry.source_id}:{ref}")
    return missing


def validContentHash(hash_value: str) -> bool:
    return hash_value.strip() != "" and hash_value.lower() != EMPTY_CONTENT_HASH_V2


def ValidateSourceCoverage(root: str) -> Optional[RuntimeError]:
    try:
        coverage = LoadSourceCoverage(root)
    except Exception as exc:
        return RuntimeError(str(exc))

    registry = atodata.LoadRegistry(root)
    if len(coverage.sources) != len(registry.records):
        return RuntimeError(f"source coverage count {len(coverage.sources)} does not match registry count {len(registry.records)}")

    expected: Dict[str, atodata.SourceRecord] = {}
    for rec in registry.records:
        canonical = coverageCanonicalURL(rec.url, rec.final_url)
        expected[sourceID(rec.url, canonical)] = rec

    coverage_by_id: Dict[str, SourceCoverageEntry] = {}
    seen: Dict[str, bool] = {}
    skill_sources, err = loadPerSkillSourceAssignments(root)
    if err is not None:
        return RuntimeError(str(err))

    for entry in coverage.sources:
        source_id = entry.source_id.strip()
        if source_id == "":
            return RuntimeError("source coverage missing source_id")
        if seen.get(source_id):
            return RuntimeError(f"duplicate source_id {source_id}")
        seen[source_id] = True
        rec = expected.get(source_id)
        if rec is None:
            return RuntimeError(f"coverage has unknown source_id {source_id}")
        canonical = coverageCanonicalURL(rec.url, rec.final_url)
        if entry.canonical_url.strip() != canonical:
            return RuntimeError(f"coverage canonical URL mismatch {source_id}: expected {canonical} got {entry.canonical_url}")
        if entry.checked_at.strip() == "":
            return RuntimeError(f"source coverage missing checked_at for {source_id}")
        if rec.last_checked and entry.checked_at != rec.last_checked:
            return RuntimeError(f"checked_at mismatch for {source_id}: registry {rec.last_checked} coverage {entry.checked_at}")
        if entry.original_url != "" and entry.original_url != rec.url:
            return RuntimeError(f"original_url mismatch for {source_id}: registry {rec.url} coverage {entry.original_url}")
        if entry.title.strip() == "":
            entry.title = rec.title
        coverage_by_id[source_id] = entry

    for entry in coverage.sources:
        rec = expected.get(entry.source_id)
        if rec is None:
            return RuntimeError(f"coverage has unknown source_id {entry.source_id}")
        if entry.status == StatusVerified:
            if not validContentHash(entry.content_hash):
                return RuntimeError(f"verified source missing valid hash {entry.source_id}")
            if entry.content_hash.strip() != (rec.content_hash or "").strip():
                return RuntimeError(f"content hash mismatch for {entry.source_id}")
            if len(entry.skills) == 0 or len(entry.references) == 0:
                return RuntimeError(f"verified source missing assignment/references {entry.source_id}")
            err = validateSourceAssignmentWithProvenance(root, entry, skill_sources, "verified source missing assignment/references {source_id}")
            if err:
                return err
        elif entry.status == StatusMetadataOnly:
            if len(entry.skills) != 0:
                if len(entry.references) == 0:
                    return RuntimeError(f"metadata-only source missing references {entry.source_id}")
                err = validateSourceAssignmentWithProvenance(root, entry, skill_sources, "metadata-only source missing references {source_id}")
                if err:
                    return err
        elif entry.status == StatusDuplicate:
            if entry.duplicate_of.strip() == "":
                return RuntimeError(f"duplicate source missing duplicate_of {entry.source_id}")
            target = coverage_by_id.get(entry.duplicate_of)
            if target is None:
                return RuntimeError(f"duplicate source references missing target {entry.source_id}")
            if target.source_id == entry.source_id:
                return RuntimeError(f"duplicate source self-referenced {entry.source_id}")
            if target.status == StatusDuplicate:
                return RuntimeError(f"duplicate source references duplicate target {entry.source_id} -> {entry.duplicate_of}")
            if entry.duplicate_evidence.strip() == "":
                return RuntimeError(f"duplicate source missing evidence {entry.source_id}")
            if not isSupportedDuplicateEvidence(entry.duplicate_evidence):
                return RuntimeError(f"duplicate source has unsupported evidence {entry.source_id}")
        elif entry.status == StatusExcluded:
            if entry.reason.strip() == "":
                return RuntimeError(f"excluded source missing reason {entry.source_id}")
        elif entry.status == StatusNeedsReview:
            return RuntimeError(f"source remains needs_review {entry.source_id}")
        else:
            return RuntimeError(f"invalid status {entry.status!r} for {entry.source_id}")

    summary = Audit(root, coverage)
    if len(summary.duplicate_chain_issues) > 0:
        return RuntimeError("invalid duplicate chain: " + ", ".join(summary.duplicate_chain_issues[: min(3, len(summary.duplicate_chain_issues))]))
    if len(summary.duplicate_evidence_issues) > 0:
        return RuntimeError("invalid duplicate evidence: " + ", ".join(summary.duplicate_evidence_issues[: min(3, len(summary.duplicate_evidence_issues))]))
    if len(summary.missing_destination_files) > 0:
        return RuntimeError("missing destination files: " + ", ".join(summary.missing_destination_files[: min(3, len(summary.missing_destination_files))]))
    if len(summary.missing_reverse_provenance) > 0:
        return RuntimeError("missing reverse provenance: " + ", ".join(summary.missing_reverse_provenance[: min(3, len(summary.missing_reverse_provenance))]))
    if len(summary.invalid_hashes) > 0:
        return RuntimeError("invalid hashes: " + ", ".join(summary.invalid_hashes[: min(3, len(summary.invalid_hashes))]))
    if len(summary.volatile_missing_periods) > 0:
        return RuntimeError("volatile values missing periods: " + ", ".join(summary.volatile_missing_periods[: min(3, len(summary.volatile_missing_periods))]))
    if len(summary.skills_missing_guardrail) > 0:
        return RuntimeError("skills missing guardrails: " + ", ".join(summary.skills_missing_guardrail))
    return validateLocalCoverageBackedByGlobal(root, coverage_by_id, skill_sources)


def isSupportedDuplicateEvidence(evidence: str) -> bool:
    e = evidence.lower()
    for item in ["identical canonical url", "identical non-empty content hash", "confirmed redirect", "manual comparison"]:
        if item in e:
            return True
    return False


def validateDuplicateEvidence(entry: SourceCoverageEntry) -> None:
    if entry.status != StatusDuplicate:
        return
    if entry.duplicate_of.strip() == "":
        raise RuntimeError(f"duplicate source missing duplicate_of: {entry.source_id}")
    if entry.duplicate_of == entry.source_id:
        raise RuntimeError(f"duplicate source self-referenced: {entry.source_id}")
    if entry.duplicate_evidence.strip() == "":
        raise RuntimeError(f"duplicate source missing evidence: {entry.source_id}")
    if not isSupportedDuplicateEvidence(entry.duplicate_evidence):
        raise RuntimeError(f"unsupported duplicate evidence for {entry.source_id}")


def validateDuplicateChainsAsList(entries: Dict[str, SourceCoverageEntry]) -> List[str]:
    issues: List[str] = []
    for entry_id, entry in entries.items():
        if entry.status != StatusDuplicate:
            continue
        if entry.duplicate_of.strip() == "":
            issues.append(f"duplicate chain missing target {entry_id}")
            continue
        if entry.duplicate_of == entry_id:
            issues.append(f"duplicate chain self-reference {entry_id}")
            continue
        next_entry = entries.get(entry.duplicate_of)
        if next_entry is None:
            issues.append(f"duplicate chain references missing source {entry_id} -> {entry.duplicate_of}")
            continue
        if next_entry.status == StatusDuplicate:
            issues.append(f"duplicate chain not direct for {entry_id}")
    return issues


def validateLocalCoverageBackedByGlobal(root: str, coverage_by_id: Dict[str, SourceCoverageEntry], per_skill: Dict[str, Dict[str, Source]]) -> Optional[RuntimeError]:
    for by_id in per_skill.values():
        for source_id, local in by_id.items():
            entry = coverage_by_id.get(source_id)
            if entry is None:
                return RuntimeError(f"per-skill source {source_id} not present in coverage")
            if not sourceMatchesCanonical(local, entry.canonical_url):
                return RuntimeError(f"per-skill source {source_id} url mismatch in coverage")
            if local.status != entry.status:
                return RuntimeError(f"status mismatch for {source_id} across global/local")
            if local.checked_at != entry.checked_at:
                return RuntimeError(f"checked_at mismatch for {source_id} across global/local")
            if not matchingOptionalContentHash(entry.content_hash, local.content_hash):
                return RuntimeError(f"content_hash mismatch for {source_id} across global/local")

    for source_id, entry in coverage_by_id.items():
        if entry.status not in (StatusVerified, StatusMetadataOnly):
            continue
        for skill in entry.skills:
            by_id = per_skill.get(skill)
            if by_id is None:
                return RuntimeError(f"coverage source {source_id} assigned to unknown skill {skill}")
            if source_id not in by_id:
                return RuntimeError(f"coverage source {source_id} missing in per-skill assignment {skill}")
    return None


def matchingOptionalContentHash(expected: str, actual: str) -> bool:
    if expected.strip() == "":
        return True
    return actual.strip() == expected.strip()


def sourceMatchesCanonical(local: Source, canonical: str) -> bool:
    return local.final_url.strip() == canonical.strip() or local.url.strip() == canonical.strip()


def validateSourceAssignmentWithProvenance(root: str, entry: SourceCoverageEntry, skill_sources: Dict[str, Dict[str, Source]], empty_msg: str) -> Optional[RuntimeError]:
    if len(entry.skills) == 0 or len(entry.references) == 0:
        return RuntimeError(empty_msg.format(entry.source_id))
    try:
        validateAssignedSourceReferences(entry, skill_sources)
    except RuntimeError as exc:
        return exc
    for ref in entry.references:
        err = validateReverseProvenanceInSource(root, entry, ref)
        if err is not None:
            return err
    return None


def validateAssignedSourceReferences(entry: SourceCoverageEntry, skill_sources: Dict[str, Dict[str, Source]]) -> None:
    for skill in entry.skills:
        by_id = skill_sources.get(skill)
        if by_id is None:
            raise RuntimeError(f"coverage assigns {entry.source_id} to unknown skill {skill}")
        local = by_id.get(entry.source_id)
        if local is None:
            raise RuntimeError(f"coverage source {entry.source_id} missing from {skill} references/sources.json")
        if not sourceMatchesCanonical(local, entry.canonical_url):
            raise RuntimeError(f"canonical URL mismatch for {entry.source_id} in {skill}")
        if local.status != entry.status:
            raise RuntimeError(f"status mismatch for {entry.source_id} in {skill}: coverage={entry.status} local={local.status}")
        if local.checked_at != entry.checked_at:
            raise RuntimeError(f"checked_at mismatch for {entry.source_id} in {skill}")
        if not matchingOptionalContentHash(entry.content_hash, local.content_hash):
            raise RuntimeError(f"content_hash mismatch for {entry.source_id} in {skill}")


def validateReverseProvenanceInSource(root: str, entry: SourceCoverageEntry, ref: str) -> Optional[RuntimeError]:
    path = os.path.join(root, os.path.normpath(ref))
    try:
        body = Path(path).read_bytes()
    except OSError as exc:
        return RuntimeError(f"reference missing source file for {entry.source_id}: {exc}")
    if entry.source_id.encode("utf-8") not in body and entry.canonical_url.encode("utf-8") not in body:
        return RuntimeError(f"reference missing reverse provenance for {entry.source_id}:{ref}")
    return None


def loadPerSkillSourceAssignments(root: str) -> tuple[Dict[str, Dict[str, Source]], Optional[RuntimeError]]:
    source_by_skill: Dict[str, Dict[str, Source]] = {}
    for skill in requiredSkillSlugs():
        path = os.path.join(root, "skills", skill, "references", "sources.json")
        try:
            body = Path(path).read_text(encoding="utf-8")
        except OSError as exc:
            return {}, RuntimeError(str(exc))
        try:
            raw = json.loads(body)
        except Exception as exc:
            return {}, RuntimeError(str(exc))
        by_id: Dict[str, Source] = {}
        for entry in raw:
            source = _source_from_json(entry)
            if source.source_id.strip() == "":
                return {}, RuntimeError(f"missing source_id in {path}")
            if source.source_id in by_id:
                return {}, RuntimeError(f"duplicate source_id {source.source_id} in {path}")
            by_id[source.source_id] = source
        source_by_skill[skill] = by_id
    return source_by_skill, None


def requiredSourceArtifacts(root: str) -> List[str]:
    out: List[str] = []
    for skill in requiredSkillSlugs():
        out.extend([
            os.path.join("skills", skill, "SKILL.md"),
            os.path.join("skills", skill, "references", "rules.md"),
            os.path.join("skills", skill, "references", "evidence.md"),
            os.path.join("skills", skill, "references", "sources.json"),
        ])
        current_values = os.path.join(root, "skills", skill, "references", "current-values.json")
        if os.path.exists(current_values):
            out.append(os.path.join("skills", skill, "references", "current-values.json"))
    for skill in ["workbook", "taxpack"]:
        out.append(os.path.join("skills", skill, "references", "topic-inputs.md"))
    out.append(os.path.join("data", "ato_knowledge_base", SOURCE_COVERAGE_FILE))
    out.sort()
    return out


def trackedGeneratedArtifacts(root: str) -> List[str]:
    out = set(requiredSourceArtifacts(root))
    for skill in requiredSkillSlugs():
        skill_path = os.path.join(root, "skills", skill, "SKILL.md")
        if os.path.exists(skill_path):
            out.add(os.path.join("skills", skill, "SKILL.md"))
        references = os.path.join(root, "skills", skill, "references")
        if not os.path.isdir(references):
            continue
        for dir_path, _, names in os.walk(references):
            for name in sorted(names):
                out.add(os.path.relpath(os.path.join(dir_path, name), root))
    return sorted(out)


def CompareGeneratedArtifacts(root: str, generated_root: str) -> Optional[RuntimeError]:
    expected_files = set(trackedGeneratedArtifacts(root))
    generated_files = set(trackedGeneratedArtifacts(generated_root))
    for rel in sorted(expected_files | generated_files):
        generated_path = os.path.join(generated_root, rel)
        expected_path = os.path.join(root, rel)
        try:
            generated_body = Path(generated_path).read_bytes()
        except OSError:
            return RuntimeError(f"generated file missing {rel}")
        try:
            expected_body = Path(expected_path).read_bytes()
        except OSError:
            return RuntimeError(f"tracked file missing expected output {rel}")
        if generated_body.strip() != expected_body.strip():
            return RuntimeError(f"generated output mismatch {rel}")
    return None


def conceptsFor(skill: str) -> List[str]:
    for t in Topics():
        if t.slug == skill:
            out = list(t.signals)
            out.extend(t.keywords)
            return sorted(compact(out))
    return []


def inferSkillsFromURL(raw: str) -> List[str]:
    for skill in requiredSkillSlugs():
        if skill in raw:
            return [skill]
    return []


def valuesMissingPeriods(root: str) -> List[str]:
    missing: List[str] = []
    for skill in requiredSkillSlugs():
        path = os.path.join(root, "skills", skill, "references", "current-values.json")
        try:
            body = Path(path).read_text(encoding="utf-8")
            raw = json.loads(body)
        except OSError:
            continue
        except Exception:
            missing.append(f"{path}:invalid-json")
            continue
        for i, value in enumerate(raw):
            v = value_from_json(value)
            if v.source_url == "" or v.source_title == "" or v.checked_at == "" or v.content_hash == "" or v.unit == "" or v.context == "":
                missing.append(f"{path}:{i}:missing-provenance")
                continue
            if v.income_year == "" and (v.effective_from == "" or v.effective_to == ""):
                missing.append(f"{path}:{i}:missing-period")
    return missing


def missingGuardrail(root: str, skill: str) -> bool:
    path = os.path.join(root, "skills", skill, "SKILL.md")
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return True
    for needle in SKILL_GUARDRAIL_NEEDLES:
        if needle not in text:
            return True
    return False


def sourceID(originalURL: str, canonicalURLValue: str) -> str:
    return "ato-" + HashBytes((originalURL + "|" + canonicalURLValue).encode("utf-8"))[:12]


def sourceMatchesCanonicalURL(local: Source, canonical: str) -> bool:
    canonical = canonical.strip()
    return local.final_url.strip() == canonical or local.url.strip() == canonical


def HashBytes(src: bytes) -> str:
    return hashlib.sha256(src).hexdigest()


def HashText(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def firstNonEmpty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def firstN(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n]


def compact(values: List[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for value in values:
        v = value.strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    return out


def fileExists(path: str) -> bool:
    return Path(path).is_file()


def writeJSON(path: str, value: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(value, f, indent=2)
        f.write("\n")


def writeText(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def foundInRegistry(registry: atodata.SourceRegistry, source_id: str) -> Optional[atodata.SourceRecord]:
    for rec in registry.records:
        if sourceID(rec.url, canonicalURL(firstNonEmpty(rec.final_url, rec.url))) == source_id:
            return rec
    return None


def _source_to_json(src: Source) -> Dict[str, Any]:
    return {
        "source_id": src.source_id,
        "url": src.url,
        "final_url": src.final_url,
        "title": src.title,
        "last_updated": src.last_updated,
        "checked_at": src.checked_at,
        "content_hash": src.content_hash,
        "assigned_skill": src.assigned_skill,
        "reference": src.reference,
        "duplicate_of": src.duplicate_of,
        "status": src.status,
        "reason": src.reason,
        "assignment_reason": src.assignment_reason,
    }


def _source_from_json(payload: Dict[str, Any]) -> Source:
    return Source(
        source_id=str(payload.get("source_id", "")),
        url=str(payload.get("url", "")),
        final_url=str(payload.get("final_url", "")),
        title=str(payload.get("title", "")),
        last_updated=str(payload.get("last_updated", "")),
        checked_at=str(payload.get("checked_at", "")),
        content_hash=str(payload.get("content_hash", "")),
        assigned_skill=str(payload.get("assigned_skill", "")),
        reference=str(payload.get("reference", "")),
        duplicate_of=str(payload.get("duplicate_of", "")),
        status=str(payload.get("status", "")),
        reason=str(payload.get("reason", "")),
        assignment_reason=str(payload.get("assignment_reason", "")),
    )


def _value_to_json(value: ValueFact) -> Dict[str, Any]:
    out = {
        "topic": value.topic,
        "value": value.value,
        "unit": value.unit,
        "context": value.context,
        "jurisdiction": value.jurisdiction,
        "income_year": value.income_year,
        "source_url": value.source_url,
        "source_title": value.source_title,
        "source_last_updated": value.last_updated,
        "checked_at": value.checked_at,
        "content_hash": value.content_hash,
        "reuse_warning": value.reuse_warning,
    }
    if value.effective_from:
        out["effective_from"] = value.effective_from
    if value.effective_to:
        out["effective_to"] = value.effective_to
    return out


def value_from_json(payload: Dict[str, Any]) -> ValueFact:
    return ValueFact(
        topic=str(payload.get("topic", "")),
        value=str(payload.get("value", "")),
        unit=str(payload.get("unit", "")),
        context=str(payload.get("context", "")),
        jurisdiction=str(payload.get("jurisdiction", "")),
        income_year=str(payload.get("income_year", "")),
        effective_from=str(payload.get("effective_from", "")),
        effective_to=str(payload.get("effective_to", "")),
        source_url=str(payload.get("source_url", "")),
        source_title=str(payload.get("source_title", "")),
        last_updated=str(payload.get("source_last_updated", payload.get("last_updated", ""))),
        checked_at=str(payload.get("checked_at", "")),
        content_hash=str(payload.get("content_hash", "")),
        reuse_warning=str(payload.get("reuse_warning", "")),
    )


def _coverage_entry_to_json(entry: SourceCoverageEntry) -> Dict[str, Any]:
    return {
        "source_id": entry.source_id,
        "original_url": entry.original_url,
        "canonical_url": entry.canonical_url,
        "source_title": entry.title,
        "source_last_updated": entry.last_updated,
        "checked_at": entry.checked_at,
        "content_hash": entry.content_hash,
        "status": entry.status,
        "skills": entry.skills,
        "references": entry.references,
        "covered_concepts": entry.covered_concepts,
        "duplicate_of": entry.duplicate_of,
        "duplicate_evidence": entry.duplicate_evidence,
        "reason": entry.reason,
    }


def _coverage_entry_from_json(payload: Dict[str, Any]) -> SourceCoverageEntry:
    return SourceCoverageEntry(
        source_id=str(payload.get("source_id", "")),
        original_url=str(payload.get("original_url", "")),
        canonical_url=str(payload.get("canonical_url", "")),
        title=str(payload.get("source_title", "")),
        last_updated=str(payload.get("source_last_updated", "")),
        checked_at=str(payload.get("checked_at", "")),
        content_hash=str(payload.get("content_hash", "")),
        status=str(payload.get("status", "")),
        skills=list(payload.get("skills", []) or []),
        references=list(payload.get("references", []) or []),
        covered_concepts=list(payload.get("covered_concepts", []) or []),
        duplicate_of=str(payload.get("duplicate_of", "")),
        duplicate_evidence=str(payload.get("duplicate_evidence", "")),
        reason=str(payload.get("reason", "")),
    )


# Legacy aliases used by historical callers
Coverage = CoverageSummary
SourceID = sourceID
Scope = SOURCE_COVERAGE_FILE
EmptyContentHashValue = EMPTY_CONTENT_HASH_V2
