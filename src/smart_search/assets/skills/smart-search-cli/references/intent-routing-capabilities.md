# Intent Routing Capabilities

Use this reference only when deciding which retrieval capabilities a request needs. Select capabilities, never providers; `main_search` is not selectable here.

## `docs_search`

Search external library, SDK, API, framework, and official technical documentation.

- Select when: The request needs authoritative documentation, API reference, configuration, or integration details.
- Do not select when: The request is general technical knowledge or merely mentions a technology without needing its documentation.

## `web_search`

Discover supplemental web sources for current, news, regional, policy, market, or cross-validation needs.

- Select when: The request needs recent or live information, locale-specific discovery, policy/news/market updates, or source reinforcement.
- Do not select when: The request is timeless, already has a known URL to read, or only needs documentation search; this capability is not main_search.

## `web_fetch`

Read, extract, or verify the body of a known HTTP(S) URL or PDF.

- Select when: The request supplies a known URL/PDF or explicitly asks to read, extract, summarize, or verify linked content.
- Do not select when: The request needs link discovery rather than content from a known URL; provider acceptance extraction is not this capability.

## `vertical_search`

Discover results for explicit vertical-domain intent, including security, finance, legal, academic, code, gaming-guide, and travel-itinerary lookup.

- Select when: The request clearly targets a structured or specialized vertical domain covered by local routing terms.
- Do not select when: The request is ordinary broad web search, uses generic game/travel words, or asks for an unverified automatic domain search.

## Decision caveats

Judge the complete set independently for the request: multiple capabilities or an empty set are valid. Provider selection, fallback, thresholds, strict validation, URL extraction, and routing merge behavior remain runtime-owned.
