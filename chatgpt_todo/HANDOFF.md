# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T160450Z`
- **Task:** `AUD-LEDGER-001`
- **Unit:** source-backed reconstruction of MV0 claim rows `CL-013` and `CL-014`
- **First observed remote `main`:** `ec4ab24ffdbcdeeae76c1e8be615cc3a6e4324d4`
- **Concurrent base incorporated before writes:** `9e1ccc57fee369293be0f090141831e0f65216b8`
- **Validated delivery head before this handoff:** `d112421d0cd56bb1b7336b4782d1bef749d9af84`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** this two-row reconstruction and validation unit is `VALIDATED`; ledger-wide `AUD-LEDGER-001` remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected repository metadata, recent history, current `main`,
mandatory scientific-review coordination files, the canonical claim ledger, cumulative
schema evidence, the MV0 report, calibration JSON, tracked producer, source-introducing
commit, PR #868, and current commit-check state.

The first observed head was `ec4ab24...`. Before writes, concurrent G4-07 work advanced
`main` to `9e1ccc57...`; the complete MV0 sequence is based on and descends from that
newer head. No force push, history rewrite, branch-only delivery, or deletion of
unrelated work was used.

PR #868 is closed, unmerged, and non-mergeable. It was not modified or merged. The
connector returned successful direct-main contents-API commit SHAs rather than
conventional textual `git push` stdout. A post-write history read showed the complete
focused sequence as consecutive commits on remote `main`.

## Confirmed defects

The pre-change claim ledger had a 43-column header, but:

- `CL-013` had 38 columns;
- `CL-014` had 37 columns.

The repository's fail-closed schema policy therefore withheld their late fields,
including truth type, status, source paths, link state, CI state, blocker,
supersession, and notes.

The former records also contained scientific/provenance defects:

- they cited `scripts/mv0_calibration.py` rather than the tracked producer path
  `scripts/mv0_calibrate_from_data.py`;
- they cited a non-existent `results.json` rather than the tracked
  `calibration.json`;
- `CL-013` represented a source-described 30% heuristic systematic range as separate
  statistical and systematic uncertainty with interval-like fields;
- `CL-014` contained shifted count and p-value-like fields not supported by the source.

## Exact source evidence

Introducing source commit:

`3c5ff5cf587c8ca9cefda20cb220ba29effd2170`

Tracked report:

- path: `reports/mv0_calibration_1782677847/REPORT.md`;
- Git blob: `34ad9f8b477390adb13f7781fbd31fb5a8f1d1d6`;
- bytes: `3733`;
- SHA-256: `dc5b74056f7cac76e9c279e8e81c181453c854fd051dd82856c645c52a48b518`.

Tracked calibration result:

- path: `reports/mv0_calibration_1782677847/calibration.json`;
- Git blob: `74e490753d3e821b0a1353490764a5ede0e9bf75`;
- bytes: `2644`;
- SHA-256: `78a905473db33311b6ccfc7ef440fc076b5d210de07d09e1f868f9fdf05cd18b`.

Source-supported values:

| Quantity | Value |
|---|---:|
| B2 median-matched gain | 92 ADC/MeV |
| Gain systematic description | heuristic 30% envelope, rounded to 28 ADC/MeV |
| B2 data pulses | 579424 |
| MC tracks with B2 hit | 321130 |
| KS statistic at gain 92 | 0.1577 |
| KS-optimal scan point | gain 60 ADC/MeV, D = 0.1188 |
| Former erroneous v1 gain | 110 ADC/MeV |

The report supplies no statistical gain uncertainty and no confidence interval. The
KS p-value is not reported. It explicitly documents unresolved shape, pile-up,
polarity, and selection mismatches. No content-addressed manifest binds the historical
producer and exact data bytes.

## Delivered changes

`CL-013` is now an exact 43-column `data_mc_calibration_proxy` record:

- value `92 ADC/MeV`;
- status `GATED`;
- `allowed_status_validated=NO`;
- source-supported systematic field `28 ADC/MeV` only;
- blank statistical, total-uncertainty, and confidence-interval fields;
- `ci_method=systematic_envelope`;
- `ci_status=SYSTEMATIC_ENVELOPE_NOT_CONFIDENCE_INTERVAL`;
- `n_data=579424`, `n_mc=321130`;
- former v1 gain 110 recorded as superseded context;
- blocker `BLK-MV0-001`;
- explicit wording that the proxy is not an authorized precision calibration.

`CL-014` is now an exact 43-column `data_mc_calibration_proxy` diagnostic:

- D = `0.1577` at the median-matched gain;
- status `TENSION`;
- comparator D = `0.1188` at the scan optimum;
- descriptive difference `0.0389`;
- `n_data=579424`, `n_mc=321130`;
- `ci_status=NOT_APPLICABLE_FIXED_OUTPUT_P_VALUE_NOT_REPORTED`;
- blocker `BLK-MV0-001`;
- explicit wording that no p-value or calibrated goodness-of-fit probability is
  established.

Corrected ledger:

