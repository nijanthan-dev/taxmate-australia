package skillgen

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"taxmate-au-skill/internal/atodata"
)

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

func TestExtractMainTextRemovesShellNoise(t *testing.T) {
	html := []byte(`<html><body><header>Skip to main content Login</header><nav>Menu footer link</nav><main><h1>Fixed rate method</h1><p>You need records for hours worked from home.</p></main><footer>Contact us</footer><script>alert(1)</script></body></html>`)
	text := ExtractMainText(html)
	for _, forbidden := range []string{"Skip to main content", "Menu", "Contact us", "alert"} {
		if strings.Contains(text, forbidden) {
			t.Fatalf("shell noise not removed: %q in %q", forbidden, text)
		}
	}
	if !strings.Contains(text, "records for hours worked") {
		t.Fatalf("main content missing: %q", text)
	}
}

func TestGenerateDeterministicAndDeduplicates(t *testing.T) {
	root := fixtureRoot(t)
	report1, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"})
	if err != nil {
		t.Fatal(err)
	}
	first, err := StableBytes(filepath.Join(root, "skills", "work-from-home", "references", "sources.json"))
	if err != nil {
		t.Fatal(err)
	}
	report2, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"})
	if err != nil {
		t.Fatal(err)
	}
	second, err := StableBytes(filepath.Join(root, "skills", "work-from-home", "references", "sources.json"))
	if err != nil {
		t.Fatal(err)
	}
	if string(first) != string(second) {
		t.Fatal("generation not deterministic")
	}
	if len(report1.Sources) != len(report2.Sources) {
		t.Fatal("report changed between identical runs")
	}
	foundDuplicate := false
	for _, src := range report1.Sources {
		if src.DuplicateOf != "" {
			foundDuplicate = true
		}
	}
	if !foundDuplicate {
		t.Fatal("duplicate canonical source not reported")
	}
}

func TestGeneratedSkillsContainGuardrailsAndNoHTML(t *testing.T) {
	root := fixtureRoot(t)
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
	root := fixtureRoot(t)
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

func TestSourceMapCompletenessDuplicateEvidenceAndReverseProvenance(t *testing.T) {
	root := fixtureRoot(t)
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	sourceMap, err := LoadSourceMap(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(sourceMap.Sources) != 3 {
		t.Fatalf("source map count = %d", len(sourceMap.Sources))
	}
	statuses := map[string]int{}
	for _, entry := range sourceMap.Sources {
		statuses[entry.Status]++
		switch entry.Status {
		case StatusUsed:
			if len(entry.Skills) == 0 || len(entry.References) == 0 || len(entry.CoveredConcepts) == 0 {
				t.Fatalf("used entry missing destination/concepts: %+v", entry)
			}
			for _, ref := range entry.References {
				body, err := os.ReadFile(filepath.Join(root, filepath.FromSlash(ref)))
				if err != nil {
					t.Fatal(err)
				}
				if !strings.Contains(string(body), entry.CanonicalURL) && !strings.Contains(string(body), entry.SourceID) {
					t.Fatalf("reference missing reverse provenance for %s in %s", entry.SourceID, ref)
				}
			}
		case StatusDuplicate:
			if entry.DuplicateOf == "" || !strings.Contains(entry.DuplicateEvidence, "identical canonical URL") {
				t.Fatalf("duplicate missing evidence: %+v", entry)
			}
		case StatusNeedsReview:
			t.Fatalf("fixture should not leave review items: %+v", entry)
		}
	}
	if statuses[StatusUsed] != 2 || statuses[StatusDuplicate] != 1 {
		t.Fatalf("unexpected statuses: %+v", statuses)
	}
}

func TestSourceMapValidationDetectsMissingDestination(t *testing.T) {
	root := fixtureRoot(t)
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(filepath.Join(root, "skills", "work-from-home", "references", "rules.md")); err != nil {
		t.Fatal(err)
	}
	if err := ValidateSourceMap(root); err == nil {
		t.Fatal("expected missing destination failure")
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
	root := fixtureRoot(t)
	if _, err := Generate(Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, "data", "ato_knowledge_base", "raw"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := Validate(root); err == nil {
		t.Fatal("expected raw snapshot validation failure")
	}
}

func fixtureRoot(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	dataDir := filepath.Join(root, "data", "ato_knowledge_base")
	if err := os.MkdirAll(filepath.Join(dataDir, "text"), 0755); err != nil {
		t.Fatal(err)
	}
	records := []*atodata.Record{
		rec("https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method", "Fixed rate method", "text/wfh.txt", "For 2025-26 you may see 70 cents per work hour. Keep records for hours worked from home.", "2026-06-07T14:00:00.000+00:00"),
		rec("https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/work-related-deductions/working-from-home-expenses/fixed-rate-method?x=1", "Fixed rate method duplicate", "text/wfh-dup.txt", "Duplicate page should dedupe.", "2026-06-07T14:00:00.000+00:00"),
		rec("https://www.ato.gov.au/individuals-and-families/investments-and-assets/capital-gains-tax/cgt-events", "CGT events", "text/cgt.txt", "A CGT event can happen on disposal. Main residence and inherited assets need review.", "2026-06-07T14:00:00.000+00:00"),
	}
	for _, r := range records {
		if err := os.WriteFile(filepath.Join(dataDir, r.TextFile), []byte(textFor(r.TextFile, records)), 0644); err != nil {
			t.Fatal(err)
		}
	}
	idx := atodata.Index{Scope: "test", Records: records}
	body, err := json.MarshalIndent(idx, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, "source_index.json"), append(body, '\n'), 0644); err != nil {
		t.Fatal(err)
	}
	return root
}

func rec(url, title, textFile, text, updated string) *atodata.Record {
	return &atodata.Record{URL: url, FinalURL: url, Status: 200, Title: title, LastUpdated: updated, TextFile: textFile}
}

func textFor(path string, records []*atodata.Record) string {
	switch path {
	case "text/wfh.txt":
		return "For 2025-26 you may see 70 cents per work hour. Keep records for hours worked from home."
	case "text/wfh-dup.txt":
		return "Duplicate page should dedupe."
	default:
		return "A CGT event can happen on disposal. Main residence and inherited assets need review."
	}
}
