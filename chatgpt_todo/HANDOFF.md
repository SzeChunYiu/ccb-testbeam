# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T140810Z`
- **Task:** `AUD-LEDGER-001`
- **Unit:** source-backed reconstruction of MV6 PCA claim rows `CL-023` and `CL-024`
- **Initial remote `main`:** `c9c432f5b96eae0fd11550be7833f18221019b1a`
- **Validated delivery head before this handoff:** `9eb46b098beda92b705db12c930dec13c5cf6bba`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** this two-row reconstruction unit is `VALIDATED`; ledger-wide `AUD-LEDGER-001` and anomaly transfer `AUD-ANOM-001` remain `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent history, repository
metadata, open pull requests, PR #868, commit status, mandatory
`chatgpt_todo/` coordination files, the claim ledger and schema gate, the tracked
MV6 producer, exact summary JSON, historical report, Chapter 6, and the previous
Chapter 9 correction. The scientific sequence was based on remote head
`c9c432f5b96eae0fd11550be7833f18221019b1a`.

No non-session commit appeared during the focused write sequence. The connector
returned successful direct-main commit SHAs rather than conventional textual
`git push` stdout. Remote history was re-read after publication.

PR #868 remains closed, unmerged and non-mergeable and was not modified. No
status checks were attached to the initial commit, so no GitHub Actions success
is inferred.

## Confirmed defects

The pre-change claim-ledger blob
`e489555f3a520c7cc64b8a7d858a0e93622b9de6` contained only 37 columns for
`CL-023` and `CL-024`. Their late fields were therefore shifted and withheld by
the canonical 43-column gate. The rows also published superseded cumulative PCA
fractions `0.89` and `0.997` while citing a noncanonical
`scripts/mv6_pca.py` / `results.json` chain.

The tracked source chain is:

- producer `scripts/mv6_representation_study.py`, blob
  `f965823518b22908f3e8974f280bff5c970368d0`;
- summary `reports/mv6_representation_1782678362/`
  `mv6_representation_summary.json`, blob
  `26c187cbe05d8dadbe588c6ed9062d25658a80a9`;
- report `reports/mv6_representation_1782678362/REPORT.md`, blob
  `2c531703755b28a0c576e978531b81374edf8ab4`;
- producing commit recorded by the source chain:
  `3c5ff5cf587c8ca9cefda20cb220ba29effd2170`.

The producer subtracts the 350-ADC pedestal, peak-normalizes each 18-sample
synthetic waveform, fits ten PCA components, and uses a four-component GMM on
the first four PCs. The summary records seed 42, 220,000 scanned events and
87,555 charged B-arm MC tracks.

## Independent reconstruction

The first eight explained-variance ratios are:

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

The eight-component reconstruction exactly matches the summary's recorded
`pca_cumulative_at_8` field.

## Delivered changes

Corrected `docs/claim_ledger.csv` so both records have exactly 43 columns:

- `CL-023` = `0.7254602133437841`, superseding `0.89`;
- `CL-024` = `0.821883926913117`, superseding `0.997`.

Both rows now use truth type `synthetic_waveform_mc`, status
`TRUTH_LEVEL_MC_ONLY`, canonical source paths, the exact producing commit,
220,000 scanned events, 87,555 MC tracks, and explicit wording that these are
fixed synthetic-waveform outputs rather than beam-data PCA or uncertainty
claims.

The corrected ledger was committed as
`bf584eec7d64c6f78cd782b7b1ff84387d0f2bfe`, Git blob
`d33180f144cca10a6e310b3e89b5ab1d065d7e66`, SHA-256
`3a08d0d561de0ad11f2bbbf4a6cc1284af2315e30bbb3ded39be308b6d5125ff`.

Added:

- `tools/audit/validate_mv6_pca_claim_rows.py`;
- `tests/test_validate_mv6_pca_claim_rows.py`;
- `docs/validation/mv6_pca_claim_rows_audit.md`;
- `docs/validation/mv6_pca_claim_rows_validation.json`;
- `docs/validation/mv6_pca_claim_rows.svg`;
- `chatgpt_todo/archive/2026-07-24T140810Z_AUD-LEDGER-001_MV6_PCA_CLAIMS.md`.

Updated cumulative schema evidence:

- `docs/validation/claim_ledger_schema_audit.md`;
- `docs/validation/claim_ledger_schema_validation.json`;
- `docs/validation/claim_ledger_schema.svg`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this handoff.

The ledger now has 10 exact-width rows and 16 malformed rows. The global schema
validator correctly remains `FLAWED`/status 1 because the remaining rows are
still withheld from field interpretation.

Policies:

- `MV6_PCA_CLAIMS_MUST_MATCH_TRACKED_SYNTHETIC_WAVEFORM_OUTPUT`;
- `NO_FIELD_INTERPRETATION_FROM_WIDTH_MISMATCHED_ROWS`.

## Validation

Executed locally:

```text
PYTHONPATH=. python -m py_compile \
  tools/audit/validate_mv6_pca_claim_rows.py \
  tests/test_validate_mv6_pca_claim_rows.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv6_pca_claim_rows.py -q

7 passed in 1.39s
```

The focused regression covers valid rows, the superseded values, row-width
failure, corrupted summary cumulative values, missing producer normalization,
machine-readable JSON/SVG generation, and invalid UTF-8 status-2 handling.
Validation JSON parsed, both SVG files parsed as XML, and changed Python files
met the repository's 100-character line convention.

The exact pre-change ledger reconstruction matched SHA-256
`9a099f76609c51b7400c8615a46c5e873058ac00e0fa9e3a0e2877a1d5e5db5c`.
The exact summary reconstruction matched SHA-256
`62c574fad724688e1fb9d455aec14ea273d089708c5593a2324e38e3eadc3be4`.

The runtime could not resolve `github.com` for a clone. Complete producer bytes
were inspected through authenticated GitHub full-file and ranged reads; local
executable validation used an exact PCA/GMM contract excerpt. This scope is
explicit in the machine-readable record.

Full repository pytest, ruff, ROOT processing, PCA reruns, repository-wide link
checking and GitHub Actions were not run.

## Direct-main commit sequence

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
11. `9eb46b098beda92b705db12c930dec13c5cf6bba` — `docs(audit): archive MV6 PCA ledger reconstruction`

Every commit is a sequential descendant of the initial main head. A post-write
history read must confirm this handoff publication as the remote head.

## Scientific boundary and next work

This unit does not rerun ROOT processing, PCA, waveform simulation or beam-data
analysis. It does not validate confidence intervals, data/MC transfer,
individual-PC physical interpretations, autoencoder comparisons, calibration or
detector performance.

Chapter 6 still contains a full PCA spectrum, sample-size statements, named PC
interpretations and method comparisons that do not match the tracked MV6
producer and summary. The next source-governance unit should correct Chapter 6
and add an exact-current validator. `AUD-ANOM-001` still requires the
preregistered matched data/MC closure.

`AUD-LEDGER-001` remains `PARTIAL`: 16 of 26 rows remain malformed and must be
reconstructed from exact source evidence before late fields may be interpreted.

`SESSION_LOG.md` was not replaced because the connector provides whole-file
replacement rather than byte-safe append and only paged/truncated current
snapshots were available. Replacing the append-only file without a complete
byte-identical reconstruction could destroy prior provenance. The immutable
archive and this handoff contain the complete session record.
