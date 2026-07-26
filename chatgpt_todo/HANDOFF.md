# Latest Handoff

## Session

- **Task ID:** `AUD-TIMING-002`
- **Stamp:** `2026-07-26T130822Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `0f7a8e50960d01156ea87cac435f6e25925cd1d9`
- **Validated implementation/evidence through:** `040f9c6c2d767d40029b3cc0a5339652c749a672`
- **Destination:** sequential commits directly to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** each GitHub contents write returned a successful direct-main commit SHA. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** audit gate, tests, fixtures, JSON, SVG, report, active-task record, immutable archive, and this handoff are `VALIDATED / COMPLETE`.
- **Scientific acceptance:** PR #939 residual visualization and broader timing claim remain `FLAWED / PARTIAL`.

## Repository and review state

At run start, remote `main` was `0f7a8e50960d01156ea87cac435f6e25925cd1d9` and had no attached combined status checks. PR #939 was open, non-mergeable, unmerged, and had no attached status checks. Its reviewed head was `ce81f22ef57c5db0b658737c0d9ced4c7fc69949`.

Reviewed PR identities:

- `scripts/real_data_cfd_timing.py` blob `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`;
- `reports/real_data_cfd_timing/result.json` blob `debc5c45d84a210f8425bab5c9f87d8b61fd279b`.

The existing `AUD-TIMING-001` event-identity audit was read before task selection. This run deliberately reviewed a separate visualization failure rather than duplicating that active evidence. PR #868 remained closed, non-mergeable, unmerged, and untouched.

## Defect and quantitative result

Policy:

`REAL_DATA_CFD_RESIDUAL_PLOTS_MUST_COVER_THE_REPORTED_DISTRIBUTION`

The PR plots the uncentered B6-B8 residual vector with:

```python
ax.hist(v, bins=80, range=(-10, 10), ...)
```

but the legend reports `sigma68(v)` from the complete vector. Values outside the fixed range are absent from the histogram while contributing to the label.

Exact reported values for the plotted distributions:

| sample | method | n | median (ns) | sigma68 (ns) |
|---|---|---:|---:|---:|
| Sample II | CFD10 | 1888 | 59.60530122976422 | 0.8985129399585929 |
| Sample II | CFD20 | 1888 | 63.55902020874973 | 15.433838062158472 |
| task runs | CFD10 | 675 | -31.827483483483483 | 3.5480843306636647 |
| task runs | CFD20 | 675 | -28.576323232323233 | 6.72995931053074 |

The reused definition is `sigma68=(q84-q16)/2`. Because `q16 <= median <= q84`, the result records give conservative bounds:

| sample | method | q16 lower bound (ns) | q84 upper bound (ns) | consequence |
|---|---|---:|---:|---|
| Sample II | CFD10 | 57.80827534984704 | 61.40232710968141 | at least 84% above +10 ns |
| Sample II | CFD20 | 32.691344084432785 | 94.42669633306667 | at least 84% above +10 ns |
| task runs | CFD10 | -38.923652144810816 | -24.731314822156154 | at least 84% below -10 ns |
| task runs | CFD20 | -42.03624185338471 | -15.116404611261753 | at least 84% below -10 ns |

Thus all four displayed distributions have at least 84% of their events guaranteed outside the visible range, without Gaussian assumptions or access to the raw residual vector. The existing PNGs cannot visually demonstrate their labels. This does not prove the numerical widths false; it establishes that the visual evidence is invalid and truncated.

## Better method and required remediation

Before merge or scientific use, PR #939 must:

1. use collision-safe `(run,event_id)` keys throughout, as required by `AUD-TIMING-001`;
2. median-center residuals before a fixed deviation plot, or select a range covering the full distribution;
3. report displayed, total, underflow, and overflow counts;
4. label the exact raw/centered/calibrated residual convention;
5. overlay the median, q16, q84, and tail threshold used by the table;
6. provide a full-range panel plus an optional centered core inset;
7. regenerate all figures/results from immutable ROOT bytes with complete content-addressed provenance.

## Work delivered

- `tools/audit/audit_real_data_cfd_residual_visualization.py`
- `tests/test_audit_real_data_cfd_residual_visualization.py`
- `tools/audit/render_real_data_cfd_residual_visualization_evidence.py`
- `docs/validation/fixtures/pr939_real_data_cfd_timing_relevant.py`
- `docs/validation/fixtures/pr939_real_data_cfd_timing_result_subset.json`
- `docs/validation/real_data_cfd_residual_visualization_validation.json`
- `docs/validation/real_data_cfd_residual_visualization.svg`
- `docs/validation/real_data_cfd_residual_visualization_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/archive/2026-07-26T130822Z_AUD-TIMING-002_RESIDUAL_VISUALIZATION.md`
- this handoff.

The two fixtures are explicitly version-controlled connector-inspected relevant copies, not a full PR checkout or raw ROOT data.

Implementation identities:

- auditor blob `41d92f8ceae38517bae28a65dc329769294f6a31`;
- focused-test blob `d684d4182a1f1bd4fb734acdcb79c949b8c48029`;
- source fixture SHA-256 `7e001aa9f8fa72f9ebff33b7f882f0b6349514ff94f7492bfbc3e6be306c403c`;
- result fixture SHA-256 `94c037941d65e2957b24ab209ac517048eb478245b89d1cfab2d7eb103889205`;
- validation JSON SHA-256 `5f4c89377417ceaca6aee9cac9b4fad49941b84a275cbc05825d3881d8a0697f`;
- SVG SHA-256 `e2693d69052fcf86349aae5bf54509d803b3230a210a46a3f4b7c31515d14d22`.

## Validation

```text
python -m py_compile \
  tools/audit/audit_real_data_cfd_residual_visualization.py \
  tests/test_audit_real_data_cfd_residual_visualization.py \
  tools/audit/render_real_data_cfd_residual_visualization_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_real_data_cfd_residual_visualization.py

