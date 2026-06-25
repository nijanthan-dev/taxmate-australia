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
)

type refreshFixtureSource struct {
	URL  string
	Text string
}

var (
	refreshCmdOnce   sync.Once
	refreshCmdBinary string
	refreshCmdErr    error
)

func refreshCommandBinary(t *testing.T) string {
	t.Helper()
	refreshCmdOnce.Do(func() {
		tmpDir, err := os.MkdirTemp("", "taxmate-australia-refresh-bin-")
		if err != nil {
			refreshCmdErr = err
			return
		}
		path := filepath.Join(tmpDir, "taxmate-australia-refresh")
		cmd := exec.Command("go", "build", "-o", path, ".")
		var out bytes.Buffer
		cmd.Stdout = &out
		cmd.Stderr = &out
		if err := cmd.Run(); err != nil {
			refreshCmdErr = fmt.Errorf("build taxmate-australia-refresh: %w: %s", err, out.String())
			return
		}
		refreshCmdBinary = path
	})
	if refreshCmdErr != nil {
		t.Fatalf("command binary build failed: %v", refreshCmdErr)
	}
	return refreshCmdBinary
}

func TestRefreshCommandUsesSourceRegistry(t *testing.T) {
	const sourceURL = "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim"
	root := refreshFixtureRoot(t, []refreshFixtureSource{
		{
			URL:  sourceURL,
			Text: "seed text",
		},
	})
	curlDir, err := os.MkdirTemp("", "taxmate-australia-fake-curl-")
	if err != nil {
		t.Fatal(err)
	}
	defer os.RemoveAll(curlDir)
	curlPath := filepath.Join(curlDir, "curl")
	curlScript := "#!/bin/sh\n" +
		"for arg in \"$@\"; do\n" +
		"  last=\"$arg\"\n" +
		"done\n" +
		"cat <<'EOF'\n" +
		"<html><head><title>Updated Mock | Australian Taxation Office</title></head><body>mock</body></html>\n" +
		"EOF\n" +
		"printf '\\n200 %s' \"$last\"\n"
	if err := os.WriteFile(curlPath, []byte(curlScript), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.Chmod(curlPath, 0o755); err != nil {
		t.Fatal(err)
	}

	cmd := exec.Command(refreshCommandBinary(t), "--all")
	cmd.Dir = root
	cmd.Env = append(os.Environ(), "PATH="+curlDir+":"+os.Getenv("PATH"))
	var out bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &out
	if err := cmd.Run(); err != nil {
		t.Fatalf("refresh --all failed: %s", out.String())
	}
	if !strings.Contains(out.String(), "\"matched\":") || !strings.Contains(out.String(), "\"changed\":") {
		t.Fatalf("unexpected refresh output: %s", out.String())
	}

	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(registry.Records) != 1 {
		t.Fatalf("expected 1 record, got %d", len(registry.Records))
	}
	record := registry.Records[0]
	if record.URL != sourceURL {
		t.Fatalf("unexpected record url %q", record.URL)
	}
	if record.Status != 200 {
		t.Fatalf("expected status 200, got %d", record.Status)
	}
	if record.Title != "Updated Mock" {
		t.Fatalf("expected refreshed title, got %q", record.Title)
	}
	if strings.TrimSpace(record.LastChecked) == "" {
		t.Fatal("expected checked timestamp after refresh")
	}
	if record.ContentHash == atodata.HashText("seed text") {
		t.Fatalf("expected content hash to update from seed")
	}
	if _, err := os.Stat(filepath.Join(root, "data", "ato_knowledge_base", "source_index.json")); !os.IsNotExist(err) {
		t.Fatal("found obsolete source_index.json")
	}
}

func refreshFixtureRoot(t *testing.T, sources []refreshFixtureSource) string {
	t.Helper()
	root := t.TempDir()
	dataDir := filepath.Join(root, "data", "ato_knowledge_base")
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		t.Fatal(err)
	}

	pluginPath := filepath.Join(root, ".codex-plugin", "plugin.json")
	if err := os.MkdirAll(filepath.Dir(pluginPath), 0o755); err != nil {
		t.Fatal(err)
	}
	pluginBody, err := json.Marshal(map[string]any{
		"name":    "taxmate-australia",
		"version": "0.0.0",
		"skills":  "./skills/",
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(pluginPath, append(pluginBody, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}

	records := make([]*atodata.SourceRecord, 0, len(sources))
	for i, source := range sources {
		record := &atodata.SourceRecord{
			URL:             source.URL,
			FinalURL:        source.URL,
			Status:          200,
			Title:           "Seed title",
			LastUpdated:     "2026-01-01",
			RawFile:         filepath.Join("raw", fmt.Sprintf("source_%03d.html", i)),
			TextFile:        filepath.Join("text", fmt.Sprintf("source_%03d.txt", i)),
			ContentHash:     atodata.HashText(source.Text),
			LastChecked:     "2026-01-01T00:00:00Z",
			ContentVerified: true,
		}
		records = append(records, record)
	}
	registry := &atodata.SourceRegistry{
		Scope:   "test",
		Records: records,
	}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		t.Fatal(err)
	}
	return root
}
