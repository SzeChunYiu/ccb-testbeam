# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T190317Z`
- **Task:** `AUD-WIKI-003`
- **Unit:** public WIKI canonical-results synchronization to exact-width claim-ledger records
- **First observed remote `main`:** `d34f99513550892e98f3e396a279952618f8623c`
- **Latest remote base before focused implementation:** `51b63d9ffad4c9eb9f95cbfbfe14516c1e5780f2`
- **Validated content/archive head before this handoff:** `de077272d9f4581c2261681e0f8e1dfba18d6c6c`
- **Destination:** direct sequential commits to `main`; no force-push, history rewrite, branch-only delivery, or PR transport
- **Acceptance:** canonical-results remediation unit `VALIDATED` / `COMPLETE`; repository-wide WIKI review remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected current `main`, recent history, repository instructions, the mandatory `chatgpt_todo/` records, the exact WIKI, the 43-field claim ledger and cumulative schema evidence, existing WIKI validators/tests, commit status metadata, and PR #868. Concurrent MV4-ledger and amplitude-evidence sessions advanced non-overlapping files while this unit was active; their changes were preserved.

PR #868 was rechecked on 2026-07-24 and remained closed, unmerged, and non-mergeable. It was not modified.

## Confirmed defect

The exact pre-remediation WIKI blob `9d8110893adeae482b2439c4187b53f94174a55e` (21,368 bytes; SHA-256 `baaa9dbd3585870c7d9c0807493e9afce81f9767f3be68d581502d62496c59d4`) produced 31 findings against 11 exact-width canonical claim bindings:

- `CL-002`, `CL-004`, and `CL-006` source-absent timing values were published as accepted measurements;
- MV0 was given an unsupported statistical uncertainty and `VALIDATED` status;
- legacy truth-MC PID was promoted above its `GATED` leakage-risk state;
- the `FLAWED` MV3 legacy profile record was absent;
- MV4 toy pulls were described as detector validation/tension;
- the analytic CFD20/timewalk source was labelled as ML;
- the public legend lacked `REVIEW` and the fixed MV6 synthetic-MC PCA values were missing.

## Correction and code-to-claim traceability

Added `tools/audit/validate_wiki_canonical_results.py` v1.0.0 with policy:

`WIKI_CANONICAL_RESULTS_MUST_MATCH_EXACT_WIDTH_LEDGER_ROWS`

The validator checks exact row width, current value or explicit withholding, statistical/systematic uncertainty support, truth type, canonical status, public legend membership, and the fixed source-backed PCA correction for:

`CL-002`, `CL-004`, `CL-006`, `CL-011`, `CL-013`, `CL-017`, `CL-022`, `CL-021`, `CL-007`, `CL-008`, and `CL-009`.

Added focused tests and rebound the exact-current WIKI integration test to this validator. Updated `WIKI.md` so the canonical front door and repeated high-level summaries now:

- withhold B6, combined-stave, and covariance values under `BLK-MV4-LEGACY-001`;
- show MV0 as a `GATED` data/MC calibration proxy with a 28 ADC/MeV heuristic envelope and no statistical CI;
- retain legacy truth-MC PID as `GATED`;
- label the MV3 profile statistic a `FLAWED` non-reconstructable legacy diagnostic;
- classify MV4 raw and corrected pulls as `GATED` toy-digitizer diagnostics;
- identify the historical timing verdict as analytic `REVIEW`, not ML;
- record MV6 synthetic-waveform PCA as 72.546% at three PCs and 82.188% at eight PCs;
- preserve the Rmax, duplicate-readout, saturation, and anomaly scientific boundaries.

## Exact validation

Executed locally on exact remote WIKI bytes and exact 43-field binding rows fetched from current `main`:

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

Measured validation state:

- pre-remediation validator: exit 1, `FLAWED`, 31 findings;
- post-remediation validator: exit 0, `VALIDATED`, zero findings;
- current WIKI Git blob: `fee0e1a15243904dbeb46254878ade4650a8e1f6`;
- current WIKI bytes: `23355`;
- current WIKI SHA-256: `c0e8c8f7aa0c6b8f024ea9821dcb046b77376aecc95c81301afaf40248417680`;
- current ledger Git blob: `bb552aa5ed70e7d81dcda888c5aa61402c01e03c`;
- current ledger bytes: `21486`;
- current ledger SHA-256: `e7e560a66df43a9cacdf5041361aaffa0995927144adae3701b5c60e0433c26b`;
- cumulative schema evidence: 26/26 rows at exactly 43 fields;
- maximum changed Python line lengths: 96, 98, and 93 characters;
- validation JSON parsed and SVG XML parsed.

