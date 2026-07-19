# smart-search

[简体中文](README.zh-CN.md) | English

CLI-first, skill-driven web research for AI agents and terminal users. `smart-search` gives AI tools one reproducible command layer for live search, source discovery, page fetching, site mapping, provider diagnostics, offline Deep Research planning, and live Deep Research execution.

<p>
  <a href="https://www.npmjs.com/package/@jfmoe/smart-search">
    <img src="https://img.shields.io/npm/v/@jfmoe/smart-search?label=npm%20latest" alt="npm latest">
  </a>
</p>

![Star History Chart](https://api.star-history.com/svg?repos=jfmoe/smartsearch&type=Date)

## What It Is

`smart-search` is not an MCP server. It is a normal CLI that AI agents can call through a skill:

```powershell
smart-search search "latest OpenAI Responses API changes" --capabilities docs_search,web_search --format json
smart-search fetch "https://example.com/article" --format markdown
smart-search deep "Compare Responses API web_search with Chat Completions search" --format json
smart-search research "Compare Responses API web_search with Chat Completions search" --format markdown
```

The current architecture has two layers:

| Layer | Responsibility |
| --- | --- |
| CLI executor | Runs deterministic commands, provider routing, fallback, JSON/Markdown output, local config, smoke/regression checks |
| Skill / AI orchestration | Infers user intent, chooses normal search vs Deep Research, executes planned CLI steps, writes final source-backed answers |

Default `smart-search search` stays fast and live. `smart-search deep` is the explicit offline Deep Research planner. It does not call providers, run `doctor`, or fetch pages by default; it emits a `research_plan` that an AI agent or user can execute step by step. `smart-search research` is the live Deep Research executor: it uses the same planner shape, then runs discovery, fetch/read, gap check, and evidence-only synthesis.

Agent-authored ordinary searches pass the complete caller capability declaration in their first `search` call: use a catalog-ordered CSV such as `docs_search,web_search`, or exactly `none` for an empty set. A declaration is authoritative: Smart Search does not add capabilities from query rules, known URLs, strict validation, embeddings, or the classifier. They do not need a `route` preflight. Any caller may omit `--capabilities` to retain hybrid routing, while `research` keeps its separate evidence workflow and does not accept this option.

Intent routing now has its own layer. Instead of letting a model pick providers directly, Smart Search first decides which capabilities are needed, then the existing capability-first provider registry chooses same-capability fallback:

```text
user query
 -> with --capabilities: authoritative caller capability set
 -> without --capabilities: rules, optional embeddings, optional classifier
 -> required_capabilities
 -> provider fallback inside docs_search / web_search / web_fetch / vertical_search
```

`smart-search route "query"` explains this decision without calling search, docs, fetch, or provider APIs. `smart-search deep` keeps the offline planner contract and uses local/rules signals only.

## Install

Stable channel:

```powershell
npm install -g @jfmoe/smart-search@latest
smart-search --version
smart-search setup
```

Test channel:

```powershell
npm install -g @jfmoe/smart-search@next
smart-search --version
```

The npm package creates an isolated Python runtime during install. Package installation does not write Skill Containers;
you still use the single `smart-search` command. Synchronization happens on the first ordinary CLI invocation after a version change,
not during npm or another package-manager install.

Prerequisites:

- Node.js 18 or newer with npm.
- Python 3.10 or newer available as `python3`.
- 0.2.0 formally supports macOS only. Other platforms may run some checks but are not a support commitment.

## Quick Start

1. Configure providers:

```powershell
smart-search setup
smart-search doctor --format json
```

2. If OpenAI-compatible `search` hangs or times out, generate the short troubleshooting report:

```powershell
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
```

3. Run a normal live search:

```powershell
smart-search search "today's important AI news" --capabilities web_search --validation balanced --extra-sources 2 --format json
```

4. Inspect intent routing without running providers:

```powershell
smart-search route "React useEffect API docs" --format markdown
smart-search route "请核验这个链接里的说法 https://example.com/source" --format json
```

5. Fetch exact page evidence:

```powershell
smart-search fetch "https://example.com/source" --format markdown --output evidence.md
```

6. Plan Deep Research:

```powershell
smart-search deep "Deep research recent Bitcoin market movement" --budget standard --format json
```

7. Run live Deep Research when you want the CLI to execute the staged workflow:

```powershell
smart-search research "Deep research recent Bitcoin market movement" --budget deep --format markdown
```

8. Install the Skill and save its complete set of Skill Containers:

```powershell
smart-search skills install
smart-search skills install agents claude hermes "C:\Users\me\.other-tool\skills"
```

With no arguments, installation selects only the Agents Skill Target (`~/.agents/skills`). Interactive `smart-search setup`
uses the same default and accepts `agents`, `claude`, `hermes`, and custom Skill Containers in its final Skill prompt.
Use `--skip-skills` to make interactive setup perform no Skill writes and preserve the existing preference. Non-interactive setup never changes Skill preferences.
The only built-in names are
`agents`, `claude`, and `hermes`; every other positional argument is a custom Skill Container. Smart Search appends the
`smart-search-cli` child directory, saves normalized container paths in `config.json`, and leaves provider configuration intact.

9. Inspect or manually repair synchronized Skills:

```powershell
smart-search skills status --format json
smart-search skills update --format json
smart-search skills clear --format json
```

`skills status` and `skills update` operate only on the saved Skill Installation Preference. `skills clear` disables future
management by saving an empty path set without uninstalling files. Updates overwrite bundled managed files but preserve
user-added and obsolete extra files. Outside the explicit interactive Skill prompt, provider setup does not change Skill preferences.

Automatic Skill Sync compares the exact CLI version string with the last fully synchronized version before the first ordinary command.
Any mismatch—including an upgrade, downgrade, or release-channel switch—synchronizes every saved container; an exact match is a no-op.
Successful background work is silent, so JSON/content stdout stays unchanged. A partial write or bounded lock timeout leaves synchronization pending,
prints concise repair guidance to standard error, and never changes the requested command's stdout or exit code. Run
`smart-search skills update --format json` to repair. Help, version, setup, and all `skills` management commands skip background synchronization.
If no structured preference exists, the first ordinary command initializes only the Agents Skill Target; legacy directories are not scanned or migrated.

## Current Architecture

| Capability | Main commands | Providers | Role |
| --- | --- | --- | --- |
| `main_search` | `search` | xAI Responses, OpenAI-compatible Chat Completions | Broad answer generation and synthesis |
| `docs_search` | `context7-library`, `context7-docs`, `exa-search` | Context7, Exa | Official docs, SDKs, APIs, framework/library evidence |
| `web_search` | `zhipu-search`, `zhipu-mcp-search`, intent-routed reinforcement inside `search` | Zhipu Web Search API, Zhipu Coding Plan MCP, Tavily, Firecrawl | Chinese, domestic, current, domain-filtered, or supplementary web discovery |
| `web_fetch` | `fetch`, `zhipu-mcp-reader` | Tavily, Jina Reader, Zhipu Coding Plan MCP Reader, Firecrawl | Exact URL content extraction for evidence |
| `vertical_search` | intent-routed domain-less `anysearch-search` | AnySearch (experimental) | Vertical Discovery for explicit vertical intent; never a Web Search fallback |
| AnySearch Acceptance Surface | `anysearch-domains`, `anysearch-search`, `anysearch-extract`, `anysearch-batch` | AnySearch (experimental) | Explicit Domain Discovery, Vertical Discovery/domain search, Batch Discovery, and AnySearch Extraction acceptance |
| `site_map` | `map` | Tavily | Site/documentation structure discovery |
| `deep_planner` | `deep` / `dr` | Local planner only | Offline plan generation; no provider call by default |
| `research_executor` | `research` / `rs` | Registered providers by capability | Live staged research: plan, discover, fetch/read, gap check, evidence-only synthesis |

Fallback is same-capability only:

| Capability | Fallback chain |
| --- | --- |
| `main_search` | xAI Responses -> OpenAI-compatible |
| `docs_search` | Context7 for library/API/docs intent; Exa for official domains, papers, product pages, and trusted-site discovery |
| `web_search` | Zhipu Web Search API -> Zhipu Coding Plan MCP `web_search_prime` -> Tavily -> Firecrawl |
| `web_fetch` | Tavily -> Jina Reader with `JINA_API_KEY` -> Zhipu Coding Plan MCP `webReader` -> Firecrawl |

AnySearch is intentionally not part of the `web_search` fallback chain and is not required by the `standard` minimum profile. Only domain-less Vertical Discovery belongs to the `vertical_search` Capability Seam. Domain Discovery, Batch Discovery, and AnySearch Extraction remain provider acceptance operations; extraction is not Web Fetch. Use the explicit commands for acceptance and boundary testing before promoting any vertical domain into a future route.

Default `search` runs automatic Vertical Discovery only after the main search succeeds, validation is `balanced` or `strict`, the local router identifies vertical intent, the provider filter allows AnySearch, and `ANYSEARCH_API_KEY` is configured. `research` reuses the same domain-less semantics when its balanced intent route selects `vertical_search` and configured AnySearch is available; it has no separate provider-filter flag or main-search gate. The key therefore means both Configured AnySearch and permission for either automatic path; without it, only explicit AnySearch Acceptance Surface commands may try anonymously. Automatic calls always use domain-less `search`: Smart Search does not select a domain/sub-domain or construct Sub-domain Parameters. `--extra-sources 0` disables only Tavily/Firecrawl horizontal extras in `search` and does not disable an otherwise eligible Vertical Discovery call.

Only normalized HTTP(S) candidates from Vertical Discovery enter `extra_sources`. AnySearch search and batch descriptions are capped at 300 characters; search, batch, discovery, and automatic Vertical Discovery omit duplicate `content`, `raw_content`, and `raw_result`. Extraction returns one `content` copy. Fetch a discovered URL with `smart-search fetch URL` when an agent needs the full page. URL-less structured responses remain compact provider results under `vertical_discovery` and are never presented as a source, citation, or evidence. Provider failures remain observable through `vertical_discovery` and `provider_attempts` (`operation`, upstream `tool`, and error category) without changing a successful main result. Domain-less responses do not claim or verify a domain. The focused local regression intents include academic, gaming-guide, and travel-itinerary queries; ordinary mentions of games or metaphorical travel do not match.

Jina Reader is a `web_fetch` provider only. `JINA_API_KEY` is required before Jina satisfies `SMART_SEARCH_MINIMUM_PROFILE=standard`; anonymous `r.jina.ai` behavior is treated as explicit/experimental fetch behavior and must not weaken fail-closed setup checks.

The CLI exposes observability fields such as `routing_decision`, `provider_attempts`, `providers_used`, `fallback_used`, `primary_sources`, `extra_sources`, `vertical_discovery`, and `source_warning`.

`routing_decision` keeps backward-compatible booleans such as `docs_intent`, `zh_current_intent`, `web_current_intent`, `fetch_intent`, and `supplemental_paths`, and also includes the unified router fields: `intent_router_mode`, `required_capabilities`, `intent_signals`, `confidence`, `router_engines_used`, and `degraded_reason`.

`extra_sources` are discovery candidates. For high-risk claims, news, policy, finance, health, selection decisions, and serious reviews, fetch key pages first and cite fetched text rather than treating a broad search answer as proof.

Routing rule of thumb: start with `search` for broad discovery and synthesis; use `research` when you want the CLI to execute the deeper evidence workflow; use Zhipu Web Search API for Chinese, domestic, policy, announcements, and current-news searches; use Zhipu Coding Plan MCP only when you explicitly want the Coding Plan quota route; use Context7 first for library/API/framework docs; use Exa for official domains, papers, product pages, trusted sites, and low-noise discovery; use Tavily/Firecrawl through `search --extra-sources` for horizontal candidates and through `fetch` for page evidence; use Jina for known-URL extraction; use AnySearch only when you explicitly need experimental vertical-domain search.

## Deep Research

Use normal search when you want a fast answer:

```powershell
smart-search search "React useEffect cleanup docs" --format json
```

Use offline Deep Research planning when you want decomposition before execution:

```powershell
smart-search deep "OpenAI Responses API web_search vs Chat Completions search: which should I use?" --budget deep --format json
smart-search dr "https://example.com/source" --format json
```

Planner output includes:

- `mode="deep_research"` and `query_mode="deep"`;
- `intent_signals`, such as recency, docs/API intent, known URL, claim risk, source authority, and cross-validation need;
- `decomposition`, with 1-6 subquestions depending on budget and difficulty;
- `capability_plan`, choosing from existing CLI blocks;
- `steps[]`, each with `tool`, `purpose`, `command`, `output_path`, and `subquestion_id`;
- `evidence_policy="fetch_before_claim"`;
- `gap_check`, which fetches missing evidence or downgrades unsupported claims.
- `usage_boundary`, which explains that `search` is live, `deep` is offline planning, and execution happens through planned commands.

Deep Research is not a fixed topic recipe system. Market research, product comparison, technical docs, news or policy, claim verification, and URL-first prompts are examples of user language, not required schema enums.

Allowed planned tools are:

```text
search, exa-search, exa-similar, zhipu-search, context7-library, context7-docs, fetch, map
```

`doctor` is preflight, not a research step. `smart-search deep` itself is offline; live research starts when an agent or user executes `steps[].command`.

Use live Deep Research execution when you want the CLI to run the staged workflow:

```powershell
smart-search research "OpenAI Responses API web_search vs Chat Completions search: which should I use?" --budget deep --fallback auto --format json
smart-search rs "https://example.com/source" --fallback off --format markdown
```

`research` runs plan -> discover -> fetch/read -> gap check -> evidence-only synthesis. It defaults to `--fallback auto`, which permits same-capability fallback even when a normal `search` configuration is conservative. `--fallback off` tries only the first provider selected inside each capability, which is useful for debugging provider behavior.

Research JSON includes `final_answer`, `citations`, `evidence_items`, `gap_check`, `provider_attempts`, `fallback_used`, `degraded`, `route_policy_version`, and `evidence_dir`. Discovery snippets are candidates only; citations are produced only from fetched/read evidence. If fallback cannot close a gap, `research` finishes degraded and lists unsupported gaps instead of inventing evidence.

The research router is capability-first plus provider-advantage:

- Context7 first for library/API/framework docs, with Exa as official-domain, paper, product, or trusted low-noise discovery.
- Zhipu Web Search API first for Chinese, domestic, current, policy, and announcement searches.
- Zhipu Coding Plan MCP remains a separate quota route through `web_search_prime` and `webReader`.
- Jina is favored for known public URLs, PDFs, and arXiv extraction; ReaderLM-v2 still requires `JINA_API_KEY`.
- Firecrawl is favored for JS-heavy, dynamic, browser-like, OCR/PDF, or robust fallback extraction.
- AnySearch participates only when vertical intent is clear, including the focused academic, gaming-guide, and travel-itinerary regression rules as well as existing CVE, finance, legal, or codebase/repository signals. It always performs domain-less Vertical Discovery; upstream chooses its internal data source.

Advanced routing overrides are available through `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` and `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS`. They can reorder or disable registered providers inside their supported capability, but they cannot move a provider across capability boundaries.

Good user-facing smoke prompts:

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json
smart-search deep "OpenAI Responses API web_search 和 Chat Completions 联网搜索怎么选" --budget deep --format json
smart-search deep "帮我核验这个说法是真是假：某某工具已经完全替代 Tavily 做 AI 搜索了" --format json
smart-search deep "https://example.com/source" --format json
```

## Provider And API Key Guide

Use `smart-search setup` for normal configuration. Environment variables remain supported for CI and advanced users.
The default interactive setup wizard includes optional smart intent router prompts, so embeddings and classifier routing can be configured without `--advanced`.

| Provider / route | Used for | Main config keys | Official docs | Key / dashboard |
| --- | --- | --- | --- | --- |
| xAI Responses API | Primary live search with `web_search,x_search` tools | `XAI_API_KEY`, `XAI_API_URL`, `XAI_MODEL`, `XAI_TOOLS` | [docs.x.ai](https://docs.x.ai/docs) | [xAI API keys](https://console.x.ai/team/default/api-keys) |
| OpenAI-compatible Chat Completions | Primary search through OpenAI or a compatible relay; no xAI search tools are sent here | `OPENAI_COMPATIBLE_API_URL`, `OPENAI_COMPATIBLE_API_KEY`, `OPENAI_COMPATIBLE_MODEL`, `OPENAI_COMPATIBLE_FALLBACK_MODELS`, `OPENAI_COMPATIBLE_STREAM` | [OpenAI platform docs](https://platform.openai.com/docs) | [OpenAI API keys](https://platform.openai.com/api-keys) or your relay provider |
| Exa | Low-noise official docs, API, paper, product, trusted-page discovery | `EXA_API_KEY`, optional `EXA_API_KEYS` | [Exa docs](https://docs.exa.ai/) | [Exa API keys](https://dashboard.exa.ai/api-keys) |
| Context7 Remote MCP | SDK, library, framework, and API documentation fallback | `CONTEXT7_API_KEY`, optional `CONTEXT7_API_KEYS`, `CONTEXT7_MCP_API_URL` (default `https://mcp.context7.com/mcp`) | [Context7 docs](https://context7.com/docs) | [Context7](https://context7.com/) |
| Zhipu Web Search API | Chinese, domestic, current, or domain-filtered web discovery | `ZHIPU_API_KEY`, `ZHIPU_API_URL`, `ZHIPU_SEARCH_ENGINE` | [Zhipu web search docs](https://docs.bigmodel.cn/cn/guide/tools/web-search) | [Zhipu API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Zhipu Coding Plan Remote MCP | Coding Plan quota web search, page reading, and open-source repo discovery | `ZHIPU_MCP_API_KEY`, `ZHIPU_MCP_SEARCH_API_URL`, `ZHIPU_MCP_READER_API_URL`, `ZHIPU_MCP_ZREAD_API_URL` | [search MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/search-mcp-server), [reader MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/reader-mcp-server), [zread MCP](https://docs.bigmodel.cn/cn/coding-plan/mcp/zread-mcp-server) | [Zhipu API keys](https://open.bigmodel.cn/usercenter/apikeys) |
| Tavily | Extra web sources, URL fetch, and site map | `TAVILY_API_URL`, `TAVILY_API_KEY`, optional `TAVILY_API_KEYS` | [Tavily docs](https://docs.tavily.com/) | [Tavily app](https://app.tavily.com/home) |
| Jina Reader | Known URL page extraction for `web_fetch`; key required for standard minimum profile | `JINA_API_KEY`, optional `JINA_API_KEYS`, `JINA_READER_API_URL`, `JINA_RESPOND_WITH`, `JINA_TIMEOUT_SECONDS` | [Jina Reader](https://jina.ai/reader/) | [Jina AI](https://jina.ai/) |
| Firecrawl | Fetch fallback and supplementary web sources | `FIRECRAWL_API_URL`, `FIRECRAWL_API_KEY`, optional `FIRECRAWL_API_KEYS` | [Firecrawl docs](https://docs.firecrawl.dev/) | [Firecrawl API keys](https://www.firecrawl.dev/app/api-keys) |
| AnySearch | Experimental vertical search acceptance surface; not a default fallback | `ANYSEARCH_API_URL`, `ANYSEARCH_API_KEY`, optional `ANYSEARCH_API_KEYS`, `ANYSEARCH_TIMEOUT_SECONDS` | [AnySearch docs](https://www.anysearch.com/docs) | [AnySearch API keys](https://www.anysearch.com/console/api-keys) |

Intent router configuration:

| Key | Purpose |
| --- | --- |
| `SMART_SEARCH_INTENT_ROUTER` | `hybrid`, `rules`, or `off`; default `hybrid` |
| `INTENT_EMBEDDING_API_URL` | Optional OpenAI-compatible embeddings endpoint for semantic capability routing; recommended setup preset uses `https://api.siliconflow.cn/v1/embeddings` |
| `INTENT_EMBEDDING_API_KEY` | Optional embeddings API key; masked by `doctor` and config output |
| `INTENT_EMBEDDING_MODEL` | Embeddings model name; recommended setup preset uses `Qwen/Qwen3-Embedding-8B` |
| `INTENT_EMBEDDING_THRESHOLD` | Semantic route threshold, default `0.74`; recommended 8B setup value `0.475`; model-specific |
| `INTENT_EMBEDDING_MARGIN` | Required top-vs-second semantic margin, default `0.05`; recommended 8B setup value `0.053`; ambiguous matches remain signals only |
| `INTENT_CLASSIFIER_API_URL` | Optional OpenAI-compatible chat-completions endpoint for structured intent classification |
| `INTENT_CLASSIFIER_API_KEY` | Optional classifier API key; masked by `doctor` and config output |
| `INTENT_CLASSIFIER_MODEL` | Classifier model name |
| `INTENT_ROUTER_TIMEOUT_SECONDS` | Timeout for optional remote router calls, default `8` |

Default `hybrid` is fail-open: if embeddings or classifier settings are missing or fail, routing records `degraded_reason` and falls back to local rules. Semantic routing may add a capability only when the top similarity score is at least `INTENT_EMBEDDING_THRESHOLD` and the top-vs-second score gap is at least `INTENT_EMBEDDING_MARGIN`; otherwise it records an ambiguous signal without adding a capability. The classifier may add capabilities, but unknown capability names and provider names are ignored. Providers are still selected only by capability.

Context7 uses its Remote MCP endpoint only. `CONTEXT7_BASE_URL` is retired and never interpreted as an MCP endpoint. If it is the only Context7 endpoint setting, commands fail closed; set `CONTEXT7_MCP_API_URL` (or remove the retired setting to use the default) before retrying.

For normal setup, use the Qwen3-Embedding-8B preset: `INTENT_EMBEDDING_API_URL=https://api.siliconflow.cn/v1/embeddings`, `INTENT_EMBEDDING_MODEL=Qwen/Qwen3-Embedding-8B`, `INTENT_EMBEDDING_THRESHOLD=0.475`, and `INTENT_EMBEDDING_MARGIN=0.053`. `smart-search setup` automatically fills the 8B threshold/margin when the 8B model is selected and those values are not already configured.

Embedding cosine scores are model-specific. Keep `route-calibrate` for advanced re-checks: run it after changing `INTENT_EMBEDDING_MODEL`, changing embedding endpoints, or expanding the real query calibration set:

```powershell
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format markdown
```

Use the report's recommended `INTENT_EMBEDDING_THRESHOLD` and `INTENT_EMBEDDING_MARGIN` before judging routing quality. The primary calibration metric is semantic-only Macro-F1; full-route Macro-F1 is reported to verify rules/classifier fallback behavior.

Important boundaries:

- xAI official live search uses the Responses API `/responses` route through `XAI_*`. Compatible relays and gateways use Chat Completions `/chat/completions` through `OPENAI_COMPATIBLE_*`.
- `OPENAI_COMPATIBLE_STREAM=true` or `smart-search search --stream` sets `stream=true` only for OpenAI-compatible `search` and provider-side `fetch` calls. It is a relay compatibility switch for long requests and does not change xAI Responses behavior, URL description, or source ranking.
- Legacy `SMART_SEARCH_API_URL`, `SMART_SEARCH_API_KEY`, `SMART_SEARCH_API_MODE`, `SMART_SEARCH_MODEL`, and `SMART_SEARCH_XAI_TOOLS` are not supported config keys. Use `XAI_*` or `OPENAI_COMPATIBLE_*` explicitly.
- Do not force xAI `web_search` / `x_search` tools or legacy `search_parameters` into the OpenAI-compatible Chat Completions route.
- `zhipu-search` support is the Web Search API route, not Zhipu Chat Completions `tools=[web_search]`, not Search Agent, and not the MCP Server.
- Zhipu Coding Plan support is a separate Remote MCP route. `web_search_prime` maps to `web_search`, `webReader` maps to `web_fetch`, and zread tools map to explicit repo/docs discovery commands. It is not mixed into the existing `/paas/v4/web_search` Zhipu REST provider.
- Zhipu Coding Plan MCP requires its own Coding Plan entitlement. A normal `ZHIPU_API_KEY` for Web Search API does not prove `zhipu-mcp-search` or zread access. If `ZHIPU_MCP_API_KEY` is absent or unauthorized, Smart Search skips those MCP providers; the `standard` minimum profile and same-capability fallback still work through the configured REST/search/fetch providers.
- Jina Reader is not a general search provider. `JINA_API_KEY` or a non-empty `JINA_API_KEYS` pool is required for Jina to count toward `standard`; `JINA_RESPOND_WITH=readerlm-v2` also requires a configured Jina credential.
- **Provider Credential Pool** (Exa, Tavily, Jina, Firecrawl, Context7, AnySearch): set optional `*_API_KEYS` to a JSON array of credentials. Non-empty KEYS fully replaces the single `*_API_KEY` after empty-strip and dedupe. Runtime round-robins across the pool and rotates within a call only on rate-limit / explicit quota exhaustion. Manage whole arrays via `config set` or setup (JSON array input)—no add/remove key subcommands. Doctor shows pool count and masked tails only. xAI, OpenAI-compatible, Zhipu, Zhipu MCP, and intent-router keys remain single-credential.
- `ZHIPU_SEARCH_ENGINE` defaults to `search_std`. Supported official values include `search_std`, `search_pro`, `search_pro_sogou`, and `search_pro_quark`; custom values remain allowed for future services.
- `TAVILY_API_URL` affects Tavily only. It does not proxy Zhipu. For Tavily Hikari / pooled endpoints, use `https://<host>/api/tavily`; setup normalizes root-host or `/mcp` inputs to that REST base.
- `FIRECRAWL_API_URL` defaults to `https://api.firecrawl.dev/v2`.
- AnySearch uses JSON-RPC 2.0 `tools/call` at `https://api.anysearch.com/mcp` by default. `anysearch-domains DOMAIN` calls only `get_sub_domains`; it never probes `tools/list`, guesses aliases, or falls back to `list_domains`. Explicit Acceptance Surface commands may try anonymous access when no credential is configured; `ANYSEARCH_API_KEY` or non-empty `ANYSEARCH_API_KEYS` marks AnySearch configured for automatic Vertical Discovery. HTTP 200 responses with `result.isError=true` are provider errors, not successful evidence.
- `doctor` and `route` report intent router status, embedding model, threshold, margin, their config source, timeout, and degradation behavior. They do not expose router API keys.

Non-interactive setup example:

```powershell
smart-search setup --non-interactive `
  --xai-api-key "your-xai-key" `
  --xai-model "grok-4-fast" `
  --openai-compatible-api-url "https://api.openai.com/v1" `
  --openai-compatible-api-key "your-openai-or-relay-key" `
  --openai-compatible-model "gpt-4.1" `
  --openai-compatible-stream "false" `
  --validation-level "balanced" `
  --fallback-mode "auto" `
  --minimum-profile "standard" `
  --intent-router "hybrid" `
  --intent-embedding-api-url "https://api.siliconflow.cn/v1/embeddings" `
  --intent-embedding-api-key "your-siliconflow-key" `
  --intent-embedding-model "Qwen/Qwen3-Embedding-8B" `
  --intent-embedding-threshold "0.475" `
  --intent-embedding-margin "0.053" `
  --exa-key "your-exa-key" `
  --context7-key "your-context7-key" `
  --zhipu-key "your-zhipu-key" `
  --zhipu-api-url "https://open.bigmodel.cn/api" `
  --zhipu-search-engine "search_pro_sogou" `
  --zhipu-mcp-key "your-zhipu-coding-plan-key" `
  --jina-key "your-jina-key" `
  --tavily-api-url "https://api.tavily.com" `
  --tavily-key "your-tavily-key" `
  --firecrawl-api-url "https://api.firecrawl.dev/v2" `
  --firecrawl-key "your-firecrawl-key"
```

Minimum profile defaults to `standard`, requiring at least:

- one `main_search` provider: xAI Responses or OpenAI-compatible;
- one `docs_search` provider: Exa or Context7;
- one `web_fetch` provider: Tavily, Jina with `JINA_API_KEY`, Zhipu Coding Plan MCP Reader, or Firecrawl.

Missing required capabilities fail closed with a configuration error. Use `SMART_SEARCH_MINIMUM_PROFILE=off` only for local experiments.

Experimental AnySearch configuration is optional and does not satisfy or change the `standard` minimum profile:

```powershell
smart-search setup --non-interactive --anysearch-api-url "https://api.anysearch.com/mcp" --anysearch-key "your-anysearch-key"
smart-search anysearch-domains security --format json
smart-search anysearch-search "latest travel ideas" --max-results 3 --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --sub-domain-params '{"type":"cve","value":"CVE-2024-3094"}' --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --format json
smart-search anysearch-batch "AAPL" "RAG papers" --max-results 2 --format json
```

`anysearch-search` without a domain is explicit Vertical Discovery. Domain search requires separate `--domain` and `--sub-domain` values plus at most one JSON object in `--sub-domain-params`; the object is nested unchanged under the upstream `sub_domain_params` field and output exposes only its keys. Dotted shorthand such as `security.cve`, legacy sub-domain aliases, incomplete pairs, invalid/non-object JSON, and reserved-field overrides fail locally with migration guidance. Smart Search validates required/type/enum only from a reliable, versioned Verified Domain Contract; live discovery schemas remain acceptance evidence. Without such a contract, `schema_validation.status=unavailable` is stable and the request is sent upstream without implicit discovery.

The versioned Verified Domain Manifest is the sole support authority. Its verified set is currently empty: `academic.search`, `security.vuln`, `finance.fundamental`, and `code.doc` remain discovered/unverified with explicit live and stability gaps. `doctor` exposes configured state, the automatic Vertical Discovery switch, independent operation-live status, verified domains, and candidate assessments. See [the first domain matrix](docs/anysearch-verified-domain-manifest.md); mock fixtures and one successful live call never promote a domain.

These terms are intentionally distinct: **Vertical Discovery** is the domain-less `vertical_search` capability call; **explicit domain search** is a user-specified `domain`/`sub_domain` Acceptance Surface call; **Provider Acceptance Operations** are Domain Discovery, explicit Vertical Discovery/domain search, Batch Discovery, and AnySearch Extraction; **Automatic Domain Search** is not implemented. Explicit operations may try anonymously without a key. `ANYSEARCH_API_KEY` alone controls both Configured AnySearch and automatic Vertical Discovery. `--extra-sources 0` does not disable that automatic call, while Batch Discovery and AnySearch Extraction are never automatic.

Static `capability_status.vertical_search` is offline and reports `configured`, `automatic_vertical_discovery`, `experimental`, manifest-backed `verified_domains`, and five `operation_live` entries. `doctor` leaves every operation `not_run`; it does not infer whole-provider availability from one `ok`. `smart-search smoke --mock` exercises the complete contract offline. `smart-search smoke --live` runs Domain Discovery, Vertical Discovery, Batch Discovery, AnySearch Extraction, and at least `academic.search` explicit domain search only when `ANYSEARCH_API_KEY` is explicitly present in the process environment; otherwise each is `not_run`. Endpoint and timeout still follow the documented environment → saved config → default priority. Set `ANYSEARCH_LIVE_ACCEPTANCE=academic.search,security.vuln` or `all` to select explicit candidate domains. Live output reports each operation and each selected domain as `passed`, `failed`, or `not_run`, with stable `operation`, upstream `tool`, and `error_type`; it never promotes the manifest.

Local config path:

- Windows default: `%LOCALAPPDATA%\smart-search\config.json`.
- Linux/macOS default: `~/.config/smart-search/config.json`.
- `SMART_SEARCH_CONFIG_DIR` is an advanced override for CI, containers, sandboxes, or portable installs.
- `SMART_SEARCH_RESEARCH_PREFERRED_PROVIDERS` and `SMART_SEARCH_RESEARCH_DISABLED_PROVIDERS` are advanced `research` routing overrides. They accept provider CSV values and can only reorder or disable providers inside existing capability boundaries.
- Earlier Windows source builds defaulted to `~\.config\smart-search\config.json`, while some installs were already pinned to `%LOCALAPPDATA%\smart-search` through `SMART_SEARCH_CONFIG_DIR`. If the new Windows default file is missing but the old home config exists, Smart Search reads the old file as `legacy_windows_home` so upgrades do not lose configuration. `doctor` reports the active path, default path, old home path, `SMART_SEARCH_CONFIG_DIR`, and whether that override merely matches the current default.

Provider timeouts:

- `TAVILY_TIMEOUT_SECONDS` controls the Tavily `doctor` connectivity check timeout and defaults to `30`.
- `ANYSEARCH_TIMEOUT_SECONDS` controls experimental AnySearch JSON-RPC calls and defaults to `30`.
- Raise it for slower Tavily Hikari / pooled / community endpoints before treating the provider as unhealthy.

## Search Result Journal

The Search Result Journal is an opt-in local diagnostic record of completed Default Search Invocations. It is disabled by default because records contain the full query, answer, source descriptions, and URLs. Enable it deliberately with environment variables or the generic config command; the usual environment → config file → default precedence applies:

```powershell
smart-search config set SMART_SEARCH_RESULT_JOURNAL_ENABLED true
smart-search config set SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS 30
```

`SMART_SEARCH_RESULT_JOURNAL_ENABLED` accepts the existing boolean spellings (`true`, `1`, or `yes`) and defaults to `false`. `SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS` accepts only non-negative integers, defaults to `30`, and uses `0` for permanent retention. The normal interactive setup does not expose this switch.

When enabled, each completed `search` or `s` invocation writes exactly one compact UTF-8 JSON line before rendering. The envelope contains `schema_version`, a UTC `recorded_at`, and the complete normalized terminal result, including primary and extra sources, routing decisions, provider attempts, fallback fields, counts, vertical discovery, timing, and structured failures or CLI timeouts. Provider acceptance commands, `fetch`, `map`, `route`, `doctor`, `deep`, `research`, `diagnose`, and `smoke` are excluded, as are interrupted or crashed processes that never produce a terminal result. Raw provider HTTP responses, request headers, intermediate payloads, and internal tool traces are not recorded.

Before persistence, values under credential-bearing keys and every occurrence of a non-empty configured credential are replaced with `[REDACTED]` in a copy. This does not alter stdout, `--output`, or the in-memory result. Redaction is intentionally limited to authentication credentials: queries, answers, URLs, source descriptions, and ordinary error messages remain complete and may still be sensitive.

Files use the resolved `SMART_SEARCH_LOG_DIR` and the local-date name `search_results_YYYYMMDD.jsonl`; `doctor` reports the enabled state, retention, resolved directory, and writable/ready status without creating a Journal file. Retention cleanup only removes expired regular files in that exact daily namespace. On POSIX-like platforms the directory is user-only and Journal/lock files are readable and writable only by the current user.

Writing is synchronous under a cross-process lock bounded to 0.5 seconds. The lock covers retention bookkeeping and one compact append; the file is flushed and closed without a per-record `fsync`. This adds one small local write to a completed search. With `--output`, the rendered artifact and the independent structured Journal record are intentionally both written. Any Journal failure emits one stderr warning but does not change the search output or exit code.

## Commands

| Command | Alias | Purpose |
| --- | --- | --- |
| `search` | `s` | Fast live search and broad synthesis |
| `route` | `rt` | Explain required capabilities without running providers |
| `deep` | `dr` | Offline Deep Research plan |
| `research` | `rs` | Live Deep Research execution |
| `fetch` | `f` | Fetch one URL as JSON, Markdown, or content |
| `map` | `m` | Map a website structure |
| `exa-search` | `exa`, `x` | Exa source discovery |
| `exa-similar` | `xs` | Similar pages from one URL |
| `zhipu-search` | `z`, `zp` | Zhipu Web Search API |
| `zhipu-mcp-search` | `zmcp-search` | Zhipu Coding Plan MCP `web_search_prime` |
| `zhipu-mcp-reader` | `zmcp-reader` | Zhipu Coding Plan MCP `webReader` |
| `zhipu-mcp-search-doc` | `zmcp-doc` | Search open-source repository docs through zread MCP |
| `zhipu-mcp-repo-structure` | `zmcp-tree` | Read repository structure through zread MCP |
| `zhipu-mcp-read-file` | `zmcp-file` | Read one repository file through zread MCP |
| `anysearch-domains` | `as-domains` | Domain Discovery for a required parent domain via `get_sub_domains` |
| `anysearch-search` | `as-search`, `as` | Vertical Discovery or explicit split domain/sub-domain search |
| `anysearch-extract` | `as-extract` | Explicit AnySearch Extraction; not Web Fetch |
| `anysearch-batch` | `as-batch` | Explicit Batch Discovery, up to 5 domain-less queries |
| `context7-library` | `c7`, `ctx7` | Resolve Context7 library candidates |
| `context7-docs` | `c7d`, `c7docs`, `ctx7-docs` | Fetch Context7 docs |
| `route-calibrate` | `route-cal`, `rcal` | Evaluate embedding router models and recommend threshold/margin |
| `doctor` | `d` | Masked config and connectivity check |
| `diagnose` | `diag` | Focused OpenAI-compatible troubleshooting report |
| `setup` | `init` | Interactive or scripted setup |
| `skills` | `skill` | Install, inspect, update, or clear saved Skill Containers |
| `config` | `cfg` | Local config read/write |
| `model` | `mdl` | Show explicit provider model settings; use `config set XAI_MODEL` or `OPENAI_COMPATIBLE_MODEL` to change them |
| `smoke` | `sm` | Provider routing smoke tests |
| `regression` | `reg` | Offline regression checks |

Useful examples:

```powershell
smart-search search "query" --capabilities none --validation balanced --extra-sources 3 --timeout 180 --format json --output result.json
smart-search route "React useEffect API docs" --format markdown
smart-search route-calibrate --models "Qwen/Qwen3-Embedding-8B" --format markdown
smart-search research "query" --budget deep --fallback auto --format json --output research.json
smart-search search "query" --stream --format json
smart-search search "query" --no-stream --format json
smart-search config set OPENAI_COMPATIBLE_FALLBACK_MODELS "grok-4.3-fast" --format json
smart-search search "nba report" --format content
smart-search exa-search "OpenAI Responses API documentation" --include-domains platform.openai.com developers.openai.com --num-results 5 --include-text --format json
smart-search context7-library "react" "hooks" --format json
smart-search context7-docs "/facebook/react" "useEffect cleanup" --format json
smart-search zhipu-search "today China AI news" --search-engine search_pro_sogou --count 5 --format json
smart-search zhipu-mcp-search "today China AI news" --count 5 --format json
smart-search zhipu-mcp-reader "https://example.com/source" --format json
smart-search zhipu-mcp-search-doc "owner/repo" "install" --format json
smart-search anysearch-search "CVE-2024-3094" --domain security --sub-domain vuln --sub-domain-params '{"type":"cve","value":"CVE-2024-3094"}' --max-results 3 --format json
smart-search anysearch-extract "https://example.com/source" --format json
smart-search exa-similar "https://example.com/source" --num-results 5 --format json
smart-search fetch "https://example.com/source" --format markdown --output page.md
smart-search map "https://docs.example.com" --instructions "Find API reference pages" --max-depth 1 --limit 50 --format json
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
smart-search smoke --mock --format json
smart-search regression
```

## Output And Evidence Policy

Use JSON for agents and scripts:

```powershell
smart-search search "query" --format json
smart-search doctor --format json
```

Use Markdown for human-readable reports, detailed diagnostics, source lists, and fetched page text:

```powershell
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
smart-search smoke --mock --format markdown
smart-search exa-search "OpenAI Responses API documentation" --format markdown
smart-search fetch "https://example.com" --format markdown
```

Use `content` for compact terminal reading:

```powershell
smart-search search "nba report" --format content
smart-search doctor --format content
```

`content` is intentionally brief. Use `doctor --format markdown` for general human troubleshooting, `diagnose openai-compatible --format markdown` for OpenAI-compatible search hangs/timeouts, and JSON formats for complete machine-readable contracts.

Save multi-source evidence under an explicit stable folder. The default uses the platform temp directory; the commands below use a Windows explicit path example:

```powershell
smart-search exa-search "Reuters Iran Hormuz latest" --format json --output C:\tmp\smart-search-evidence\iran-hormuz\01-exa.json
smart-search fetch "https://example.com/source" --format markdown --output C:\tmp\smart-search-evidence\iran-hormuz\02-fetch.md
```

For claim-level evidence:

1. Discover candidate URLs with `search`, `exa-search`, `zhipu-search`, or `exa-similar`.
2. Fetch exact URLs with `fetch`.
3. Cite fetched text in the final answer.
4. Unsupported key claims must be fetched or downgraded to unverified candidates.

## Troubleshooting

If `doctor` reports `config_error`:

```powershell
smart-search setup
smart-search config list --format json
smart-search doctor --format markdown
```

If OpenAI-compatible `search` hangs or times out after `doctor` passes:

```powershell
smart-search doctor --format markdown
smart-search diagnose openai-compatible --format markdown
```

The diagnose report masks the API key and says whether the problem is missing config, the upstream/relay hanging on the real Smart Search prompt, or a stream/no-stream compatibility mismatch.

If search is slow:

- reduce `--extra-sources`;
- split broad questions into smaller queries;
- use `exa-search` or `zhipu-search` for source discovery, then `fetch` key pages.

If installed CLI health is uncertain:

```powershell
smart-search --help
smart-search --version
smart-search regression
smart-search smoke --mock --format json
```

On Windows npm/mise installs, verify non-ASCII JSON piping:

```powershell
smart-search deep "深度搜索一下最近的比特币行情" --format json | ConvertFrom-Json
```

## Development

```powershell
.\.venv\Scripts\python.exe -m compileall -q src tests
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe -m smart_search.cli regression
.\.venv\Scripts\python.exe -m smart_search.cli smoke --mock --format json
npm test
npm pack --dry-run
```

## 0.6.0 release line

`@jfmoe/smart-search@0.6.0` is the personal distribution line. Node is the only
promised JavaScript launcher, and macOS is the only formally supported platform.
The public Skill is maintained from `skills/smart-search-cli`; the packaged
copy is generated by `scripts/sync-skill.py`.

## Release lanes

- A normal `main` push runs `npm test` only; it cannot publish.
- A preview is available only through `workflow_dispatch`. It requires an
  immutable, full 40-character commit SHA and a prerelease of the checked-out
  `package.json` version; it publishes only to npm `next`.
- A stable release is available only from an exact `vX.Y.Z` tag. Before npm
  `latest` is published, the workflow verifies that the tag, npm metadata,
  Python metadata, lockfile, and `npm version` are exactly `X.Y.Z`.

Each public version maps to immutable source: do not move a release tag, rebase
or force-push released `main` history, or try to overwrite an npm version.
Prepare `.github/releases/vX.Y.Z.md` before the stable tag; the workflow uses
it as the GitHub Release body.

The current read-only upstream baseline is recorded in
`docs/release/upstream-baseline.md`. Upstream changes are selected only through
a separate sync PR; release work does not fetch, merge, or publish upstream.

## License

MIT
