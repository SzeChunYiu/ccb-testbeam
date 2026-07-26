# Active Task

- **Task ID:** `AUD-FIG-005`
- **Owner:** scheduled scientific-review session
- **Session stamp:** `2026-07-26T170400Z`
- **Initial remote main SHA:** `03851ff128a5a351f39c7754e47ac35fe80e0fa0`
- **Scope:** bind every paper-figure `build_report.json` to the exact duplicate-key-safe registry byte snapshot used for parsing, and convert registry format failures into controlled CLI diagnostics.
- **Policy:** `FIGURE_BUILD_REPORT_MUST_BIND_TO_EXACT_REGISTRY_SNAPSHOT`.
- **Files:** `tools/figure_registry/builder.py`, focused regressions, JSON/SVG/Markdown validation evidence, immutable archive, and handoff.
- **Assumptions:** registry scientific content is not revalidated by this task; build-report provenance and error-boundary integrity are the focused acceptance unit.
- **Validation plan:** compile changed Python; run the new focused tests plus `tests/test_figure_registry_duplicate_keys.py`; verify exact SHA-256/byte-count binding, replacement-after-read stability, controlled duplicate-key and invalid-UTF8 CLI failures, structural-invalid report provenance, JSON/SVG parsing, and changed-line length.
- **Progress:** task claimed on current remote `main`; implementation in progress.
- **Status:** `ACTIVE`
