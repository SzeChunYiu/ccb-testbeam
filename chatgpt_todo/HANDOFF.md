# Latest Handoff

## Session

- **Task ID:** `AUD-TIMING-003`
- **Stamp:** `2026-07-26T143114Z`
- **Owner:** scheduled scientific-review session
- **Initial remote main:** `f4b5f193838effbf0ab9c82911a4fb8652eced8a`
- **Validated implementation/evidence through:** `0c807f553ac38dd55de2e7574eb9d29f69163e13`
- **Destination:** sequential commits directly to `main`; no task branch, pull-request transport, force-push, or history rewrite.
- **Push result:** each GitHub contents write returned a successful direct-main commit SHA. The connector does not return a conventional terminal `git push` transcript, and none is claimed.
- **Focused acceptance:** audit gate, tests, fixtures, deterministic controls, JSON, SVG, report, active-task record, immutable archive, and this handoff are `VALIDATED / COMPLETE`.
- **Scientific acceptance:** PR #939 single-stave inference and broader timing claim remain `FLAWED / PARTIAL`.

## Repository and review state

At run start, remote `main` was `f4b5f193838effbf0ab9c82911a4fb8652eced8a` and had no attached combined status checks. PR #939 was open, unmerged, mergeable, and had no attached status checks. Its reviewed head was `ce81f22ef57c5db0b658737c0d9ced4c7fc69949`.

Reviewed PR identities:

- `scripts/real_data_cfd_timing.py` blob `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`;
- `reports/real_data_cfd_timing/result.json` blob `debc5c45d84a210f8425bab5c9f87d8b61fd279b`.

The previous `AUD-TIMING-001` event-identity and `AUD-TIMING-002` residual-visualization audits were read before task selection. This run reviewed a distinct statistical-identifiability defect rather than duplicating those tasks. PR #868 was not modified or merged.

## Policy and confirmed defect

Policy:

`PAIR_SIGMA68_DIV_SQRT2_REQUIRES_VALIDATED_IDENTICAL_INDEPENDENT_GAUSSIAN_OR_EXPLICIT_DECONVOLUTION`

The PR computes:

```python
single = best_sigma68["sigma68_ns"] / np.sqrt(2)
```

and publishes the result as a single-stave estimate consistent with `CL-002`.
For a variance estimator,

```text
Var(t6 - t8) = Var(t6) + Var(t8) - 2 Cov(t6, t8).
```

Dividing a pair standard deviation by `sqrt(2)` identifies a common individual standard deviation only under equal-variance and zero-covariance assumptions. The PR instead applies the transformation to `sigma68`, a robust interquantile width that has no general quadrature-deconvolution law.

The PR result records no independent B6/B8 resolution constraint, external reference, covariance/common-mode model, distributional deconvolution, or machine-readable single-stave authorization and uncertainty state.

## Quantitative result

The headline B6-B8 pair record contains:

- `n = 1888`;
- `sigma68 = 0.8985129399585929 ns`;
- pair bootstrap interval `[0.8123935669551073, 1.0723601562332614] ns`;
- tail fraction beyond 5 ns `0.15889830508474576`;
- full RMS `9.69875913667869 ns`;
- `RMS / sigma68 = 10.794`.

The PR's assumption-dependent conversion is:

```text
0.8985129399585929 / sqrt(2) = 0.6353445928285822 ns
```

That number is not independently identified as B6 resolution by the pair data.
The source states `assume equal`, while the same result records B6/B8 selected-pulse counts of 17,197/10,619 and median pulse widths above 10% of 8/10 samples. These differences do not prove unequal timing resolution, but they show equality was not established by the recorded diagnostics.

The fail-closed audit returns `FLAWED` with eight finding families:

1. `PAIR_SIGMA68_DIVIDED_BY_SQRT2`;
2. `PAIR_ONLY_RESULT_PROMOTED_TO_SINGLE_STAVE_CLAIM`;
3. `SINGLE_STAVE_INFERENCE_NOT_MACHINE_READABLE`;
4. `NO_COVARIANCE_OR_COMMON_MODE_MODEL`;
5. `NO_INDIVIDUAL_STAVE_DECONVOLUTION`;
6. `NON_GAUSSIAN_PAIR_WIDTH_USED_FOR_SQRT2_SCALING`;
7. `SINGLE_STAVE_UNCERTAINTY_NOT_PROPAGATED`;
8. `EQUAL_STAVE_ASSUMPTION_UNVALIDATED`.

## Independent controls and better method

Fixed-seed controls quantify failure of the naive transformation relative to stave-A `sigma68`:

| control | relative error |
|---|---:|
| independent identical normal | -0.53% |
| independent identical Laplace | +10.65% |
| independent identical heavy-tail mixture | +21.73% |
| unequal independent normal | +57.42% |
| equal normal with correlation 0.5 | -29.31% |

The current result must remain pair-only and record
`single_stave_inference.authorized=false`. An individual-stave result requires a validated three-detector/multi-pair solution, an independently calibrated external reference, or a hierarchical/deconvolution model that records individual constraints, covariance/common-mode treatment, uncertainty propagation, assumption sensitivity, and injection/recovery or held-out closure.

