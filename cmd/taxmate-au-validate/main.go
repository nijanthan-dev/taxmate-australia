package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"taxmate-au-skill/internal/atodata"
)

var topicQueries = map[string][]string{
	"wfh_fixed_rate_2025_26": {"working-from-home-expenses/fixed-rate-method", "70 cents per work hour"},
	"wfh_actual_cost":        {"working-from-home-expenses/actual-cost-method"},
	"employee_records":       {"records-you-need-to-keep", "work-related expenses"},
	"employee_software_assets": {"computers-laptops-and-software",
		"assets-costing-300"},
	"abn_business_income":     {"assessable-income", "business-partnership-and-trust-income"},
	"abn_business_deductions": {"deductions-for-digital-product-expenses", "deductions-for-other-operating-expenses"},
	"abn_business_losses":     {"business-losses"},
	"psi":                     {"personal-services-income"},
	"home_business":           {"deductions-for-home-based-business-expenses", "home-based-business-and-cgt-implications"},
	"gst_credits":             {"claiming-gst-credits", "when-you-can-claim-a-gst-credit"},
	"gst_tax_invoices":        {"tax-invoices"},
	"gst_bas":                 {"business-activity-statements-bas", "goods-and-services-tax-gst"},
	"payg_instalments":        {"payg instalments", "instalment notices"},
	"payg_withholding":        {"payg withholding", "tax tables"},
	"stp_income_statements":   {"single touch payroll", "income statement"},
	"fbt":                     {"fringe benefits tax", "gross-up rate"},
	"investments_income":      {"income-you-must-declare/investment-income", "shares-funds-and-trusts"},
	"cgt_calculation":         {"calculating your cgt", "cgt discount"},
	"shares_cgt":              {"capital-gains-tax/shares-and-similar-investments", "dividend-reinvestment-plans"},
	"crypto_records":          {"crypto-asset-investments", "keeping crypto records"},
	"rental_property_records": {"records-for-rental-properties-and-holiday-homes", "rental properties"},
	"non_commercial_losses":   {"non-commercial loss", "carrying on a business"},
	"tpar":                    {"taxable payments annual report", "contractor payments"},
	"super":                   {"personal-super-contributions", "concessional-contributions", "super guarantee"},
	"private_health":          {"private-health-insurance-rebate", "medicare-levy-surcharge"},
}

var staleSeedReplacements = map[string][]string{
	"deductions-you-can-claim/tools-and-equipment":                {"tools-and-equipment-to-perform-your-work"},
	"deductions-you-can-claim/other-work-related-deductions":      {"deductions-you-can-claim/claiming-deductions"},
	"income-and-deductions-for-business/business-income":          {"income-and-deductions-for-business/assessable-income"},
	"claiming-a-tax-deduction-for-business-expenses":              {"income-and-deductions-for-business/deductions"},
	"deductions/motor-vehicle-and-car-expenses":                   {"deductions-for-motor-vehicle-expenses"},
	"gst-credits-and-income-tax-deductions":                       {"effect-of-gst-credits-on-income-tax-deductions"},
	"managed-investment-funds":                                    {"shares-funds-and-trusts", "trust-non-assessable-payments-cgt-event-e4"},
	"investments-and-assets/investment-income":                    {"income-you-must-declare/investment-income"},
	"how-to-save-more-in-your-super/personal-super-contributions": {"super/growing-and-keeping-track-of-your-super/how-to-save-more-in-your-super/personal-super-contributions"},
	"claiming-deductions-for-personal-super-contributions":        {"personal-super-contributions"},
}

type check struct {
	Name   string `json:"check"`
	Passed bool   `json:"passed"`
	Detail string `json:"detail"`
}

func main() {
	root, err := atodata.SkillRoot()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	report, ok := validate(root)
	_ = atodata.WriteJSON(report)
	if !ok {
		os.Exit(1)
	}
}

