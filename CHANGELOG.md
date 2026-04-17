# Changelog

## v0.2.0 - 2026-04-17

Focused release for PR usability and source-level diagnostics.

### Added

- YAML extraction now captures best-effort `source.file` and `source.line` diagnostics for semantic models, entities, dimensions, and metrics
- Change records now carry source diagnostics through diffing and JSON output
- Markdown and text reports now append `file:line` context when available
- Added `semguard comment-pr` for sticky GitHub PR comment publishing
- Composite action can now publish or update a sticky PR comment with `pr-comment: true`

### Changed

- README and action examples now target `v0.2.0`
- Release coverage now explicitly documents diagnostics and PR comment support

## v0.1.1 - 2026-04-17

Marketplace packaging follow-up release.

### Fixed

- Composite action now installs from `github.action_path` instead of the caller workspace
- Added Marketplace branding metadata to `action.yml`
- Replaced local `uses: ./` consumer guidance with the published action ref
- Replaced broken Windows absolute README links with repo-relative links

## v0.1.0 - 2026-04-17

Initial public release.

### Added

- CLI commands for `extract`, `diff`, and `check`
- Latest-spec YAML extraction for semantic models, model-local metrics, and top-level advanced metrics
- Explicit manifest ingestion path normalized into the same semantic contract
- Deterministic semantic diffing with `breaking`, `risky`, and `safe` classifications
- Text, Markdown, and JSON reporting
- Checkout-free git ref comparison for YAML-based diffs
- Composite GitHub Action that writes a workflow summary, uploads a JSON artifact, and enforces a severity threshold
- Example dbt project, docs, and automated tests

### Current limits

- Manifest support targets a narrow explicit artifact shape in `v0.1`
- No legacy Semantic Layer YAML support yet
- No rename inference or migration metadata
- No PR comment orchestration yet
