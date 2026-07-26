# Active Task

- **Task ID:** `AUD-FIG-002-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T100542Z`
- **Initial remote main SHA:** `8b460728fce2f550d63bed078f17c2285e0c2b2a`
- **Scope:** remediate paper-figure result/source artifact provenance so parsing, hashing, sizing, and publication use one exact retained byte snapshot.
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`.
- **Finding:** former result and source-artifact paths could be replaced between the bytes used and later provenance reads; publication errors also needed a controlled builder failure boundary.
- **Delivered:** immutable result/source byte snapshots; strict result decoding; atomic source and source-data publication; final-target hash/size verification; controlled publication errors; five direct replacement/failure/alias regressions; JSON, SVG, audit report, and immutable archive.
- **Validation:** compilation passed; focused pytest `5 passed in 0.39s`; exact-current source audit `VALIDATED` with zero findings; result/source replacement controls retained the original identities; injected publication failure preserved the previous target and left zero temporary files; JSON and SVG parsed.
- **Implementation:** final builder blob `cc56e548b54fd8f2692182de6114ee3bcfe196c4`; final focused-test blob `8550b37469278b708237d2a9ef181e24f608fda3`.
- **Acceptance:** focused software/provenance remediation `VALIDATED / COMPLETE`; no scientific paper value or detector-performance claim authorized.
- **Remaining boundary:** complete paper build, repository-wide pytest/ruff, link inventory, and GitHub Actions were not run.
- **Status:** `COMPLETE`
