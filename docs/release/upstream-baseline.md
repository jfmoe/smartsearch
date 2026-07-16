# Upstream baseline

## Selected baseline

- Read-only upstream: `konbakuyomu/smartsearch`
- Ref: `refs/heads/main`
- Commit: `667c465d0f6ea16a423f03c434f94e21505d3595`
- Commit subject: `fix(openai-compatible): 增加流式与模型降级保护`
- Tag: none; the baseline is the upstream `main` tip recorded on 2026-07-16.

This is the exact source baseline inherited by the 0.2.0 personal release work.
It was verified read-only with `git ls-remote
https://github.com/konbakuyomu/smartsearch.git refs/heads/main`, which returned
this SHA, and with `git merge-base HEAD <SHA>`, which returned the same SHA.
A commit endpoint being resolvable is not sufficient evidence: GitHub fork
networks can resolve commits that do not belong to the upstream ref.
No upstream commit was fetched, merged, or published as part of this release
identity change.

## Sync boundary

The upstream remote is read-only for this distribution. Future upstream changes
must be selected by SHA or tag in a dedicated sync PR, with this file updated to
the newly selected baseline and the upstream ref verified directly. Recording a
baseline does not authorize fetching or merging upstream code. Release-identity
PRs must not merge upstream, rewrite released `main` history, or move a
published tag.
