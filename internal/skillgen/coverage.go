package skillgen

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"taxmate-au-skill/internal/atodata"
)

const (
	StatusVerified         = "verified"
	StatusMetadataOnly     = "metadata_only"
	StatusDuplicate        = "duplicate"
	StatusExcluded         = "excluded"
	StatusNeedsReview      = "needs_review"
	EmptyContentHashValue  = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
	sourceCoverageFileName = "source_coverage.json"
)

type SourceCoverage struct {
	Sources []SourceCoverageEntry `json:"sources"`
}

type SourceCoverageEntry struct {
	SourceID          string   `json:"source_id"`
	OriginalURL       string   `json:"original_url"`
	CanonicalURL      string   `json:"canonical_url"`
	Title             string   `json:"source_title"`
	LastUpdated       string   `json:"source_last_updated,omitempty"`
	CheckedAt         string   `json:"checked_at"`
	ContentHash       string   `json:"content_hash,omitempty"`
	Status            string   `json:"status"`
	Skills            []string `json:"skills,omitempty"`
	References        []string `json:"references,omitempty"`
	CoveredConcepts   []string `json:"covered_concepts,omitempty"`
	DuplicateOf       string   `json:"duplicate_of,omitempty"`
	DuplicateEvidence string   `json:"duplicate_evidence,omitempty"`
	Reason            string   `json:"reason,omitempty"`
}

type CoverageSkillState struct {
	AssignedSources     int    `json:"assigned_sources"`
	VerifiedSources     int    `json:"verified_sources"`
	MetadataOnlySources int    `json:"metadata_only_sources"`
	CoverageStatus      string `json:"coverage_status"`
}

type CoverageSummary struct {
	Total                     int
	Verified                  int
	MetadataOnly              int
	Duplicate                 int
	Excluded                  int
	NeedsReview               int
	BySkill                   map[string]CoverageSkillState
	MissingDestinationFiles   []string
	MissingReverseProvenance  []string
	InvalidHashes             []string
	DuplicateEvidenceIssues   []string
	DuplicateChainIssues      []string
	RequiredAssignmentMissing []string
	RequiredVerifiedMissing   []string
	VolatileMissingPeriods    []string
	SkillsMissingGuardrail    []string
	NotUsedEntries            []string
	ReviewEntries             []string
	CGTCoverage               map[string]bool
}

func BuildSourceCoverage(report *GenerationReport) SourceCoverage {
	coverageByCanonical := map[string]string{}
	coverage := SourceCoverage{}
	for _, src := range report.Sources {
		canonical := coverageCanonicalURL(src.URL, src.FinalURL)
		sourceIDValue := sourceID(src.URL, canonical)
		if src.Status != StatusDuplicate && src.Status != StatusNeedsReview {
			coverageByCanonical[canonical] = sourceIDValue
		}
	}
	for _, src := range report.Sources {
		canonical := coverageCanonicalURL(src.URL, src.FinalURL)
		entry := SourceCoverageEntry{
			SourceID:        sourceID(src.URL, canonical),
			OriginalURL:     src.URL,
			CanonicalURL:    canonical,
			Title:           src.Title,
			LastUpdated:     src.LastUpdated,
			CheckedAt:       src.CheckedAt,
			ContentHash:     src.ContentHash,
			Status:          src.Status,
			CoveredConcepts: conceptsFor(src.AssignedSkill),
			Reason:          firstNonEmpty(src.AssignmentReason, src.Reason),
		}
		if entry.CanonicalURL == "" {
			entry.CanonicalURL = src.URL
		}
		switch src.Status {
		case StatusVerified, StatusMetadataOnly:
			if src.AssignedSkill != "" {
				entry.Skills = append(entry.Skills, src.AssignedSkill)
				entry.References = append(entry.References,
					filepath.ToSlash(filepath.Join("skills", src.AssignedSkill, "references", "rules.md")),
					filepath.ToSlash(filepath.Join("skills", src.AssignedSkill, "references", "sources.json")),
				)
			}
		case StatusDuplicate:
			entry.DuplicateOf = firstNonEmpty(src.DuplicateOf, coverageByCanonical[canonical])
			entry.DuplicateEvidence = firstNonEmpty(src.AssignmentReason, "identical canonical URL")
			if entry.DuplicateOf == "" {
				entry.DuplicateOf = sourceID(src.URL, canonical)
			}
		case StatusExcluded:
			entry.Reason = firstNonEmpty(src.Reason, "excluded")
		}
		coverage.Sources = append(coverage.Sources, entry)
	}
	sort.Slice(coverage.Sources, func(i, j int) bool {
		return coverage.Sources[i].SourceID < coverage.Sources[j].SourceID
	})
	return coverage
}

