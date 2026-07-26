# Immutable handoff — AUD-FIG-006

- Session stamp: `2026-07-26T180117Z`
- Initial remote main: `8acfc727a1479ff5b616042e65743b0652900c25`
- Owner: scheduled scientific-review session
- Policy: `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`
- Focus: stale paper-figure outputs after BLOCKED, QUARANTINED, FAIL, or registry removal
- Audit state: `VALIDATED / COMPLETE`
- Production builder state: `FLAWED / PARTIAL`

## Confirmed defect

The current builder returns non-PASS records and catches per-entry failures without
removing earlier managed outputs. It also has no reconciliation step for IDs removed
from the current registry. A deterministic two-file control leaves both prior
artifacts in BLOCKED, failed, and removed-entry scenarios.

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_stale_artifacts.py \
  tests/test_audit_figure_registry_stale_artifacts.py \
  tools/audit/render_figure_registry_stale_artifact_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_figure_registry_stale_artifacts.py
6 passed in 0.05s
```

The current-like fixture returned `FLAWED` with four findings. The corrected fixture
returned `VALIDATED` with zero findings. JSON/SVG parsing, invalid-UTF8 handling,
alias rejection, and atomic JSON failure preservation passed.

## Required next unit

Implement a complete managed-output inventory and fail-closed reconciliation for
PASS-to-non-PASS transitions and removed IDs. Prefer a staged output directory and
controlled directory swap; record removed paths and prior hashes. Run direct builder
regressions and the complete shipped-registry/paper build before accepting the
production remediation.

## Scientific boundary

No scientific result or paper figure was regenerated. The audit proves a software
provenance gap, not that any specific numerical result is false.

## Coordination limitation

`SESSION_LOG.md` and long aggregate ledgers were not replaced because connector
reads are paged while writes replace the whole file. Partial reconstruction could
erase unrelated append-only provenance. This archive is the append-equivalent
record and does not claim the mandatory append succeeded.
