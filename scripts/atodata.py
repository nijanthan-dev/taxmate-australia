#!/usr/bin/env python3
"""ATO data refresh helpers (Python replacement)."""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urljoin, urlparse, urlunparse

from datetime import datetime, timezone


SCOPE = (
    "ATO official pages relevant to Australian FY2025-26 individual, employment, ABN/sole trader, GST/BAS, "
    "PAYG instalments, PAYG withholding, STP, TPAR, FBT, CGT, ETF/investment, crypto, rental-property "
    "records, super, private health, and company, trust, and partnership return skeleton preparation."
)

SOURCE_TITLE_OVERRIDES = {
    "https://www.ato.gov.au/api/public/content/0-e220713e-6a6f-4401-b966-8bddf3ba96fd": "Company tax return instructions 2025",
    "https://www.ato.gov.au/api/public/content/0-70d99f71-9469-4fd4-97fe-e328d58b37ab": "Trust tax return instructions 2025",
    "https://www.ato.gov.au/api/public/content/1453e44ff39e4eb789ea83eeb6eac10b?v=5c58b86f": "Partnership tax return instructions 2025",
}

SEED_URLS = [
    "https://www.ato.gov.au/individuals-and-families/your-tax-return",
    "https://www.ato.gov.au/individuals-and-families/your-tax-return/how-to-lodge-your-tax-return",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/records-you-need-to-keep",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/actual-cost-method",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/occupancy-expenses",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/tools-and-equipment",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/other-work-related-deductions",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare",
    "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/income-you-must-declare/employment-income",
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business",
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/business-income",
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions",
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions/deductions-for-home-based-business-expenses",
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions/claiming-a-tax-deduction-for-business-expenses",
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions/motor-vehicle-and-car-expenses",
    "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income",
    "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst",
    "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/registering-for-gst",
    "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/claiming-gst-credits",
    "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/gst-credits-and-income-tax-deductions",
    "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/tax-invoices",
    "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/when-to-charge-gst-and-when-not-to",
    "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas",
    "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/how-to-lodge-your-bas",
    "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/payg-instalments",
    "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/reports-and-returns/taxable-payments-annual-report",
    "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding",
    "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/single-touch-payroll",
    "https://www.ato.gov.au/tax-rates-and-codes/tax-tables-overview",
    "https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents",
    "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax",
    "https://www.ato.gov.au/tax-rates-and-codes/fringe-benefits-tax-rates-and-thresholds",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/investing-in-shares",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/calculating-your-cgt",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments/managed-investment-funds",
    "https://www.ato.gov.au/individuals-and-families/investments-and-assets/investment-income",
    "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families",
    "https://www.ato.gov.au/businesses-and-organisations/super-for-employers/paying-super-contributions/how-much-super-to-pay",
    "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/growing-and-keeping-track-of-your-super/how-to-save-more-in-your-super/personal-super-contributions",
    "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/growing-and-keeping-track-of-your-super/how-to-save-more-in-your-super/personal-super-contributions",
    "https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super-contributions-tax-and-government-contributions/claiming-deductions-for-personal-super-contributions",
    "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance",
    "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/private-health-insurance-rebate",
    "https://www.ato.gov.au/individuals-and-families/medicare-and-private-health-insurance/medicare-levy-surcharge",
]

PATH_KEYWORDS = [
    "/individuals-and-families/income-deductions-offsets-and-records",
    "/individuals-and-families/investments-and-assets",
    "/individuals-and-families/super-for-individuals-and-families",
    "/individuals-and-families/medicare-and-private-health-insurance",
    "/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business",
    "/businesses-and-organisations/gst-excise-and-indirect-taxes/gst",
    "/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas",
    "/businesses-and-organisations/preparing-lodging-and-paying/reports-and-returns",
    "/businesses-and-organisations/hiring-and-paying-your-workers",
    "/businesses-and-organisations/super-for-employers",
    "/tax-rates-and-codes",
]

SCRIPT_RE = re.compile(r"(?is)<script.*?</script>")
STYLE_RE = re.compile(r"(?is)<style.*?</style>")
TAG_RE = re.compile(r"(?s)<[^>]+>")
SPACE_RE = re.compile(r"\s+")
TITLE_RE = re.compile(r"([^|]{3,120})\s+\|\s+Australian Taxation Office")
MODIFIED_RE = re.compile(r'dcterms\.modified" content="[^;]+;\s*([^"]+)"')
UPDATED_RE = re.compile(r"Last updated\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})")
HREF_RE = re.compile(r"(?i)href=['\"]([^'\"]+)['\"]")
TERM_RE = re.compile(r"[^a-z0-9]+")
GENERIC_QUERY_TERMS = {
    "and",
    "ato",
    "for",
    "not",
    "tax",
    "the",
    "you",
    "your",
}