func WriteSourceCoverage(root string, coverage SourceCoverage) error {
	return writeJSON(filepath.Join(root, "data", "ato_knowledge_base", sourceCoverageFileName), coverage)
}

func LoadSourceCoverage(root string) (SourceCoverage, error) {
	body, err := os.ReadFile(filepath.Join(root, "data", "ato_knowledge_base", sourceCoverageFileName))
	if err != nil {
		return SourceCoverage{}, err
	}
	var out SourceCoverage
	if err := json.Unmarshal(body, &out); err != nil {
		return SourceCoverage{}, err
	}
	return out, nil
}

func coverageCanonicalURL(primaryURL, fallbackURL string) string {
	canonical := canonicalURL(fallbackURL)
	if canonical == "" {
		canonical = canonicalURL(primaryURL)
	}
	if canonical == "" {
		return primaryURL
	}
	return canonical
}

func WriteCoverageReport(root string, format string) ([]byte, error) {
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		return nil, err
	}
	summary := Audit(root, coverage)
	if format == "json" {
		payload := map[string]any{
			"summary":         summary,
			"source_coverage": coverage,
		}
		body, err := json.MarshalIndent(payload, "", "  ")
		if err != nil {
			return nil, err
		}
		return append(body, '\n'), nil
	}
	if format == "" {
		format = "markdown"
	}
	if format != "markdown" {
		return nil, fmt.Errorf("unsupported format %q", format)
	}
	var b strings.Builder
	b.WriteString("# Source Coverage Report\n\n")
	b.WriteString(fmt.Sprintf("Checked sources: %d\n\n", summary.Total))
	b.WriteString("## Coverage counts\n\n")
	b.WriteString(fmt.Sprintf("- total: %d\n", summary.Total))
	b.WriteString(fmt.Sprintf("- verified: %d\n", summary.Verified))
	b.WriteString(fmt.Sprintf("- metadata_only: %d\n", summary.MetadataOnly))
	b.WriteString(fmt.Sprintf("- duplicate: %d\n", summary.Duplicate))
	b.WriteString(fmt.Sprintf("- excluded: %d\n", summary.Excluded))
	b.WriteString(fmt.Sprintf("- needs_review: %d\n", summary.NeedsReview))

	b.WriteString("\n## Coverage by skill\n\n")
	for _, skill := range sortedStringKeys(summary.BySkill) {
		state := summary.BySkill[skill]
		b.WriteString(fmt.Sprintf("- %s: assigned=%d verified=%d metadata_only=%d coverage_status=%s\n",
			skill, state.AssignedSources, state.VerifiedSources, state.MetadataOnlySources, state.CoverageStatus))
	}

	b.WriteString("\n## Required topics\n\n")
	writeList(&b, "required tax areas with no source assignment", summary.RequiredAssignmentMissing)
	writeList(&b, "required tax areas with no verified source content", summary.RequiredVerifiedMissing)
	writeList(&b, "missing destination files", summary.MissingDestinationFiles)
	writeList(&b, "missing reverse provenance", summary.MissingReverseProvenance)
	writeList(&b, "invalid hashes", summary.InvalidHashes)
	writeList(&b, "unsupported duplicate evidence", summary.DuplicateEvidenceIssues)
	writeList(&b, "duplicate chain issues", summary.DuplicateChainIssues)
	writeList(&b, "volatile values missing effective periods", summary.VolatileMissingPeriods)
	writeList(&b, "skills missing guardrails", summary.SkillsMissingGuardrail)

	b.WriteString("## Source state\n\n")
	writeList(&b, "unassigned sources", summary.NotUsedEntries)
	writeList(&b, "review required sources", summary.ReviewEntries)

	b.WriteString("\n## CGT coverage\n\n")
	for _, key := range []string{"general", "shares_etfs_managed_funds", "crypto", "property_rental"} {
		if summary.CGTCoverage[key] {
			b.WriteString("- " + key + ": covered\n")
		} else {
			b.WriteString("- " + key + ": missing\n")
		}
	}
	return []byte(b.String()), nil
}

