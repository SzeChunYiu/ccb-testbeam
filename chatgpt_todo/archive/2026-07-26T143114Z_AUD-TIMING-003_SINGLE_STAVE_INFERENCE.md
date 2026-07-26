# Immutable handoff — AUD-TIMING-003

## Session identity

- Stamp: `2026-07-26T143114Z`
- Owner: scheduled scientific-review session
- Initial remote main: `f4b5f193838effbf0ab9c82911a4fb8652eced8a`
- Reviewed PR: #939
- Reviewed PR head: `ce81f22ef57c5db0b658737c0d9ced4c7fc69949`
- PR source blob: `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`
- PR result blob: `debc5c45d84a210f8425bab5c9f87d8b61fd279b`

## Policy and result

`PAIR_SIGMA68_DIV_SQRT2_REQUIRES_VALIDATED_IDENTICAL_INDEPENDENT_GAUSSIAN_OR_EXPLICIT_DECONVOLUTION`

The pair metric is `0.8985129399585929 ns`; the PR divides it by `sqrt(2)` and
publishes `0.635 ns` as a single-stave estimate. The result has no individual
stave constraints, covariance/common-mode model, deconvolution method, or
single-stave uncertainty state. The headline pair has tail fraction
`0.15889830508474576` and `RMS/sigma68 = 10.794`, so the robust width is not
shown to obey Gaussian quadrature scaling.

The fail-closed audit returned `FLAWED` with eight findings. Fixed-seed controls
showed relative errors of -0.53% for iid normal, +10.65% for iid Laplace, +21.73%
for an iid heavy-tail mixture, +57.42% for unequal independent normal widths, and
-29.31% for equal normal widths with correlation 0.5.

## Files delivered

- `tools/audit/audit_real_data_cfd_single_stave_inference.py`
- `tests/test_audit_real_data_cfd_single_stave_inference.py`
- `tools/audit/render_real_data_cfd_single_stave_inference_evidence.py`
- `docs/validation/fixtures/pr939_real_data_cfd_single_stave_relevant.py`
- `docs/validation/fixtures/pr939_real_data_cfd_single_stave_result_subset.json`
- `docs/validation/real_data_cfd_single_stave_inference_validation.json`
- `docs/validation/real_data_cfd_single_stave_inference.svg`
- `docs/validation/real_data_cfd_single_stave_inference_audit.md`
- `chatgpt_todo/ACTIVE_TASK.md`
- this archive record
- `chatgpt_todo/HANDOFF.md`

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

The current-like fixture returned `FLAWED` with eight findings. A corrected
pair-only fixture returned `VALIDATED` with zero findings. Invalid UTF-8 and
input/output aliasing failed closed. Injected JSON publication failure preserved
the previous target and removed its temporary file. JSON and SVG parsing passed.

## Scientific boundary

No ROOT file, waveform, event selection, pair width, covariance, or single-stave
resolution was rerun. No `CL-002` claim was changed. The accepted result of this
unit is a governance and statistical-identifiability boundary: the B6-B8 pair
measurement does not by itself identify B6 resolution.

## Required next action

Retain pair-only wording and set
`single_stave_inference.authorized=false`. Authorize an individual-stave result
only after validated multi-pair or external-reference deconvolution with explicit
covariance/common-mode treatment, uncertainty propagation, and closure.
PR #939 must also fix the existing composite-key and residual-visualization
failures before merge.
