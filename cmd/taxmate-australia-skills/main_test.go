package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"taxmate-au-skill/internal/atodata"
	"taxmate-au-skill/internal/skillgen"
)

type skillsCliFixtureSource struct {
	URL       string
	FinalURL  string
	Title     string
	Text      string
	CheckedAt string
}

var (
	skillCmdOnce   sync.Once
	skillCmdBinary string
	skillCmdErr    error
)

func skillCommandBinary(t *testing.T) string {
	t.Helper()
	skillCmdOnce.Do(func() {
		tmpDir, err := os.MkdirTemp("", "taxmate-australia-skills-bin-")
		if err != nil {
			skillCmdErr = err
			return
		}
		path := filepath.Join(tmpDir, "taxmate-australia-skills")
		cmd := exec.Command("go", "build", "-o", path, ".")
		var out bytes.Buffer
		cmd.Stdout = &out
		cmd.Stderr = &out
		if err := cmd.Run(); err != nil {
			skillCmdErr = fmt.Errorf("build taxmate-australia-skills: %w: %s", err, out.String())
			return
		}
		skillCmdBinary = path
	})
	if skillCmdErr != nil {
		t.Fatalf("command binary build failed: %v", skillCmdErr)
	}
	return skillCmdBinary
}

func TestGenerateCheckCommandLeavesTrackedFilesUnchanged(t *testing.T) {
	root := skillsCliFixtureRoot(t, []skillsCliFixtureSource{
		{
			URL:  "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/records-you-need-to-keep",
			Title: "Records and claims",
			Text:  "ATO records are required to support expense claims and income details.",
		},
	})
	before := pathDigestSnapshot(t, root)
	out, err := runCommand(skillCommandBinary(t), root, []string{"generate", "--check", "--checked-at", "2026-06-24T00:00:00Z"})
	if err != nil {
		t.Fatalf("generate --check failed: %s", out)
	}
	if !strings.Contains(out, "\"ok\": true") || !strings.Contains(out, "\"sources\":") {
		t.Fatalf("unexpected generate --check output: %s", out)
	}
	after := pathDigestSnapshot(t, root)
	if len(before) != len(after) {
		t.Fatalf("tracked files changed: before=%d after=%d", len(before), len(after))
	}
	for path, digest := range before {
		if after[path] != digest {
			t.Fatalf("tracked file changed during generate --check: %s", path)
		}
	}
}

func TestAuditCheckCommandLeavesTrackedFilesUnchanged(t *testing.T) {
	root := skillsCliFixtureRoot(t, []skillsCliFixtureSource{
		{
			URL:  "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst",
			Title: "GST",
			Text:  "GST obligations can include registration and credit adjustments.",
		},
	})
	before := pathDigestSnapshot(t, root)
	out, err := runCommand(skillCommandBinary(t), root, []string{"audit", "--check"})
	if err != nil {
		t.Fatalf("audit --check failed: %s", out)
	}
	if !strings.Contains(out, "\"audit\": \"source_coverage\"") || !strings.Contains(out, "\"ok\": true") {
		t.Fatalf("unexpected audit --check output: %s", out)
	}
	after := pathDigestSnapshot(t, root)
	if len(before) != len(after) {
		t.Fatalf("tracked files changed: before=%d after=%d", len(before), len(after))
	}
	for path, digest := range before {
		if after[path] != digest {
			t.Fatalf("tracked file changed during audit --check: %s", path)
		}
	}
}