func Audit(root string, coverage SourceCoverage) CoverageSummary {
	summary := CoverageSummary{
		Total:       len(coverage.Sources),
		BySkill:     map[string]CoverageSkillState{},
		CGTCoverage: map[string]bool{},
	}

	byID := map[string]SourceCoverageEntry{}
	for _, entry := range coverage.Sources {
		if strings.TrimSpace(entry.SourceID) == "" {
			continue
		}
		byID[entry.SourceID] = entry
		switch entry.Status {
		case StatusVerified:
			summary.Verified++
			for _, skill := range entry.Skills {
				state := summary.BySkill[skill]
				state.AssignedSources++
				state.VerifiedSources++
				summary.BySkill[skill] = state
				summary = cgtMark(summary, skill)
			}
			if !validContentHash(entry.ContentHash) {
				summary.InvalidHashes = append(summary.InvalidHashes, entry.SourceID+":"+entry.CanonicalURL)
			}
			summary.MissingDestinationFiles = appendIfMissing(summary.MissingDestinationFiles, checkReferences(root, entry)...)
			summary.MissingReverseProvenance = appendIfMissing(summary.MissingReverseProvenance, checkReverseProvenance(root, entry)...)
		case StatusMetadataOnly:
			summary.MetadataOnly++
			for _, skill := range entry.Skills {
				state := summary.BySkill[skill]
				state.AssignedSources++
				state.MetadataOnlySources++
				summary.BySkill[skill] = state
			}
			summary.MissingDestinationFiles = appendIfMissing(summary.MissingDestinationFiles, checkReferences(root, entry)...)
			summary.MissingReverseProvenance = appendIfMissing(summary.MissingReverseProvenance, checkReverseProvenance(root, entry)...)
		case StatusDuplicate:
			summary.Duplicate++
			if err := validateDuplicateEvidence(entry); err != nil {
				summary.DuplicateEvidenceIssues = append(summary.DuplicateEvidenceIssues, err.Error())
			}
		case StatusExcluded:
			summary.Excluded++
		case StatusNeedsReview:
			summary.NeedsReview++
			summary.ReviewEntries = append(summary.ReviewEntries, entry.SourceID)
		default:
			summary.NeedsReview++
			summary.ReviewEntries = append(summary.ReviewEntries, entry.SourceID)
		}
	}

	skillStates := sortedStringKeys(summary.BySkill)
	for _, skill := range requiredSkillSlugs() {
		state := summary.BySkill[skill]
		if _, ok := summary.BySkill[skill]; !ok {
			state = CoverageSkillState{}
		}
		if state.VerifiedSources > 0 {
			state.CoverageStatus = "verified"
		} else if state.MetadataOnlySources > 0 {
			state.CoverageStatus = "metadata_only"
			summary.RequiredVerifiedMissing = append(summary.RequiredVerifiedMissing, skill)
		} else {
			state.CoverageStatus = "missing"
			summary.RequiredAssignmentMissing = append(summary.RequiredAssignmentMissing, skill)
		}
		summary.BySkill[skill] = state
	}
	for _, entry := range coverage.Sources {
		if entry.Status == StatusNeedsReview {
			continue
		}
		if len(entry.Skills) == 0 {
			summary.NotUsedEntries = append(summary.NotUsedEntries, entry.SourceID)
		}
	}
	sort.Strings(summary.NotUsedEntries)

	summary.VolatileMissingPeriods = valuesMissingPeriods(root)
	for _, skill := range skillStates {
		if missingGuardrail(root, skill) {
			summary.SkillsMissingGuardrail = append(summary.SkillsMissingGuardrail, skill)
		}
	}

	summary.DuplicateChainIssues = validateDuplicateChainsAsList(byID)

	sort.Strings(summary.MissingDestinationFiles)
	sort.Strings(summary.MissingReverseProvenance)
	sort.Strings(summary.InvalidHashes)
	sort.Strings(summary.DuplicateEvidenceIssues)
	sort.Strings(summary.DuplicateChainIssues)
	sort.Strings(summary.RequiredAssignmentMissing)
	sort.Strings(summary.RequiredVerifiedMissing)
	sort.Strings(summary.VolatileMissingPeriods)
	sort.Strings(summary.SkillsMissingGuardrail)
	return summary
}

func cgtMark(summary CoverageSummary, skill string) CoverageSummary {
	switch skill {
	case "capital-gains-tax":
		summary.CGTCoverage["general"] = true
	case "shares-etfs-managed-funds":
		summary.CGTCoverage["shares_etfs_managed_funds"] = true
	case "crypto-assets":
		summary.CGTCoverage["crypto"] = true
	case "property-rental-cgt":
		summary.CGTCoverage["property_rental"] = true
	}
	return summary
}

