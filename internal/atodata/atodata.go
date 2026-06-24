package atodata

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"html"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"
)

const Scope = "ATO official pages relevant to Australian FY2025-26 individual, employment, ABN/sole trader, GST/BAS, PAYG instalments, PAYG withholding, STP, TPAR, FBT, CGT, ETF/investment, crypto, rental-property records, super, and private health tax preparation."

var SeedURLs = []string{
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
}

var PathKeywords = []string{
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
}

type Index struct {
	FetchedAt   string    `json:"fetched_at,omitempty"`
	RefreshedAt string    `json:"refreshed_at,omitempty"`
	Scope       string    `json:"scope"`
	Records     []*Record `json:"records"`
	Failures    []Failure `json:"failures"`
}

type Record struct {
	URL         string `json:"url"`
	FinalURL    string `json:"final_url"`
	Status      int    `json:"status"`
	Title       string `json:"title"`
	LastUpdated string `json:"last_updated"`
	RawFile     string `json:"raw_file"`
	TextFile    string `json:"text_file"`
	LastChecked string `json:"last_checked,omitempty"`
}

type Failure struct {
	URL   string `json:"url"`
	Error string `json:"error"`
}

type RefreshResult struct {
	URL     string `json:"url"`
	Status  int    `json:"status,omitempty"`
	Changed bool   `json:"changed"`
	Title   string `json:"title,omitempty"`
	Error   string `json:"error,omitempty"`
}

type FetchResult struct {
	Status   int
	FinalURL string
	Body     []byte
}

func SkillRoot() (string, error) {
	exe, err := os.Executable()
	if err != nil {
		return "", err
	}
	dir := filepath.Dir(exe)
	if filepath.Base(dir) == "bin" {
		return filepath.Dir(dir), nil
	}
	if filepath.Base(dir) == "scripts" {
		return filepath.Dir(dir), nil
	}
	return filepath.Dir(dir), nil
}

func DataDir(root string) string {
	return filepath.Join(root, "data", "ato_knowledge_base")
}

func CacheDir(root string) string {
	return filepath.Join(root, ".cache", "ato")
}

func IndexPath(root string) string {
	return filepath.Join(DataDir(root), "source_index.json")
}

func LoadIndex(root string) (*Index, error) {
	body, err := os.ReadFile(IndexPath(root))
	if err != nil {
		return nil, err
	}
	var idx Index
	if err := json.Unmarshal(body, &idx); err != nil {
		return nil, err
	}
	return &idx, nil
}

func SaveIndex(root string, idx *Index) error {
	idx.RefreshedAt = time.Now().UTC().Format(time.RFC3339)
	body, err := json.MarshalIndent(idx, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(IndexPath(root), append(body, '\n'), 0644)
}

func Fetch(rawURL string) (*FetchResult, error) {
	cmd := exec.Command(
		"curl",
		"-L",
		"--silent",
		"--show-error",
		"--max-time",
		"30",
		"--write-out",
		"\n%{http_code} %{url_effective}",
		rawURL,
	)
	output, err := cmd.Output()
	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			return nil, fmt.Errorf("%v: %s", err, string(exitErr.Stderr))
		}
		return nil, err
	}
	body, meta, ok := bytes.Cut(output, []byte("\n"))
	if !ok {
		return nil, errors.New("curl output missing response metadata")
	}
	// Use the last newline because HTML bodies can contain newlines.
	if last := bytes.LastIndexByte(output, '\n'); last >= 0 {
		body = output[:last]
		meta = output[last+1:]
	}
	parts := strings.SplitN(string(meta), " ", 2)
	if len(parts) != 2 {
		return nil, fmt.Errorf("invalid curl metadata: %q", string(meta))
	}
	var status int
	if _, err := fmt.Sscanf(parts[0], "%d", &status); err != nil {
		return nil, err
	}
	return &FetchResult{Status: status, FinalURL: parts[1], Body: body}, nil
}

