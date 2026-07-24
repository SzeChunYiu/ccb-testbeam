# CL-022 early-peak/C12 claim audit

## Scope

This audit reviews the canonical `CL-022` anomaly claim against the exact
repository report and machine-readable MV6 summary. It distinguishes repository
facts, truth-labelled simulation counts, independently calculated intervals,
and unresolved transfer to real beam data.

Policy: `SEPARATE_EARLY_PEAK_RATE_FROM_C12_COMPOSITION`.

## Confirmed defects

The former `CL-022` row had 39 columns under the canonical 43-column schema, so
its late fields were positionally unsafe. It also named a “C12 anomaly
fraction” while storing numerator/denominator `283/87555`. Those counts describe
the total early-peak morphology rate among all selected MC tracks, not a
C12-specific rate.

The former row also cited two nonexistent paths:

- `scripts/mv6_anomaly.py`;
- `reports/mv6_representation_1782678362/results.json`.

The actual tracked sources are:

- `scripts/mv6_representation_study.py`;
- `reports/mv6_representation_1782678362/mv6_representation_summary.json`;
- `reports/mv6_representation_1782678362/REPORT.md`.

The README repeated the ambiguous phrase and still advertised numerical Rmax as
`VALIDATED`, contradicting exact-width `CL-010`, which withholds the value.

## Source-backed quantities

The exact MV6 summary records 87,555 truth-labelled MC tracks and 283
`early_peak` tracks. No `low_area` tracks are present in the morphology-count
object. The selected early-peak class contains 156 C12-labelled tracks, while
the full sample contains 7,302 C12-labelled tracks.

These are three different binomial quantities:

| Quantity | Numerator / denominator | Estimate | Wilson 95% interval | Meaning |
|---|---:|---:|---:|---|
| Total early-peak rate | 283 / 87,555 | 0.323225% | 0.287745–0.363065% | Rate among all selected truth-labelled MC tracks |
| C12 share of early-peak class | 156 / 283 | 55.1237% | 49.2989–60.8113% | Species composition inside the selected MC class |
| Early-peak rate within C12 | 156 / 7,302 | 2.13640% | 1.82905–2.49408% | Rate among C12-labelled MC tracks |

Wilson intervals were calculated directly from the source counts with
`z = 1.959963984540054`; no detector-data interval or data species identity is
inferred.

## Correction

`CL-022` is now exactly 43 columns and names the stored quantity
“Early-peak anomaly fraction in truth-labelled MC.” It records the source counts,
Wilson interval, correct source paths, source commit, and a note separating all
three proportions. Status remains `TRUTH_LEVEL_MC_ONLY` and the unresolved
matched data/MC closure is explicit.

The README now:

- withholds numerical Rmax pending `S-STAT-003`;
- reports the early-peak rate with its Wilson interval;
- reports the C12 composition separately as `156/283`;
- states that real-data identity remains unvalidated.

`scripts/sync_c12_public_claims.py` and its regression were updated so check mode
recognizes the current README rather than obsolete table snippets.

The repository-wide schema audit consequently advances from 7/26 to 8/26
exact-width rows. Eighteen rows remain malformed and withheld.

## Validation

```text
python -m py_compile \
  tools/audit/validate_claim_ledger_cl022.py \
  scripts/sync_c12_public_claims.py \
  tests/test_validate_claim_ledger_cl022.py \
  tests/test_sync_c12_public_claims.py

python -m pytest \
  tests/test_validate_claim_ledger_cl022.py \
  tests/test_sync_c12_public_claims.py -q

19 passed in 0.06s
```

Additional checks:

- direct corrected-state validator: `VALIDATED`, zero issues;
- exact former 39-column row: status 1, `LEDGER_ROW_WIDTH_MISMATCH`;
- README synchronization check: zero pending replacements;
- validation JSON parsed;
- both SVG files parsed as XML;
- changed Python files compile and contain no line longer than 100 characters;
- exact local report Git blob matches `2c531703755b28a0c576e978531b81374edf8ab4`;
- exact local summary Git blob matches `26c187cbe05d8dadbe588c6ed9062d25658a80a9`;
- authenticated GitHub review confirms source-script blob
  `f965823518b22908f3e8974f280bff5c970368d0` at source commit
  `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`.

## Remaining flaw and scientific boundary

This repair does not identify the related data anomaly as C12, measure anomaly
detection efficiency or false-positive rate, or validate a data veto. The
matched data/MC closure under `AUD-ANOM-001` remains open.

The academic Chapter 9 remains source-inconsistent beyond its corrected
abstract: it describes an eight-dimensional/K=7 BIC-selected GMM and 99.7% PCA
coverage, while the tracked MV6 producer uses K=4 on the first four PCs and the
summary records 82.188% cumulative variance at eight PCs. That larger chapter
rewrite is registered as follow-up work and is not silently treated as resolved
by this claim-row correction.