func validate(root string) (map[string]any, bool) {
	var checks []check
	add := func(name string, passed bool, detail string) {
		checks = append(checks, check{Name: name, Passed: passed, Detail: detail})
	}

	manifest, manifestErr := readPluginManifest(root)
	manifestText := readText(filepath.Join(root, ".codex-plugin", "plugin.json"))
	add("codex_plugin_manifest_exists", manifestErr == nil, fmt.Sprint(manifestErr))
	add("codex_plugin_manifest_required_keys", (manifest["name"] == "taxmate-au" || manifest["name"] == "taxmate-australia") && manifest["version"] != "" && manifest["skills"] == "./skills/", "")
	add("public_manifest_polished", (strings.Contains(manifestText, "TaxMate Australia Maintainers") || strings.Contains(manifestText, "TaxMate AU Maintainers")) && !strings.Contains(manifestText, `"Local"`) && !strings.Contains(manifestText, `"Private"`) && !strings.Contains(manifestText, `"repository": "local"`), "")
	add("plugin_icon_declared", strings.Contains(manifestText, `"composerIcon": "./assets/icon.png"`) && strings.Contains(manifestText, `"logo": "./assets/icon.png"`) && fileExists(filepath.Join(root, "assets", "icon.png")), "")
	add("codex_plugin_no_root_monolith", !fileExists(filepath.Join(root, "SKILL.md")), "")
	add("open_plugin_backend_dirs", fileExists(filepath.Join(root, "bin")) && fileExists(filepath.Join(root, "cmd")) && fileExists(filepath.Join(root, "internal")) && fileExists(filepath.Join(root, "data")) && fileExists(filepath.Join(root, "skills")), "")
	add("publication_docs_exist", fileExists(filepath.Join(root, "README.md")) && fileExists(filepath.Join(root, "DISCLAIMER.md")) && fileExists(filepath.Join(root, "docs", "PUBLICATION_CHECKLIST.md")), "")

	requiredSkills := []string{"research", "finance-review", "calculators", "workbook", "taxpack"}
	skillText, missingSkills, badFrontmatter := loadSkillDocs(root, requiredSkills)
	add("codex_plugin_required_skills_exist", len(missingSkills) == 0, strings.Join(missingSkills, ", "))
	add("skill_frontmatter_valid", len(badFrontmatter) == 0, strings.Join(badFrontmatter, ", "))
	add("description_nonempty", allSkillDescriptionsLong(root, requiredSkills), "")
	add("invocation_documented", (strings.Contains(skillText, "$taxmate-australia:research") || strings.Contains(skillText, "$taxmate-au:research")) &&
		(strings.Contains(skillText, "$taxmate-australia:finance-review") || strings.Contains(skillText, "$taxmate-au:finance-review")) &&
		(strings.Contains(skillText, "$taxmate-australia:workbook") || strings.Contains(skillText, "$taxmate-au:workbook")), "")
	add("go_binaries_documented", strings.Contains(skillText, "bin/taxmate-au-refresh") && strings.Contains(skillText, "bin/taxmate-au-validate") && strings.Contains(skillText, "bin/taxmate-au-finance") && strings.Contains(skillText, "bin/taxmate-au-calc"), "")
	add("portable_root_documented", strings.Contains(skillText, "TAXMATE_AU_ROOT") && strings.Contains(readText(filepath.Join(root, "README.md")), "TAXMATE_AU_ROOT"), "")
	publicDocs := publicDocFiles(root)
	add("public_docs_no_private_paths", noPrivatePaths(root, publicDocs), strings.Join(firstN(privatePathHits(root, publicDocs), 5), "; "))
	add("wrappers_mark_local_fallback", wrappersMarkLocalFallback(root), "")
	add("wrapper_frontmatter_names", wrapperFrontmatterNamesMatchPath(root), "")
	add("wrapper_invocation_paths", wrapperInvocationsUseAustraliaPrefix(root), "")
	disclaimerText := readText(filepath.Join(root, "DISCLAIMER.md"))
	add("public_disclaimer_documented", hasPublicDisclaimers(readText(filepath.Join(root, "README.md"))+disclaimerText+skillText+manifestText), "")
	add("output_layer_separated", strings.Contains(skillText, "must not create new tax logic") && strings.Contains(skillText, "consumes reviewed data"), "")
	add("expanded_domain_rules_documented", strings.Contains(skillText, "PAYG") && strings.Contains(skillText, "FBT") && strings.Contains(skillText, "CGT") && strings.Contains(skillText, "stamp duty"), "")

	idx, err := atodata.LoadIndex(root)
	add("source_index_exists", err == nil, "")
	if err != nil {
		return finish(root, checks, nil, false)
	}
	add("source_record_count", len(idx.Records) >= 290, fmt.Sprint(len(idx.Records)))
	add("source_scope_present", idx.Scope != "", "")
	dataDir := atodata.DataDir(root)
	add("scope_summary_exists", fileExists(filepath.Join(dataDir, "SCOPE_SUMMARY.md")), "")
	add("readme_exists", fileExists(filepath.Join(dataDir, "README.md")), "")

	var missingFiles []string
	all200 := true
	for _, rec := range idx.Records {
		if rec.Status != 200 {
			all200 = false
		}
		if !fileExists(filepath.Join(dataDir, rec.RawFile)) {
			missingFiles = append(missingFiles, rec.FinalURL+":raw_file")
		}
		if !fileExists(filepath.Join(dataDir, rec.TextFile)) {
			missingFiles = append(missingFiles, rec.FinalURL+":text_file")
		}
	}
	add("indexed_files_exist", len(missingFiles) == 0, strings.Join(firstN(missingFiles, 5), "; "))
	add("all_records_http_200", all200, "")

	hay := haystack(root, idx)
	var missingTopics []string
	for topic, needles := range topicQueries {
		if !containsAny(hay, needles) {
			missingTopics = append(missingTopics, topic)
		}
	}
	add("key_tax_topics_covered", len(missingTopics) == 0, strings.Join(missingTopics, ", "))

	var unresolved []string
	for _, failure := range idx.Failures {
		matched := false
		for stale, replacements := range staleSeedReplacements {
			if strings.Contains(failure.URL, stale) {
				matched = containsAny(hay, replacements)
				break
			}
		}
		if !matched {
			unresolved = append(unresolved, failure.URL)
		}
	}
	add("stale_seed_failures_have_replacements", len(unresolved) == 0, strings.Join(firstN(unresolved, 5), "; "))

	add("go_binaries_exist", fileExists(filepath.Join(root, "bin", "taxmate-au-refresh")) && fileExists(filepath.Join(root, "bin", "taxmate-au-validate")) && fileExists(filepath.Join(root, "bin", "taxmate-au-finance")) && fileExists(filepath.Join(root, "bin", "taxmate-au-calc")), "")
	generated, _ := filepath.Glob(filepath.Join(root, "**", "__pycache__"))
	pyFiles := findBySuffix(root, ".py")
	pycFiles := findBySuffix(root, ".pyc")
	dotGoFiles := findBySuffix(root, ".go")
	add("no_python_backend", len(pyFiles) == 0 && len(pycFiles) == 0 && len(generated) == 0, strings.Join(firstN(relativePaths(root, append(pyFiles, pycFiles...)), 5), "; "))
	isWrapperRuntime := strings.Contains(root, string(filepath.Separator)+".agents"+string(filepath.Separator)+"skills"+string(filepath.Separator))
	wrapperRuntimeClean := len(dotGoFiles) == 0 || !isWrapperRuntime
	wrapperRuntimeDetail := ""
	if !wrapperRuntimeClean {
		wrapperRuntimeDetail = strings.Join(firstN(relativePaths(root, dotGoFiles), 5), "; ")
	}
	add("wrapper_runtime_no_go_source", wrapperRuntimeClean, wrapperRuntimeDetail)

	return finish(root, checks, idx, true)
}