## Work delivered

- `tools/audit/audit_real_data_cfd_single_stave_inference.py`
- `tests/test_audit_real_data_cfd_single_stave_inference.py`
- `tools/audit/render_real_data_cfd_single_stave_inference_evidence.py`
- `docs/validation/fixtures/pr939_real_data_cfd_single_stave_relevant.py`
- `docs/validation/fixtures/pr939_real_data_cfd_single_stave_result_subset.json`
- `docs/validation/real_data_cfd_single_stave_inference_validation.json`
- `docs/validation/real_data_cfd_single_stave_inference.svg`
- `docs/validation/real_data_cfd_single_stave_inference_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- `chatgpt_todo/archive/2026-07-26T143114Z_AUD-TIMING-003_SINGLE_STAVE_INFERENCE.md`
- this handoff.

The fixtures are explicitly connector-inspected relevant copies, not a complete PR checkout or raw ROOT data.

Implementation SHA-256 identities:

- auditor `d70d5bc996a0c139bf1dbbea27a0a9971c7ef259cb8cb967e3ce8678cb4eb75e`;
- focused tests `070be227742138b3bdbaa57ded4f23b87453fc8a8c0e25c681b07f131af1ba1c`;
- renderer `74c8bd93cc60913ae69c210b7cefa28e782b16f3763a3c5ba4dd05b8a78b8468`;
- source fixture `63676dbb0a995f9663df5dae2b40a8b98f188ceb5b57a094f8ac1b67ba4c5600`;
- result fixture `465cc4de72860cd17022cac7b7f4be6da476ba593ca0c8fd5f0e9464676ab9e7`;
- validation JSON `8d1dd4129b8bbbe3b077c18d16ee49c9bef202eafc300e1ebba1a548d871dd17`;
- SVG `04d2196399bab7bf0902b5c4e3628b8a00e8985e0942a5c0df0529f665e98c8a`.

## Validation

```text
python -m py_compile \
  tools/audit/audit_real_data_cfd_single_stave_inference.py \
  tests/test_audit_real_data_cfd_single_stave_inference.py \
  tools/audit/render_real_data_cfd_single_stave_inference_evidence.py

PYTHONPATH=. pytest -q \
  tests/test_audit_real_data_cfd_single_stave_inference.py

6 passed in 0.24s
```

Environment: Python 3.13.5, pytest 9.0.2, NumPy 2.4.2.

The current-like fixture returned `FLAWED` with eight findings. A corrected pair-only fixture with `single_stave_inference.authorized=false` returned `VALIDATED` with zero findings. Invalid UTF-8 and destructive output aliasing failed closed. An injected JSON publication failure preserved the previous target and removed the temporary file. JSON and SVG parsing passed. Changed Python lines are at most 100 characters.

## Direct-main sequence

- `64bdc694abc47df601f4309ae0ca90d8d2f518a4` — inspected source fixture;
- `a8751e25075a58aadaaacf6645e38047038f1db9` — inspected result fixture;
- `0e6c8d13d32215e525ea07c79ce0d419fe657699` — audit gate;
- `45c32e82c17b0a08aca3978909a0a4ee43ff82ac` — focused regressions;
- `8958d534a04218f68b4d991b766cec3dede3d446` — evidence renderer;
- `5cad1668c69fcb61a35c0515d6c933b6a56b7e5b` — validation JSON;
- `064461857e3603cfa02c3f3eeafb3d81ce1887fd` — SVG evidence;
- `d1f6ec66df9a2e55e0e03ef2fb4ae6ba84ab8044` — audit report;
- `be2c50253aa6066d8822e44bd142d9f99fa4ce0c` — active-task completion;
- `0c807f553ac38dd55de2e7574eb9d29f69163e13` — immutable archive;
- this handoff commit.

## Scientific boundary and unrun checks

No ROOT file was reprocessed. No event identity, channel mapping, pedestal subtraction, CFD estimator, in-time selection, bootstrap coverage, pair timing width, single-stave resolution, `CL-002` status, or detector-performance result was validated or changed.

Repository-wide pytest and ruff, a complete PR checkout, producer rerun, documentation/link inventory, and GitHub Actions were not run and are not claimed as passing. PR #939 must remain unmerged until its demonstrated event-identity, residual-visualization, and single-stave-identifiability failures are fixed and scientific acceptance criteria are rerun.

`SESSION_LOG.md` was reviewed but not safely appended. Connector reads are paged/truncated while writes replace the complete file; reconstructing it manually could erase append-only provenance. The immutable archive and this handoff retain the complete append-equivalent record without claiming that the mandatory append succeeded.

## Next action

Correct PR #939 to retain pair-only wording and a machine-readable unauthorized single-stave state; fix composite event keys and residual visualization; then regenerate content-addressed results from immutable ROOT inputs. Pursue individual-stave inference only through validated multi-pair or external-reference deconvolution with explicit covariance and uncertainty.