@dataclass
class SourceRecord:
    url: str
    final_url: str
    status: int
    title: str
    last_updated: str
    raw_file: str
    text_file: str
    content_hash: str = ""
    content_verified: bool = False
    last_checked: str = ""

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SourceRecord":
        return cls(
            url=str(payload.get("url", "")),
            final_url=str(payload.get("final_url", "")),
            status=int(payload.get("status", 0)),
            title=str(payload.get("title", "")),
            last_updated=str(payload.get("last_updated", "")),
            raw_file=str(payload.get("raw_file", "")),
            text_file=str(payload.get("text_file", "")),
            content_hash=str(payload.get("content_hash", "")),
            content_verified=bool(payload.get("content_verified", False)),
            last_checked=str(payload.get("last_checked", "")),
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "title": self.title,
            "last_updated": self.last_updated,
            "raw_file": self.raw_file,
            "text_file": self.text_file,
            "content_hash": self.content_hash,
            "content_verified": self.content_verified,
            "last_checked": self.last_checked,
        }

    @property
    def URL(self) -> str:
        return self.url

    @URL.setter
    def URL(self, value: str) -> None:
        self.url = value

    @property
    def FinalURL(self) -> str:
        return self.final_url

    @FinalURL.setter
    def FinalURL(self, value: str) -> None:
        self.final_url = value

    @property
    def Status(self) -> int:
        return self.status

    @Status.setter
    def Status(self, value: int) -> None:
        self.status = value

    @property
    def Title(self) -> str:
        return self.title

    @Title.setter
    def Title(self, value: str) -> None:
        self.title = value

    @property
    def LastUpdated(self) -> str:
        return self.last_updated

    @LastUpdated.setter
    def LastUpdated(self, value: str) -> None:
        self.last_updated = value

    @property
    def RawFile(self) -> str:
        return self.raw_file

    @RawFile.setter
    def RawFile(self, value: str) -> None:
        self.raw_file = value

    @property
    def TextFile(self) -> str:
        return self.text_file

    @TextFile.setter
    def TextFile(self, value: str) -> None:
        self.text_file = value

    @property
    def ContentHash(self) -> str:
        return self.content_hash

    @ContentHash.setter
    def ContentHash(self, value: str) -> None:
        self.content_hash = value

    @property
    def ContentVerified(self) -> bool:
        return self.content_verified

    @ContentVerified.setter
    def ContentVerified(self, value: bool) -> None:
        self.content_verified = value

    @property
    def LastChecked(self) -> str:
        return self.last_checked

    @LastChecked.setter
    def LastChecked(self, value: str) -> None:
        self.last_checked = value


@dataclass
class SourceFailure:
    url: str
    error: str

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SourceFailure":
        return cls(url=str(payload.get("url", "")), error=str(payload.get("error", "")))

    def to_dict(self) -> Dict[str, object]:
        return {"url": self.url, "error": self.error}

    @property
    def URL(self) -> str:
        return self.url

    @URL.setter
    def URL(self, value: str) -> None:
        self.url = value

    @property
    def Error(self) -> str:
        return self.error

    @Error.setter
    def Error(self, value: str) -> None:
        self.error = value


