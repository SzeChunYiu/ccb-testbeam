# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T132532Z`
- **Task:** `AUD-ANOM-001`
- **Unit:** Chapter 9 MV6 producer/summary source synchronization
- **Initial remote `main`:** `a4420ed5ecb51074bff68d9e0d2265e6b6bee978`
- **Validated scientific delivery head before this handoff:** `b7f7584c6650dfcc349fc05df99fade1f511ee9f`
- **Destination:** direct sequential commits to `main`
- **Acceptance:** this Chapter 9 documentation/method-traceability unit is `VALIDATED`; matched data/MC anomaly closure remains `PARTIAL`

## Start-of-run, repository and concurrency review

Authenticated GitHub reads inspected current `main`, recent history, repository
permissions, status/workflow attachments, PR #868, repository coordination
instructions, mandatory `chatgpt_todo/` files, `docs/claim_ledger.csv`, the
academic Chapter 9, the tracked MV6 producer, exact summary and historical
report. The run based all writes on initial remote head
`a4420ed5ecb51074bff68d9e0d2265e6b6bee978`.

No concurrent non-session commit appeared during the focused sequence. A local
checkout could not reach GitHub because the runtime could not resolve
`github.com`; authenticated connector reads and contents-API writes were used.
The connector reports successful direct-main commit SHAs rather than
conventional textual `git push` stdout.

PR #868 remains closed, unmerged and non-mergeable and was not modified. No
status checks or workflow runs were attached to the initial head, so no GitHub
Actions success is inferred.

## Confirmed method and claim defects

The pre-change Chapter 9 blob
`409abcdefe686edf9c2ac5c5c6ba02aae9c9a331` described an eight-dimensional,
K=7, BIC-selected GMM with 99.7% cumulative variance at eight PCs, a
127-iteration convergence result, named physical meanings for every PC,
alternative-detector benchmarks, manual review, physical production and
stopping calculations, optical-response estimates, and veto-performance
numbers.

Those statements are not present in the tracked MV6 analysis contract. The
producer blob `f965823518b22908f3e8974f280bff5c970368d0`:

- selects charged B-arm tracks with summed deposited energy above 0.02 MeV;
- builds 18-sample synthetic waveforms with seed 42 and explicit historical
  response constants;
- peak-normalizes pedestal-subtracted waveforms;
- fits PCA with up to ten components;
- fits exactly one `GaussianMixture(n_components=4, random_state=42, n_init=3)`
  on the first four PCs;
- runs no BIC scan.

The exact summary blob `26c187cbe05d8dadbe588c6ed9062d25658a80a9`
records cumulative PCA variance 0.745517570480533 at four PCs and
0.821883926913117 at eight PCs. The former chapter mixed source-backed facts,
unsupported reconstructions and hypotheses as if they were one validated
study.

## Source-backed counts and calculations

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
historical producer's `binom_ci` returns a normal-approximate half-width rather
than Wilson lower and upper bounds.

The four recorded GMM clusters contain 22,345, 28,191, 14,587 and 22,432
tracks. Cluster 2 contains 282 of 283 early-peak tracks, but its carbon-12
truth-label purity is only 0.4450538150407897. Cluster dominant-species purity,
cluster morphology composition and carbon-12 share of the selected early-peak
class are separate quantities.

## Delivered changes

Updated:

- `docs/academic_chapters/09_anomaly_id.md`;
- `chatgpt_todo/ACTIVE_TASK.md`;
- this `HANDOFF.md`.

Added:

- `tools/audit/validate_chapter9_mv6_claims.py`;
- `tests/test_validate_chapter9_mv6_claims.py`;
- `docs/validation/chapter9_mv6_claims_audit.md`;
- `docs/validation/chapter9_mv6_claims_validation.json`;
- `docs/validation/chapter9_mv6_claims.svg`;
- `chatgpt_todo/archive/2026-07-24T132532Z_AUD-ANOM-001_CHAPTER9_MV6_SOURCE_SYNC.md`.

The corrected chapter documents the actual selection, waveform constants,
taxonomy, PCA and GMM configuration, separates the three denominators, reports
independent finite-count intervals, explicitly quarantines unsupported method
and performance claims, and specifies the matched data/MC closure required by
`AUD-ANOM-001`.

Policy: `CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY`.

## Validation

