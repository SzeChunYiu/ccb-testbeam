# Immutable handoff — AUD-FIG-001

## Session identity

- Stamp: `2026-07-26T061216Z`
- Owner: scheduled scientific-review session
- Initial remote main: `d046259666a08dbf9188e8a80d5a3b0cbced5765`
- Destination: direct commits to `main`; no force-push, history rewrite, task branch, or PR merge.

## Reviewed

- current remote history and repository permissions;
- open draft PR #933 and closed PR #868;
- current-main commit status;
- `chatgpt_todo/ACTIVE_TASK.md`, `BACKLOG.md`, `HANDOFF.md`, and recent `SESSION_LOG.md` entries;
- `tools/figure_registry/registry.py`;
- `tools/figure_registry/builder.py`;
- `tools/figure_registry/__init__.py`;
- `paper/figures.yaml`;
- `tests/test_figure_registry.py`;
- the content-addressed repository CI failure ledger and exact workflow log summary.

## Findings

The shipped paper registry cannot satisfy its governing structural validator.

- Implementation statuses: 5.
- Shipped statuses: 10.
- Unsupported shipped statuses: `BLOCKED`, `GATED`, `MC_METHOD_CLOSURE`, `PARTIAL`, `SIMULATION_RESULT`, `SUPERSEDED`.
- Unsupported shipped kind: `figure_sourced`.
- Illustrative entries without `result`: `CLAIM-DASHBOARD`, `DASHBOARD-OVERVIEW`, `SCH-01`, `SCH-02`, `SCH-03`.
- The validator unconditionally requires `result`.
- The test suite freezes the obsolete five-status vocabulary while asserting the shipped registry validates.

The focused audit returned nine findings and a corrected contract fixture returned zero.

## Files added

- `tools/audit/audit_figure_registry_schema_alignment.py`
- `tests/test_audit_figure_registry_schema_alignment.py`
- `tools/audit/render_figure_registry_schema_evidence.py`
- `docs/validation/figure_registry_schema_alignment_validation.json`
- `docs/validation/figure_registry_schema_alignment.svg`
- `docs/validation/figure_registry_schema_alignment_audit.md`

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_schema_alignment.py \
  tests/test_audit_figure_registry_schema_alignment.py \
  tools/audit/render_figure_registry_schema_evidence.py

pytest -q tests/test_audit_figure_registry_schema_alignment.py

5 passed in 0.07s
```

JSON and SVG parsing passed. Invalid UTF-8, output/input aliasing, and atomic publication failed or passed as designed.

## Provenance

Git blobs inspected through the authenticated connector:

- registry implementation: `0828d42c50e697bdc793d46d8bd23c4a57e3054d`;
- shipped registry: `5d03f284fd2e018fcda786313f46c64ea7a20105`;
- existing test: `1546b8b6896fdbbdce28cfb53fccc8d727479436`.

The local current-like execution used a connector-reconstructed semantic excerpt. It was not represented as a byte-identical checkout.

## Required remediation

1. Define the complete controlled scientific-status vocabulary.
2. Define an explicit status-to-build-disposition map.
3. Add `figure_sourced` or replace it with an equally explicit source-figure contract.
4. Require `result` only where a numerical result is actually consumed.
5. Require `source_figure` for figure-sourced and illustrative entries.
6. Keep blocked, gated, partial, superseded, and MC-only entries non-authorizing by default.
7. Update focused tests and require the exact shipped registry to validate.
8. Run builder tests and the repository-wide gate before claiming integration.

## Scientific boundary

No paper figure or scientific number was regenerated or validated. This is software/schema governance only.

## Coordination limitation

`SESSION_LOG.md`, `BACKLOG.md`, `MASTER_INDEX.md`, and aggregate matrices were reviewed but not replaced. The connector exposes whole-file replacement rather than byte-safe append/patch, while the complete long shared files are returned only through paged or truncated views. Replacing a partial reconstruction could erase append-only or concurrent provenance. This unmet mandatory synchronization step is recorded here and in the latest handoff rather than reported as complete.
