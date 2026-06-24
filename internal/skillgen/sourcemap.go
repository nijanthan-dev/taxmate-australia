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
	StatusUsed        = "used"
	StatusDuplicate   = "duplicate"
	StatusNotUsed     = "not_used"
	StatusNeedsReview = "needs_review"
)

type SourceMap struct {
	GeneratedAt string           `json:"generated_at"`
	Sources     []SourceMapEntry `json:"sources"`
}

type SourceMapEntry struct {
	SourceID          string   `json:"source_id"`
	OriginalURL       string   `json:"original_url"`
	CanonicalURL      string   `json:"canonical_url"`
	Title             string   `json:"source_title"`
	LastUpdated       string   `json:"source_last_updated,omitempty"`
	CheckedAt         string   `json:"checked_at"`
	ContentHash       string   `json:"content_hash"`
	Status            string   `json:"status"`
	Skills            []string `json:"skills,omitempty"`
	References        []string `json:"references,omitempty"`
	CoveredConcepts   []string `json:"covered_concepts,omitempty"`
	DuplicateOf       string   `json:"duplicate_of,omitempty"`
	DuplicateEvidence string   `json:"duplicate_evidence,omitempty"`
	Reason            string   `json:"reason,omitempty"`
}

type AuditSummary struct {
	Total                  int
	Used                   int
	Duplicate              int
	NotUsed                int
	NeedsReview            int
	BySkill                map[string]int
	MissingDestinations    []string
	MissingProvenance      []string
	InsufficientCoverage   []string
	CGTCoverage            map[string]bool
	VolatileMissingPeriods []string
	SkillsMissingGuardrail []string
	NotUsedEntries         []SourceMapEntry
	ReviewEntries          []SourceMapEntry
}

func WriteSourceMapAndAudit(root string, report *MigrationReport) error {
	sourceMap := BuildSourceMap(report)
	if err := writeJSON(filepath.Join(root, "migration", "source-to-skill-map.json"), sourceMap); err != nil {
		return err
	}
	return WriteAuditReport(root, sourceMap)
}

func BuildSourceMap(report *MigrationReport) SourceMap {
	sourceIDByCanonical := map[string]string{}
	out := SourceMap{GeneratedAt: report.GeneratedAt}
	for _, src := range report.Sources {
		if src.DuplicateOf == "" && src.AssignedSkill != "" {
			sourceIDByCanonical[src.FinalURL] = sourceID(src.URL, src.FinalURL)
		}
	}
	for _, src := range report.Sources {
		entry := SourceMapEntry{
			SourceID:     sourceID(src.URL, src.FinalURL),
			OriginalURL:  src.URL,
			CanonicalURL: src.FinalURL,
			Title:        src.Title,
			LastUpdated:  src.LastUpdated,
			CheckedAt:    src.CheckedAt,
			ContentHash:  src.ContentHash,
		}
		switch {
		case src.DuplicateOf != "":
			entry.Status = StatusDuplicate
			entry.DuplicateOf = sourceIDByCanonical[src.DuplicateOf]
			if entry.DuplicateOf == "" {
				entry.DuplicateOf = src.DuplicateOf
			}
			entry.DuplicateEvidence = "identical canonical URL: " + src.DuplicateOf
		case src.AssignedSkill != "":
			entry.Status = StatusUsed
			entry.Skills = []string{src.AssignedSkill}
			entry.References = []string{
				filepath.ToSlash(filepath.Join("skills", src.AssignedSkill, "references", "rules.md")),
				filepath.ToSlash(filepath.Join("skills", src.AssignedSkill, "references", "sources.json")),
			}
			entry.CoveredConcepts = conceptsFor(src.AssignedSkill)
		case src.Unsupported:
			entry.Status = StatusNotUsed
			entry.Reason = firstNonEmpty(src.AssignmentReason, "content outside approved official-source hosts")
		case src.Unassigned:
			entry.Status = StatusNotUsed
			entry.Reason = firstNonEmpty(src.AssignmentReason, "no supported TaxMate topic match")
		default:
			entry.Status = StatusNeedsReview
			entry.Reason = "source classification incomplete"
		}
		out.Sources = append(out.Sources, entry)
	}
	sort.Slice(out.Sources, func(i, j int) bool { return out.Sources[i].SourceID < out.Sources[j].SourceID })
	return out
}

