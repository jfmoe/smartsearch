---
status: accepted
---

# Treat caller capability declarations as authoritative

A Caller Capability Declaration is the complete and authoritative capability set for any ordinary search or route diagnostic that supplies one. Smart Search does not supplement it from local rules, URL recognition, strict validation, embeddings, or the classifier; `none` therefore remains empty even when the query contains a URL or uses strict validation. Calls without a declaration retain the existing configured intent router, while provider selection, same-capability fallback, unconditional main search, and the separate research evidence workflow remain unchanged.

This supersedes ADR-0003 because merging lower-fidelity keyword rules into an Agent's complete semantic decision caused false capabilities, including Vertical Search for documentation requests that merely asked for accurate code. Route diagnostics report only the caller engine for this path, making the declared authority observable rather than presenting unused rules as decision inputs.
