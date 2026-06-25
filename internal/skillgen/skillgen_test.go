package skillgen

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"taxmate-au-skill/internal/atodata"
)

type fixtureSource struct {
	URL          string
	FinalURL     string
	Title        string
	Text         string
	LastUpdated  string
	CheckedAt    string
	Status       int
	RegistryHash string
}

func TestHostApprovedOfficialOnly(t *testing.T) {
	for _, raw := range []string{"https://www.ato.gov.au/a", "https://ato.gov.au/a", "https://www.abr.gov.au/a"} {
		if !HostApproved(raw) {
			t.Fatalf("expected approved host: %s", raw)
		}
	}
	for _, raw := range []string{"https://evil.example/a", "https://ato.gov.au.evil.example/a", "not-url"} {
		if HostApproved(raw) {
			t.Fatalf("expected rejected host: %s", raw)
		}
	}
}

func TestSourceIDStableAfterRename(t *testing.T) {
	url := "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method"
	canonical := canonicalURL(url + "?q=1")
	first := sourceID(url, canonical)
	second := sourceID(url, canonical)
	if first != second {
		t.Fatalf("source id must be stable: %s != %s", first, second)
	}
}

func TestLoadSourceRegistry(t *testing.T) {
	root := t.TempDir()
	dataDir := filepath.Join(root, "data", "ato_knowledge_base")
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		t.Fatal(err)
	}

	records := []*atodata.SourceRecord{
		{URL: "https://www.ato.gov.au/example", FinalURL: "https://www.ato.gov.au/example", Status: 200, Title: "Example", LastUpdated: "2026-01-01", TextFile: "text/example.txt", ContentHash: "abc123", LastChecked: "2026-06-20T00:00:00Z"},
	}
	registry := &atodata.SourceRegistry{Scope: "test", Records: records}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		t.Fatal(err)
	}
	loaded, err := atodata.LoadRegistry(root)
	if err != nil {
		t.Fatal(err)
	}
	if loaded.Scope != "test" {
		t.Fatalf("scope mismatch: %q", loaded.Scope)
	}
	if len(loaded.Records) != len(records) {
		t.Fatalf("record count mismatch: %d", len(loaded.Records))
	}
}

func TestCoverageHasEntryPerRegistrySource(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "working from home fixed-rate records and receipts"},
		{URL: "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-events", Title: "CGT events", Text: "capital gains tax event records for disposal and proceeds"},
		{URL: "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business", Title: "Business income", Text: "business income includes assessable income and deductions"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(coverage.Sources) != len(registry.Records) {
		t.Fatalf("coverage entries %d != registry records %d", len(coverage.Sources), len(registry.Records))
	}
	seen := map[string]struct{}{}
	for _, rec := range registry.Records {
		canonical := canonicalURL(firstNonEmpty(rec.FinalURL, rec.URL))
		seen[sourceID(rec.URL, canonical)] = struct{}{}
	}
	for _, entry := range coverage.Sources {
		if _, ok := seen[entry.SourceID]; !ok {
			t.Fatalf("coverage source_id not in registry: %s", entry.SourceID)
		}
	}
}

func TestGenerateDeterministicAndDeduplicates(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "working from home fixed-rate records and receipts"},
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method?x=1", Title: "WFH fixed duplicate", Text: "same topic, same canonical URL and content"},
		{URL: "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-events", Title: "CGT events", Text: "A capital gains event occurs on disposal and can create gain or loss"},
	})

	report1, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"})
	if err != nil {
		t.Fatal(err)
	}
	first, err := StableBytes(filepath.Join(root, "data", "ato_knowledge_base", "source_coverage.json"))
	if err != nil {
		t.Fatal(err)
	}
	if report1 == nil || len(report1.Sources) == 0 {
		t.Fatal("expected generation report")
	}
	report2, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"})
	if err != nil {
		t.Fatal(err)
	}
	second, err := StableBytes(filepath.Join(root, "data", "ato_knowledge_base", "source_coverage.json"))
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Equal(first, second) == false {
		t.Fatal("generation not deterministic")
	}
	if len(report1.Sources) != len(report2.Sources) {
		t.Fatal("report source count changed between identical runs")
	}
	foundDuplicate := false
	for _, src := range report1.Sources {
		if src.Status == StatusDuplicate {
			foundDuplicate = true
			break
		}
	}
	if !foundDuplicate {
		t.Fatal("duplicate canonical source not reported")
	}
}

