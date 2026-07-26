# Active Task

- **Task ID:** `AUD-FIG-002-R1`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T100542Z`
- **Initial remote main SHA:** `8b460728fce2f550d63bed078f17c2285e0c2b2a`
- **Scope:** remediate paper-figure result/source artifact provenance so parsing, hashing, sizing, and publication use one exact retained byte snapshot.
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`.
- **Assumptions:** software/provenance unit only; no underlying scientific value, uncertainty, or detector-performance claim is authorized.
- **Files:** `tools/figure_registry/builder.py`; focused replacement-race tests; existing snapshot auditor/evidence; `chatgpt_todo/` archive and handoff.
- **Validation plan:** compile changed Python; run focused builder and audit regressions; execute deterministic result/source path-replacement controls; verify atomic failure preservation; parse JSON/SVG; inspect exact-current source with the existing auditor.
- **Progress:** task claimed on the latest remote `main`; production changes not yet delivered.
- **Status:** `ACTIVE`
