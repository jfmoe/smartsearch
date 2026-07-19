---
name: smart-search-cli
description: "CLI-first web research and source retrieval through the local smart-search command. Use when the user needs current web search, X/Twitter search, source-backed fact checking, URL fetching, site mapping, official/API/documentation search, deep research, or reproducible search evidence via Skill + CLI instead of MCP tools or native web search."
---

# Smart Search CLI

Use the local `smart-search` command as the default execution layer for web research. This entrypoint keeps only routing, boundaries, and reference selection; load the focused reference file when command details or provider contracts matter.

## Task Router

Select the first branch whose condition matches the user's task. Load only the context named in that branch unless the result sends you to another branch.

### 1. Research or retrieval

**Choose this branch when:** the user wants web research, current information, X/Twitter search, documentation, a known URL fetched, or Deep Research, and no Smart Search failure is currently blocking the work.

1. Select the required capability before selecting a provider: broad or current discovery, documentation search, known-URL fetch, experimental vertical search, or Deep Research orchestration. Read `references/provider-routing.md` for capability boundaries.
2. Run the matching `smart-search` command. Read `references/command-patterns.md` for evidence-oriented commands and timeout recovery, `references/deep-research-mode.md` only for an explicit deep/multi-source request, and `references/cli-core.md` only when exact syntax or output fields matter.

**Completion criterion:** the CLI returns the requested output successfully, and any claim-level evidence required by the request comes from fetched page content rather than discovery candidates alone.

### 2. Diagnose or configure

**Choose this branch when:** `smart-search` is unavailable, a command fails, configuration is uncertain, or a required capability is missing.

1. Run `smart-search doctor --format json` and follow its reported error instead of switching research tools.
2. Use `smart-search setup` or `smart-search config set KEY VALUE` when configuration is missing and the user supplies the required value. If OpenAI-compatible search still hangs or times out after `doctor` succeeds, run `smart-search diagnose openai-compatible --format markdown`. Read `references/setup-config.md` for setup, storage, and diagnostic details.

**Completion criterion:** `doctor` returns `ok: true` and the blocked command succeeds; if recovery is not possible, explicitly report the observed failure, the missing or unhealthy capability, and the next recovery command.

### 3. Update an installed Skill

**Choose this branch when:** the user explicitly asks to refresh or synchronize installed Smart Search Skills and `smart-search skills status --format json` reports a saved path as `stale`.

1. Run the read-only `smart-search skills status --format json` check to record saved containers and stale files.
2. Run `smart-search skills update --format json`, then rerun status. Read `references/setup-config.md` for saved preference management and the update boundary; this path must not rerun provider setup or delete extra user files.

**Completion criterion:** each saved path reports `up_to_date` or `extra_files` after the update, or the update failure and path are reported explicitly.

### 4. Validate architecture changes

**Choose this branch when:** the task changes CLI or provider architecture, routing, fallback, configuration, packaging, or release behavior.

1. Read `references/provider-routing.md` for capability and fallback invariants, `references/intent-routing-capabilities.md` when changing routing capability definitions, and `references/regression-release.md` for the distributable smoke/release gate.
2. From a source checkout, run `python scripts/sync-skill.py --check`, `smart-search regression`, and `smart-search smoke --mock --format json`. Add live checks only when real keys are available and the user expects them.

**Completion criterion:** the mirror check and source regression exit successfully, mock smoke returns `ok: true` with no failed cases, and any failure is reported with its command and observed result.

## Cross-branch invariants

- **CLI-first:** use the local `smart-search` CLI for this workflow and never silently switch to a native or unrelated web-search route.
- **Capability-safe fallback:** fallback may try only another provider in the same capability; never substitute a docs, broad-search, or page-fetch provider across capability boundaries. Keep AnySearch Domain Discovery, explicit domain search, Batch Discovery, and AnySearch Extraction as explicit Provider Acceptance Operations; only domain-less Vertical Discovery may participate in `vertical_search`, and none is Web Search/Web Fetch or a standard-profile requirement. Automatic Domain Search is not implemented. Explicit operations may try anonymously, but `ANYSEARCH_API_KEY` alone marks AnySearch configured and enables automatic Vertical Discovery. Default `search` requires successful main search, `balanced`/`strict` validation, routed vertical intent, an AnySearch-allowing provider filter, and the key; `research` reuses the domain-less call when its balanced intent route selects `vertical_search` and configured AnySearch is available, without a provider-filter flag or main-search gate. `--extra-sources 0` affects only Tavily/Firecrawl in `search`; Batch Discovery and AnySearch Extraction are never automatic. Only normalized HTTP(S) results become `extra_sources`; keep URL-less structured provider output in `vertical_discovery`, never as source/evidence. AnySearch search/batch descriptions are capped at 300 characters without `content`, `raw_content`, or `raw_result`; extraction returns one `content` copy, and full discovered pages are read with `fetch`. Focused local intent regressions cover academic, gaming guides, and travel itineraries.
- **Fetched evidence for consequential claims:** for high-risk or time-sensitive facts, fetch the key pages before making claim-level statements and summarize only what the fetched text supports.
- **Safe, explicit failures:** never put API keys in output, logs, evidence, or errors; mask secrets and explicitly report every failed command with actionable recovery guidance.
