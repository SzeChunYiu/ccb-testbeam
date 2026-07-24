# Immutable session record — legacy MV3 claim reconstruction

## Identity

- UTC stamp: `2026-07-24T173757Z`
- Task: `AUD-LEDGER-001`
- Unit: `CL-019`, `CL-020`, and `CL-021`
- Initial remote `main`: `1e44fd19a02c33377e727bd5d85be7a8aa96b587`
- Owner: scheduled scientific-review session

## Reviewed evidence

- canonical 43-column claim ledger and cumulative schema evidence;
- `reports/mv3_stopping_v3_1782679272/REPORT.md`;
- `src/ccb_mc_validation/studies/mv3_stopping_depth.py`;
- introducing commit `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`;
- recent main history, current coordination files, PR #868, and current CI/status metadata.

## Findings

- `CL-019`, `CL-020`, and `CL-021` had 38, 38, and 36 columns.
- Former source paths `scripts/mv3_stopping.py` and
  `reports/mv3_stopping_v3_1782679272/results.json` are not tracked on current `main`.
- The report gives 249484 MC tracks, 306745 data events, B8 fractions 0.223 and 0.023, and the literal label `chi2/ndf = 68269.4`.
- It gives no exact per-stave counts, separate chi-square, ndf, p-value, bin variance, or covariance.
- Rounded-fraction inversion yields 55511–55759 possible MC B8 counts and 6902–7208 possible data B8 counts; exact numerators and binomial intervals are not identifiable.
- Current remediation blocks without explicit `sample_label` and per-layer hit/energy masks and removes event-parity and stop-layer occupancy proxies.

## Delivered files

- corrected `docs/claim_ledger.csv`;
- `tools/audit/validate_mv3_legacy_claim_rows.py`;
- `tools/audit/render_mv3_legacy_claim_evidence.py`;
- `tests/test_validate_mv3_legacy_claim_rows.py`;
- `docs/validation/mv3_legacy_claim_rows_audit.md`;
- `docs/validation/mv3_legacy_claim_rows_validation.json`;
- `docs/validation/mv3_legacy_claim_rows.svg`;
- refreshed cumulative schema Markdown, JSON, and SVG;
- updated active task and latest handoff.

## Validation

```text
python -m py_compile \
  tools/audit/validate_mv3_legacy_claim_rows.py \
  tools/audit/render_mv3_legacy_claim_evidence.py \
  tests/test_validate_mv3_legacy_claim_rows.py

PYTHONPATH=. python -m pytest tests/test_validate_mv3_legacy_claim_rows.py -q
7 passed in 1.05s
```

Direct validation: `VALIDATED`, zero issues. JSON and SVG parse. Maximum changed Python line length is at most 100 characters. Exact committed blobs for the validator, renderer, and tests match the local validated blobs.

## Acceptance

The three-row governance reconstruction is `VALIDATED`. The physics claims are not promoted: `CL-019` and `CL-020` are `GATED`, `CL-021` is `FLAWED`, and all remain blocked by `BLK-MV3-LEGACY-001`. Ledger-wide `AUD-LEDGER-001` remains `PARTIAL` at 19/26 exact rows.

## Limitations

No ROOT, Geant4, beam-data, or historical producer rerun was performed. No exact B8 count, confidence interval, valid chi-square statistic, p-value, sample-trigger closure, threshold-transfer closure, or detector-performance result is claimed. PR #868 remains closed and unmerged.
