# Immutable session record — AUD-LEDGER-001 MV6 PCA claim reconstruction

## Session identity

- Session stamp: `2026-07-24T140810Z`
- Owner: scheduled scientific-review session
- Initial remote `main`: `c9c432f5b96eae0fd11550be7833f18221019b1a`
- Task: reconstruct malformed claim-ledger rows `CL-023` and `CL-024` from exact tracked MV6 evidence
- Core-work remote head before this archive: `a9575a99bac67e07496ef07db16d9dbb9c8127d3`

## Repository and coordination review

Inspected current `main`, recent commits, open pull requests, PR #868, current commit status, `chatgpt_todo/HANDOFF.md`, `ACTIVE_TASK.md`, `BACKLOG.md`, `SESSION_LOG.md`, `MASTER_INDEX.md`, the claim ledger and schema validator/evidence, the tracked MV6 producer, summary JSON, report, Chapter 6, and the previous Chapter 9 correction.

PR #868 was confirmed closed, unmerged, and non-mergeable and was not modified. No status checks were attached to the initial main commit.

## Confirmed defects

The pre-change ledger blob `e489555f3a520c7cc64b8a7d858a0e93622b9de6` had only 37 columns for both `CL-023` and `CL-024`, so late fields were shifted and withheld by the 43-column schema gate. It also published unsupported values `0.89` and `0.997` and cited a noncanonical `scripts/mv6_pca.py` / `results.json` source chain.

The tracked source chain is:

- `scripts/mv6_representation_study.py`, blob `f965823518b22908f3e8974f280bff5c970368d0`;
- `reports/mv6_representation_1782678362/mv6_representation_summary.json`, blob `26c187cbe05d8dadbe588c6ed9062d25658a80a9`;
- `reports/mv6_representation_1782678362/REPORT.md`, blob `2c531703755b28a0c576e978531b81374edf8ab4`;
- producing commit recorded by the claim chain: `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`.

The producer subtracts the 350-ADC pedestal, peak-normalizes each synthetic waveform, fits ten PCA components, and uses a four-component GMM on the first four PCs. The summary records seed 42, 220,000 scanned events, and 87,555 charged B-arm MC tracks.

## Independent calculation

The first explained-variance ratios are:

```text
0.6397275304111596
0.05803144748933653
0.027701235443287935
0.02005735713674897
0.01943928056747368
0.01915966934733869
0.01891806012034366
0.018849346397427923
```

Using `math.fsum`:

```text
3-PC cumulative fraction = 0.7254602133437841
4-PC cumulative fraction = 0.745517570480533
8-PC cumulative fraction = 0.821883926913117
```

The eight-PC reconstruction exactly matches the summary's recorded cumulative field.

## Delivered correction

`CL-023` and `CL-024` now each contain exactly 43 columns, use truth type `synthetic_waveform_mc`, status `TRUTH_LEVEL_MC_ONLY`, canonical report/script/data paths, event and MC-track counts, producing commit, link state, superseded values, and explicit non-transfer/non-uncertainty caveats.

The corrected ledger was committed as `bf584eec7d64c6f78cd782b7b1ff84387d0f2bfe`, blob `d33180f144cca10a6e310b3e89b5ab1d065d7e66`, SHA-256 `3a08d0d561de0ad11f2bbbf4a6cc1284af2315e30bbb3ded39be308b6d5125ff`.

Added a fail-closed semantic validator, focused regression, Markdown audit, machine-readable JSON, and SVG evidence. Refreshed cumulative ledger schema evidence from 8/26 exact and 18 malformed to 10/26 exact and 16 malformed. The global schema status remains intentionally `FLAWED`/nonzero until all rows are source-reconstructed.

## Validation commands and results

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/validate_mv6_pca_claim_rows.py \
  tests/test_validate_mv6_pca_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv6_pca_claim_rows.py -q

7 passed in 1.39s
```

Additional checks:

- pre-change ledger SHA-256 matched `9a099f76609c51b7400c8615a46c5e873058ac00e0fa9e3a0e2877a1d5e5db5c`;
- validation JSON parsed;
- both SVG files parsed as XML;
- changed Python line lengths were at most 100 characters;
- focused tests cover stale values, row-width failure, summary inconsistency, producer-contract mutation, JSON/SVG generation, and invalid UTF-8 status 2.

Local executable validation used an exact PCA/GMM contract excerpt because the runtime could not resolve `github.com` for a clone. The complete producer was inspected through authenticated GitHub full-file and ranged reads. This distinction is explicit in the machine-readable record.

## Files changed

- `docs/claim_ledger.csv`
- `tools/audit/validate_mv6_pca_claim_rows.py`
- `tests/test_validate_mv6_pca_claim_rows.py`
- `docs/validation/mv6_pca_claim_rows_audit.md`
- `docs/validation/mv6_pca_claim_rows_validation.json`
- `docs/validation/mv6_pca_claim_rows.svg`
- `docs/validation/claim_ledger_schema_audit.md`
- `docs/validation/claim_ledger_schema_validation.json`
- `docs/validation/claim_ledger_schema.svg`
- `chatgpt_todo/ACTIVE_TASK.md`
- this immutable archive and the final handoff

## Ordered direct-main commits before archive

1. `bf584eec7d64c6f78cd782b7b1ff84387d0f2bfe` — `fix(ledger): reconstruct MV6 PCA claims from source`
2. `d730dfb79ed1814af7852a4bb32d1445fd55a07d` — `feat(audit): validate MV6 PCA claim rows`
3. `12d2a8d93ff9385ee5fb5af0bc4b9cc3b1a78541` — `test(audit): cover MV6 PCA claim reconstruction`
4. `b6b85afdac36215e63e47b019a24ac078dd57249` — `docs(validation): record MV6 PCA claim-row audit`
5. `edc7ad219ab31d646392009435b451cfa2b289fb` — `docs(validation): add MV6 PCA claim validation record`
6. `3f0a75c566953f74aed457a6becce011011f244e` — `docs(validation): visualize MV6 PCA claim reconstruction`
7. `30e20ece5971b1837b4e6b51ece457e366ee0ade` — `docs(validation): refresh ledger audit after PCA repair`
8. `e91186672b32a158a49e411e501d59e66613bac6` — `docs(validation): refresh ledger schema record after PCA repair`
9. `e8b3a67c3b79ab919053563dfafffeaee3d0105f` — `docs(validation): visualize ten exact ledger rows`
10. `a9575a99bac67e07496ef07db16d9dbb9c8127d3` — `docs(audit): complete MV6 PCA ledger reconstruction unit`

The connector returned successful direct-main commit SHAs rather than conventional textual `git push` stdout. Remote history was re-read after publication.

## Scientific and operational boundary

No ROOT processing, PCA refit, waveform simulation, beam-data analysis, confidence interval, calibration, or detector-performance result was generated. These values are fixed synthetic-waveform MC representation outputs, not empirical transfer claims.

Chapter 6 still contains PCA-spectrum, component-meaning, autoencoder-comparison, and sample-size statements that do not match the tracked MV6 producer/summary and require a separate source-synchronization unit. `AUD-ANOM-001` matched data/MC closure remains open.

Full repository pytest, ruff, ROOT execution, repository-wide link checking, and GitHub Actions were not run. No broader CI success is claimed.

`SESSION_LOG.md` was not replaced in this unit because the connector supports whole-file replacement but not byte-safe append and only paged/truncated snapshots were available. Replacing the append-only log without a complete byte-identical reconstruction would risk destroying prior provenance. This immutable archive and `HANDOFF.md` retain the complete run.