6 passed in 0.08s
```

Environment: Python 3.13.5, pytest 9.0.2.

The current fixture returned exit 1 and `FLAWED` with six findings. Centered and dynamic-range fixtures returned `VALIDATED` with zero findings. Duplicate method records, invalid UTF-8, and destructive output aliasing fail closed. An injected JSON publication failure preserved the prior target and removed the temporary file. JSON and SVG parsing passed. Changed Python lines are at most 100 characters.

## Direct-main sequence

- `c85c249dabfe7bae3280bf886a6639db1f7f6877` — audit gate;
- `68e98a44608cb3c9f872f6e9b2af982957092f45` — focused regressions;
- `10d7ce773d6ecf5eed40d9361f7e5fdfe6b11d6b` — evidence renderer;
- `b02405ea9126c49d4130a9b28b2d199b4eef955a` — inspected source fixture;
- `a3f774d5f85904b42fde992c8ac19f97f86c02b9` — inspected result fixture;
- `0761e353958c80f3ff018ec82cf1c879f445ba3d` — validation JSON;
- `5a331ed835b378547fd92dbc999d104c157d7743` — SVG evidence;
- `963ef9175debe6258f264442c9cc9c55f8a86e71` — audit report;
- `70dcad8c9aa0d38f561d03ee411947b478efeb6e` — active-task completion;
- `040f9c6c2d767d40029b3cc0a5339652c749a672` — immutable archive;
- this handoff commit.

## Scientific boundary and unrun checks

No ROOT file was reprocessed. No event identity, channel mapping, pedestal subtraction, CFD estimator, in-time selection, bootstrap coverage, equal/independent-stave assumption, single-stave resolution, `CL-002` status, or detector-performance result was validated or changed.

Repository-wide pytest and ruff, a complete PR checkout, the producer rerun, documentation/link inventory, and GitHub Actions were not run and are not claimed as passing. PR #939 must remain unmerged until its demonstrated event-identity and visualization failures are fixed and scientific acceptance criteria are rerun.

`SESSION_LOG.md` was reviewed but not safely appended. Connector reads are paged/truncated while writes replace the complete file; reconstructing it manually could erase append-only provenance. The immutable archive and this handoff retain the full append-equivalent record without claiming that the mandatory append succeeded.

## Next action

Repair the producer's composite event key and residual visualization together, regenerate content-addressed figures/results from immutable ROOT inputs, add direct producer regressions for underflow/overflow and visual-statistic support, and rerun the timing validation before any merge or public claim.