func LoadSourceMap(root string) (SourceMap, error) {
	body, err := os.ReadFile(filepath.Join(root, "migration", "source-to-skill-map.json"))
	if err != nil {
		return SourceMap{}, err
	}
	var sourceMap SourceMap
	if err := json.Unmarshal(body, &sourceMap); err != nil {
		return SourceMap{}, err
	}
	return sourceMap, nil
}

func WriteAuditReport(root string, sourceMap SourceMap) error {
	summary := Audit(root, sourceMap)
	var b strings.Builder
	b.WriteString("# Source To Skill Report\n\n")
	b.WriteString("Generated at: " + sourceMap.GeneratedAt + "\n\n")
	b.WriteString("## Counts\n\n")
	b.WriteString(fmt.Sprintf("- total indexed sources: %d\n", summary.Total))
	b.WriteString(fmt.Sprintf("- used: %d\n", summary.Used))
	b.WriteString(fmt.Sprintf("- duplicate: %d\n", summary.Duplicate))
	b.WriteString(fmt.Sprintf("- not_used: %d\n", summary.NotUsed))
	b.WriteString(fmt.Sprintf("- needs_review: %d\n", summary.NeedsReview))
	b.WriteString("\n## Sources By Skill\n\n")
	for _, skill := range sortedKeys(summary.BySkill) {
		b.WriteString(fmt.Sprintf("- %s: %d\n", skill, summary.BySkill[skill]))
	}
	b.WriteString("\n## Generated References\n\n")
	for _, skill := range requiredSkillSlugs() {
		refs := existingReferences(root, skill)
		b.WriteString("- " + skill + "\n")
		for _, ref := range refs {
			b.WriteString("  - " + ref + "\n")
		}
	}
	writeList(&b, "Missing Destination Files", summary.MissingDestinations)
	writeList(&b, "References Missing Provenance", summary.MissingProvenance)
	writeList(&b, "Required Tax Areas With Insufficient Coverage", summary.InsufficientCoverage)
	b.WriteString("\n## CGT Coverage\n\n")
	for _, key := range []string{"general", "shares_etfs_managed_funds", "crypto", "property_rental"} {
		b.WriteString(fmt.Sprintf("- %s: %t\n", key, summary.CGTCoverage[key]))
	}
	writeList(&b, "Volatile Values Missing Effective Periods", summary.VolatileMissingPeriods)
	writeList(&b, "Skills Missing Guardrails", summary.SkillsMissingGuardrail)
	b.WriteString("\n## Not Used Sources\n\n")
	if len(summary.NotUsedEntries) == 0 {
		b.WriteString("- none\n")
	} else {
		for _, entry := range summary.NotUsedEntries {
			b.WriteString(fmt.Sprintf("- %s: %s\n", entry.CanonicalURL, entry.Reason))
		}
	}
	b.WriteString("\n## Unresolved Review Items\n\n")
	if len(summary.ReviewEntries) == 0 {
		b.WriteString("- none\n")
	} else {
		for _, entry := range summary.ReviewEntries {
			b.WriteString(fmt.Sprintf("- %s: %s\n", entry.CanonicalURL, entry.Reason))
		}
	}
	return os.WriteFile(filepath.Join(root, "migration", "SOURCE_TO_SKILL_REPORT.md"), []byte(b.String()), 0644)
}