func finish(root string, checks []check, idx *atodata.Index, includeIndex bool) (map[string]any, bool) {
	passed := 0
	for _, item := range checks {
		if item.Passed {
			passed++
		}
	}
	score := float64(passed) / float64(len(checks)) * 100
	report := map[string]any{
		"plugin": filepath.Base(root),
		"score":  score,
		"passed": passed,
		"total":  len(checks),
		"checks": checks,
	}
	if includeIndex && idx != nil {
		report["records"] = len(idx.Records)
		report["failures"] = len(idx.Failures)
	}
	return report, passed == len(checks)
}

func readPluginManifest(root string) (map[string]string, error) {
	body, err := os.ReadFile(filepath.Join(root, ".codex-plugin", "plugin.json"))
	if err != nil {
		return nil, err
	}
	var raw map[string]any
	if err := json.Unmarshal(body, &raw); err != nil {
		return nil, err
	}
	out := map[string]string{}
	for _, key := range []string{"name", "version", "skills"} {
		if value, ok := raw[key].(string); ok {
			out[key] = value
		}
	}
	return out, nil
}

func loadSkillDocs(root string, skills []string) (string, []string, []string) {
	var b strings.Builder
	var missing []string
	var bad []string
	for _, skill := range skills {
		path := filepath.Join(root, "skills", skill, "SKILL.md")
		body, err := os.ReadFile(path)
		if err != nil {
			missing = append(missing, skill)
			continue
		}
		text := string(body)
		frontmatter := parseFrontmatter(text)
		if frontmatter == nil || frontmatter["name"] != skill || frontmatter["description"] == "" {
			bad = append(bad, skill)
		}
		b.WriteString(text)
		b.WriteByte('\n')
	}
	return b.String(), missing, bad
}