func TestGeneratedSkillsContainGuardrailsAndNoHTML(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "For 2025-26 you may see 70 cents per hour. Keep records for hours worked from home."},
		{URL: "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-events", Title: "CGT events", Text: "A CGT event can happen on disposal and includes main residence treatment"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	body, err := os.ReadFile(filepath.Join(root, "skills", "capital-gains-tax", "SKILL.md"))
	if err != nil {
		t.Fatal(err)
	}
	text := string(body)
	for _, needle := range []string{"Accountant review", "Claim candidate", "must not be bypassed", "never fabricate"} {
		if !strings.Contains(text, needle) {
			t.Fatalf("missing guardrail %q", needle)
		}
	}
	if strings.Contains(text, "<html") || strings.Contains(text, "<script") {
		t.Fatal("generated skill contains raw HTML")
	}
}

func TestVolatileValuesHaveProvenance(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/working-from-home-expenses", Title: "WFH fixed", Text: "For 2025-26 you may see 70 cents per work hour. Keep records for hours worked from home."},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	body, err := os.ReadFile(filepath.Join(root, "skills", "work-from-home", "references", "current-values.json"))
	if err != nil {
		t.Fatal(err)
	}
	var values []ValueFact
	if err := json.Unmarshal(body, &values); err != nil {
		t.Fatal(err)
	}
	if len(values) == 0 {
		t.Fatal("expected volatile value facts")
	}
	for _, value := range values {
		if value.SourceURL == "" || value.SourceTitle == "" || value.CheckedAt == "" || value.ContentHash == "" || value.ReuseWarning == "" {
			t.Fatalf("missing provenance: %+v", value)
		}
		if value.IncomeYear == "" && (value.EffectiveFrom == "" || value.EffectiveTo == "") {
			t.Fatalf("missing period: %+v", value)
		}
	}
}

func TestCoverageUnknownSourceRejects(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "records for fixed rate"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	coverage.Sources = append(coverage.Sources, SourceCoverageEntry{
		SourceID:        "ato-000000000000",
		CanonicalURL:    "https://www.example.com/unknown",
		CheckedAt:       "2026-06-24T00:00:00Z",
		Status:          StatusMetadataOnly,
		References:      []string{"skills/work-from-home/references/sources.json"},
		Skills:          []string{"work-from-home"},
		Reason:          "test-only",
		ContentHash:     "abc",
		LastUpdated:     "2026-06-20T00:00:00Z",
		CoveredConcepts: []string{"missing"},
	})
	if err := writeSourceCoverageToRegistryPath(root, coverage); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected unknown source_id failure")
	}
}

func TestCoverageMissingRegistrySourceRejects(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "records for fixed rate"},
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim", Title: "Deductible expenses", Text: "deductible expenses for work"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(registry.Records) > 0 {
		registry.Records = registry.Records[1:]
	}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected registry mismatch failure")
	}
}

func TestVerifiedSourceRequiresNonEmptyExtractedContent(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "   \t  \n"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, entry := range coverage.Sources {
		if entry.Status == StatusVerified {
			t.Fatalf("source %s was verified with empty content", entry.SourceID)
		}
	}
}

func TestVerifiedSourcesRejectEmptyContentHash(t *testing.T) {
	text := "working from home records for effective verification"
	hash := atodata.HashText(text)
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: text, RegistryHash: hash},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	for i := range coverage.Sources {
		if coverage.Sources[i].Status == StatusVerified {
			coverage.Sources[i].ContentHash = EmptyContentHashValue
			break
		}
	}
	if err := writeSourceCoverageToRegistryPath(root, coverage); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected empty-content hash failure")
	}
}

func TestMetadataOnlySourcesRemainMetadataOnly(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/working-from-home-expenses", Title: "WFH fixed", Text: ""},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	body, err := os.ReadFile(filepath.Join(root, "skills", "work-from-home", "references", "sources.json"))
	if err != nil {
		t.Fatal(err)
	}
	var localSources []Source
	if err := json.Unmarshal(body, &localSources); err != nil {
		t.Fatal(err)
	}
	if len(localSources) == 0 || localSources[0].Status != StatusMetadataOnly {
		t.Fatalf("expected metadata-only source in per-skill sources: %+v", localSources)
	}
	rules, err := os.ReadFile(filepath.Join(root, "skills", "work-from-home", "references", "rules.md"))
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(string(rules), "Metadata-only official-source links") {
		t.Fatal("missing metadata-only heading")
	}
}