@dataclass
class SourceRegistry:
    fetched_at: str = ""
    refreshed_at: str = ""
    scope: str = SCOPE
    records: List[SourceRecord] = field(default_factory=list)
    failures: List[SourceFailure] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: Dict[str, object]) -> "SourceRegistry":
        records = [SourceRecord.from_dict(value) for value in payload.get("records", []) if isinstance(value, dict)]
        failures = [SourceFailure.from_dict(value) for value in payload.get("failures", []) if isinstance(value, dict)]
        return cls(
            fetched_at=str(payload.get("fetched_at", payload.get("fetchedAt", ""))),
            refreshed_at=str(payload.get("refreshed_at", payload.get("refreshedAt", ""))),
            scope=str(payload.get("scope", payload.get("Scope", SCOPE))),
            records=records,
            failures=failures,
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "fetched_at": self.fetched_at,
            "refreshed_at": self.refreshed_at,
            "scope": self.scope,
            "records": [record.to_dict() for record in self.records],
            "failures": [failure.to_dict() for failure in self.failures],
        }

    @property
    def FetchedAt(self) -> str:
        return self.fetched_at

    @FetchedAt.setter
    def FetchedAt(self, value: str) -> None:
        self.fetched_at = value

    @property
    def RefreshedAt(self) -> str:
        return self.refreshed_at

    @RefreshedAt.setter
    def RefreshedAt(self, value: str) -> None:
        self.refreshed_at = value

    @property
    def Scope(self) -> str:
        return self.scope

    @Scope.setter
    def Scope(self, value: str) -> None:
        self.scope = value

    @property
    def Records(self) -> List[SourceRecord]:
        return self.records

    @Records.setter
    def Records(self, value: List[SourceRecord]) -> None:
        self.records = value

    @property
    def Failures(self) -> List[SourceFailure]:
        return self.failures

    @Failures.setter
    def Failures(self, value: List[SourceFailure]) -> None:
        self.failures = value


@dataclass
class RefreshResult:
    url: str
    status: int = 0
    changed: bool = False
    title: str = ""
    error: str = ""

    def to_dict(self) -> Dict[str, object]:
        return {
            "url": self.url,
            "status": self.status,
            "changed": self.changed,
            "title": self.title,
            "error": self.error,
        }

    @property
    def URL(self) -> str:
        return self.url

    @URL.setter
    def URL(self, value: str) -> None:
        self.url = value

    @property
    def Status(self) -> int:
        return self.status

    @Status.setter
    def Status(self, value: int) -> None:
        self.status = value

    @property
    def Changed(self) -> bool:
        return self.changed

    @Changed.setter
    def Changed(self, value: bool) -> None:
        self.changed = value

    @property
    def Title(self) -> str:
        return self.title

    @Title.setter
    def Title(self, value: str) -> None:
        self.title = value

    @property
    def Error(self) -> str:
        return self.error

    @Error.setter
    def Error(self, value: str) -> None:
        self.error = value


@dataclass
class FetchResult:
    status: int
    final_url: str
    body: bytes

    @property
    def Status(self) -> int:
        return self.status

    @Status.setter
    def Status(self, value: int) -> None:
        self.status = value

    @property
    def FinalURL(self) -> str:
        return self.final_url

    @FinalURL.setter
    def FinalURL(self, value: str) -> None:
        self.final_url = value


def skill_root() -> str:
    explicit_root = os.environ.get("TAXMATE_AUSTRALIA_ROOT")
    if explicit_root:
        candidate = Path(explicit_root).expanduser().resolve()
        if candidate.joinpath(".codex-plugin", "plugin.json").exists():
            return str(candidate)
    exe = Path(__file__).resolve()
    dir_path = exe.parent
    if dir_path.name == "bin":
        return str(dir_path.parent)
    if dir_path.name == "scripts":
        return str(dir_path.parent)
    return str(dir_path.parent)


def data_dir(root: str) -> str:
    return os.path.join(root, "data", "ato_knowledge_base")


def cache_dir(root: str) -> str:
    return os.path.join(root, ".cache", "ato")


def registry_path(root: str) -> str:
    return os.path.join(data_dir(root), "source_registry.json")


def load_registry(root: str) -> SourceRegistry:
    body = Path(registry_path(root)).read_bytes()
    return SourceRegistry.from_dict(json.loads(body.decode("utf-8")))


def save_registry(root: str, registry: SourceRegistry) -> None:
    path = registry_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    registry.refreshed_at = utc_timestamp()
    path_obj = Path(path)
    path_obj.write_text(json.dumps(registry.to_dict(), indent=2) + "\n", encoding="utf-8")


def curl_fetch(raw_url: str) -> FetchResult:
    with tempfile.NamedTemporaryFile() as body_file:
        command = [
            "curl",
            "--disable",
            "-L",
            "--silent",
            "--show-error",
            "--max-time",
            "30",
            "--user-agent",
            "taxmate-australia-runtime",
            "--output",
            body_file.name,
            "--write-out",
            "%{http_code}\n%{url_effective}",
            raw_url,
        ]
        try:
            proc = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        except OSError as exc:
            raise RuntimeError(str(exc)) from exc
        body_file.seek(0)
        body = body_file.read()

    if proc.returncode != 0:
        error = proc.stderr.decode("utf-8", errors="ignore").strip()
        if not error:
            error = f"curl failed with exit {proc.returncode}"
        raise RuntimeError(error)

    metadata = proc.stdout.decode("utf-8", errors="ignore").splitlines()
    status = int(metadata[0]) if metadata and metadata[0].isdigit() else 0
    final_url = metadata[1].strip() if len(metadata) > 1 and metadata[1].strip() else raw_url
    return FetchResult(status=status, final_url=final_url, body=body)