func checkReferences(root string, entry SourceCoverageEntry) []string {
	missing := []string{}
	for _, ref := range entry.References {
		refPath := filepath.Join(root, filepath.FromSlash(ref))
		if _, err := os.Stat(refPath); err != nil {
			missing = append(missing, entry.SourceID+":"+ref)
		}
	}
	return missing
}

func checkReverseProvenance(root string, entry SourceCoverageEntry) []string {
	missing := []string{}
	for _, ref := range entry.References {
		refPath := filepath.Join(root, filepath.FromSlash(ref))
		body, err := os.ReadFile(refPath)
		if err != nil {
			continue
		}
		if len(body) == 0 {
			missing = append(missing, entry.SourceID+":"+ref)
			continue
		}
		if !bytes.Contains(body, []byte(entry.SourceID)) && !bytes.Contains(body, []byte(entry.CanonicalURL)) {
			missing = append(missing, entry.SourceID+":"+ref)
		}
	}
	return missing
}

func validContentHash(hash string) bool {
	if strings.TrimSpace(hash) == "" {
		return false
	}
	if strings.EqualFold(hash, EmptyContentHashValue) {
		return false
	}
	return true
}

func ValidateSourceCoverage(root string) error {
	coverage, err := LoadSourceCoverage(root)
	if err != nil {
		return err
	}
	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		return err
	}
	if len(coverage.Sources) != len(registry.Records) {
		return fmt.Errorf("source coverage count %d does not match registry count %d", len(coverage.Sources), len(registry.Records))
	}

	expected := map[string]atodata.SourceRecord{}
	for _, rec := range registry.Records {
		canonical := coverageCanonicalURL(rec.URL, rec.FinalURL)
		expected[sourceID(rec.URL, canonical)] = *rec
	}

	coverageByID := map[string]SourceCoverageEntry{}
	seen := map[string]bool{}
	skillSources, err := loadPerSkillSourceAssignments(root)
	if err != nil {
		return err
	}
	for _, entry := range coverage.Sources {
		sourceIDValue := strings.TrimSpace(entry.SourceID)
		if sourceIDValue == "" {
			return errors.New("source coverage missing source_id")
		}
		if seen[sourceIDValue] {
			return fmt.Errorf("duplicate source_id %s", sourceIDValue)
		}
		seen[sourceIDValue] = true
		rec, ok := expected[sourceIDValue]
		if !ok {
			return fmt.Errorf("coverage has unknown source_id %s", sourceIDValue)
		}
		canonical := coverageCanonicalURL(rec.URL, rec.FinalURL)
		if strings.TrimSpace(entry.CanonicalURL) != canonical {
			return fmt.Errorf("coverage canonical URL mismatch %s: expected %s got %s", sourceIDValue, canonical, entry.CanonicalURL)
		}
		if strings.TrimSpace(entry.CheckedAt) == "" {
			return fmt.Errorf("source coverage missing checked_at for %s", sourceIDValue)
		}
		if expectedChecked := strings.TrimSpace(rec.LastChecked); expectedChecked != "" && entry.CheckedAt != expectedChecked {
			return fmt.Errorf("checked_at mismatch for %s: registry %s coverage %s", sourceIDValue, expectedChecked, entry.CheckedAt)
		}
		if entry.OriginalURL != "" && entry.OriginalURL != rec.URL {
			return fmt.Errorf("original_url mismatch for %s: registry %s coverage %s", sourceIDValue, rec.URL, entry.OriginalURL)
		}
		if strings.TrimSpace(entry.Title) == "" {
			entry.Title = rec.Title
		}
		coverageByID[sourceIDValue] = entry
	}

	for _, entry := range coverage.Sources {
		sourceIDValue := strings.TrimSpace(entry.SourceID)
		rec, ok := expected[sourceIDValue]
		if !ok {
			return fmt.Errorf("coverage has unknown source_id %s", sourceIDValue)
		}
		switch entry.Status {
		case StatusVerified:
			if !validContentHash(entry.ContentHash) {
				return fmt.Errorf("verified source missing valid hash %s", sourceIDValue)
			}
			if strings.TrimSpace(entry.ContentHash) != strings.TrimSpace(rec.ContentHash) {
				return fmt.Errorf("content hash mismatch for %s", sourceIDValue)
			}
			if len(entry.Skills) == 0 || len(entry.References) == 0 {
				return fmt.Errorf("verified source missing assignment/references %s", sourceIDValue)
			}
			if err := validateSourceAssignmentWithProvenance(root, entry, skillSources, "verified source missing assignment/references %s"); err != nil {
				return err
			}
		case StatusMetadataOnly:
			if len(entry.Skills) != 0 {
				if len(entry.References) == 0 {
					return fmt.Errorf("metadata-only source missing references %s", sourceIDValue)
				}
				if err := validateSourceAssignmentWithProvenance(root, entry, skillSources, "metadata-only source missing references %s"); err != nil {
					return err
				}
			}
		case StatusDuplicate:
			if strings.TrimSpace(entry.DuplicateOf) == "" {
				return fmt.Errorf("duplicate source missing duplicate_of %s", sourceIDValue)
			}
			target, ok := coverageByID[entry.DuplicateOf]
			if !ok {
				return fmt.Errorf("duplicate source references missing target %s", sourceIDValue)
			}
			if target.SourceID == sourceIDValue {
				return fmt.Errorf("duplicate source self-referenced %s", sourceIDValue)
			}
			if target.Status == StatusDuplicate {
				return fmt.Errorf("duplicate source references duplicate target %s -> %s", sourceIDValue, entry.DuplicateOf)
			}
			if strings.TrimSpace(entry.DuplicateEvidence) == "" {
				return fmt.Errorf("duplicate source missing evidence %s", sourceIDValue)
			}
			if !isSupportedDuplicateEvidence(entry.DuplicateEvidence) {
				return fmt.Errorf("duplicate source has unsupported evidence %s", sourceIDValue)
			}
		case StatusExcluded:
			if strings.TrimSpace(entry.Reason) == "" {
				return fmt.Errorf("excluded source missing reason %s", sourceIDValue)
			}
		case StatusNeedsReview:
			return fmt.Errorf("source remains needs_review %s", sourceIDValue)
		default:
			return fmt.Errorf("invalid status %q for %s", entry.Status, sourceIDValue)
		}
	}

	summary := Audit(root, coverage)
	if len(summary.DuplicateChainIssues) > 0 {
		return fmt.Errorf("invalid duplicate chain: %s", strings.Join(summary.DuplicateChainIssues[:minLen(summary.DuplicateChainIssues, 3)], ", "))
	}
	if len(summary.DuplicateEvidenceIssues) > 0 {
		return fmt.Errorf("invalid duplicate evidence: %s", strings.Join(summary.DuplicateEvidenceIssues[:minLen(summary.DuplicateEvidenceIssues, 3)], ", "))
	}
	if len(summary.MissingDestinationFiles) > 0 {
		return fmt.Errorf("missing destination files: %s", strings.Join(summary.MissingDestinationFiles[:minLen(summary.MissingDestinationFiles, 3)], ", "))
	}
	if len(summary.MissingReverseProvenance) > 0 {
		return fmt.Errorf("missing reverse provenance: %s", strings.Join(summary.MissingReverseProvenance[:minLen(summary.MissingReverseProvenance, 3)], ", "))
	}
	if len(summary.InvalidHashes) > 0 {
		return fmt.Errorf("invalid hashes: %s", strings.Join(summary.InvalidHashes[:minLen(summary.InvalidHashes, 3)], ", "))
	}
	if len(summary.VolatileMissingPeriods) > 0 {
		return fmt.Errorf("volatile values missing periods: %s", strings.Join(summary.VolatileMissingPeriods[:minLen(summary.VolatileMissingPeriods, 3)], ", "))
	}
	if len(summary.SkillsMissingGuardrail) > 0 {
		return fmt.Errorf("skills missing guardrails: %s", strings.Join(summary.SkillsMissingGuardrail, ", "))
	}
	if err := validateLocalCoverageBackedByGlobal(root, coverageByID, skillSources); err != nil {
		return err
	}
	return nil
}