```text
python -m py_compile \
  tools/audit/validate_chapter9_mv6_claims.py \
  tests/test_validate_chapter9_mv6_claims.py

python -m pytest tests/test_validate_chapter9_mv6_claims.py -q

6 passed in 1.15s
```

The regression covers a valid source contract, the former K=7/BIC claim, the
former 99.7% claim, a mutated PCA summary value, missing producer contract,
machine-readable status-1 flaw output, and invalid-UTF-8 status-2 failure.
Validation JSON parsed, the SVG parsed as XML, and changed Python line lengths
were within the repository's 100-character convention.

Exact source blobs:

- historical chapter: `409abcdefe686edf9c2ac5c5c6ba02aae9c9a331`;
- producer: `f965823518b22908f3e8974f280bff5c970368d0`;
- summary: `26c187cbe05d8dadbe588c6ed9062d25658a80a9`;
- historical report: `2c531703755b28a0c576e978531b81374edf8ab4`;
- canonical ledger: `e489555f3a520c7cc64b8a7d858a0e93622b9de6`.

Exact committed correction blobs re-fetched from `main`:

- corrected chapter: `c54753c58b0eb9e68a7e2b908d4e31310b0c991f`;
- validator: `fbb9d9423ad2fc6130656d6cdfa11345e738f095`;
- regression test: `ebc61f19916baf8a9dee1a86aa7deb9b08ecb259`.

The corrected chapter and validator blobs matched the locally validated
candidates. ROOT processing, model reruns, full repository pytest, ruff,
repository-wide broken-link checking and GitHub Actions were not run.

## Direct-main commit and publication sequence

1. `b646af9dcc6e4af719c7773cc30135e9e5a5e3b2` — `fix(docs): align Chapter 9 with tracked MV6 method`
2. `ed37eb208671a93658204d80d04a96043c61719c` — `feat(audit): validate Chapter 9 MV6 source claims`
3. `ca4b2391180a8998a6fe701fb1f9bdd6b18490bc` — `test(audit): cover Chapter 9 MV6 claim gate`
4. `0954e2453559ac54fd0f190c9ffac0550260a6d8` — `docs(validation): record Chapter 9 MV6 claims audit`
5. `985c79039feb50153df162c5792f2930824ef1e4` — `docs(validation): add Chapter 9 MV6 validation record`
6. `45ba154e65dcc92b26e8d9556587c39428b12633` — `docs(validation): visualize Chapter 9 MV6 correction`
7. `57e3e24ab8d1984cf67f9383cdb90a6910b326f8` — `docs(audit): track validated Chapter 9 MV6 correction`
8. `4ea6dbff80701aeafba66051135dd457cadf9295` — `docs(validation): correct Chapter 9 artifact provenance`
9. `84c5a09c3a58f16806c8e9f0e94873abab410e34` — `docs(validation): bind Chapter 9 evidence to committed blobs`
10. `b7f7584c6650dfcc349fc05df99fade1f511ee9f` — `docs(audit): archive validated Chapter 9 MV6 correction`

Each contents-API write returned a successful commit SHA and advanced remote
`main`. Remote history was re-read after the scientific/evidence sequence and
confirmed the commits as consecutive descendants of the initial head. The
post-handoff history read must confirm this handoff commit as the remote head.

## Scientific boundary and unresolved risk

This unit does **not**:

- identify the beam-data anomaly as carbon-12;
- validate an independent data species tag;
- measure efficiency, purity, false-positive rate or veto impact in data;
- quantify generator, geometry, detector-response or waveform-model
  uncertainty;
- reproduce the historical ROOT processing environment;
- authorize a detector-performance or physics-yield correction.

`AUD-ANOM-001` remains `PARTIAL`. The next scientific unit is the
preregistered matched data/MC closure in
`docs/validation/C12_DATA_MC_CLOSURE_SPEC.md`.

Ledger-wide `AUD-LEDGER-001` also remains `PARTIAL`. Malformed `CL-023` and
`CL-024` should be reconstructed using the exact PCA source values, and Chapter
6 plus remaining public summaries should be checked for superseded 0.89/0.997
representation claims.

`SESSION_LOG.md` was not replaced because the connector exposes whole-file
replacement rather than a byte-safe append operation and a complete current
byte snapshot was not safely reconstructed. Replacing the append-only log could
destroy prior provenance. The immutable archive and this handoff contain the
complete session record.
