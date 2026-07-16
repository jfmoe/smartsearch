# Regression And Release

## Table of Contents

- Regression
- Smoke matrix
- Release lanes
- Release closeout lessons

## Regression

Run `smart-search regression` before considering CLI or skill changes complete.

- In a source checkout, it runs offline pytest coverage for CLI, service, smoke, provider, and skill contract behavior.
- In npm / mise packaged installs, repository test files are not bundled; since v0.1.8 it falls back to built-in mock smoke regression so users can still verify installed CLI health.
- For release validation, use a source checkout for full pytest-backed regression and use packaged-install regression only as an install-health check.
- Provider architecture changes must be verified as distributable CLI behavior, not as behavior that only works because one developer machine has a specific wrapper, shell profile, or local config file.
- After provider-routing changes, run source-checkout regression plus `smart-search smoke --mock --format json`. If live keys were used, run a targeted secret scan for exact key substrings before committing.

## Smoke Matrix

- Deep Research smoke coverage is mock-full plus live-limited.
- Mock-full coverage should cover trigger phrases, normal search requests that should not trigger Deep Research, required `research_plan` fields, allowed tool whitelist, `fetch_before_claim`, evidence paths, capability boundaries, `intent_signals`, `capability_plan`, `gap_check`, simple current prompts such as `深度搜索一下最近的比特币行情`, docs/API prompts, claim-verification prompts, user-provided URL fetch-first flows, missing-provider failure guidance, research provider advantage routing, same-capability research fallback, and the rule that fixed topic recipe ids are not required schema.
- Live-limited coverage should run `doctor`, one broad `search`, one `exa-search`, and one `fetch` when real keys are available and live checks are expected; when Context7 is configured, its smoke is only one `resolve-library-id` health check, not a full resolve/query-docs E2E. Add one small `research` smoke when configured keys make it stable.
- If a smoke issue is found, fix the affected docs/code/tests and rerun the affected smoke until it passes or is proven to be an external provider blocker.

## Release Lanes

- The personal release line starts at `@jfmoe/smart-search@0.2.0`. Node is the only promised JavaScript launcher and macOS is the only formally supported platform.
- A normal `main` push runs tests only. It has no publish permission and must never publish an npm preview.
- Preview releases are manual `workflow_dispatch` jobs. They accept only a full 40-character commit SHA, require a prerelease of the checked-out package version, and publish only with dist-tag `next`.
- Stable releases are exact `vX.Y.Z` tags. The workflow validates that tag version against npm metadata, Python metadata, lockfile metadata, and `npm version` before publishing npm `latest`.
- Stable GitHub release notes are stored as `.github/releases/vX.Y.Z.md`. npm versions and release tags are immutable: do not overwrite a package version or move a released tag.

## Release Closeout Lessons

- Run `npm test` before a release. It verifies the public Skill mirror, release identity allowlist, metadata consistency, workflow policy, wrapper repair behavior, and `npm pack --dry-run` content.
- Read registry facts without exposing credentials: `npm view @jfmoe/smart-search versions --json` and `npm view @jfmoe/smart-search dist-tags --json`.
- The read-only upstream baseline is recorded in `docs/release/upstream-baseline.md`; update it only in a separately reviewed upstream sync PR.
- Do not run `npm publish`, create a tag, create a GitHub Release, or dispatch the publish workflow without the dedicated release approval.