def fetch(raw_url: str) -> FetchResult:
    return curl_fetch(raw_url)


def clean_text(src: bytes) -> str:
    text = src.decode("utf-8", errors="ignore")
    text = SCRIPT_RE.sub(" ", text)
    text = STYLE_RE.sub(" ", text)
    text = TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = text.replace("\r", "")
    text = SPACE_RE.sub(" ", text)
    return text.strip()


def title_of(text: str) -> str:
    match = TITLE_RE.search(text)
    if match:
        return match.group(1).strip()
    if len(text) > 90:
        return text[:90].strip()
    return text.strip()


def modified_of(src: bytes, text: str) -> str:
    match = MODIFIED_RE.search(src.decode("utf-8", errors="ignore"))
    if match:
        return match.group(1).strip()
    match = UPDATED_RE.search(text)
    if match:
        return match.group(1)
    return ""


def slug_for(raw_url: str) -> str:
    parsed = urlparse(raw_url)
    path = "home"
    if parsed.path.strip("/"):
        path = parsed.path.strip("/").replace("/", "__")
    path = re.sub(r"[^A-Za-z0-9_.-]+", "-", path)
    if len(path) > 160:
        path = path[:160]
    return f"{path}__{hashlib.sha256(raw_url.encode('utf-8')).hexdigest()[:8]}"


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="ignore")).hexdigest()


def record_text(root: str, rec: SourceRecord) -> str:
    for path in (os.path.join(data_dir(root), rec.text_file), os.path.join(cache_dir(root), rec.text_file)):
        try:
            return Path(path).read_text(encoding="utf-8")
        except OSError:
            continue
    return ""


def terms(query: str) -> List[str]:
    return [term for term in TERM_RE.split(query.lower()) if len(term) > 2 and term not in GENERIC_QUERY_TERMS]


def query_score(root: str, rec: SourceRecord, query: str) -> int:
    title_url = " ".join([rec.title, rec.url, rec.final_url]).lower()
    candidates = terms(query)
    if not candidates:
        return 0
    score = 0
    phrase = query.strip().lower()
    if phrase and phrase in title_url:
        score += 100
    for term in candidates:
        if term in title_url:
            score += 15
    slug = first_non_empty(rec.final_url, rec.url).replace("-", " ").lower()
    for term in candidates:
        if term in slug:
            score += 10
    text = record_text(root, rec).lower()
    if phrase and phrase in text:
        score += 20
    for term in candidates:
        if term in text:
            score += 2
    return score


def select_by_query(root: str, records: List[SourceRecord], query: str, limit: int) -> List[SourceRecord]:
    scored = []
    for rec in records:
        score = query_score(root, rec, query)
        if score >= 15:
            scored.append((score, rec))
    scored.sort(key=lambda item: item[0], reverse=True)
    if limit <= 0 or limit > len(scored):
        limit = len(scored)
    return [item[1] for item in scored[:limit]]


def select_by_url(records: List[SourceRecord], urls: Sequence[str]) -> Tuple[List[SourceRecord], List[str]]:
    wanted = {url: True for url in urls}
    selected: List[SourceRecord] = []
    for rec in records:
        if rec.url in wanted or rec.final_url in wanted:
            selected.append(rec)
            wanted.pop(rec.url, None)
            wanted.pop(rec.final_url, None)
    missing = sorted(wanted.keys())
    return selected, missing


def discover_links(base_url: str, src: bytes) -> List[str]:
    try:
        base = urlparse(base_url)
    except Exception:
        return []
    seen = {}
    for match in HREF_RE.finditer(src.decode("utf-8", errors="ignore")):
        href = match.group(1)
        if href.startswith(("#", "mailto:", "tel:")):
            continue
        try:
            parsed = urlparse(href)
        except Exception:
            continue
        absolute = urlunparse(urlparse(urljoin(base.geturl(), parsed.geturl())))
        if absolute == "":
            continue
        parts = urlparse(absolute)
        if parts.scheme != "https" or parts.netloc.lower() != "www.ato.gov.au":
            continue
        normalized = (parts.scheme, parts.netloc, parts.path.rstrip("/"), "", "", "")
        rebuilt = urlunparse(normalized)
        if path_allowed(parts.path):
            seen[rebuilt] = True
    links = list(seen.keys())
    links.sort()
    return links