var (
	scriptRE   = regexp.MustCompile(`(?is)<script.*?</script>`)
	styleRE    = regexp.MustCompile(`(?is)<style.*?</style>`)
	tagRE      = regexp.MustCompile(`(?s)<[^>]+>`)
	spaceRE    = regexp.MustCompile(`\s+`)
	titleRE    = regexp.MustCompile(`([^|]{3,120})\s+\|\s+Australian Taxation Office`)
	modifiedRE = regexp.MustCompile(`dcterms\.modified" content="[^;]+;\s*([^"]+)"`)
	updatedRE  = regexp.MustCompile(`Last updated\s+([0-9]{1,2}\s+[A-Za-z]+\s+[0-9]{4})`)
	hrefRE     = regexp.MustCompile(`(?i)href=["']([^"']+)["']`)
	termRE     = regexp.MustCompile(`[^a-z0-9]+`)
)

func CleanText(src []byte) string {
	s := string(src)
	s = scriptRE.ReplaceAllString(s, " ")
	s = styleRE.ReplaceAllString(s, " ")
	s = tagRE.ReplaceAllString(s, " ")
	s = html.UnescapeString(s)
	s = strings.ReplaceAll(s, "\r", "")
	s = spaceRE.ReplaceAllString(s, " ")
	return strings.TrimSpace(s)
}

func TitleOf(text string) string {
	if match := titleRE.FindStringSubmatch(text); len(match) > 1 {
		return strings.TrimSpace(match[1])
	}
	if len(text) > 90 {
		return strings.TrimSpace(text[:90])
	}
	return strings.TrimSpace(text)
}

func ModifiedOf(src []byte, text string) string {
	if match := modifiedRE.FindSubmatch(src); len(match) > 1 {
		return strings.TrimSpace(string(match[1]))
	}
	if match := updatedRE.FindStringSubmatch(text); len(match) > 1 {
		return match[1]
	}
	return ""
}

func SlugFor(rawURL string) string {
	parsed, err := url.Parse(rawURL)
	path := "home"
	if err == nil && strings.Trim(parsed.Path, "/") != "" {
		path = strings.ReplaceAll(strings.Trim(parsed.Path, "/"), "/", "__")
	}
	path = regexp.MustCompile(`[^A-Za-z0-9_.-]+`).ReplaceAllString(path, "-")
	if len(path) > 160 {
		path = path[:160]
	}
	sum := sha1Short(rawURL)
	return fmt.Sprintf("%s__%s", path, sum)
}

func sha1Short(s string) string {
	h := sha256.Sum256([]byte(s))
	return hex.EncodeToString(h[:])[:8]
}

func HashText(s string) string {
	h := sha256.Sum256([]byte(s))
	return hex.EncodeToString(h[:])
}

func RecordText(root string, rec *Record) string {
	body, err := os.ReadFile(filepath.Join(DataDir(root), rec.TextFile))
	if err == nil {
		return string(body)
	}
	body, err = os.ReadFile(filepath.Join(CacheDir(root), rec.TextFile))
	if err != nil {
		return ""
	}
	return string(body)
}

func QueryScore(root string, rec *Record, query string) int {
	titleURL := strings.ToLower(rec.Title + " " + rec.URL + " " + rec.FinalURL)
	terms := Terms(query)
	if len(terms) == 0 {
		return 0
	}
	score := 0
	phrase := strings.ToLower(strings.TrimSpace(query))
	if phrase != "" && strings.Contains(titleURL, phrase) {
		score += 100
	}
	for _, term := range terms {
		if strings.Contains(titleURL, term) {
			score += 15
		}
	}
	slug := strings.ReplaceAll(strings.ToLower(firstNonEmpty(rec.FinalURL, rec.URL)), "-", " ")
	for _, term := range terms {
		if strings.Contains(slug, term) {
			score += 10
		}
	}
	text := strings.ToLower(RecordText(root, rec))
	if phrase != "" && strings.Contains(text, phrase) {
		score += 20
	}
	for _, term := range terms {
		if strings.Contains(text, term) {
			score += 2
		}
	}
	return score
}

func Terms(query string) []string {
	raw := termRE.Split(strings.ToLower(query), -1)
	var terms []string
	for _, term := range raw {
		if len(term) > 2 {
			terms = append(terms, term)
		}
	}
	return terms
}

