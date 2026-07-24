# Immutable audit archive — AUD-LEDGER-002 MV3 remediation

- **Session stamp:** `2026-07-24T210523Z`
- **Initial remote main:** `a52ea7c3f76eddff204e8ebb990a55cfe8793e7f`
- **Task status:** `PARTIAL`
- **Validated unit:** exact tracked MV3 claim rows, validator contract, regressions, machine-readable evidence, and visual evidence
- **Still open:** byte-safe root-WIKI MV3/GAP-01 synchronization and scientific closure under `BLK-MV3-LEGACY-001`

## Repository/history review

Reviewed recent remote-main history, PR #868, `chatgpt_todo/` active/handoff/backlog/blocker state, the canonical claim ledger, legacy MV3 report and tracked summary, strict current MV3 implementation, prior provenance auditor/validator/tests, root WIKI, and related PID/MC documentation.

PR #868 remained closed, unmerged, non-mergeable, and untouched.

## Confirmed source facts

Tracked `mv3_summary.json` contains:

- MC B2/B4/B6/B8 counts `117213/45507/31145/55619`;
- thresholded-MC denominator `249484` and B8 fraction `0.22293614019335908`;
- data counts `268576/19284/11834/7051`;
- selected-data denominator `306745` and B8 fraction `0.02298651974767315`;
- Pearson chi-square `204808.2179684494`;
- ndf `3`;
- chi-square/ndf `68269.40598948313`.

Independent binary64 reconstruction used `expected_i = 306745 * mc_fraction_i` and `sum((data_i - expected_i)^2 / expected_i)` and exactly reproduced the stored statistic.

## Corrections

- Concurrent commit `bbaa81fe291e777dee9bbd3ecfa473e61465bac5` bound CL-019/020/021 to the exact tracked values and retained CL-021 as `FLAWED`.
- Validator v2.0 now checks exact row width, count/fraction consistency, independent Pearson arithmetic, exact source paths/commit, unsupported uncertainty fields, notes/caveats, and strict current MV3 fail-closed input requirements.
- Regression tests now accept the exact current contract and reject rounded values, altered numerators, altered summary chi-square, count/fraction inconsistency, and invalid UTF-8.
- Renderer and committed SVG display exact B8 counts/fractions and the non-acceptance boundary.

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

Direct validator: `VALIDATED`, zero issues. Former ledger blob `bb552aa5ed70e7d81dcda888c5aa61402c01e03c`: status 1, `FLAWED`, 33 findings. JSON parse, SVG XML parse, and changed-Python line length <=100 passed.

## Direct-main commit sequence

- `f06767eddafd724e629977609e3ce7bff6825d10` — temporary remediation workflow added; it did not run.
- `bbaa81fe291e777dee9bbd3ecfa473e61465bac5` — concurrent exact ledger correction.
- `08e80e81f866218765f8ca427b9b95f6fe2ef3b2` — inactive workflow removed.
- `6a23387b3845f7f5bf0359e958d50dde0203489e` — validator v2.0.
- `322227f4c254bfc92ca501a1c1a31ab985f74ccb` — exact-contract validator tests.
- `71240c25f8df55fd4da1d3a72edc1616ec6e93fe` — exact evidence renderer.
- `3b7bc437310833414289a9e171e823925d098b22` — provenance test expectations.
- `f06ef21a51d15f33e65e4c45bd680aa46f03ada3` then `7339690c2b6798d1ca2e5d575677c93327083144` — WIKI sync test created then removed because a safe complete WIKI replacement was not available.
- `31b5df46377e95adf537988fb225f20bbf5b3183` — audit report.
- `5dc7edfb279ef26ffcc5fa3fb24b8a6a35a930f2` — validation JSON.
- `72f295425fee337a63d94364e1e3c27376f0a4ab` — SVG evidence.
- `bb0c7651b5c70970dd89055843d9040b2986032e` — active-task update.

The contents connector returned successful commit SHAs rather than conventional textual `git push` output. History reads confirmed every listed commit on remote `main`. No force-push or history rewrite was used.

## Coordination limitation

`SESSION_LOG.md`, the long backlog/blocker registers, and aggregate matrices were not replaced from partial or truncated snapshots. Whole-file replacement without a complete byte-safe snapshot could destroy unrelated append-only provenance. This immutable archive and the latest handoff retain the complete run. The root WIKI also remains pending for the same safe-patch reason.

## Scientific boundary

No ROOT/Geant4 rerun, corrected geometry/material model, matched trigger/selection transfer, covariance matrix, systematic uncertainty propagation, p-value interpretation, acceptance correction, calibration, or detector-performance result was produced. Exact arithmetic is provenance validation, not accepted stopping-profile closure.
