# Immutable Scientific-Review Record — Chapter 9 MV6 Source Sync

## Session identity

- **UTC stamp:** `2026-07-24T132532Z`
- **Task:** `AUD-ANOM-001`
- **Unit:** reconcile Chapter 9 with the tracked MV6 producer and summary
- **Initial remote `main`:** `a4420ed5ecb51074bff68d9e0d2265e6b6bee978`
- **Validated delivery head before archive:** `84c5a09c3a58f16806c8e9f0e94873abab410e34`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** this documentation/method-traceability unit is `VALIDATED`; matched data/MC anomaly closure remains `PARTIAL`

## Start-of-run and concurrency review

Authenticated GitHub reads inspected the latest `main` history, repository
permissions, status/workflow attachments, PR #868, mandatory `chatgpt_todo/`
records, the claim ledger, the academic Chapter 9, the tracked MV6 producer,
summary and historical report. No concurrent non-session commit appeared during
the focused write sequence. A conventional local clone was unavailable because
the runtime could not resolve `github.com`; reads and direct-main writes used
the authenticated GitHub connector.

PR #868 remained closed, unmerged and non-mergeable and was not modified. No
status checks or workflow runs were attached to the initial head.

## Confirmed scientific and traceability defects

The pre-change Chapter 9 blob
`409abcdefe686edf9c2ac5c5c6ba02aae9c9a331` described:

- an eight-dimensional GMM input;
- 99.7% cumulative PCA variance at eight components;
- K = 7 selected by a BIC scan;
- a 127-iteration convergence result;
- named physical meanings for every PC;
- alternative anomaly-detector benchmarks;
- manual adjudication and inter-reviewer studies;
- SRIM/Birks tables, production-rate estimates, optical calculations, and veto
  performance.

The tracked producer blob
`f965823518b22908f3e8974f280bff5c970368d0` instead fits PCA to
peak-normalised 18-sample waveforms, then fits
`GaussianMixture(n_components=4, random_state=42, n_init=3)` to the first four
PCs. It runs no BIC scan. The tracked summary blob
`26c187cbe05d8dadbe588c6ed9062d25658a80a9` records cumulative variance
0.745517570480533 at four PCs and 0.821883926913117 at eight PCs.

The former chapter therefore mixed repository evidence, unsupported
reconstructions, and hypotheses as if they were one validated analysis.

## Source-backed counts and independent calculations

Tracked fixed-output facts:

- events scanned: `220000`;
- retained charged B-arm tracks: `87555`;
- early-peak tracks: `283`;
- low-area tracks: `0`;
- carbon-12-labelled tracks: `7302`;
- carbon-12-labelled early-peak tracks: `156`.

Independent Wilson 95% intervals:

| Quantity | Counts | Estimate | Interval |
|---|---:|---:|---:|
| Early-peak rate among retained MC tracks | 283 / 87555 | 0.003232254011764034 | [0.002877452112691542, 0.003630645177388446] |
| Carbon-12 share of early-peak class | 156 / 283 | 0.5512367491166078 | [0.4929885941153212, 0.6081125511627331] |
| Early-peak rate within carbon-12 | 156 / 7302 | 0.021364009860312245 | [0.018290520583369645, 0.024940838952822255] |

These are different binomial estimands and cannot be interchanged. The
historical producer's `binom_ci` returns a normal-approximate half-width, not
Wilson lower and upper bounds.

## Delivered changes

Updated:

- `docs/academic_chapters/09_anomaly_id.md`;
- `chatgpt_todo/ACTIVE_TASK.md`.

Added:

- `tools/audit/validate_chapter9_mv6_claims.py`;
- `tests/test_validate_chapter9_mv6_claims.py`;
- `docs/validation/chapter9_mv6_claims_audit.md`;
- `docs/validation/chapter9_mv6_claims_validation.json`;
- `docs/validation/chapter9_mv6_claims.svg`;
- this immutable archive.

The corrected chapter documents the actual selection, waveform model, taxonomy,
PCA and GMM configuration; separates cluster purity from selected-class
composition; reports independent confidence intervals; quarantines unsupported
method and physical-performance claims; and specifies the matched data/MC
closure required by `AUD-ANOM-001`.

Policy: `CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY`.

## Validation

```text
python -m py_compile \
  tools/audit/validate_chapter9_mv6_claims.py \
  tests/test_validate_chapter9_mv6_claims.py

python -m pytest tests/test_validate_chapter9_mv6_claims.py -q

6 passed in 1.15s
```

The focused regression covers a valid source contract, the former K=7/BIC
claim, the former 99.7% claim, a changed summary PCA value, missing producer
contract statements, machine-readable status-1 output, and controlled invalid
UTF-8 status-2 failure. JSON parsing, SVG XML parsing, and changed-Python
line-length checks passed.

Exact committed blobs re-fetched from `main`:

- corrected chapter: `c54753c58b0eb9e68a7e2b908d4e31310b0c991f`;
- validator: `fbb9d9423ad2fc6130656d6cdfa11345e738f095`;
- regression test: `ebc61f19916baf8a9dee1a86aa7deb9b08ecb259`.

The corrected chapter and validator matched the locally validated candidates.
The complete committed test file was re-fetched and its Git blob retained as the
canonical artifact identity. ROOT processing, model reruns, full repository
pytest, ruff, link checking, and GitHub Actions were not run.

## Direct-main commit sequence before archive

1. `b646af9dcc6e4af719c7773cc30135e9e5a5e3b2` — `fix(docs): align Chapter 9 with tracked MV6 method`
2. `ed37eb208671a93658204d80d04a96043c61719c` — `feat(audit): validate Chapter 9 MV6 source claims`
3. `ca4b2391180a8998a6fe701fb1f9bdd6b18490bc` — `test(audit): cover Chapter 9 MV6 claim gate`
4. `0954e2453559ac54fd0f190c9ffac0550260a6d8` — `docs(validation): record Chapter 9 MV6 claims audit`
5. `985c79039feb50153df162c5792f2930824ef1e4` — `docs(validation): add Chapter 9 MV6 validation record`
6. `45ba154e65dcc92b26e8d9556587c39428b12633` — `docs(validation): visualize Chapter 9 MV6 correction`
7. `57e3e24ab8d1984cf67f9383cdb90a6910b326f8` — `docs(audit): track validated Chapter 9 MV6 correction`
8. `4ea6dbff80701aeafba66051135dd457cadf9295` — `docs(validation): correct Chapter 9 artifact provenance`
9. `84c5a09c3a58f16806c8e9f0e94873abab410e34` — `docs(validation): bind Chapter 9 evidence to committed blobs`

The connector returns successful commit SHAs rather than conventional textual
`git push` output. Remote history was re-read and confirmed this consecutive
sequence on `main` before the archive write.

## Scientific boundary and next work

This unit does not identify the beam-data anomaly as carbon-12, establish an
independent data species tag, measure efficiency or false-positive rate,
validate a veto, quantify generator/detector-model uncertainty, or regenerate
the ROOT analysis.

`AUD-ANOM-001` remains `PARTIAL`. The next scientific unit is the preregistered
matched data/MC closure in `docs/validation/C12_DATA_MC_CLOSURE_SPEC.md`.
Ledger-wide `AUD-LEDGER-001` also remains `PARTIAL`; malformed `CL-023` and
`CL-024` should be reconstructed from the exact PCA source values, and Chapter
6/public summaries should be checked for superseded 0.89/0.997 claims.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file
replacement rather than a byte-safe append operation and a complete current byte
snapshot was not safely reconstructed. Replacing the append-only log could
destroy prior provenance. This immutable archive and the latest handoff retain
the complete run record.