def path_allowed(path: str) -> bool:
    return any(token in path for token in PATH_KEYWORDS)


@dataclass
class QueueItem:
    url: str
    depth: int


def recrawl(root: str, max_pages: int) -> SourceRegistry:
    if max_pages <= 0:
        max_pages = 250
    cache_root = cache_dir(root)
    os.makedirs(os.path.join(cache_root, "raw"), exist_ok=True)
    os.makedirs(os.path.join(cache_root, "text"), exist_ok=True)

    queue: List[QueueItem] = [QueueItem(url=url.rstrip("/"), depth=0) for url in SEED_URLS]
    seen = {item.url: True for item in queue}

    registry = SourceRegistry(fetched_at=utc_timestamp())
    idx = 0
    while queue and len(registry.records) < max_pages:
        item = queue.pop(0)
        idx += 1
        try:
            fetched = fetch(item.url)
        except Exception as exc:
            msg = str(exc)
            registry.failures.append(SourceFailure(url=item.url, error=msg))
            continue
        if fetched.status >= 400:
            registry.failures.append(
                SourceFailure(url=item.url, error=f"HTTP Error {fetched.status}: HTTP error")
            )
            continue

        text, content_hash, content_verified = content_state(fetched.body)
        slug = slug_for(fetched.final_url)
        raw_file = os.path.join("raw", f"{slug}.html")
        text_file = os.path.join("text", f"{slug}.txt")
        raw_path = os.path.join(cache_root, raw_file)
        text_path = os.path.join(cache_root, text_file)

        Path(raw_path).write_bytes(fetched.body)
        Path(text_path).write_text(text, encoding="utf-8")
        registry.records.append(
            SourceRecord(
                url=item.url,
                final_url=fetched.final_url,
                status=fetched.status,
                title=title_of(text),
                last_updated=modified_of(fetched.body, text),
                raw_file=raw_file,
                text_file=text_file,
                content_hash=content_hash,
                content_verified=content_verified,
                last_checked=utc_timestamp(),
            )
        )

        if item.depth < 1:
            for link in discover_links(fetched.final_url, fetched.body):
                if not seen.get(link):
                    seen[link] = True
                    queue.append(QueueItem(url=link, depth=item.depth + 1))
        time.sleep(0.15)

    write_readme(root, registry)
    save_registry(root, registry)
    return registry


def write_readme(root: str, registry: SourceRegistry) -> None:
    lines = ["# ATO Tax Knowledge Base", "", f"Fetched: {registry.fetched_at}", "", registry.scope, "", "## Sources", ""]
    for rec in registry.records:
        updated = f" - last updated {rec.last_updated}" if rec.last_updated else ""
        lines.append(f"- [{rec.title}]({rec.final_url}){updated}")
    if registry.failures:
        lines.extend(["", "## Fetch Failures", ""])
        for failure in registry.failures:
            lines.append(f"- {failure.url}: {failure.error}")
    Path(os.path.join(data_dir(root), "README.md")).write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_record(root: str, rec: SourceRecord) -> RefreshResult:
    target = first_non_empty(rec.final_url, rec.url)
    try:
        fetched = fetch(target)
    except Exception as exc:
        return RefreshResult(url=target, error=str(exc))

    if fetched.status >= 400:
        return RefreshResult(url=target, status=fetched.status, error=f"HTTP {fetched.status}")

    text, new_hash, content_verified = content_state(fetched.body)
    text_path = os.path.join(cache_dir(root), rec.text_file)
    raw_path = os.path.join(cache_dir(root), rec.raw_file)

    old_bytes = b""
    try:
        old_bytes = Path(text_path).read_bytes()
    except OSError:
        old_bytes = b""

    old_hash = (
        rec.content_hash
        if fetched.body.startswith(b"%PDF")
        else hash_text(old_bytes.decode("utf-8", errors="ignore"))
    )
    changed = old_hash != new_hash
    if changed:
        Path(raw_path).parent.mkdir(parents=True, exist_ok=True)
        Path(text_path).parent.mkdir(parents=True, exist_ok=True)
        Path(raw_path).write_bytes(fetched.body)
        Path(text_path).write_text(text, encoding="utf-8")

    rec.final_url = fetched.final_url
    rec.status = fetched.status
    rec.title = SOURCE_TITLE_OVERRIDES.get(rec.url, title_of(text))
    rec.last_updated = modified_of(fetched.body, text)
    rec.last_checked = utc_timestamp()
    rec.content_hash = new_hash
    rec.content_verified = content_verified
    return RefreshResult(url=fetched.final_url, status=fetched.status, changed=changed, title=rec.title)