func validateAssignedSourceReferences(entry SourceCoverageEntry, skillSources map[string]map[string]Source) error {
	for _, skill := range entry.Skills {
		byID, ok := skillSources[skill]
		if !ok {
			return fmt.Errorf("coverage assigns %s to unknown skill %s", entry.SourceID, skill)
		}
		local, ok := byID[entry.SourceID]
		if !ok {
			return fmt.Errorf("coverage source %s missing from %s references/sources.json", entry.SourceID, skill)
		}
		if !sourceMatchesCanonical(local, entry.CanonicalURL) {
			return fmt.Errorf("canonical URL mismatch for %s in %s", entry.SourceID, skill)
		}
		if local.Status != entry.Status {
			return fmt.Errorf("status mismatch for %s in %s: coverage=%s local=%s", entry.SourceID, skill, entry.Status, local.Status)
		}
		if local.CheckedAt != entry.CheckedAt {
			return fmt.Errorf("checked_at mismatch for %s in %s", entry.SourceID, skill)
		}
		if !matchingOptionalContentHash(entry.ContentHash, local.ContentHash) {
			return fmt.Errorf("content_hash mismatch for %s in %s", entry.SourceID, skill)
		}
	}
	return nil
}

func validateSourceAssignmentWithProvenance(root string, entry SourceCoverageEntry, skillSources map[string]map[string]Source, emptyMsg string) error {
	if len(entry.Skills) == 0 || len(entry.References) == 0 {
		return fmt.Errorf(emptyMsg, entry.SourceID)
	}
	if err := validateAssignedSourceReferences(entry, skillSources); err != nil {
		return err
	}
	for _, ref := range entry.References {
		if err := validateReverseProvenanceInSource(root, entry, ref); err != nil {
			return err
		}
	}
	return nil
}

