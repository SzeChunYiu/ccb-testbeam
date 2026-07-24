# Latest Scientific-Review Handoff

## Session identity

- **UTC stamp:** `2026-07-24T210523Z`
- **Task:** `AUD-LEDGER-002`
- **Unit:** MV3 exact tracked-summary ledger and validator remediation
- **Initial remote `main`:** `a52ea7c3f76eddff204e8ebb990a55cfe8793e7f`
- **Validated evidence head:** `72f295425fee337a63d94364e1e3c27376f0a4ab`
- **Coordination/archive head before handoff:** `4431c5089df2226a1817a8f959aaa98621c4c73b`
- **Final validated main SHA before metadata-only confirmation:** `8278e689b9bdbc99e1ccb82a4d014389802fdc19`
- **Post-handoff cleanup head:** `593eed0ec0feb032e57d641ecdc410d704a2381f` — reintroduced inactive workflow removed; no scientific files changed
- **Remote-main confirmation:** post-write history confirmed both `8278e689b9bdbc99e1ccb82a4d014389802fdc19` and cleanup `593eed0ec0feb032e57d641ecdc410d704a2381f` on remote `main`; this record adds confirmation metadata only
- **Destination:** direct sequential commits to remote `main`; no force-push, history rewrite, task branch, or PR transport
- **Acceptance:** canonical MV3 rows, exact-source validator, regressions, machine-readable evidence, and visual evidence are validated; root-WIKI synchronization and scientific stopping-profile closure remain partial

## Start-of-run review and concurrency

Authenticated GitHub reads inspected recent `main` history, repository instructions and coordination files, the canonical claim ledger, legacy MV3 report and tracked summary, strict current MV3 implementation, prior validators/tests/evidence, root WIKI MV3/GAP-01 prose, related PID/MC documentation, and PR #868.

A direct clone attempt could not resolve `github.com`, so all repository reads and writes used the authenticated GitHub connector. Repository access, commands, and validation outcomes were not fabricated.

Concurrent commit `bbaa81fe291e777dee9bbd3ecfa473e61465bac5` corrected CL-019/020/021 while this session was active. It was preserved and became the canonical ledger basis. PR #868 remained closed, unmerged, non-mergeable, and untouched.

## Confirmed source result

Tracked `reports/mv3_stopping_v3_1782679272/mv3_summary.json` contains:

- thresholded-MC B2/B4/B6/B8 counts `117213/45507/31145/55619`;
- MC denominator `249484` and B8 fraction `0.22293614019335908`;
- selected-data counts `268576/19284/11834/7051`;
- data denominator `306745` and B8 fraction `0.02298651974767315`;
- Pearson chi-square `204808.2179684494`;
- ndf `3`;
- chi-square/ndf `68269.40598948313`.

Independent binary64 reconstruction used:

```text
expected_i = 306745 * mc_fraction_i
chi2 = sum((data_count_i - expected_i)^2 / expected_i)
ndf = 4 - 1
```

and exactly reproduced the stored statistic.

This establishes fixed-source arithmetic and provenance only. It does not establish calibrated goodness-of-fit acceptance or contemporary stopping-profile closure.

## Corrections delivered

- `CL-019` now binds exact `55619/249484 = 0.22293614019335908` and remains `GATED`.
- `CL-020` now binds exact `7051/306745 = 0.02298651974767315` and remains `GATED`.
- `CL-021` now binds exact Pearson chi-square/ndf `68269.40598948313` and remains `FLAWED`.
- `tools/audit/validate_mv3_legacy_claim_rows.py` is version `2.0.0` with policy `TRACKED_MV3_SUMMARY_EXACT_COUNTS_WITH_FAIL_CLOSED_STRICT_RERUN`.
- The validator independently verifies count/fraction consistency, Pearson arithmetic, exact source fields, absence of unsupported uncertainty values, scientific caveats, and strict-current MV3 fail-closed inputs.
- Validator and provenance regression suites now accept the exact current contract and reject rounded values, altered numerators, altered chi-square, fraction mismatches, and invalid UTF-8.
- `tools/audit/render_mv3_legacy_claim_evidence.py` and the committed SVG show exact B8 counts/fractions, the reconstructed diagnostic, and the non-acceptance boundary.

Evidence:

- `docs/validation/mv3_summary_remediation_audit.md`
- `docs/validation/mv3_summary_remediation_validation.json`
- `docs/validation/mv3_summary_remediation.svg`
- `chatgpt_todo/archive/2026-07-24T210523Z_AUD-LEDGER-002_MV3_REMEDIATION.md`

## Validation