func Audit(root string, sourceMap SourceMap) AuditSummary {
	summary := AuditSummary{
		BySkill:        map[string]int{},
		CGTCoverage:    map[string]bool{},
		Total:          len(sourceMap.Sources),
		NotUsedEntries: []SourceMapEntry{},
		ReviewEntries:  []SourceMapEntry{},
	}
	for _, entry := range sourceMap.Sources {
		switch entry.Status {
		case StatusUsed:
			summary.Used++
			for _, skill := range entry.Skills {
				summary.BySkill[skill]++
				switch skill {
				case "capital-gains-tax":
					summary.CGTCoverage["general"] = true
				case "shares-etfs-managed-funds":
					summary.CGTCoverage["shares_etfs_managed_funds"] = true
				case "crypto-assets", "crypto-cgt":
					summary.CGTCoverage["crypto"] = true
				case "property-rental-cgt":
					summary.CGTCoverage["property_rental"] = true
				}
			}
			for _, ref := range entry.References {
				refPath := filepath.Join(root, filepath.FromSlash(ref))
				body, err := os.ReadFile(refPath)
				if err != nil {
					summary.MissingDestinations = append(summary.MissingDestinations, entry.SourceID+":"+ref)
					continue
				}
				if !bytes.Contains(body, []byte(entry.CanonicalURL)) && !bytes.Contains(body, []byte(entry.SourceID)) {
					summary.MissingProvenance = append(summary.MissingProvenance, entry.SourceID+":"+ref)
				}
			}
		case StatusDuplicate:
			summary.Duplicate++
		case StatusNotUsed:
			summary.NotUsed++
			summary.NotUsedEntries = append(summary.NotUsedEntries, entry)
		case StatusNeedsReview:
			summary.NeedsReview++
			summary.ReviewEntries = append(summary.ReviewEntries, entry)
		}
	}
	for _, skill := range requiredSkillSlugs() {
		if summary.BySkill[skill] == 0 {
			summary.InsufficientCoverage = append(summary.InsufficientCoverage, skill)
		}
	}
	for _, topic := range []string{"general", "shares_etfs_managed_funds", "crypto", "property_rental"} {
		if !summary.CGTCoverage[topic] {
			summary.InsufficientCoverage = append(summary.InsufficientCoverage, "cgt:"+topic)
		}
	}
	summary.VolatileMissingPeriods = valuesMissingPeriods(root)
	for _, skill := range requiredSkillSlugs() {
		if missingGuardrail(root, skill) {
			summary.SkillsMissingGuardrail = append(summary.SkillsMissingGuardrail, skill)
		}
	}
	sort.Strings(summary.MissingDestinations)
	sort.Strings(summary.MissingProvenance)
	sort.Strings(summary.InsufficientCoverage)
	sort.Strings(summary.VolatileMissingPeriods)
	sort.Strings(summary.SkillsMissingGuardrail)
	return summary
}