func TestDuplicateEvidenceAndChainValidation(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "same content for duplicate detection"},
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method?x=1", Title: "WFH fixed variant", Text: "same content for duplicate detection"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	var duplicate *SourceCoverageEntry
	for _, entry := range coverage.Sources {
		if entry.Status == StatusDuplicate {
			tmp := entry
			duplicate = &tmp
			break
		}
	}
	if duplicate == nil {
		t.Fatal("expected duplicate source")
	}
	if duplicate.DuplicateOf == "" {
		t.Fatal("duplicate missing duplicate_of")
	}
	if duplicate.DuplicateEvidence == "" {
		t.Fatal("duplicate missing evidence")
	}
	if !isSupportedDuplicateEvidence(duplicate.DuplicateEvidence) {
		t.Fatalf("unsupported duplicate evidence %q", duplicate.DuplicateEvidence)
	}
	if err := ValidateSourceCoverage(root); err != nil {
		t.Fatal(err)
	}
	for i, entry := range coverage.Sources {
		if entry.SourceID == duplicate.SourceID {
			coverage.Sources[i].DuplicateEvidence = "unsupported"
		}
	}
	if err := writeSourceCoverageToRegistryPath(root, coverage); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected unsupported duplicate evidence failure")
	}
}

func TestDuplicateSelfReferenceRejected(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "same content for duplicate detection"},
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method?x=1", Title: "WFH fixed variant", Text: "same content for duplicate detection"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	for i, entry := range coverage.Sources {
		if entry.Status == StatusDuplicate {
			coverage.Sources[i].DuplicateOf = entry.SourceID
		}
	}
	if err := writeSourceCoverageToRegistryPath(root, coverage); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected duplicate self-reference failure")
	}
}

func TestExcludedSourcesRequireReason(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://example.com/not-ato-page", Title: "External", Text: ""},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(coverage.Sources) != 1 || coverage.Sources[0].Status != StatusExcluded {
		t.Fatalf("expected excluded source: %+v", coverage.Sources)
	}
	if strings.TrimSpace(coverage.Sources[0].Reason) == "" {
		t.Fatal("expected excluded reason")
	}
	coverage.Sources[0].Reason = ""
	if err := writeSourceCoverageToRegistryPath(root, coverage); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected excluded reason check failure")
	}
}

func TestNeedsReviewRejectedByCoverageValidation(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "working from home records"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(coverage.Sources) > 0 {
		coverage.Sources[0].Status = StatusNeedsReview
	}
	if err := writeSourceCoverageToRegistryPath(root, coverage); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected needs_review failure")
	}
}