```text
python -m py_compile \
  tools/audit/validate_mv3_legacy_claim_rows.py \
  tools/audit/audit_mv3_summary_provenance.py \
  tools/audit/render_mv3_legacy_claim_evidence.py \
  tests/test_validate_mv3_legacy_claim_rows.py \
  tests/test_audit_mv3_summary_provenance.py

PYTHONPATH=. python -m pytest \
  tests/test_validate_mv3_legacy_claim_rows.py \
  tests/test_audit_mv3_summary_provenance.py -q

11 passed in 1.76s
```

Additional checks:

- direct exact-source validator: `VALIDATED`, zero issues;
- former ledger blob `bb552aa5ed70e7d81dcda888c5aa61402c01e03c`: status 1, `FLAWED`, 33 findings;
- JSON parse: PASS;
- SVG XML parse: PASS;
- changed Python line length <=100: PASS.

The validation JSON explicitly distinguishes an exact locally reconstructed ledger used for execution from the current remote whole-file Git blob `8135794d6f0b22da6b760bf6234bb8e1cae795fb`; no unsupported remote whole-file SHA-256 is claimed.

## Direct-main commit sequence

- `f06767eddafd724e629977609e3ce7bff6825d10` — temporary remediation workflow added; no run occurred.
- `bbaa81fe291e777dee9bbd3ecfa473e61465bac5` — concurrent exact ledger correction.
- `08e80e81f866218765f8ca427b9b95f6fe2ef3b2` — inactive workflow removed.
- `6a23387b3845f7f5bf0359e958d50dde0203489e` — validator v2.0.
- `322227f4c254bfc92ca501a1c1a31ab985f74ccb` — exact-contract validator tests.
- `71240c25f8df55fd4da1d3a72edc1616ec6e93fe` — exact evidence renderer.
- `3b7bc437310833414289a9e171e823925d098b22` — provenance regression expectations.
- `f06ef21a51d15f33e65e4c45bd680aa46f03ada3` then `7339690c2b6798d1ca2e5d575677c93327083144` — WIKI sync test created then removed because the public WIKI was not safely replaced.
- `31b5df46377e95adf537988fb225f20bbf5b3183` — audit report.
- `5dc7edfb279ef26ffcc5fa3fb24b8a6a35a930f2` — validation JSON.
- `72f295425fee337a63d94364e1e3c27376f0a4ab` — visual evidence.
- `bb0c7651b5c70970dd89055843d9040b2986032e` — active-task update.
- `4431c5089df2226a1817a8f959aaa98621c4c73b` — immutable archive.
- `f16fb196145a7dce8d45f508ede426d2e73c4e33` — inactive workflow was reintroduced by concurrent activity; no run was claimed.
- `8278e689b9bdbc99e1ccb82a4d014389802fdc19` — complete remediation handoff.
- `f7f4bbc93688feeb6725683f64522eeca5b175a1` — delivery-SHA confirmation metadata.
- `593eed0ec0feb032e57d641ecdc410d704a2381f` — reintroduced workflow removed; current tree contains no remediation workflow file.

The contents connector returned successful commit SHAs rather than conventional textual `git push` stdout. Recent-history reads confirmed these commits on remote `main` in order. No broad GitHub Actions success is claimed.

## Remaining blocker and next task

The root `WIKI.md` was reviewed and still contains stale MV3/GAP-01 absence wording. The connector offers whole-file replacement, while the available long-file reads were ranged or truncated; replacing a public 23 kB document without a byte-safe complete snapshot risked erasing unrelated concurrent work. The temporary WIKI regression was therefore removed rather than left failing.

Next unit:

1. obtain a byte-safe complete current WIKI snapshot;
2. replace the absence narrative with exact `7051/306745`, `55619/249484`, Pearson chi-square `204808.2179684494`, ndf `3`, and chi-square/ndf `68269.40598948313`;
3. retain `FLAWED` and `BLK-MV3-LEGACY-001`;
4. run the MV3 validators, WIKI front-door validators, and broken-link checker together.

## Coordination limitation

`ACTIVE_TASK.md`, this handoff, validation artifacts, and the immutable archive were updated. `SESSION_LOG.md`, `BACKLOG.md`, `BLOCKERS.md`, and aggregate matrices were not replaced from partial/truncated snapshots because whole-file replacement could destroy unrelated append-only provenance. No claim is made that those aggregate files contain this run.

## Scientific boundary

No ROOT or Geant4 rerun, corrected geometry/material model, matched trigger/selection transfer, gain-response closure, covariance matrix, p-value interpretation, systematic uncertainty propagation, acceptance correction, calibration, or detector-performance result was produced. `BLK-MV3-LEGACY-001` remains open.