def add_url(root: str, raw_url: str) -> Tuple[Optional[SourceRecord], RefreshResult]:
    if not ato_url_allowed(raw_url):
        return None, RefreshResult(url=raw_url, error="new source URL must use https://www.ato.gov.au")
    try:
        fetched = fetch(raw_url)
    except Exception as exc:
        return None, RefreshResult(url=raw_url, error=str(exc))
    if fetched.status >= 400:
        return None, RefreshResult(url=raw_url, status=fetched.status, error=f"HTTP {fetched.status}")
    if not ato_url_allowed(fetched.final_url):
        return None, RefreshResult(url=raw_url, status=fetched.status, error="source redirected outside www.ato.gov.au")

    text, content_hash, content_verified = content_state(fetched.body)
    slug = slug_for(fetched.final_url)
    raw_file = os.path.join("raw", f"{slug}.html")
    text_file = os.path.join("text", f"{slug}.txt")
    raw_path = Path(cache_dir(root), raw_file)
    text_path = Path(cache_dir(root), text_file)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(fetched.body)
    text_path.write_text(text, encoding="utf-8")
    record = SourceRecord(
        url=raw_url,
        final_url=fetched.final_url,
        status=fetched.status,
        title=SOURCE_TITLE_OVERRIDES.get(raw_url, title_of(text)),
        last_updated=modified_of(fetched.body, text),
        raw_file=raw_file,
        text_file=text_file,
        content_hash=content_hash,
        content_verified=content_verified,
        last_checked=utc_timestamp(),
    )
    return record, RefreshResult(
        url=fetched.final_url,
        status=fetched.status,
        changed=True,
        title=record.title,
    )


def content_state(body: bytes) -> Tuple[str, str, bool]:
    if body.startswith(b"%PDF"):
        return "", hashlib.sha256(body).hexdigest(), bool(body)
    text = clean_text(body)
    content_hash = hash_text(text)
    return text, content_hash, bool(text.strip()) and content_hash != hash_text("")


def ato_url_allowed(raw_url: str) -> bool:
    parsed = urlparse(raw_url)
    return parsed.scheme == "https" and parsed.netloc.lower() == "www.ato.gov.au"


def first_non_empty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ""


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def copy_dir(src: str, dst: str) -> None:
    source = Path(src)
    destination = Path(dst)
    if not source.exists():
        raise FileNotFoundError(src)
    if not source.is_dir():
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(source.read_bytes())
        return
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)


def write_json(value: object) -> None:
    print(json.dumps(value, indent=2))


def errorf(message: str, *args: object) -> None:
    print(message % args if args else message, file=os.sys.stderr)


def ensure_root(root: str) -> None:
    if not os.path.exists(os.path.join(root, "SKILL.md")):
        raise RuntimeError("cannot locate skill root with SKILL.md")


SkillRoot = skill_root
DataDir = data_dir
CacheDir = cache_dir
RegistryPath = registry_path
LoadRegistry = load_registry
SaveRegistry = save_registry
Fetch = fetch
CleanText = clean_text
TitleOf = title_of
ModifiedOf = modified_of
SlugFor = slug_for
HashText = hash_text
RecordText = record_text
Terms = terms
QueryScore = query_score
SelectByQuery = select_by_query
SelectByURL = select_by_url
DiscoverLinks = discover_links
PathAllowed = path_allowed
firstNonEmpty = first_non_empty
CopyDir = copy_dir
WriteJSON = write_json
Errorf = errorf
EnsureRoot = ensure_root
Recrawl = recrawl
WriteReadme = write_readme
RefreshRecord = refresh_record
AddURL = add_url
Scope = SCOPE
SeedURLs = SEED_URLS
PathKeywords = PATH_KEYWORDS
