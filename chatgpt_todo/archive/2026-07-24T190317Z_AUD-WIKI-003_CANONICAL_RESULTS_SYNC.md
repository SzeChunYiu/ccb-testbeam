# Immutable Session Record — AUD-WIKI-003

## Identity

- UTC session stamp: `2026-07-24T190317Z`
- Owner: scheduled scientific-review session
- First observed remote `main`: `d34f99513550892e98f3e396a279952618f8623c`
- Latest remote base before focused implementation: `51b63d9ffad4c9eb9f95cbfbfe14516c1e5780f2`
- Coordination head before this archive: `c76c254dd167beab24aaee813a59dc28d8aba84e`
- Destination: direct commits to `main`; no force-push or history rewrite

## Repository and concurrency review

The run inspected current `main`, recent commits, repository instructions and coordination files, the exact WIKI, the complete 43-field claim schema and bound claim rows, the cumulative 26/26 exact-width ledger evidence, existing WIKI validators/tests, workflow status metadata, and PR #868. Concurrent MV4-ledger and amplitude-evidence sessions advanced non-overlapping files while this unit was in progress; their changes were retained.

PR #868 was rechecked and remained closed, unmerged, and non-mergeable. It was not modified.

## Confirmed defects

Exact pre-remediation WIKI bytes (`9d8110893adeae482b2439c4187b53f94174a55e`, 21,368 bytes, SHA-256 `baaa9dbd3585870c7d9c0807493e9afce81f9767f3be68d581502d62496c59d4`) produced 31 fail-closed findings against exact ledger bindings:

- source-absent B6, combined-stave, and covariance values were published as accepted;
- MV0 had an unsupported statistical uncertainty and `VALIDATED` status;
- legacy truth-MC PID was upgraded above its `GATED` state;
- the canonical `FLAWED` MV3 diagnostic was absent;
- MV4 toy pulls were presented as detector validation/tension;
- an analytic CFD20/timewalk source was labelled as ML;
- the `REVIEW` status and fixed MV6 synthetic-MC PCA values were absent.

## Correction

Added `tools/audit/validate_wiki_canonical_results.py` v1.0.0 with policy `WIKI_CANONICAL_RESULTS_MUST_MATCH_EXACT_WIDTH_LEDGER_ROWS`. It validates 11 canonical WIKI rows against exact 43-field ledger records, including values, missing-value withholding, statistical/systematic uncertainty support, truth type, status vocabulary, and fixed PCA correction text.

Added focused unit tests and rebound the exact-current WIKI integration test to the canonical-results validator. Updated `WIKI.md` to:

- withhold `CL-002`, `CL-004`, and `CL-006` under `BLK-MV4-LEGACY-001`;
- classify MV0 as a `GATED` data/MC calibration proxy with no statistical CI;
- retain legacy truth-MC PID as `GATED`;
- represent `CL-021` as a `FLAWED` legacy profile diagnostic;
- classify MV4 raw/corrected pulls as `GATED` toy diagnostics;
- identify the timing verdict as analytic `REVIEW`, not ML;
- record MV6 synthetic-waveform PCA as 72.546% at three PCs and 82.188% at eight PCs;
- propagate the same boundaries through timing, energy, PID, MC-validation, and open-question summaries.

Added reproducible Markdown, JSON, and SVG evidence under `docs/validation/`. The visual is explicitly documentation/provenance evidence, not detector data.

## Validation

Executed locally against exact remote WIKI bytes and exact extracted 43-field binding rows from current `main`:

```text
python -m py_compile \
  tools/audit/validate_wiki_canonical_results.py \
  tests/test_validate_wiki_canonical_results.py \
  tests/test_wiki_claim_front_door_current.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_wiki_canonical_results.py \
  tests/test_wiki_claim_front_door_current.py -q

8 passed in 1.14s
```

Additional checks:

- pre-remediation validator: exit 1, `FLAWED`, 31 findings;
- post-remediation validator: exit 0, `VALIDATED`, zero findings;
- exact current WIKI blob: `fee0e1a15243904dbeb46254878ade4650a8e1f6`;
- exact current WIKI: 23,355 bytes; SHA-256 `c0e8c8f7aa0c6b8f024ea9821dcb046b77376aecc95c81301afaf40248417680`;
- exact current ledger blob: `bb552aa5ed70e7d81dcda888c5aa61402c01e03c`;
- current ledger: 21,486 bytes; SHA-256 `e7e560a66df43a9cacdf5041361aaffa0995927144adae3701b5c60e0433c26b`;
- cumulative schema evidence: 26/26 rows at exactly 43 fields;
- changed Python maximum line lengths: 96, 98, and 93 characters;
- validation JSON parsed and SVG XML parsed.

The exact full ledger could not be downloaded as one local file through the available connector path. Validation therefore used exact 43-field rows fetched from current `main`, while the independent cumulative schema evidence established 26/26 exact-width rows. This scope is recorded in the machine-readable evidence.

## Direct-main commits

- `9cbd0666d8c1a54c33ff02666d0ab54d3ddb8b9b` — `feat(audit): validate WIKI canonical result claims`
- `7ad1798c856f75d021817113c8e8df166ecd53c3` — `test(audit): cover WIKI canonical result drift`
- `e215a4cd44ca6ed2eff3ec45921fcc72faa1e115` — `docs(wiki): synchronize public claims with canonical ledger`
- `64b59439d65505f7fc69bc5cdd990b796aad0be0` — `test(wiki): bind current front door to canonical ledger validator`
- `0405d85412cd1b036082e9d3a99ca6966f61bdaa` — `docs(validation): record WIKI canonical claim remediation`
- `8e0275beccd61aa9626b2cd988d1c381e8a8810c` — `docs(validation): explain WIKI canonical claim remediation`
- `09a735ed8e8bcc12c27e83415ac8c252b7457813` — `docs(validation): visualize WIKI canonical claim remediation`
- `9cda31bd5b0c54dc5b767573264ab813d029684f` — remove unused first workflow
- `4518ade7192d3236fb80753d719bc7b72ac1f5ba` — remove unused retry workflow
- `c76c254dd167beab24aaee813a59dc28d8aba84e` — complete active-task record

Two one-time workflows (`d91e0313...` and `e5a2144c...`) were created while testing whether contents-API pushes triggered Actions. They did not produce the remediation commit and were removed. No CI success is inferred from them.

## Scientific boundary and residuals

No detector data, ROOT output, simulation, calibration, uncertainty estimate, or performance result was generated. The corrected public table does not establish a B6 or combined timing resolution, covariance, precision gain, beam-data PID result, reconstructable MV3 goodness-of-fit statistic, or data species identity.

A residual prose issue remains outside the validated canonical table: GAP-01 still uses a coarse MV3 geometry-failure shorthand based on the unreconstructable legacy statistic. A separate focused documentation task should synchronize that line to `CL-021`.

`SESSION_LOG.md` was not replaced in this run because the connector exposes whole-file replacement but not byte-safe append, and only truncated/paged representations of the concurrent append-only file were available. Replacing it from a partial reconstruction could destroy earlier provenance. This immutable archive and the latest handoff retain the complete run.