- Git blob: `1964fadd5a1078c534cc14bdc30e63a38f1d73c8`;
- bytes: `15274`;
- SHA-256: `30a1f5fd03d82366df3201a9d0d37be54572f13fd6c990d92b6bd5a9feab69a5`.

Cumulative ledger state:

- exact-width rows: `14/26`;
- malformed and withheld rows: `12/26`;
- width histogram: `36:1, 37:2, 38:7, 39:2, 43:14`;
- global schema state remains intentionally `FLAWED` until every row is reconstructed.

Added:

- `tools/audit/validate_mv0_claim_rows.py`;
- `tests/test_validate_mv0_claim_rows.py`;
- `docs/validation/mv0_claim_rows_audit.md`;
- `docs/validation/mv0_claim_rows_validation.json`;
- `docs/validation/mv0_claim_rows.svg`;
- `chatgpt_todo/archive/2026-07-24T160450Z_AUD-LEDGER-001_MV0_CLAIMS.md`.

Updated:

- `docs/claim_ledger.csv`;
- `docs/validation/claim_ledger_schema_audit.md`;
- `docs/validation/claim_ledger_schema_validation.json`;
- `docs/validation/claim_ledger_schema.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

Policies:

- `MV0_CLAIMS_REQUIRE_EXACT_WIDTH_AND_SOURCE_BACKED_LIMITATIONS`;
- `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

## Validation

Executed locally against exact reconstructions before publication:

```text
python -m py_compile \
  tools/audit/validate_mv0_claim_rows.py \
  tests/test_validate_mv0_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv0_claim_rows.py -q

5 passed in 0.03s
```

The direct claim-row validator returned `VALIDATED` with zero issues. Regression
coverage includes valid exact-width rows, wrong-gain rejection, required-caveat
enforcement, 42-column fail-closed handling, and controlled invalid-UTF-8 input. JSON
parsing, SVG XML parsing, source Git-blob matching, and the 100-character Python line
convention passed.

Not run: full repository pytest, ruff, ROOT processing, historical calibration rerun,
beam-data reprocessing, simulation, repository-wide link checking, or GitHub Actions.
No broader CI success is claimed; no status checks were attached to the observed head.

## Direct-main commit sequence

1. `b4a55d38d35641c1784b71bcdf49a13c1c1ae9c5` — `fix(ledger): reconstruct MV0 gain and KS claims`
2. `aae50fe46e24f4d0d6bcf7473bac0071c7f97894` — `feat(audit): validate MV0 claim rows`
3. `e5268a1fed1d260eb994e50a84f8d841b32e2797` — `test(audit): cover MV0 claim-row reconstruction`
4. `779ff38d4a6a48a589067f981e2fd243f75e14b9` — `docs(validation): add MV0 claim-row record`
5. `dddb270387f7b6125d0df0fa14729901798f4be9` — `docs(validation): visualize MV0 claim-row reconstruction`
6. `ff73bfe1ec350508b68bf5fc3e6fd3b9f7ff0073` — `docs(validation): record MV0 claim-row audit`
7. `82925c2b79b0cb19767d56cc301b8e89e8e36e71` — `docs(validation): refresh ledger schema after MV0 repair`
8. `9a6dd560e0c1ce8b8a83bcd6d10fbef6e1b5b496` — `docs(validation): update ledger schema machine record`
9. `62d0b95cb517493e4fd70c8a26e1a6645d283e27` — `docs(validation): visualize fourteen exact ledger rows`
10. `484f0616f263636b372a4a075f0e83e33ec65736` — `docs(audit): complete MV0 claim-row unit`
11. `d112421d0cd56bb1b7336b4782d1bef749d9af84` — `docs(audit): archive MV0 claim-row reconstruction`

Every listed commit is a sequential descendant of the concurrent base
`9e1ccc57fee369293be0f090141831e0f65216b8`. The contents-API write responses reported
success for every commit, and remote-history reads confirmed the sequence on `main`.

## Scientific boundary and next work

This unit does not establish a precision gain calibration, reproduce historical
ROOT/data inputs, validate pulse-selection transfer, provide a confidence interval,
resolve the data/MC shape mismatch, or produce a detector-performance result.

Resolving `BLK-MV0-001` requires exact producer, configuration, and input hashes; a
clean-environment rerun; explicit pulse-selection, threshold, baseline, and polarity
closure; preregistered alternative calibration methods; independent validation data;
and an accepted statistical/systematic uncertainty model.

`AUD-LEDGER-001` remains `PARTIAL`; 12 malformed rows still require source-backed
reconstruction before late fields can be interpreted. The next unit should select a
source-coherent pair and preserve the fail-closed policy.

`SESSION_LOG.md`, `BACKLOG.md`, and `BLOCKERS.md` were not replaced during this
connector-only unit. Their current states require complete whole-file replacement, and
reconstructing them while concurrent main work is active could erase unrelated
provenance. The immutable archive and this handoff preserve the complete run; the exact
claim rows carry the stable blocker ID `BLK-MV0-001`.