func RefreshRecord(root string, rec *Record) RefreshResult {
	target := firstNonEmpty(rec.FinalURL, rec.URL)
	fetched, err := Fetch(target)
	if err != nil {
		return RefreshResult{URL: target, Changed: false, Error: err.Error()}
	}
	if fetched.Status >= 400 {
		return RefreshResult{URL: target, Status: fetched.Status, Changed: false, Error: fmt.Sprintf("HTTP %d", fetched.Status)}
	}
	text := CleanText(fetched.Body)
	textPath := filepath.Join(CacheDir(root), rec.TextFile)
	rawPath := filepath.Join(CacheDir(root), rec.RawFile)
	oldBytes, _ := os.ReadFile(textPath)
	changed := HashText(string(oldBytes)) != HashText(text)
	if changed {
		_ = os.MkdirAll(filepath.Dir(rawPath), 0755)
		_ = os.MkdirAll(filepath.Dir(textPath), 0755)
		_ = os.WriteFile(rawPath, fetched.Body, 0644)
		_ = os.WriteFile(textPath, []byte(text), 0644)
	}
	rec.FinalURL = fetched.FinalURL
	rec.Status = fetched.Status
	rec.Title = TitleOf(text)
	rec.LastUpdated = ModifiedOf(fetched.Body, text)
	rec.LastChecked = time.Now().UTC().Format(time.RFC3339)
	return RefreshResult{URL: fetched.FinalURL, Status: fetched.Status, Changed: changed, Title: rec.Title}
}

func SelectByQuery(root string, records []*Record, query string, limit int) []*Record {
	type scored struct {
		score int
		rec   *Record
	}
	var scoredRecords []scored
	for _, rec := range records {
		score := QueryScore(root, rec, query)
		if score > 0 {
			scoredRecords = append(scoredRecords, scored{score: score, rec: rec})
		}
	}
	sort.SliceStable(scoredRecords, func(i, j int) bool {
		return scoredRecords[i].score > scoredRecords[j].score
	})
	if limit <= 0 || limit > len(scoredRecords) {
		limit = len(scoredRecords)
	}
	selected := make([]*Record, 0, limit)
	for _, item := range scoredRecords[:limit] {
		selected = append(selected, item.rec)
	}
	return selected
}

func SelectByURL(records []*Record, urls []string) ([]*Record, []string) {
	wanted := map[string]bool{}
	for _, raw := range urls {
		wanted[raw] = true
	}
	var selected []*Record
	for _, rec := range records {
		if wanted[rec.URL] || wanted[rec.FinalURL] {
			selected = append(selected, rec)
			delete(wanted, rec.URL)
			delete(wanted, rec.FinalURL)
		}
	}
	var missing []string
	for raw := range wanted {
		missing = append(missing, raw)
	}
	sort.Strings(missing)
	return selected, missing
}

func DiscoverLinks(baseURL string, src []byte) []string {
	base, err := url.Parse(baseURL)
	if err != nil {
		return nil
	}
	seen := map[string]bool{}
	for _, match := range hrefRE.FindAllSubmatch(src, -1) {
		href := string(match[1])
		if strings.HasPrefix(href, "#") || strings.HasPrefix(href, "mailto:") || strings.HasPrefix(href, "tel:") {
			continue
		}
		parsed, err := url.Parse(href)
		if err != nil {
			continue
		}
		abs := base.ResolveReference(parsed)
		if abs.Host != "www.ato.gov.au" {
			continue
		}
		abs.RawQuery = ""
		abs.Fragment = ""
		abs.Path = strings.TrimRight(abs.Path, "/")
		if pathAllowed(abs.Path) {
			seen[abs.String()] = true
		}
	}
	var links []string
	for link := range seen {
		links = append(links, link)
	}
	sort.Strings(links)
	return links
}

func pathAllowed(path string) bool {
	for _, keyword := range PathKeywords {
		if strings.Contains(path, keyword) {
			return true
		}
	}
	return false
}

type QueueItem struct {
	URL   string
	Depth int
}

