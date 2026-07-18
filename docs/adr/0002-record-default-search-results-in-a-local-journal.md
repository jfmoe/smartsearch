---
status: accepted
---

# Record default search results in a local journal

Smart Search will offer an opt-in Search Result Journal that records every completed Default Search Invocation, including success, structured failure, and CLI timeout, without mixing result records into the existing debug log. A dedicated daily JSONL stream preserves the complete final Smart Search result—including primary and extra sources—in a machine-readable form, while credential redaction, restricted file permissions, bounded retention, and non-fatal write failures limit the privacy and operational risks of persisting full queries and answers.

## Decision

- `SMART_SEARCH_RESULT_JOURNAL_ENABLED` defaults to `false`; when enabled, every `smart-search search` invocation, including its `s` alias and every output format, records exactly one terminal result. Invocations terminated before producing a terminal JSON result are outside this guarantee.
- Each compact UTF-8 JSONL record has `schema_version`, an RFC 3339 UTC `recorded_at` timestamp, and the complete normalized result under `result`. Raw provider HTTP responses and internal tool traces are not journaled.
- Before persistence, configured credentials and values under credential-bearing keys are recursively redacted. Queries, answers, URLs, source descriptions, routing decisions, and provider attempts otherwise remain intact.
- Records are appended synchronously under a cross-process lock after the final result is assembled and before CLI rendering. The append is flushed and closed without a per-record `fsync`; a journal failure warns on stderr but never changes the search result or exit code.
- Files live under the resolved `SMART_SEARCH_LOG_DIR` as `search_results_YYYYMMDD.jsonl`, with user-only directory and file permissions where the platform supports them. `SMART_SEARCH_RESULT_JOURNAL_RETENTION_DAYS` defaults to `30`; `0` retains files indefinitely, and cleanup only targets this journal filename namespace.
- Version 1 adds status reporting to `doctor` but no dedicated journal reader, compression, record truncation, size quota, or public schema-compatibility promise.

## Consequences

Enabled searches perform one additional local serialization and synchronous append, and `--output` therefore intentionally writes both the requested artifact and the journal record. Keeping the critical section to one compact append and omitting `fsync` bounds the expected overhead, while avoiding an unreliable fire-and-forget task or the complexity of a persistent background writer.
