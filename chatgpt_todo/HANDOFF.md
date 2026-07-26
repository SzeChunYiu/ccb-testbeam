# Latest Handoff

## Session

- **Task ID:** `AUD-FIG-006`
- **Stamp:** `2026-07-26T180117Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `8acfc727a1479ff5b616042e65743b0652900c25`
- **Validated evidence/archive/active-task head:** `cdc2c0d204eced6ec012d6f8c2e8c946646bf130`
- **Destination:** authenticated sequential commits directly to `main`; no force-push, branch transport, or history rewrite.
- **Acceptance:** audit implementation/evidence `VALIDATED / COMPLETE`; production builder contract `FLAWED / PARTIAL`.

## Defect

Policy: `FIGURE_REGISTRY_BUILD_MUST_NOT_LEAVE_STALE_ARTIFACTS`.

The current paper-figure builder can leave older managed outputs at their canonical paths when an entry becomes `BLOCKED` or `QUARANTINED`, raises a per-entry build failure, or disappears from the registry. The current `_process_entry` returns non-PASS records without cleanup, the `FigureRegistryError` handler records `FAIL` without cleanup, and `build` has no reconciliation step for removed IDs.

A deterministic control started with `Q.png` and `Q_source_data.csv`. Both files survived the BLOCKED, failed, and removed-entry current-contract models; the corrected cleanup model left zero files in every scenario. This proves a software/provenance gap, not that a specific committed figure is stale or a numerical value is false.

## Files delivered

- `tools/audit/audit_figure_registry_stale_artifacts.py`
- `tests/test_audit_figure_registry_stale_artifacts.py`
- `docs/validation/fixtures/figure_registry_builder_stale_artifact_current.py`
- `tools/audit/render_figure_registry_stale_artifact_evidence.py`
- `docs/validation/figure_registry_stale_artifact_validation.json`
- `docs/validation/figure_registry_stale_artifact.svg`
- `docs/validation/figure_registry_stale_artifact_audit.md`
- `chatgpt_todo/archive/2026-07-26T180117Z_AUD-FIG-006_STALE_ARTIFACTS.md`
- updated `chatgpt_todo/ACTIVE_TASK.md`

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_stale_artifacts.py \
  tests/test_audit_figure_registry_stale_artifacts.py \
  tools/audit/render_figure_registry_stale_artifact_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_figure_registry_stale_artifacts.py

6 passed in 0.05s
```

Environment: Python 3.13.5, pytest 9.0.2.

- current-like source fixture: `FLAWED`, four finding families;
- corrected fixture: `VALIDATED`, zero findings;
- invalid UTF-8 and destructive aliasing: controlled rejection;
- injected JSON publication failure: prior target preserved and temporary removed;
- validation JSON and SVG parsed successfully;
- maximum changed Python line length: 93.

The inspected current builder blob is `39dcd3b13d3886c43f3e9111291d420f86cc7c85`. The fixture records the exact blob and relevant source range but is explicitly a semantic excerpt, not a byte-identical copy of the complete module.

## Direct-main sequence

- `9e01ccea849e1a8d731a8a302785e8fdd1e220a5` — audit gate
- `6b88476c722d1bd88bc619c373540e95796b4671` — focused regressions
- `7974953481366cd82d5514c822b5d77c37065388` — current-source fixture
- `6bec3d85e56605e68bf66834112992182d342a3f` — evidence renderer
- `f6563409ffa6b2470135df21916b7e15d7a6cf11` — machine-readable evidence
- `3dac03cca404ef934d1e5db0e6f07bce684ae1db` — visual evidence
- `b7c037e08a65753f7913186030c24026974ee1a5` — audit report
- `c151045a8f09c1dc1cf29d27a95dec711d47e29d` — immutable archive
- `cdc2c0d204eced6ec012d6f8c2e8c946646bf130` — completed active task

## Required remediation

Define the complete managed output inventory per entry, remove or quarantine prior outputs before any current non-PASS disposition, reconcile IDs removed from the registry, protect against path escape/aliasing, and publish the report plus managed artifact set as one coherent fail-closed state. Prefer a staged output directory and controlled directory swap. Add direct PASS-to-BLOCKED, PASS-to-FAIL, kind/suffix-change, and removed-ID regressions, then run the complete shipped-registry and paper build.

## Scientific boundary and limitations

No paper figure, registry entry, central value, uncertainty, calibration, timing result, PID result, stopping profile, pile-up rate, or detector-performance claim was regenerated or revalidated. Repository-wide pytest/ruff, complete registry build, paper build, link inventory, and GitHub Actions were not run.

`SESSION_LOG.md` and long aggregate ledgers were not partially reconstructed because connector reads are paged while writes replace whole files. The immutable archive is the append-equivalent record; this mandatory synchronization gap is recorded rather than falsely claimed as complete.
