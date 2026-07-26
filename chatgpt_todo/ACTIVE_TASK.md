# Active Task

- **Task ID:** `AUD-FIG-002`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T092835Z`
- **Initial remote main SHA:** `770fa6e8ba305b29c539e64f1f151c4cf5dc1053`
- **Scope:** audit whether the paper-figure builder binds rendered/copied artifacts and recorded provenance to one exact byte snapshot.
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`.
- **Repository facts:** the quantitative path parses result JSON from one read and later re-hashes the path; the source-artifact path copies first and later hashes/stats the source path.
- **Validation plan:** exact-source AST inspection; replacement-race behavioral controls; focused pytest; strict UTF-8, alias, atomic-publication, JSON, and SVG checks.
- **Acceptance:** audit tooling and evidence may be validated on `main`; the builder remains non-accepting until it reads each result/source artifact once and publishes metadata from the same retained bytes.
- **Status:** `ACTIVE`