func ValidateSourceMap(root string) error {
	idx, err := atodata.LoadIndex(root)
	if err != nil {
		return err
	}
	sourceMap, err := LoadSourceMap(root)
	if err != nil {
		return err
	}
	if len(sourceMap.Sources) != len(idx.Records) {
		return fmt.Errorf("source map count %d does not match source index count %d", len(sourceMap.Sources), len(idx.Records))
	}
	expected := map[string]bool{}
	for _, rec := range idx.Records {
		expected[sourceID(rec.URL, canonicalURL(firstNonEmpty(rec.FinalURL, rec.URL)))] = true
	}
	seen := map[string]bool{}
	for _, entry := range sourceMap.Sources {
		if !expected[entry.SourceID] {
			return fmt.Errorf("source map has unknown source_id %s", entry.SourceID)
		}
		if seen[entry.SourceID] {
			return fmt.Errorf("source map duplicate source_id %s", entry.SourceID)
		}
		seen[entry.SourceID] = true
		switch entry.Status {
		case StatusUsed:
			if len(entry.Skills) == 0 || len(entry.References) == 0 {
				return fmt.Errorf("used source missing destinations: %s", entry.SourceID)
			}
		case StatusDuplicate:
			if entry.DuplicateOf == "" || entry.DuplicateEvidence == "" {
				return fmt.Errorf("duplicate source missing evidence: %s", entry.SourceID)
			}
		case StatusNotUsed:
			if entry.Reason == "" {
				return fmt.Errorf("not_used source missing reason: %s", entry.SourceID)
			}
		case StatusNeedsReview:
			return fmt.Errorf("source remains needs_review: %s", entry.SourceID)
		default:
			return fmt.Errorf("invalid source status %q for %s", entry.Status, entry.SourceID)
		}
	}
	summary := Audit(root, sourceMap)
	if len(summary.MissingDestinations) > 0 {
		return fmt.Errorf("missing destination files: %s", strings.Join(summary.MissingDestinations[:min(3, len(summary.MissingDestinations))], ", "))
	}
	if len(summary.MissingProvenance) > 0 {
		return fmt.Errorf("references missing provenance: %s", strings.Join(summary.MissingProvenance[:min(3, len(summary.MissingProvenance))], ", "))
	}
	if len(summary.InsufficientCoverage) > 0 {
		return fmt.Errorf("insufficient coverage: %s", strings.Join(summary.InsufficientCoverage, ", "))
	}
	if len(summary.VolatileMissingPeriods) > 0 {
		return fmt.Errorf("volatile values missing effective periods: %s", strings.Join(summary.VolatileMissingPeriods[:min(3, len(summary.VolatileMissingPeriods))], ", "))
	}
	if len(summary.SkillsMissingGuardrail) > 0 {
		return fmt.Errorf("skills missing guardrails: %s", strings.Join(summary.SkillsMissingGuardrail, ", "))
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

func requiredSkillSlugs() []string {
	out := []string{}
	for _, t := range Topics() {
		out = append(out, t.Slug)
	}
	sort.Strings(out)
	return out
}

func existingReferences(root, skill string) []string {
	dir := filepath.Join(root, "skills", skill, "references")
	var refs []string
	_ = filepath.WalkDir(dir, func(path string, d os.DirEntry, err error) error {
		if err == nil && !d.IsDir() {
			rel, relErr := filepath.Rel(root, path)
			if relErr == nil {
				refs = append(refs, filepath.ToSlash(rel))
			}
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
			}
			if value.IncomeYear == "" && (value.EffectiveFrom == "" || value.EffectiveTo == "") {
				missing = append(missing, fmt.Sprintf("%s:%d:missing-period", filepath.ToSlash(path), i))
			}
		}
	}
	return missing
}

func missingGuardrail(root, skill string) bool {
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

func sourceID(originalURL, canonical string) string {
	return "ato-" + HashBytes([]byte(originalURL + "|" + canonical))[:12]
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

func sortedKeys(m map[string]int) []string {
	var keys []string
	for key := range m {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func writeList(b *strings.Builder, title string, values []string) {
	b.WriteString("\n## " + title + "\n\n")
	if len(values) == 0 {
		b.WriteString("- none\n")
		return
	}
	for _, value := range values {
		b.WriteString("- " + value + "\n")
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func ValidateValueForYear(value ValueFact, requestedIncomeYear string) error {
	if value.SourceURL == "" || value.SourceTitle == "" || value.CheckedAt == "" || value.ContentHash == "" {
		return errors.New("value missing official provenance")
	}
	if value.IncomeYear == "" && (value.EffectiveFrom == "" || value.EffectiveTo == "") {
		return errors.New("value missing income year or effective period")
	}
	if requestedIncomeYear != "" && value.IncomeYear != "" && value.IncomeYear != requestedIncomeYear {
		return fmt.Errorf("value income year %s does not match requested %s", value.IncomeYear, requestedIncomeYear)
	}
	return nil
}

func ValidateCurrentValue(value ValueFact, requestedIncomeYear string, sourceVerified bool) error {
	if !sourceVerified {
		return errors.New("current official source was not verified")
	}
	return ValidateValueForYear(value, requestedIncomeYear)
}
