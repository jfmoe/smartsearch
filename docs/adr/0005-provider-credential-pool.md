# Provider Credential Pool for allowlisted providers

Smart Search keeps a single credential per provider today. We add a **Provider Credential Pool** only for an allowlisted set of providers (Exa, Tavily, Jina, Firecrawl, Context7, AnySearch): multiple credentials selected by round-robin to spread load and reduce single-credential rate limits. This is a runtime selection mechanism, not high-availability failover and not a free-tier harvest feature—product and code narrative describe multi-credential rotation on rate limits, not free-account aggregation (that remains a separate glossary motive, Cross-account Quota Aggregation).

**Config:** keep `*_API_KEY`; add `*_API_KEYS` as a JSON string array (config and env). Non-empty `KEYS` fully replaces `KEY` after empty-strip and dedupe. First-cut management is whole-array `config set` / setup, not add/remove subcommands.

**Selection and failure:** claim `next_index` under a config-dir file lock at request start and advance immediately (no rollback). On `rate_limited` / explicit quota exhaustion only, try other pool members in the same request (each credential at most once per request); do not backoff-retry the same credential for those errors. Other errors stay on existing same-credential or capability-level paths.

**Observability:** report pool enablement, key count, masked tails, and rotation/`key_index` facts; never persist or print raw credentials. Cursor state stores indices only.
