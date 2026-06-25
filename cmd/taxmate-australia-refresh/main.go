package main

import (
	"flag"
	"os"
	"path/filepath"

	"taxmate-au-skill/internal/atodata"
)

func main() {
	query := flag.String("query", "", "Refresh indexed pages matching a topic query.")
	all := flag.Bool("all", false, "Refresh all indexed pages.")
	recrawl := flag.Bool("recrawl", false, "Rebuild the scoped ATO source pack from seed URLs.")
	limit := flag.Int("limit", 12, "Max query matches to refresh.")
	maxPages := flag.Int("max-pages", 250, "Max pages for --recrawl.")
	var urls multiFlag
	flag.Var(&urls, "url", "Refresh explicit indexed ATO URL. Repeatable.")
	flag.Parse()

	root, err := commandRoot()
	if err != nil {
		atodata.Errorf("%v", err)
		os.Exit(1)
	}

	if *recrawl {
		registry, err := atodata.Recrawl(root, *maxPages)
		if err != nil {
			atodata.Errorf("%v", err)
			os.Exit(1)
		}
		_ = atodata.WriteJSON(map[string]any{
			"records":  len(registry.Records),
			"failures": len(registry.Failures),
			"registry": atodata.RegistryPath(root),
		})
		return
	}

	registry, err := atodata.LoadRegistry(root)
	if err != nil {
		atodata.Errorf("%v", err)
		os.Exit(1)
	}

	var selected []*atodata.SourceRecord
	var missing []string
	switch {
	case *all:
		selected = registry.Records
	case len(urls) > 0:
		selected, missing = atodata.SelectByURL(registry.Records, urls)
	case *query != "":
		selected = atodata.SelectByQuery(root, registry.Records, *query, *limit)
	default:
		atodata.Errorf("use --query, --url, --all, or --recrawl")
		os.Exit(2)
	}

	results := make([]atodata.RefreshResult, 0, len(selected)+len(missing))
	for _, rawURL := range missing {
		results = append(results, atodata.RefreshResult{URL: rawURL, Error: "not in source registry"})
	}
	changed := 0
	for _, rec := range selected {
		result := atodata.RefreshRecord(root, rec)
		if result.Changed {
			changed++
		}
		results = append(results, result)
	}
	if err := atodata.SaveRegistry(root, registry); err != nil {
		atodata.Errorf("%v", err)
		os.Exit(1)
	}
	_ = atodata.WriteJSON(map[string]any{
		"matched": len(selected),
		"changed": changed,
		"results": results,
	})
}

type multiFlag []string

func (m *multiFlag) String() string {
	return ""
}

func (m *multiFlag) Set(value string) error {
	*m = append(*m, value)
	return nil
}

func commandRoot() (string, error) {
	if cwd, err := os.Getwd(); err == nil {
		if _, statErr := os.Stat(filepath.Join(cwd, ".codex-plugin", "plugin.json")); statErr == nil {
			return cwd, nil
		}
	}
	return atodata.SkillRoot()
}
