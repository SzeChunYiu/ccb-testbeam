# MV3 exact-summary public-WIKI synchronization gate

## Status

**PARTIAL.** The validator, focused tests, exact replacement contract, candidate WIKI snapshot, and synthetic visual evidence are validated. The public root `WIKI.md` on remote `main` was **not** synchronized in this run and remains `FLAWED` with the rounded/absence narrative.

This audit does not validate stopping-profile physics closure or detector performance.

## Session identity

- UTC stamp: `2026-07-24T221537Z`
- Task: `AUD-WIKI-001`
- Unit: MV3 exact tracked-summary public synchronization gate
- Initial remote `main`: `e844e779c9c431c6fcfe144b5cc5d856323c7bcf`
- Transport-stage commit: `b3d674a1d9b9cb22bac1072b4574e0be6cc6f59f`
- Transport-retrigger commit: `c9548f1abb8d8de465e618255f0c835987e8141f`
- Current stale WIKI blob during recheck: `fee0e1a15243904dbeb46254878ade4650a8e1f6`
- Claim-ledger blob: `8135794d6f0b22da6b760bf6234bb8e1cae795fb`
- MV3 summary blob: `2bb4b34e499642dfdf8ceb13e2f6351ff6e5cc6d`

## Confirmed defect

The canonical ledger and tracked `mv3_summary.json` bind exact values, but the remote public WIKI still says the underlying chi-square, ndf, and exact counts are unavailable or not reconstructable. It retains rounded-only `2.3%`, `22.3%`, and `68,269.4` summaries and asks readers to recover evidence already tracked.

The exact remote snapshot fails the new validator with status 1 and 12 findings:

- 7 missing exact public tokens;
- 5 stale absence-narrative occurrences.

## Exact tracked result

| Quantity | Exact value |
|---|---:|
| Selected-data B8 count | `7051 / 306745` |
| Selected-data B8 fraction | `0.02298651974767315` |
| Thresholded-MC B8 count | `55619 / 249484` |
| Thresholded-MC B8 fraction | `0.22293614019335908` |
| Pearson chi-square | `204808.2179684494` |
| Degrees of freedom | `3` |
| Chi-square / ndf | `68269.40598948313` |

Independent binary64 reconstruction used:

```text
mc_fraction_i = mc_count_i / 249484
expected_i = 306745 * mc_fraction_i
chi2 = sum((data_count_i - expected_i)^2 / expected_i)
ndf = 4 - 1
```

The reconstructed values exactly match the tracked summary.

## Candidate correction contract

A complete exact snapshot of the root WIKI was patched locally. The candidate:

1. reports exact B8 counts and fractions in the canonical results table;
2. reports exact Pearson chi-square, ndf, and chi-square/ndf;
3. states that fixed-source arithmetic is reproducible;
4. removes claims that exact counts/statistic provenance is absent;
5. updates MV3, Monte Carlo, PID, material-budget, and GAP-01 wording consistently;
6. retains `FLAWED` and `BLK-MV3-LEGACY-001`;
7. does not claim calibrated goodness-of-fit acceptance or B8 correction.

The candidate is `24,023` bytes with SHA-256 `89537456afc070e2aa39cd15ac9c91d55526d35f719d85e5fe55b178a2d45fec`. Its Markdown link-target sequence is unchanged at 44 internal/external targets. It is implementation-ready but was not published to remote `main` in this run.

## Reproducible gate

Added to remote `main`:

- `tools/audit/validate_wiki_mv3_summary.py`
- `tools/audit/render_wiki_mv3_summary_evidence.py`
- `tests/test_validate_wiki_mv3_summary.py`

Policy:

`WIKI_MV3_MUST_REPORT_EXACT_TRACKED_SUMMARY_WITH_FLAWED_BOUNDARY`

The validator requires exact-width `CL-019`, `CL-020`, and `CL-021` rows, independently reconstructs fractions and Pearson arithmetic, requires exact public tokens and the non-acceptance boundary, rejects stale absence narratives, records exact byte provenance, and returns status 0/1/2 for validated/flawed/malformed input.

## Validation

```text
python -m py_compile \
  tools/audit/validate_wiki_mv3_summary.py \
  tools/audit/render_wiki_mv3_summary_evidence.py \
  tests/test_validate_wiki_mv3_summary.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_wiki_mv3_summary.py -q

5 passed in 0.04s
```

Additional checks:

- candidate direct validator: `VALIDATED`, zero issues;
- exact remote/pre-change negative control: status 1, `FLAWED`, 12 findings;
- SVG XML parse: PASS;
- JSON parse: PASS;
- candidate/pre-change Markdown link-target sequence: unchanged, 44 targets;
- maximum changed Python line lengths: 93, 98, and 93 characters;
- Python `3.13.5`; pytest `9.0.2`.

## Transport outcome

A one-time, fail-closed GitHub Actions transport was staged and retriggered on `main`. No workflow-generated follow-up commit was observed, and the remote WIKI blob remained unchanged. The workflow must be removed rather than left as an unvalidated recurring mutation path. No claim is made that the candidate WIKI was delivered.

## Scientific boundary

This validates documentation rules and fixed-source arithmetic only. It does not establish correct Geant4 geometry/material modelling, matched trigger/selection transfer, calibrated gain/response closure, covariance-aware inference, a meaningful p-value, detector/model systematic uncertainty, an accepted B8 correction, calibration, or detector performance.

The MV3 result remains `FLAWED` under `BLK-MV3-LEGACY-001`. The next session must publish the exact candidate through a byte-safe complete-file write, rerun this validator against remote bytes, run the WIKI front-door validators and link checker, and require zero issues before closing the public synchronization unit.