func TestAuditOutputWrittenOnlyWithOutputFlag(t *testing.T) {
	root := skillsCliFixtureRoot(t, []skillsCliFixtureSource{
		{
			URL:  "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/claiming-gst-credits",
			Title: "GST Credits",
			Text:  "GST credits may require tax invoices and effective period.",
		},
	})
	tmpReport := filepath.Join(root, "source-coverage.md")
	out, err := runCommand(skillCommandBinary(t), root, []string{"audit", "--format", "markdown"})
	if err != nil {
		t.Fatalf("audit markdown failed: %s", out)
	}
	if strings.Contains(string(out), tmpReport) {
		t.Fatalf("expected stdout-only report before output flag")
	}
	if _, err := os.Stat(tmpReport); err == nil {
		t.Fatalf("report written unexpectedly without --output")
	} else if !os.IsNotExist(err) {
		t.Fatal(err)
	}
	out, err = runCommand(skillCommandBinary(t), root, []string{"audit", "--format", "markdown", "--output", tmpReport})
	if err != nil {
		t.Fatalf("audit markdown output file failed: %s", out)
	}
	if !strings.Contains(out, "\"output\":") {
		t.Fatalf("expected output path in audit response: %s", out)
	}
	body, err := os.ReadFile(tmpReport)
	if err != nil {
		t.Fatalf("missing generated report: %v", err)
	}
	if !strings.Contains(string(body), "# Source Coverage Report") {
		t.Fatalf("missing report contents")
	}
}

func skillsCliFixtureRoot(t *testing.T, sources []skillsCliFixtureSource) string {
	t.Helper()
	root := t.TempDir()
	dataDir := filepath.Join(root, "data", "ato_knowledge_base")
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, ".cache", "ato", "text"), 0o755); err != nil {
		t.Fatal(err)
	}

	pluginPath := filepath.Join(root, ".codex-plugin", "plugin.json")
	if err := os.MkdirAll(filepath.Dir(pluginPath), 0o755); err != nil {
		t.Fatal(err)
	}
	pluginBody, err := json.Marshal(map[string]any{
		"name":     "taxmate-australia",
		"version":  "0.0.0",
		"skills":   "./skills/",
		"manifest": "cli fixture",
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(pluginPath, append(pluginBody, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	records := make([]*atodata.SourceRecord, 0, len(sources))
	for i, source := range sources {
		id := fmt.Sprintf("source_%03d", i)
		entry := &atodata.SourceRecord{
			URL:         source.URL,
			FinalURL:    firstNonEmptyString(source.FinalURL, source.URL),
			Status:      200,
			Title:       source.Title,
			LastUpdated: firstNonEmptyString(source.CheckedAt, "2026-06-20T00:00:00Z"),
			LastChecked: firstNonEmptyString(source.CheckedAt, "2026-06-20T00:00:00Z"),
			RawFile:     filepath.Join("raw", id+".html"),
			TextFile:     filepath.Join("text", id+".txt"),
			ContentHash:  atodata.HashText(source.Text),
			ContentVerified: source.Text != "",
		}
		if source.Text != "" {
			cacheFile := filepath.Join(root, ".cache", "ato", entry.TextFile)
			if err := os.MkdirAll(filepath.Dir(cacheFile), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(cacheFile, []byte(source.Text), 0o644); err != nil {
				t.Fatal(err)
			}
		}
		records = append(records, entry)
	}
	registry := &atodata.SourceRegistry{Scope: "test", Records: records, RefreshedAt: "2026-06-20T00:00:00Z", FetchedAt: "2026-06-20T00:00:00Z"}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		t.Fatal(err)
	}
	if _, err := skillgen.Generate(skillgen.Options{Root: root, CheckedAt: "2026-06-24T00:00:00Z"}); err != nil {
		t.Fatal(err)
	}
	return root
}

func runCommand(binary string, dir string, args []string) (string, error) {
	cmd := exec.Command(binary, args...)
	cmd.Dir = dir
	cmd.Env = append(os.Environ(), fmt.Sprintf("TZ=UTC"))
	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out
	err := cmd.Run()
	return out.String(), err
}

func firstNonEmptyString(values ...string) string {
	for _, value := range values {
		if value != "" {
			return value
		}
	}
	return ""
}

func pathDigestSnapshot(t *testing.T, root string) map[string]string {
	t.Helper()
	out := map[string]string{}
	_ = filepath.WalkDir(root, func(path string, d os.DirEntry, err error) error {
		if err != nil || d.IsDir() {
			return nil
		}
		rel, err := filepath.Rel(root, path)
		if err != nil {
			return nil
		}
		body, err := os.ReadFile(path)
		if err != nil {
			return nil
		}
		out[rel] = string(bytes.TrimSpace(body))
		return nil
	})
	return out
}