func TestSourceProvenanceMatchesPerSkillFiles(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method", Title: "WFH fixed", Text: "records for WFH fixed-rate 2026"},
		{URL: "https://www.ato.gov.au/investments-and-assets/capital-gains-tax", Title: "CGT", Text: "capital gains tax disclosure and events"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	assigned, err := loadPerSkillSourceAssignments(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, entry := range coverage.Sources {
		if entry.Status != StatusVerified && entry.Status != StatusMetadataOnly {
			continue
		}
		for _, skill := range entry.Skills {
			local, ok := assigned[skill][entry.SourceID]
			if !ok {
				t.Fatalf("missing local source %s for skill %s", entry.SourceID, skill)
			}
			if local.Status != entry.Status {
				t.Fatalf("status mismatch %s for %s", entry.SourceID, skill)
			}
			if local.CheckedAt != entry.CheckedAt {
				t.Fatalf("checked_at mismatch for %s", entry.SourceID)
			}
		}
	}
}

func TestAuditAssignmentAndVerifiedCoverageStates(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/working-from-home-expenses", Title: "WFH fixed", Text: ""},
		{URL: "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax", Title: "CGT", Text: "capital gains tax events"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	summary := Audit(root, coverage)
	wfh := summary.BySkill["work-from-home"]
	if wfh.CoverageStatus != "metadata_only" || wfh.MetadataOnlySources != 1 {
		t.Fatalf("unexpected work-from-home state %+v", wfh)
	}
	if !contains(summary.RequiredVerifiedMissing, "work-from-home") {
		t.Fatalf("expected work-from-home in required_verified_missing")
	}
	if summary.BySkill["capital-gains-tax"].CoverageStatus != "verified" {
		t.Fatalf("expected verified state for capital-gains-tax: %+v", summary.BySkill["capital-gains-tax"])
	}
}

func TestCGTSubtopicCoverage(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{URL: "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount", Title: "CGT discount", Text: "capital gains discount rules apply"},
		{URL: "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-discount?x=1", Title: "CGT shares", Text: "shares and similar investments are CGT assets"},
		{URL: "https://www.ato.gov.au/individuals-and-families/income/crypto-asset-investments", Title: "Crypto", Text: "crypto swaps and proceeds are records"},
		{URL: "https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/shares-and-similar-investments", Title: "Shares", Text: "shares ETFs and DRP are CGT assets"},
		{URL: "https://www.ato.gov.au/individuals-and-families/income-and-capital-proceeds/property-and-capital-gains-tax", Title: "Property CGT", Text: "property rental is treated as capital gains asset"},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	summary := Audit(root, coverage)
	if !summary.CGTCoverage["general"] {
		t.Fatal("expected general cgT coverage")
	}
	if !summary.CGTCoverage["shares_etfs_managed_funds"] {
		t.Fatal("expected shares ETF cgT coverage")
	}
	if !summary.CGTCoverage["crypto"] {
		t.Fatal("expected crypto CGT coverage")
	}
	if !summary.CGTCoverage["property_rental"] {
		t.Fatal("expected property CGT coverage")
	}
}

func TestGenerateCheckDoesNotMutateTrackedFiles(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{
		{
			URL:   "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method",
			Title: "WFH fixed",
			Text:  "records for fixed rate and receipts",
		},
	})
	_, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"})
	if err != nil {
		t.Fatal(err)
	}
	before := stableDirectorySnapshot(t, root)
	tmpDir, err := os.MkdirTemp("", "taxmate-coverage-check-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = os.RemoveAll(tmpDir) })
	workRoot := filepath.Join(tmpDir, "work")
	if err := copyDirForTest(filepath.Join(root, "data", "ato_knowledge_base"), filepath.Join(workRoot, "data", "ato_knowledge_base")); err != nil {
		t.Fatal(err)
	}
	if err := copyDirForTest(filepath.Join(root, "skills"), filepath.Join(workRoot, "skills")); err != nil {
		t.Fatal(err)
	}
	if _, err := Generate(Options{Root: workRoot, OutputRoot: workRoot, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	if err := CompareGeneratedArtifacts(root, workRoot); err != nil {
		t.Fatal(err)
	}
	after := stableDirectorySnapshot(t, root)
	if len(before) != len(after) {
		t.Fatalf("tracked file count changed: before=%d after=%d", len(before), len(after))
	}
	for path, digest := range before {
		if after[path] != digest {
			t.Fatalf("tracked file changed: %s", path)
		}
	}
}

func TestGenerateWithPreviousCoveragePreservesVerifiedWhenTextDropped(t *testing.T) {
	content := "working from home records for effective extraction"
	hash := atodata.HashText(content)
	root := fixtureRoot(t, []fixtureSource{{
		URL:          "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method",
		Title:        "WFH fixed",
		Text:         content,
		LastUpdated:  "2026-06-24T00:00:00Z",
		RegistryHash: hash,
	}})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(coverage.Sources) == 0 || coverage.Sources[0].Status != StatusVerified {
		t.Fatal("initial run expected verified")
	}
	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		t.Fatal(err)
	}
	for _, rec := range registry.Records {
		rec.TextFile = ""
	}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		t.Fatal(err)
	}
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-25T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage2, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(coverage2.Sources) == 0 || coverage2.Sources[0].Status != StatusVerified {
		t.Fatalf("expected preserved verified status, got %v", coverage2.Sources)
	}
	if coverage2.Sources[0].ContentHash == "" {
		t.Fatal("expected preserved content hash")
	}
	if coverage2.Sources[0].ContentHash != coverage.Sources[0].ContentHash {
		t.Fatalf("preserved hash mismatch: %s != %s", coverage2.Sources[0].ContentHash, coverage.Sources[0].ContentHash)
	}
}

func TestCacheCleanupDoesNotInvalidateVerifiedCoverage(t *testing.T) {
	text := "workplace travel records and amounts with clear headings"
	root := fixtureRoot(t, []fixtureSource{
		{
			URL:          "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions",
			Title:        "Business deductions",
			Text:         text,
			RegistryHash: atodata.HashText(text),
		},
	})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}

	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(registry.Records) != 1 {
		t.Fatalf("expected one registry record, got %d", len(registry.Records))
	}
	cachePath := filepath.Join(root, ".cache", "ato", registry.Records[0].TextFile)
	if err := os.Remove(cachePath); err != nil && !os.IsNotExist(err) {
		t.Fatalf("remove cache path failed: %v", err)
	}

	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-25T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(coverage.Sources) != 1 {
		t.Fatalf("expected one coverage source, got %d", len(coverage.Sources))
	}
	if coverage.Sources[0].Status != StatusVerified {
		t.Fatalf("expected verified status after cache cleanup, got %s", coverage.Sources[0].Status)
	}
	if coverage.Sources[0].ContentHash != atodata.HashText(text) {
		t.Fatalf("expected preserved hash %s, got %s", atodata.HashText(text), coverage.Sources[0].ContentHash)
	}
	if coverage.Sources[0].CheckedAt != "2026-06-25T00:00:00Z" {
		t.Fatalf("expected refreshed checked_at, got %s", coverage.Sources[0].CheckedAt)
	}
}

func TestCurrentValueValidationRejectsStaleWrongYearAndMissingPeriod(t *testing.T) {
	value := ValueFact{
		Value:       "70 cents",
		Unit:        "cents",
		Context:     "For 2025-26 only",
		IncomeYear:  "2025-26",
		SourceURL:   "https://www.ato.gov.au/example",
		SourceTitle: "Example",
		CheckedAt:   "2026-06-24T00:00:00Z",
		ContentHash: "abc123",
	}
	if err := ValidateCurrentValue(value, "2025-26", true); err != nil {
		t.Fatalf("expected usable value: %v", err)
	}
	if err := ValidateCurrentValue(value, "2024-25", true); err == nil {
		t.Fatal("expected wrong-year rejection")
	}
	if err := ValidateCurrentValue(value, "2025-26", false); err == nil {
		t.Fatal("expected unverified-source rejection")
	}
	value.IncomeYear = ""
	if err := ValidateCurrentValue(value, "", true); err == nil {
		t.Fatal("expected missing-period rejection")
	}
}

func TestClassificationConservative(t *testing.T) {
	if got := Classify(ClassificationInput{HasEvidence: false}); got != "Insufficient evidence" {
		t.Fatalf("missing evidence got %s", got)
	}
	if got := Classify(ClassificationInput{HasEvidence: true, ComplexCGT: true}); got != "Accountant review" {
		t.Fatalf("complex CGT got %s", got)
	}
	if got := Classify(ClassificationInput{HasEvidence: true, OverrideReview: true}); got != "Accountant review" {
		t.Fatalf("override got %s", got)
	}
	if got := Classify(ClassificationInput{HasEvidence: true, FabricateRecords: true}); got != "Not claimable" {
		t.Fatalf("fabrication got %s", got)
	}
	if got := Classify(ClassificationInput{HasEvidence: true}); got != "Claim candidate" {
		t.Fatalf("supported evidence got %s", got)
	}
}

func TestValidateFailsWhenRawSnapshotsRemain(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{{
		URL:   "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method",
		Title: "WFH fixed",
		Text:  "working from home records",
	}})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, "data", "ato_knowledge_base", "raw"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "data", "ato_knowledge_base", "raw", "snapshot.html"), []byte("x"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := Validate(root); err == nil {
		t.Fatal("expected raw snapshot validation failure")
	}
}

func TestSourceRegistryAndCoverageFileExistAfterGenerate(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{{
		URL:   "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method",
		Title: "WFH fixed",
		Text:  "working from home records",
	}})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	if _, err := os.Stat(filepath.Join(root, "data", "ato_knowledge_base", "source_registry.json")); err != nil {
		t.Fatalf("source_registry missing")
	}
	if _, err := os.Stat(filepath.Join(root, "data", "ato_knowledge_base", "source_coverage.json")); err != nil {
		t.Fatalf("source_coverage missing")
	}
}

