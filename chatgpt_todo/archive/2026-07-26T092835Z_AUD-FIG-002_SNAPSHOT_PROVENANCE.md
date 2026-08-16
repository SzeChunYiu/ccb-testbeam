# Immutable handoff — AUD-FIG-002

## Session

- **Stamp:** `2026-07-26T092835Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `770fa6e8ba305b29c539e64f1f151c4cf5dc1053`
- **Destination:** direct sequential commits to `main`; no task branch, force-push, or history rewrite.
- **Policy:** `FIGURE_ARTIFACT_PROVENANCE_MUST_BIND_TO_SINGLE_READ_EXACT_BYTES`
- **Focused acceptance:** audit gate and evidence `VALIDATED`; current production builder `FLAWED / PARTIAL`.

## Repository area reviewed

- `tools/figure_registry/builder.py`
- `tools/figure_registry/registry.py`
- `tests/test_figure_registry.py`
- `paper/figures.yaml`
- prior `AUD-FIG-001` schema-alignment audit and remediation history
- current `chatgpt_todo/` handoff and backlog
- open pull requests and current-main status checks

Reviewed builder blob:

`ef6e11cfac3e9eacdabfb146ec7586e8764fceb1`

## Confirmed defect

The quantitative path parses result JSON from one path read, then later hashes `entry.result` again while writing figure source data. The existing-artifact path copies the source first, then separately hashes and stats the source path. A path replacement between those operations can pair a rendered/copied artifact with provenance from different bytes.

Synthetic controls reproduced both mismatches:

- result bytes used: `33066bb044c6d3dc3c6afe6ca68d0104cf7f29a9735659cccf650018f5b24c78`;
- later result hash: `3b6204ea9a2aad1f6c90d59f42f6484bb9ec9e766094bdae23981c70306988d7`;
- copied source target: `baabbed7db11b99073870ca9517ea3caf20541d33848bfbde0830d77be6d2eb3`;
- later source hash: `5846f2f03f5bfc0b295fccb71360798c49e95c1b1528964a82db0f17c92f7cb7`.

The corrected controls parsed/copied, hashed, and sized one retained byte snapshot and matched exactly.

## Files delivered

- `tools/audit/audit_figure_registry_snapshot_provenance.py`
- `tests/test_audit_figure_registry_snapshot_provenance.py`
- `tools/audit/render_figure_registry_snapshot_provenance_evidence.py`
- `docs/validation/figure_registry_snapshot_provenance_validation.json`
- `docs/validation/figure_registry_snapshot_provenance.svg`
- `docs/validation/figure_registry_snapshot_provenance_audit.md`
- this immutable archive record
- updated `chatgpt_todo/ACTIVE_TASK.md`
- updated `chatgpt_todo/HANDOFF.md`

## Validation

```text
python -m py_compile \
  tools/audit/audit_figure_registry_snapshot_provenance.py \
  tests/test_audit_figure_registry_snapshot_provenance.py \
  tools/audit/render_figure_registry_snapshot_provenance_evidence.py

PYTHONPATH=. pytest -q tests/test_audit_figure_registry_snapshot_provenance.py

5 passed in 0.10s
```

Additional checks:

- current-like fixture: `FLAWED`, three findings;
- corrected fixture: `VALIDATED`, zero findings;
- invalid UTF-8 and destructive alias: fail closed;
- injected atomic-replacement failure: prior JSON preserved, no temp residue;
- JSON and SVG parsing: passed.

Validated local file SHA-256 values:

- auditor: `e00f21ed1d936d603b80b07b053dd6488b4f45095d60ae3a2cad04fa20ee8308`;
- tests: `11bd9a8a07f61c4ddb8d74d87e44b448722142772dde4e73a750c70e964400bf`;
- renderer: `0f13ded4f9f5f80c20ecfb01229e6b9f9354fcba8e8cf2a9e98e180db2f55e5b`;
- validation JSON: `818555ab3491e1d156678fbd11b58797c4ad629e0f36792cc395c7d741eeeab0`;
- SVG: `36ada9d68a446236c02235d219f9f60c822130dd6b30a1176243f8f23543e669`.

## Required next remediation

1. Read result JSON bytes once and parse/hash/size that snapshot.
2. Read source-artifact bytes once and publish target atomically from that snapshot.
3. Record both source snapshot and final target digests.
4. Add direct builder regressions with injected path replacement.
5. Require the exact current-source audit to return zero findings.
6. Run focused figure-registry tests and the shipped-registry validation.

## Scientific boundary

No paper figure was regenerated and no scientific value, uncertainty, calibration, PID result, timing result, stopping profile, rate, or detector-performance claim was validated or changed. Repository-wide pytest, ruff, full paper build, link inventory, and GitHub Actions were not run and are not claimed as passing.

PR #939 remained open, non-mergeable, and unmerged. PR #868 remained closed and unmerged.