func Recrawl(root string, maxPages int) (*Index, error) {
	if maxPages <= 0 {
		maxPages = 250
	}
	dataDir := DataDir(root)
	if err := os.MkdirAll(filepath.Join(dataDir, "raw"), 0755); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(filepath.Join(dataDir, "text"), 0755); err != nil {
		return nil, err
	}
	var queue []QueueItem
	seen := map[string]bool{}
	for _, raw := range SeedURLs {
		clean := strings.TrimRight(raw, "/")
		queue = append(queue, QueueItem{URL: clean})
		seen[clean] = true
	}
	idx := &Index{
		FetchedAt: time.Now().UTC().Format(time.RFC3339),
		Scope:     Scope,
	}
	for len(queue) > 0 && len(idx.Records) < maxPages {
		item := queue[0]
		queue = queue[1:]
		fetched, err := Fetch(item.URL)
		if err != nil || fetched.Status >= 400 {
			msg := "unknown error"
			if err != nil {
				msg = err.Error()
			} else {
				msg = fmt.Sprintf("HTTP Error %d: HTTP error", fetched.Status)
			}
			idx.Failures = append(idx.Failures, Failure{URL: item.URL, Error: msg})
			continue
		}
		text := CleanText(fetched.Body)
		slug := SlugFor(fetched.FinalURL)
		rawFile := filepath.Join("raw", slug+".html")
		textFile := filepath.Join("text", slug+".txt")
		if err := os.WriteFile(filepath.Join(dataDir, rawFile), fetched.Body, 0644); err != nil {
			return nil, err
		}
		if err := os.WriteFile(filepath.Join(dataDir, textFile), []byte(text), 0644); err != nil {
			return nil, err
		}
		idx.Records = append(idx.Records, &Record{
			URL:         item.URL,
			FinalURL:    fetched.FinalURL,
			Status:      fetched.Status,
			Title:       TitleOf(text),
			LastUpdated: ModifiedOf(fetched.Body, text),
			RawFile:     rawFile,
			TextFile:    textFile,
		})
		if item.Depth < 1 {
			for _, link := range DiscoverLinks(fetched.FinalURL, fetched.Body) {
				if !seen[link] {
					seen[link] = true
					queue = append(queue, QueueItem{URL: link, Depth: item.Depth + 1})
				}
			}
		}
		time.Sleep(150 * time.Millisecond)
	}
	if err := WriteReadme(root, idx); err != nil {
		return nil, err
	}
	body, err := json.MarshalIndent(idx, "", "  ")
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(IndexPath(root), append(body, '\n'), 0644); err != nil {
		return nil, err
	}
	return idx, nil
}

func WriteReadme(root string, idx *Index) error {
	var buf bytes.Buffer
	buf.WriteString("# ATO Tax Knowledge Base\n\n")
	buf.WriteString("Fetched: " + idx.FetchedAt + "\n\n")
	buf.WriteString(idx.Scope + "\n\n")
	buf.WriteString("## Sources\n\n")
	for _, rec := range idx.Records {
		updated := ""
		if rec.LastUpdated != "" {
			updated = " - last updated " + rec.LastUpdated
		}
		buf.WriteString(fmt.Sprintf("- [%s](%s)%s\n", rec.Title, rec.FinalURL, updated))
	}
	if len(idx.Failures) > 0 {
		buf.WriteString("\n## Fetch Failures\n\n")
		for _, failure := range idx.Failures {
			buf.WriteString(fmt.Sprintf("- %s: %s\n", failure.URL, failure.Error))
		}
	}
	return os.WriteFile(filepath.Join(DataDir(root), "README.md"), buf.Bytes(), 0644)
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func WriteJSON(value any) error {
	body, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return err
	}
	_, err = os.Stdout.Write(append(body, '\n'))
	return err
}

func Errorf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, format+"\n", args...)
}

func EnsureRoot(root string) error {
	if _, err := os.Stat(filepath.Join(root, "SKILL.md")); err != nil {
		return errors.New("cannot locate skill root with SKILL.md")
	}
	return nil
}