func allSkillDescriptionsLong(root string, skills []string) bool {
	for _, skill := range skills {
		body, err := os.ReadFile(filepath.Join(root, "skills", skill, "SKILL.md"))
		if err != nil {
			return false
		}
		frontmatter := parseFrontmatter(string(body))
		if frontmatter == nil || len(frontmatter["description"]) < 40 {
			return false
		}
	}
	return true
}

func readText(path string) string {
	body, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return string(body)
}

func publicDocFiles(root string) []string {
	var files []string
	for _, path := range []string{
		filepath.Join(root, "README.md"),
		filepath.Join(root, "DISCLAIMER.md"),
		filepath.Join(root, ".codex-plugin", "plugin.json"),
		filepath.Join(root, "agents", "openai.yaml"),
		filepath.Join(root, "docs", "PUBLICATION_CHECKLIST.md"),
	} {
		files = append(files, path)
	}
	for _, dir := range []string{filepath.Join(root, "skills")} {
		_ = filepath.WalkDir(dir, func(path string, d os.DirEntry, err error) error {
			if err == nil && !d.IsDir() {
				files = append(files, path)
			}
			return nil
		})
	}
	return files
}

func noPrivatePaths(root string, paths []string) bool {
	return len(privatePathHits(root, paths)) == 0
}

func privatePathHits(root string, paths []string) []string {
	var hits []string
	needles := []string{"/Users/", "custom" + "_apps/skills" + "_and" + "_plugins", "Developer/custom" + "_apps"}
	for _, path := range paths {
		text := readText(path)
		for _, needle := range needles {
			if strings.Contains(text, needle) {
				hits = append(hits, relativePath(root, path)+":"+needle)
				break
			}
		}
	}
	return hits
}

func wrappersMarkLocalFallback(root string) bool {
	wrapperDir := filepath.Join(root, "wrappers")
	wrappers := findBySuffix(wrapperDir, "SKILL.md")
	if len(wrappers) < 5 {
		return false
	}
	for _, path := range wrappers {
		text := readText(path)
		if !strings.Contains(text, "TAXMATE_AU_ROOT") || !strings.Contains(text, "when available") {
			return false
		}
	}
	return true
}

