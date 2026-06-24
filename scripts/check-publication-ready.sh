#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export GOCACHE="${GOCACHE:-$ROOT/.cache/go-build}"

fail() {
  echo "error: $*" >&2
  exit 1
}

[[ -f .codex-plugin/plugin.json ]] || fail "missing plugin manifest"
[[ -f README.md ]] || fail "missing README"
[[ -f DISCLAIMER.md ]] || fail "missing DISCLAIMER.md"
[[ -f LICENSE ]] || fail "missing LICENSE"
[[ -f SECURITY.md ]] || fail "missing SECURITY.md"
[[ -f CONTRIBUTING.md ]] || fail "missing CONTRIBUTING.md"
[[ -f docs/PUBLICATION_CHECKLIST.md ]] || fail "missing publication checklist"
[[ -f hooks.json ]] || fail "missing hooks.json"
[[ -f scripts/clean-source-cache.sh ]] || fail "missing source-cache cleaner"

if git ls-files 'bin/*' | grep -q .; then
  fail "built binaries are tracked"
fi

if git grep -nE 'public[-]work|taxmate-australia-public[-]work' -- . ':!data/ato_knowledge_base/raw/**' ':!data/ato_knowledge_base/text/**'; then
  fail "temporary staging name leaked"
fi

if git grep -nE '/Users/[[:alnum:]_.-]+|custom[_]apps/skills[_]and[_]plugins|Developer/custom[_]apps' -- README.md .codex-plugin agents skills docs; then
  fail "private machine path leaked into public docs"
fi

if git grep -nE 'taxmate-au($|[^s])|TaxMate AU($|[^s])|TAXMATE_AU_ROOT' -- README.md DISCLAIMER.md SECURITY.md CONTRIBUTING.md docs .github .codex-plugin .agents agents skills wrappers plugin.lock.json; then
  fail "legacy public identity leaked"
fi

git grep -Eq 'not (professional )?tax, legal, accounting, financial' -- README.md DISCLAIMER.md .codex-plugin skills || fail "missing professional-advice disclaimer"
git grep -q 'not affiliated with' -- README.md DISCLAIMER.md .codex-plugin skills || fail "missing affiliation disclaimer"
git grep -q 'does not lodge' -- DISCLAIMER.md || fail "missing lodgment disclaimer"
git grep -q 'Accountant review' -- DISCLAIMER.md skills || fail "missing accountant-review boundary"

if git grep -nE 'taxmate-australia-re[d]act|internal/pri[v]acy|cmd/taxmate-australia-re[d]act|RE[D]ACTED' -- . ':!data/ato_knowledge_base/raw/**' ':!data/ato_knowledge_base/text/**'; then
  fail "legacy file-sanitisation artifact found"
fi

go test ./...
mkdir -p bin
go build -o bin/taxmate-australia-refresh ./cmd/taxmate-australia-refresh
go build -o bin/taxmate-australia-skills ./cmd/taxmate-australia-skills
go build -o bin/taxmate-australia-validate ./cmd/taxmate-australia-validate
go build -o bin/taxmate-australia-finance ./cmd/taxmate-australia-finance
go build -o bin/taxmate-australia-calc ./cmd/taxmate-australia-calc
bin/taxmate-australia-skills validate >/tmp/taxmate-australia-skills-validate.json
bin/taxmate-australia-skills audit >/tmp/taxmate-australia-skills-audit.json
bin/taxmate-australia-validate >/tmp/taxmate-australia-validate.json
bash scripts/clean-source-cache.sh

echo "publication checks passed"
