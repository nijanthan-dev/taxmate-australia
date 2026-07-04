---
name: taxmate-release-closeout
description: Execute TaxMate Australia repo PR closeout, review hardening, and release delivery. Use when fixing or merging TaxMate Australia GitHub PRs, handling @Codex review comments, encoding repeated review lessons into guardrails/tests, running Gitleaks gates, merging Release Please PRs, verifying published tags/releases, or cleaning TaxMate worktrees/branches after release.
---

# TaxMate Release Closeout

Use this only for the `nijanthan-dev/taxmate-australia` repo. Prefer `gh` for GitHub. Recheck live state before acting; memories are hints, not truth.

## Preflight

1. Confirm repo, remote, current branch, and worktree state.
2. If work starts from `main`, create a fresh `fix/`, `feat/`, or `chore/` branch or worktree from current `origin/main`.
3. Recheck issue/PR head SHA, mergeability, checks, latest reviews, and unresolved review threads.
4. Never merge on eyes/ack reactions. Wait for a latest-head review body or explicit user go-ahead.
5. If GitHub auth lacks scope, report the missing scope and stop. Do not run `gh auth refresh` unless asked in the current turn.

## Fix PR Review Comments

1. Patch all current-head review comments, not only the easiest one.
2. If feedback repeats or points to a contract class, update `scripts/taxmate_review_guardrails.py` and focused tests before the one-off code fix.
3. Audit the same bug class across flat, nested, itemized, generated, and rendered paths before re-requesting review.
4. For generated skill/doc output, patch `scripts/skillgen.py` or the source file first; do not hand-edit generated `skills/*/SKILL.md` unless the generator owns no path.
5. Run focused tests for the touched area, then the repo's relevant validation path.
6. Reply to each review thread with the fix and resolve it.
7. Push and recheck current-head checks, reviews, and threads.
8. If `@Codex` only adds eyes, keep polling for the review body. Do not request review again unless asked.

## Validation Gates

Run the strongest relevant local checks before merge. Common TaxMate checks include:

```bash
./scripts/taxmate validate
./scripts/check-publication-ready.sh
gitleaks dir . --redact
```

Also scan history and PR diff before merge. If a secret reached remote Git, stop and remove it from branch history before merge.

For ATO fetch/runtime changes, preserve `curl --disable -L` ordering and verify status, final URL, and body handling through tests.

For release/version changes, inspect `.release-please-manifest.json`, `.codex-plugin/plugin.json`, `skill.json`, `plugin.lock.json`, `CHANGELOG.md`, and Release Please config as applicable.

## Merge And Release

1. Squash-merge the fix PR only after live review/check/leak gates pass.
2. Verify issue closure and updated `main` state.
3. Wait for Release Please to open the next release PR when the fix should ship.
4. Inspect release PR version bumps and changelog; request/poll latest-head review there too when review flow is in use.
5. Merge the release PR with squash merge.
6. Verify tag, GitHub release, version artifacts, and any relevant main CI.
7. Fast-forward local `main` if safe.
8. Clean merged temp branches/worktrees only after verifying no user changes would be lost. Preserve unrelated untracked paths.

## Stop Conditions

Stop and report plainly when:

- Missing GitHub scope blocks required action.
- Latest-head review is absent and user did not give explicit go-ahead.
- Any Gitleaks gate finds a real secret.
- Release Please fails because required repo secret/config is missing.
- Cleanup would delete user work or an active worktree.