func validateReverseProvenanceInSource(root string, entry SourceCoverageEntry, ref string) error {
	refPath := filepath.Join(root, filepath.FromSlash(ref))
	body, err := os.ReadFile(refPath)
	if err != nil {
		return fmt.Errorf("reference missing source file for %s: %w", entry.SourceID, err)
	}
	if !bytes.Contains(body, []byte(entry.SourceID)) && !bytes.Contains(body, []byte(entry.CanonicalURL)) {
		return fmt.Errorf("reference missing reverse provenance for %s:%s", entry.SourceID, ref)
	}
	return nil
}

func isSupportedDuplicateEvidence(evidence string) bool {
	e := strings.ToLower(evidence)
	supported := []string{
		"identical canonical url",
		"identical non-empty content hash",
		"confirmed redirect",
		"manual comparison",
	}
	for _, item := range supported {
		if strings.Contains(e, item) {
			return true
		}
	}
	return false
}

func validateDuplicateEvidence(entry SourceCoverageEntry) error {
	if entry.Status != StatusDuplicate {
		return nil
	}
	if strings.TrimSpace(entry.DuplicateOf) == "" {
		return fmt.Errorf("duplicate source missing duplicate_of: %s", entry.SourceID)
	}
	if strings.EqualFold(entry.DuplicateOf, entry.SourceID) {
		return fmt.Errorf("duplicate source self-referenced: %s", entry.SourceID)
	}
	if strings.TrimSpace(entry.DuplicateEvidence) == "" {
		return fmt.Errorf("duplicate source missing evidence: %s", entry.SourceID)
	}
	if !isSupportedDuplicateEvidence(entry.DuplicateEvidence) {
		return fmt.Errorf("unsupported duplicate evidence for %s", entry.SourceID)
	}
	return nil
}

func validateDuplicateChains(entries map[string]SourceCoverageEntry) error {
	if issues := validateDuplicateChainsAsList(entries); len(issues) > 0 {
		return errors.New(issues[0])
	}
	return nil
}

func validateDuplicateChainsAsList(entries map[string]SourceCoverageEntry) []string {
	var issues []string
	for id, entry := range entries {
		if entry.Status != StatusDuplicate {
			continue
		}
		if strings.TrimSpace(entry.DuplicateOf) == "" {
			issues = append(issues, fmt.Sprintf("duplicate chain missing target %s", id))
			continue
		}
		if entry.DuplicateOf == id {
			issues = append(issues, fmt.Sprintf("duplicate chain self-reference %s", id))
			continue
		}
		next, ok := entries[entry.DuplicateOf]
		if !ok {
			issues = append(issues, fmt.Sprintf("duplicate chain references missing source %s -> %s", id, entry.DuplicateOf))
			continue
		}
		if next.Status == StatusDuplicate {
			issues = append(issues, fmt.Sprintf("duplicate chain not direct for %s", id))
		}
	}
	return issues
}

