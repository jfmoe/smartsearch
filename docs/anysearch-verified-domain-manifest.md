# AnySearch Verified Domain Manifest

`src/smart_search/assets/anysearch/verified-domain-manifest.json` is the only source of truth for Verified Vertical Domain support. Live Domain Discovery is observational data: it cannot edit the manifest, promote a domain, or make the Vertical Search Capability ready. Domain-less Vertical Discovery likewise exposes no final domain selection.

The manifest starts with an empty `verified_domains` collection. A future Verified Domain Contract must include separate `domain` and `sub_domain` values, an acceptance date, a canonical schema fingerprint, the accepted parameter schema, and `status=verified`. Candidate assessments are separate and use `status=discovered_unverified` with explicit gaps.

## First candidate matrix

| Candidate | Versioned mock evidence | Result shape | Current conclusion | Missing gates |
| --- | --- | --- | --- | --- |
| `academic.search` | discovery schema, valid request, missing `keywords`, provider error | URL result | discovered/unverified | sanitized live capture, complete independent live run, upstream stability window |
| `security.vuln` | discovery schema, valid request, missing `product`, provider error | URL-less structured result | discovered/unverified | sanitized live capture, complete independent live run, upstream stability window |
| `finance.fundamental` | discovery schema, valid request, missing `ticker`, provider error | URL-less structured result | discovered/unverified | sanitized live capture, complete independent live run, upstream stability window |
| `code.doc` | discovery schema, valid request, missing `repository`, provider error | URL result | discovered/unverified | sanitized live capture, complete independent live run, upstream stability window |

The fixtures under `tests/fixtures/anysearch/` are sanitized synthetic transport fixtures, not live acceptance evidence. Their schema fingerprints are checked against the manifest in ordinary offline CI. `security.cve` is intentionally absent and rejected locally without a compatibility mapping; the candidate is `security.vuln`.

## Opt-in live acceptance

Each candidate can be exercised independently without changing the manifest:

```bash
ANYSEARCH_API_KEY=... ANYSEARCH_LIVE_ACCEPTANCE=academic.search \
  pytest -q tests/test_anysearch_live_acceptance.py
```

Use a comma-separated list or `all` to select more candidates. The live check covers Domain Discovery, one valid request, and the upstream missing-required-parameter response. It remains opt-in, requires no credentials in ordinary CI, and deliberately does not promote a candidate. Promotion requires a reviewed, sanitized evidence update covering all matrix gates, including stable provider-error classification and the upstream stability/version decision.
