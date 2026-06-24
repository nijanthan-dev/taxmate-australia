package main

import (
	"encoding/json"
	"flag"
	"fmt"
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
		_ = fs.Parse(os.Args[2:])
		report, err := skillgen.Generate(skillgen.Options{Root: root, CheckedAt: *checkedAt})
		sources := 0
		if report != nil {
			sources = len(report.Sources)
		}
		exitJSON(map[string]any{"generated": true, "sources": sources, "report": "data/ato_knowledge_base/migration_report.json"}, err)
	case "refresh":
		fs := flag.NewFlagSet("refresh", flag.ExitOnError)
		topic := fs.String("topic", "", "topic slug")
		all := fs.Bool("all", false, "refresh all generated source URLs")
		_ = fs.Parse(os.Args[2:])
		exitJSON(refresh(root, *topic, *all))
	case "audit":
		sourceMap, err := skillgen.LoadSourceMap(root)
		if err == nil {
			err = skillgen.WriteAuditReport(root, sourceMap)
		}
		exitJSON(map[string]any{"audit": "migration/SOURCE_TO_SKILL_REPORT.md"}, err)
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
	idx, err := atodata.LoadIndex(root)
	if err != nil {
		return nil, err
	}
	selected, missing := atodata.SelectByURL(idx.Records, urls)
	results := make([]atodata.RefreshResult, 0, len(selected)+len(missing))
	for _, raw := range missing {
		results = append(results, atodata.RefreshResult{URL: raw, Error: "not in index; run taxmate-australia-refresh --url or recrawl first"})
	}
	for _, rec := range selected {
		results = append(results, atodata.RefreshRecord(root, rec))
	}
	if err := atodata.SaveIndex(root, idx); err != nil {
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
  taxmate-australia-skills refresh --topic gst-bas
  taxmate-australia-skills refresh --all
  taxmate-australia-skills audit
  taxmate-australia-skills validate
`))
}
