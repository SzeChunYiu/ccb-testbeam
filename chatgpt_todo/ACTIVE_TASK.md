# Active Task

- **Task ID:** AUD-MV3-SEL-003
- **Owner:** scheduled scientific-review session
- **Session stamp:** 2026-07-26T002131Z
- **Initial remote main SHA:** `54a899d82c1991747218a5b3a5a0835c51991420`
- **Transport branch:** `chatgpt/AUD-MV3-SEL-003-chi2-remediation-20260726T002131Z`
- **Scope:** remediate the weighted MV3 producer's Pearson chi-square implementation after the
  validated support audit showed that positive observed mass at zero model expectation was silently
  omitted and nonunit model profiles were accepted.
- **Policy:**
  `PEARSON_CHI2_MUST_REJECT_OUT_OF_SUPPORT_DATA_AND_NONUNIT_PROFILES`.
- **Implementation:** preserve the current weighted producer body as a content-addressed internal
  dependency; make the canonical script a strict front door that requires exact B2/B4/B6/B8 keys,
  finite nonnegative inputs, unit-normalized model fractions within `1e-12`, positive observed total,
  rejection of observed mass outside model support, supported-category ndf, and `math.fsum`.
- **Provenance:** every generated summary must record the canonical front-door bytes/SHA-256 and the
  exact internal implementation bytes/SHA-256 from the single-read snapshot used at import.
- **Files:** `scripts/studies/mv3_selection_matched.py`,
  `scripts/studies/_internal/mv3_selection_matched_impl.py.inc`,
  `tests/test_mv3_chi2_producer_contract.py`, focused validation evidence, immutable archive,
  `HANDOFF.md`, and `SESSION_LOG.md` where a byte-safe append is possible.
- **Validation plan:** local synthetic wrapper regression; pull-request GitHub Actions over the exact
  candidate tree; focused exact-source audit; JSON/SVG parsing; line-length and blob checks; then
  merge or fast-forward validated work to remote `main` without force-push.
- **Progress:** local synthetic wrapper regression returned `6 passed`; candidate exact-tree CI and
  complete repository tests remain pending.
- **Focused status:** `ACTIVE` until exact candidate CI passes and the resulting commit is confirmed
  on remote `main`.
- **Scientific boundary:** no ROOT or beam-data file is rerun; no weighted profile, covariance,
  sensitivity scan, calibration, PID, closure, or detector-performance result is authorized.