func wrapperFrontmatterNamesMatchPath(root string) bool {
	wrapperDir := filepath.Join(root, "wrappers")
	wrappers := findBySuffix(wrapperDir, "SKILL.md")
	if len(wrappers) == 0 {
		return false
	}
	for _, path := range wrappers {
		wrapperName := filepath.Base(filepath.Dir(path))
		if !strings.HasPrefix(wrapperName, "taxmate-australia") {
			return false
		}
		frontmatter := parseFrontmatter(readText(path))
		if frontmatter == nil || frontmatter["name"] != wrapperName {
			return false
		}
	}
	return true
}

func wrapperInvocationsUseAustraliaPrefix(root string) bool {
	wrapperDir := filepath.Join(root, "wrappers")
	for _, path := range findBySuffix(wrapperDir, "SKILL.md") {
		text := readText(path)
		if strings.Contains(text, "$taxmate-au:") || !strings.Contains(text, "$taxmate-australia:") {
			return false
		}
	}
	return true
}

func hasPublicDisclaimers(text string) bool {
	needles := []string{
		"not tax, legal, accounting, financial",
		"not affiliated with",
		"endorsed",
		"Australian Taxation Office",
		"registered-tax-agent advice",
		"does not lodge",
		"Accountant review",
	}
	lower := strings.ToLower(text)
	for _, needle := range needles {
		if !strings.Contains(lower, strings.ToLower(needle)) {
			return false
		}
	}
	return true
}

func parseFrontmatter(text string) map[string]string {
	if !strings.HasPrefix(text, "---\n") {
		return nil
	}
	end := strings.Index(text[4:], "\n---\n")
	if end < 0 {
		return nil
	}
	body := text[4 : 4+end]
	out := map[string]string{}
	for _, line := range strings.Split(body, "\n") {
		if strings.TrimSpace(line) == "" || strings.HasPrefix(line, " ") || strings.HasPrefix(line, "\t") {
			continue
		}
		line = strings.TrimSpace(line)
		parts := strings.SplitN(line, ":", 2)
		if len(parts) != 2 {
			return nil
		}
		out[strings.TrimSpace(parts[0])] = strings.Trim(strings.TrimSpace(parts[1]), `"`)
	}
	return out
}

func onlyKeys(m map[string]string, keys ...string) bool {
	allowed := map[string]bool{}
	for _, key := range keys {
		allowed[key] = true
	}
	for key := range m {
		if !allowed[key] {
			return false
		}
	}
	return true
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func haystack(root string, idx *atodata.Index) string {
	var b strings.Builder
	for _, rec := range idx.Records {
		b.WriteString(rec.Title)
		b.WriteByte('\n')
		b.WriteString(rec.URL)
		b.WriteByte('\n')
		b.WriteString(rec.FinalURL)
		b.WriteByte('\n')
	}
	textDir := filepath.Join(atodata.DataDir(root), "text")
	_ = filepath.WalkDir(textDir, func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() || filepath.Ext(path) != ".txt" {
			return nil
		}
		body, err := os.ReadFile(path)
		if err == nil {
			b.WriteString(filepath.Base(path))
			b.WriteByte('\n')
			if len(body) > 20000 {
				body = body[:20000]
			}
			b.Write(body)
			b.WriteByte('\n')
		}
		return nil
	})
	return strings.ToLower(b.String())
}

func containsAny(hay string, needles []string) bool {
	for _, needle := range needles {
		if strings.Contains(hay, strings.ToLower(needle)) {
			return true
		}
	}
	return false
}

func firstN(values []string, n int) []string {
	if len(values) <= n {
		return values
	}
	return values[:n]
}

func relativePaths(root string, paths []string) []string {
	out := make([]string, 0, len(paths))
	for _, path := range paths {
		out = append(out, relativePath(root, path))
	}
	return out
}

func relativePath(root, path string) string {
	rel, err := filepath.Rel(root, path)
	if err != nil || strings.HasPrefix(rel, "..") {
		return path
	}
	return rel
}

func findBySuffix(root, suffix string) []string {
	var out []string
	_ = filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err == nil && !d.IsDir() && strings.HasSuffix(path, suffix) {
			out = append(out, path)
		}
		return nil
	})
	return out
}