func validateLocalCoverageBackedByGlobal(root string, coverageByID map[string]SourceCoverageEntry, perSkill map[string]map[string]Source) error {
	_ = root
	for _, byID := range perSkill {
		for id, local := range byID {
			entry, ok := coverageByID[id]
			if !ok {
				return fmt.Errorf("per-skill source %s not present in coverage", id)
			}
			if !sourceMatchesCanonical(local, entry.CanonicalURL) {
				return fmt.Errorf("per-skill source %s url mismatch in coverage", id)
			}
			if local.Status != entry.Status {
				return fmt.Errorf("status mismatch for %s across global/local", id)
			}
			if local.CheckedAt != entry.CheckedAt {
				return fmt.Errorf("checked_at mismatch for %s across global/local", id)
			}
			if !matchingOptionalContentHash(entry.ContentHash, local.ContentHash) {
				return fmt.Errorf("content_hash mismatch for %s across global/local", id)
			}
		}
	}
	for id, entry := range coverageByID {
		if entry.Status != StatusVerified && entry.Status != StatusMetadataOnly {
			continue
		}
		for _, skill := range entry.Skills {
			byID, ok := perSkill[skill]
			if !ok {
				return fmt.Errorf("coverage source %s assigned to unknown skill %s", id, skill)
			}
			if _, ok := byID[id]; !ok {
				return fmt.Errorf("coverage source %s missing in per-skill assignment %s", id, skill)
			}
		}
	}
	return nil
}

func sourceMatchesCanonical(local Source, canonical string) bool {
	return strings.TrimSpace(local.FinalURL) == strings.TrimSpace(canonical) || strings.TrimSpace(local.URL) == strings.TrimSpace(canonical)
}

func matchingOptionalContentHash(expected, actual string) bool {
	expected = strings.TrimSpace(expected)
	if expected == "" {
		return true
	}
	return strings.TrimSpace(actual) == expected
}

func loadPerSkillSourceAssignments(root string) (map[string]map[string]Source, error) {
	sourceBySkill := map[string]map[string]Source{}
	for _, skill := range requiredSkillSlugs() {
		path := filepath.Join(root, "skills", skill, "references", "sources.json")
		body, err := os.ReadFile(path)
		if err != nil {
			return nil, err
		}
		var sources []Source
		if err := json.Unmarshal(body, &sources); err != nil {
			return nil, err
		}
		byID := map[string]Source{}
		for _, source := range sources {
			sourceIDValue := strings.TrimSpace(source.SourceID)
			if sourceIDValue == "" {
				return nil, fmt.Errorf("missing source_id in %s", path)
			}
			if _, ok := byID[sourceIDValue]; ok {
				return nil, fmt.Errorf("duplicate source_id %s in %s", sourceIDValue, path)
			}
			byID[sourceIDValue] = source
		}
		sourceBySkill[skill] = byID
	}
	return sourceBySkill, nil
}

func requiredSourceArtifacts(root string) ([]string, error) {
	var out []string
	for _, skill := range requiredSkillSlugs() {
		out = append(out,
			filepath.ToSlash(filepath.Join("skills", skill, "SKILL.md")),
			filepath.ToSlash(filepath.Join("skills", skill, "references", "rules.md")),
			filepath.ToSlash(filepath.Join("skills", skill, "references", "evidence.md")),
			filepath.ToSlash(filepath.Join("skills", skill, "references", "sources.json")),
		)
		currentValues := filepath.Join(root, "skills", skill, "references", "current-values.json")
		if _, err := os.Stat(currentValues); err == nil {
			out = append(out, filepath.ToSlash(filepath.Join("skills", skill, "references", "current-values.json")))
		}
	}
	for _, skill := range []string{"workbook", "taxpack"} {
		out = append(out, filepath.ToSlash(filepath.Join("skills", skill, "references", "topic-inputs.md")))
	}
	out = append(out, filepath.ToSlash(filepath.Join("data", "ato_knowledge_base", sourceCoverageFileName)))
	sort.Strings(out)
	return out, nil
}

func CompareGeneratedArtifacts(root string, generatedRoot string) error {
	generatedFiles, err := requiredSourceArtifacts(generatedRoot)
	if err != nil {
		return err
	}
	for _, rel := range generatedFiles {
		generatedPath := filepath.Join(generatedRoot, filepath.FromSlash(rel))
		expectedPath := filepath.Join(root, filepath.FromSlash(rel))
		generatedBody, err := os.ReadFile(generatedPath)
		if err != nil {
			if os.IsNotExist(err) {
				return fmt.Errorf("generated file missing %s", rel)
			}
			return err
		}
		expectedBody, err := os.ReadFile(expectedPath)
		if err != nil {
			if os.IsNotExist(err) {
				return fmt.Errorf("tracked file missing expected output %s", rel)
			}
			return err
		}
		if !bytes.Equal(bytes.TrimSpace(generatedBody), bytes.TrimSpace(expectedBody)) {
			return fmt.Errorf("generated output mismatch %s", rel)
		}
	}
	return nil
}