The exact full ledger could not be downloaded as one local file through the available connector path. The executable validation used exact 43-field binding rows fetched from current `main`; independent cumulative evidence establishes 26/26 exact-width rows. This limitation is explicit in the machine-readable record.

## Evidence

- `docs/validation/wiki_canonical_results_audit.md`
- `docs/validation/wiki_canonical_results_validation.json`
- `docs/validation/wiki_canonical_results.svg`
- `chatgpt_todo/archive/2026-07-24T190317Z_AUD-WIKI-003_CANONICAL_RESULTS_SYNC.md`

The SVG is explicitly documentation/provenance evidence and not detector data.

## Direct-main commit sequence

- `9cbd0666d8c1a54c33ff02666d0ab54d3ddb8b9b` — `feat(audit): validate WIKI canonical result claims`
- `7ad1798c856f75d021817113c8e8df166ecd53c3` — `test(audit): cover WIKI canonical result drift`
- `e215a4cd44ca6ed2eff3ec45921fcc72faa1e115` — `docs(wiki): synchronize public claims with canonical ledger`
- `64b59439d65505f7fc69bc5cdd990b796aad0be0` — `test(wiki): bind current front door to canonical ledger validator`
- `0405d85412cd1b036082e9d3a99ca6966f61bdaa` — `docs(validation): record WIKI canonical claim remediation`
- `8e0275beccd61aa9626b2cd988d1c381e8a8810c` — `docs(validation): explain WIKI canonical claim remediation`
- `09a735ed8e8bcc12c27e83415ac8c252b7457813` — `docs(validation): visualize WIKI canonical claim remediation`
- `9cda31bd5b0c54dc5b767573264ab813d029684f` — remove unused first remediation workflow
- `4518ade7192d3236fb80753d719bc7b72ac1f5ba` — remove unused retry workflow
- `c76c254dd167beab24aaee813a59dc28d8aba84e` — complete active-task record
- `de077272d9f4581c2261681e0f8e1dfba18d6c6c` — immutable session archive

The GitHub contents API returned each commit SHA as the push result. Post-write history reads confirmed that these commits were present on remote `main`; conventional textual `git push` stdout is not exposed by this connector.

Two one-time workflow commits (`d91e0313...` and `e5a2144c...`) were created to test whether contents-API writes would trigger Actions. They produced no remediation commit and were removed. No CI success is inferred from them.

## Scientific boundary and unresolved risks

This run did not create or validate a B6 timing resolution, combined-stave timing resolution, covariance estimate, precision gain calibration, beam-data PID performance, reconstructable MV3 goodness-of-fit statistic, real-data species identification, ROOT output, or simulation result.

One residual WIKI prose item remains outside the validated canonical table: GAP-01 still uses a coarse MV3 geometry-failure shorthand based on the non-reconstructable legacy statistic. The next focused documentation task should synchronize that line to the exact `CL-021` boundary.

Full repository pytest, ruff, ROOT processing, simulation reruns, repository-wide broken-link checking, and GitHub Actions were not run. No broad CI success is claimed.

## Coordination limitation

`SESSION_LOG.md` was not replaced because the connector exposes whole-file replacement but no byte-safe append operation, and only truncated/paged views of the concurrently changing append-only file were available. Replacing it from a partial reconstruction could destroy prior provenance. The immutable archive and this handoff contain the complete session record.

Long aggregate `BACKLOG.md`, `MASTER_INDEX.md`, `CLAIM_EVIDENCE_MATRIX.md`, `CODE_RESULT_MAP.md`, `STUDY_REVIEW_LEDGER.md`, `VISUALIZATION_MATRIX.md`, and `BLOCKERS.md` were likewise not replaced from partial snapshots. The stable task ID, evidence paths, residual, and acceptance state are fully recorded here and in `ACTIVE_TASK.md`.

## Next validated unit

`AUD-WIKI-004`: replace the GAP-01 MV3 shorthand with the exact `CL-021` limitation, add it to the fail-closed WIKI validator, run focused tests and a repository-wide link check, and update the aggregate audit ledgers through a complete checked-out snapshot or byte-safe append mechanism.
