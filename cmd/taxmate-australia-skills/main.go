package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"taxmate-au-skill/internal/atodata"
	"taxmate-au-skill/internal/skillgen"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	root, err := commandRoot()
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	switch os.Args[1] {
	case "generate":
		fs := flag.NewFlagSet("generate", flag.ExitOnError)
		checkedAt := fs.String("checked-at", "", "verification timestamp for deterministic generation")
		check := fs.Bool("check", false, "validate generated output without writing tracked files")
		_ = fs.Parse(os.Args[2:])
		if *check {
			sources, err := checkGeneration(root, skillgen.Options{CheckedAt: *checkedAt})
			exitJSON(map[string]any{
				"generated":       true,
				"sources":         sources,
				"source_coverage": "data/ato_knowledge_base/source_coverage.json",
			}, err)
			return
		}
		report, err := skillgen.Generate(skillgen.Options{Root: root, CheckedAt: *checkedAt})
		sources := 0
		if report != nil {
			sources = len(report.Sources)
		}
		exitJSON(map[string]any{"generated": true, "sources": sources, "source_coverage": "data/ato_knowledge_base/source_coverage.json"}, err)
	case "refresh":
		fs := flag.NewFlagSet("refresh", flag.ExitOnError)
		topic := fs.String("topic", "", "topic slug")
		all := fs.Bool("all", false, "refresh all generated source URLs")
		_ = fs.Parse(os.Args[2:])
		exitJSON(refresh(root, *topic, *all))
	case "audit":
		fs := flag.NewFlagSet("audit", flag.ExitOnError)
		format := fs.String("format", "markdown", "output format: markdown or json")
		output := fs.String("output", "", "optional output path for audit report")
		check := fs.Bool("check", false, "validate coverage and exit non-zero on failure")
		_ = fs.Parse(os.Args[2:])
		if *check {
			exitJSON(map[string]any{"audit": "source_coverage"}, skillgen.ValidateSourceCoverage(root))
			return
		}
		report, err := skillgen.WriteCoverageReport(root, *format)
		if err != nil {
			exitJSON(map[string]any{"audit": "source_coverage"}, err)
			return
		}
		if strings.TrimSpace(*output) != "" {
			err = os.WriteFile(*output, report, 0644)
			exitJSON(map[string]any{"audit": "source_coverage", "output": *output}, err)
			return
		}
		_, _ = io.WriteString(os.Stdout, string(report))
		exitJSON(map[string]any{"audit": "source_coverage"}, nil)
	case "validate":
		exitJSON(map[string]any{"valid": true}, skillgen.Validate(root))
	default:
		usage()
		os.Exit(2)
	}
}

func commandRoot() (string, error) {
	if cwd, err := os.Getwd(); err == nil {
		if _, statErr := os.Stat(filepath.Join(cwd, ".codex-plugin", "plugin.json")); statErr == nil {
			return cwd, nil
		}
	}
	return atodata.SkillRoot()
}

func checkGeneration(root string, opts skillgen.Options) (int, error) {
	workRoot, err := os.MkdirTemp("", "taxmate-australia-skills-check-")
	if err != nil {
		return 0, err
	}
	defer os.RemoveAll(workRoot)
	if err := copyDir(filepath.Join(root, "data", "ato_knowledge_base"), filepath.Join(workRoot, "data", "ato_knowledge_base")); err != nil {
		return 0, err
	}
	report, err := skillgen.Generate(skillgen.Options{Root: workRoot, OutputRoot: workRoot, CheckedAt: opts.CheckedAt})
	if err != nil {
		return 0, err
	}
	return len(report.Sources), skillgen.CompareGeneratedArtifacts(root, workRoot)
}

func copyDir(src, dst string) error {
	info, err := os.Stat(src)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(dst, 0755); err != nil {
		return err
	}
	if !info.IsDir() {
		body, err := os.ReadFile(src)
		if err != nil {
			return err
		}
		return os.WriteFile(dst, body, 0644)
	}
	return filepath.WalkDir(src, func(path string, d os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		rel, relErr := filepath.Rel(src, path)
		if relErr != nil {
			return relErr
		}
		target := filepath.Join(dst, rel)
		if d.IsDir() {
			if rel == "." {
				return nil
			}
			return os.MkdirAll(target, 0755)
		}
		if err := os.MkdirAll(filepath.Dir(target), 0755); err != nil {
			return err
		}
		body, err := os.ReadFile(path)
		if err != nil {
			return err
		}
		return os.WriteFile(target, body, 0644)
	})
}

func refresh(root, topic string, all bool) (map[string]any, error) {
	if !all && topic == "" {
		return nil, fmt.Errorf("use --topic or --all")
	}
	var urls []string
	for _, t := range skillgen.Topics() {
		if !all && t.Slug != topic {
			continue
		}
		path := filepath.Join(root, "skills", t.Slug, "references", "sources.json")
		body, err := os.ReadFile(path)
		if err != nil {
			if all {
				continue
			}
			return nil, err
		}
		var sources []skillgen.Source
		if err := json.Unmarshal(body, &sources); err != nil {
			return nil, err
		}
		for _, src := range sources {
			if src.FinalURL != "" && skillgen.HostApproved(src.FinalURL) {
				urls = append(urls, src.FinalURL)
			}
		}
	}
	if len(urls) == 0 {
		return map[string]any{"refreshed": 0}, nil
	}
	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		return nil, err
	}
	selected, missing := atodata.SelectByURL(registry.Records, urls)
	results := make([]atodata.RefreshResult, 0, len(selected)+len(missing))
	for _, raw := range missing {
		results = append(results, atodata.RefreshResult{URL: raw, Error: "not in registry; run taxmate-australia-refresh --url or recrawl first"})
	}
	for _, rec := range selected {
		results = append(results, atodata.RefreshRecord(root, rec))
	}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		return nil, err
	}
	return map[string]any{"requested": len(urls), "matched": len(selected), "results": results}, nil
}

func exitJSON(value map[string]any, err error) {
	if err != nil {
		_ = json.NewEncoder(os.Stdout).Encode(map[string]any{"ok": false, "error": err.Error()})
		os.Exit(1)
	}
	value["ok"] = true
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(value)
}

func usage() {
	fmt.Fprintln(os.Stderr, strings.TrimSpace(`
usage:
  taxmate-australia-skills generate
    --checked-at <timestamp>
    --check
  taxmate-australia-skills refresh --topic gst-bas
  taxmate-australia-skills refresh --all
  taxmate-australia-skills audit
    --format markdown|json
    --output <path>
    --check
  taxmate-australia-skills validate
`))
}
