# AUD-TIMING-003-R1 — real-data CFD production safeguards

## Session

- **Stamp:** `2026-07-26T190253Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `be97e1a1e77de3bba6305f28802d1c876d2d1605`
- **Trigger:** PR #939 merged the real-data CFD study after current-main audits had already demonstrated event-identity, residual-visualization, and individual-stave-inference defects.
- **Policy:** `REAL_DATA_CFD_REQUIRES_COMPOSITE_EVENT_KEYS_AND_PAIR_ONLY_INFERENCE`
- **Acceptance:** focused software remediation `VALIDATED`; production result `PAIR_ONLY_PENDING_CONTENT_ADDRESSED_RERUN`.

## Repository facts reviewed

- PR #939 merged as `be97e1a1e77de3bba6305f28802d1c876d2d1605` on 2026-07-26.
- The merged producer pivoted and selected on `event_id` alone while processing multiple runs.
- It plotted uncentered residuals in a fixed `[-10,10] ns` range while labels used full-vector statistics.
- It reported `0.8985129399585929 / sqrt(2) = 0.6353445928285822 ns` as an individual-stave estimate.
- The merged Sample-II vector reported `n=1888`, pair `sigma68=0.8985129399585929 ns`, bootstrap interval `[0.8123935669551073,1.0723601562332614] ns`, tail fraction `0.15889830508474576`, and full RMS `9.69875913667869 ns`. These are retained as historical output, not revalidated values.

## Remediation

- Added `scripts/real_data_cfd_contract.py` with collision-safe `(run,event_id)` pivots, duplicate `(run,event_id,stave)` rejection, pair residual construction, median-centered visualization accounting, and a machine-readable pair-only inference contract.
- Updated `scripts/real_data_cfd_timing.py` to version `2.0.0`.
- Removed every pair-width-to-individual-stave conversion.
- Added full-range and core residual panels with q16/q84 and explicit displayed/underflow/overflow counts.
- Converted optional nonfinite fit diagnostics to JSON `null`; required metrics fail closed when nonfinite; output uses `allow_nan=False` and atomic text publication.
- Quarantined the merged `REPORT.md` and `result.json` without pretending to rerun ROOT data. Existing residual PNGs are explicitly unauthorized pending regeneration.

## Deterministic controls

1. Two runs reuse `EVENTNO=7`. Event-ID-only identity produces one identifier; `(run,event_id)` preserves two events and pair residuals `[1.0,1.0]`.
2. Residuals `[-100,-2,-1,0,1,2,100] ns` have median zero. Full-range underflow/overflow is `0/0`; a `[-5,5] ns` core view records underflow/overflow `1/1`; q16/q84 are `-5.9200000000000035/+5.9200000000000035 ns`.
3. `single_stave_inference.authorized=false`; individual-stave inference requires multi-pair or external-reference deconvolution, covariance/common-mode treatment, propagated uncertainty/sensitivity, and closure or injection recovery.

## Validation

```text
python -m py_compile \
  scripts/real_data_cfd_contract.py \
  scripts/real_data_cfd_timing.py \
  tests/test_real_data_cfd_production_safeguards.py \
  tools/audit/render_real_data_cfd_production_safeguard_evidence.py

PYTHONPATH=. pytest -q tests/test_real_data_cfd_production_safeguards.py

8 passed in 0.05s
```

Additional checks:

- evidence status `VALIDATED`, zero findings;
- strict JSON parse passed with no NaN tokens;
- SVG XML parse passed;
- changed Python lines are at most 95 characters;
- environment: Python 3.13.5, NumPy 2.3.5, pandas 2.2.3, Matplotlib 3.10.8, pytest 9.0.2;
- `uproot` and immutable LUNARC ROOT files were unavailable, so no producer execution or scientific rerun is claimed.

## Validated content identities

- contract SHA-256: `ae1386a80389787e41620e9351c72a1d091e22bba6c8969636014f67ccd320bd`
- producer SHA-256: `83422ea881d34c777928d30b548ad553c25b0ace3a324d6204246ade9f96825e`
- tests SHA-256: `e2306704e16ccf89a47a8f41d55902b48ff214d9e186cf8022b5015565415ef7`
- renderer SHA-256: `2a0b9db4445c65a2e9b6283f89b3083b74e3f8cfa49776caa1801c1a3eec2aff`
- quarantine report SHA-256: `79cbcb5bcb0cf480ed03bc52f7261bbd5f9d156c8d92ef78dfa722f89acef8c5`
- quarantine JSON SHA-256: `0eb33e7dd41f9a382aff3eacdf9f901de0c60f8c7301ef28cbac64c8ae1b6d02`
- validation JSON SHA-256: `cb93aa081cf08059bf551fa34943b90496e3ecf6611cd6ef15edb2ce2122e709`
- deterministic SVG SHA-256: `059254c36e2ff42171d3cbe16683feb8a0cbd75d2da30ac629094620818800af`

## Direct-main sequence before archive

- `af20aef19fac1d8a6ad99932e9b06fcd8cdee5a4` — task claim
- `609b3450888d508e14c9272deb8138f5ed233efd` — contract
- `b9e874a7ad2ca59a3f9199c46b12de420724c2f3` — initial producer remediation
- `b3d6ad7791f96fa6fd74e408dbb7e5830e4e3cb2` — initial tests
- `e2790c7227e309acef3a82d36094fdf9e089b544` — report quarantine
- `0614ae1e2f535e60df7e614348ff12e85dca6b72` — final producer safeguards
- `8e6af22c3981cd184787932852e6719cbc58fbdd` — final tests
- `f0476141e50be1d7a26933d028316380505958f1` — result quarantine
- `88114bb2d2d1110e10156c4ccc19e3f8588b6391` — initial renderer
- `5e0a728bc8e445eb9d8a1d1e679f3044a975cd99` — validation JSON
- `2ae162b24f42bc6807d8b80ffe25079f16554f5e` — deterministic renderer
- `335c2e1bc25d5f856fc525838654cc93e8f5a0e6` — SVG evidence
- `84d49de5d6f141fcc6e94e354c212902efa4d9eb` — audit report

## Unrun checks and scientific boundary

Repository-wide pytest/ruff, producer execution, ROOT hashing/processing, regeneration of the six study PNGs, full link checking, and GitHub Actions were not run. No event count, pair timing width, individual-stave resolution, channel map, CFD estimator performance, CL-002 status, or detector-performance result is accepted or changed by this software remediation.

A replacement production bundle must retain immutable ROOT paths, byte counts and SHA-256 digests, producer commit, exact command and environment, composite-key cardinality closure, regenerated artifacts and their hashes, and independent diagnostic review.

`SESSION_LOG.md` and the long aggregate ledgers were reviewed but could not be safely appended through the available connector: reads are paged/truncated while writes replace the complete file. This archive is the append-equivalent record; the mandatory synchronization gap is stated rather than falsely reported as complete.