func TestLegacySourceArtifactsAreNotRequiredForGeneration(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{{
		URL:   "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method",
		Title: "WFH fixed",
		Text:  "working from home records",
	}})
	registryOld := filepath.Join(root, "data", "ato_knowledge_base", "source_index.json")
	if err := os.Remove(registryOld); err != nil && !os.IsNotExist(err) {
		t.Fatal(err)
	}
	if _, err := os.Stat(registryOld); err == nil {
		t.Fatal("old registry path should be absent")
	}
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
}

func TestValidationRejectsNeedsReviewAndUnknownCoverageEntries(t *testing.T) {
	root := fixtureRoot(t, []fixtureSource{{
		URL:   "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/fixed-rate-method",
		Title: "WFH fixed",
		Text:  "working from home records",
	}})
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(coverage.Sources) == 0 {
		t.Fatal("no coverage entries")
	}
	coverage.Sources = append(coverage.Sources, SourceCoverageEntry{SourceID: "bad", CanonicalURL: "https://example.com", Status: StatusNeedsReview, CheckedAt: "2026-06-24T00:00:00Z"})
	if err := writeSourceCoverageToRegistryPath(root, coverage); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceCoverage(root); err == nil {
		t.Fatal("expected needs_review validation failure")
	}
}

func fixtureRoot(t *testing.T, sources []fixtureSource) string {
	t.Helper()
	root := t.TempDir()
	dataDir := filepath.Join(root, "data", "ato_knowledge_base")
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, ".cache", "ato", "text"), 0o755); err != nil {
		t.Fatal(err)
	}
	for _, status := range requiredSkillSlugs() {
		for _, suffix := range []string{"SKILL.md", "references/rules.md", "references/evidence.md", "references/sources.json"} {
			path := filepath.Join(root, "skills", status)
			if err := os.MkdirAll(filepath.Dir(filepath.Join(path, suffix)), 0o755); err != nil {
				t.Fatal(err)
			}
		}
	}

	entries := make([]*atodata.SourceRecord, 0, len(sources))
	for i, source := range sources {
		entry := &atodata.SourceRecord{URL: source.URL, Status: source.Status, Title: source.Title}
		if entry.Status == 0 {
			entry.Status = 200
		}
		if source.FinalURL != "" {
			entry.FinalURL = source.FinalURL
		} else {
			entry.FinalURL = source.URL
		}
		entry.LastUpdated = firstNonEmpty(source.LastUpdated, "2026-06-20T00:00:00Z")
		entry.LastChecked = source.CheckedAt
		if source.RegistryHash != "" {
			entry.ContentHash = source.RegistryHash
		} else if source.Text != "" {
			entry.ContentHash = atodata.HashText(source.Text)
		}
		if source.Text != "" {
			textFile := filepath.Join("text", "source_"+slugForTest(i))
			cacheFile := filepath.Join(root, ".cache", "ato", textFile)
			if err := os.WriteFile(cacheFile, []byte(source.Text), 0o644); err != nil {
				t.Fatal(err)
			}
			entry.TextFile = textFile
		}
		entries = append(entries, entry)
	}
	registry := &atodata.SourceRegistry{Scope: "test", Records: entries}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		t.Fatal(err)
	}
	return root
}