func conceptsFor(skill string) []string {
	for _, t := range Topics() {
		if t.Slug == skill {
			out := append([]string{}, t.Signals...)
			out = append(out, t.Keywords...)
			sort.Strings(out)
			return compact(out)
		}
	}
	return nil
}

func inferSkillsFromURL(raw string) []string {
	for _, skill := range requiredSkillSlugs() {
		if strings.Contains(raw, skill) {
			return []string{skill}
		}
	}
	return nil
}

func requiredSkillSlugs() []string {
	out := make([]string, 0, len(Topics()))
	for _, t := range Topics() {
		out = append(out, t.Slug)
	}
	sort.Strings(out)
	return out
}

func existingReferences(root string, skill string) []string {
	dir := filepath.Join(root, "skills", skill, "references")
	var refs []string
	_ = filepath.WalkDir(dir, func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		rel, relErr := filepath.Rel(root, path)
		if relErr == nil {
			refs = append(refs, filepath.ToSlash(rel))
		}
		return nil
	})
	sort.Strings(refs)
	return refs
}

func valuesMissingPeriods(root string) []string {
	var missing []string
	for _, skill := range requiredSkillSlugs() {
		path := filepath.Join(root, "skills", skill, "references", "current-values.json")
		body, err := os.ReadFile(path)
		if err != nil {
			continue
		}
		var values []ValueFact
		if err := json.Unmarshal(body, &values); err != nil {
			missing = append(missing, filepath.ToSlash(path)+":invalid-json")
			continue
		}
		for i, value := range values {
			if value.SourceURL == "" || value.SourceTitle == "" || value.CheckedAt == "" || value.ContentHash == "" || value.Unit == "" || value.Context == "" {
				missing = append(missing, fmt.Sprintf("%s:%d:missing-provenance", filepath.ToSlash(path), i))
				continue
			}
			if value.IncomeYear == "" && (value.EffectiveFrom == "" || value.EffectiveTo == "") {
				missing = append(missing, fmt.Sprintf("%s:%d:missing-period", filepath.ToSlash(path), i))
			}
		}
	}
	return missing
}

func missingGuardrail(root string, skill string) bool {
	body, err := os.ReadFile(filepath.Join(root, "skills", skill, "SKILL.md"))
	if err != nil {
		return true
	}
	text := string(body)
	for _, needle := range []string{"Accountant review", "Claim candidate", "Supported record", "Insufficient evidence", "Not claimable", "must not be bypassed"} {
		if !strings.Contains(text, needle) {
			return true
		}
	}
	return false
}

func writeList(b *strings.Builder, title string, values []string) {
	b.WriteString("## " + title + "\n\n")
	if len(values) == 0 {
		b.WriteString("- none\n\n")
		return
	}
	for _, value := range values {
		b.WriteString("- " + value + "\n")
	}
	b.WriteString("\n")
}

func appendIfMissing(existing []string, additions ...string) []string {
	seen := map[string]bool{}
	for _, item := range existing {
		seen[item] = true
	}
	for _, item := range additions {
		if !seen[item] {
			existing = append(existing, item)
			seen[item] = true
		}
	}
	sort.Strings(existing)
	return existing
}

func minLen(values []string, max int) int {
	if len(values) < max {
		return len(values)
	}
	return max
}

func sortedStringKeys(m map[string]CoverageSkillState) []string {
	keys := make([]string, 0, len(m))
	for key := range m {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func sourceID(originalURL, canonicalURL string) string {
	return "ato-" + HashBytes([]byte(originalURL + "|" + canonicalURL))[:12]
}

func sortedIDs(byID map[string]SourceCoverageEntry) []string {
	out := make([]string, 0, len(byID))
	for id := range byID {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

func compact(values []string) []string {
	seen := map[string]bool{}
	var out []string
	for _, value := range values {
		value = strings.TrimSpace(value)
		if value != "" && !seen[value] {
			out = append(out, value)
			seen[value] = true
		}
	}
	return out
}