func slugForTest(i int) string {
	return fmt.Sprintf("source_%03d", i)
}

func contains(values []string, item string) bool {
	for _, value := range values {
		if value == item {
			return true
		}
	}
	return false
}

func writeSourceCoverageToRegistryPath(root string, coverage SourceCoverage) error {
	path := filepath.Join(root, "data", "ato_knowledge_base", sourceCoverageFileName)
	return writeJSON(path, coverage)
}

func copyDirForTest(src, dst string) error {
	info, err := os.Stat(src)
	if err != nil {
		return err
	}
	if !info.IsDir() {
		if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
			return err
		}
		body, readErr := os.ReadFile(src)
		if readErr != nil {
			return readErr
		}
		return os.WriteFile(dst, body, 0o644)
	}
	if err := os.MkdirAll(dst, 0o755); err != nil {
		return err
	}
	return filepath.WalkDir(src, func(path string, d os.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel, relErr := filepath.Rel(src, path)
		if relErr != nil {
			return relErr
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			return os.MkdirAll(target, 0o755)
		}
		body, readErr := os.ReadFile(path)
		if readErr != nil {
			return readErr
		}
		if err := os.MkdirAll(filepath.Dir(target), 0o755); err != nil {
			return err
		}
		return os.WriteFile(target, body, 0o644)
	})
}

func stableDirectorySnapshot(t *testing.T, root string) map[string]string {
	t.Helper()
	out := map[string]string{}
	_ = filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		body, readErr := os.ReadFile(path)
		if readErr != nil {
			return nil
		}
		rel, relErr := filepath.Rel(root, path)
		if relErr != nil {
			return nil
		}
		out[rel] = string(bytes.TrimSpace(body))
		return nil
	})
	return out
}
