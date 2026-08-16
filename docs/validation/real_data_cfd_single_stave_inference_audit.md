# Real-data CFD single-stave inference audit

## Scope

Task `AUD-TIMING-003` reviews the PR #939 conversion from a B6-B8 pair residual
width to a claimed B6 single-stave timing resolution. The reviewed PR head is
`ce81f22ef57c5db0b658737c0d9ced4c7fc69949`.

Inspected upstream identities:

- `scripts/real_data_cfd_timing.py` blob
  `ef13a859bb756dbf4b7ea6fa40f681d8858a7ac7`;
- `reports/real_data_cfd_timing/result.json` blob
  `debc5c45d84a210f8425bab5c9f87d8b61fd279b`.

The version-controlled fixtures are connector-inspected relevant excerpts, not a
full PR checkout or replacement for the immutable ROOT inputs.

## Policy

`PAIR_SIGMA68_DIV_SQRT2_REQUIRES_VALIDATED_IDENTICAL_INDEPENDENT_GAUSSIAN_OR_EXPLICIT_DECONVOLUTION`

For a variance estimator, the pair relation is

`Var(t6 - t8) = Var(t6) + Var(t8) - 2 Cov(t6, t8)`.

Dividing a pair standard deviation by `sqrt(2)` identifies a common individual
standard deviation only when the two variances are equal and covariance is zero.
The PR instead divides the robust interquantile width `sigma68` by `sqrt(2)`.
Outside a validated distribution family, `sigma68` does not obey a general
quadrature-deconvolution law.

## Confirmed findings

The reviewed producer computes

```python
single = best_sigma68["sigma68_ns"] / np.sqrt(2)
```

and its report publishes

```text
Single-stave estimate (pair / sqrt2) = 0.635 ns,
consistent with ... CL-002 (B6 = 0.63-0.80 ns)
```

The machine-readable result contains only the pair metric. It does not contain
individual B6/B8 resolution constraints, a covariance/common-mode model, an
explicit deconvolution method, or a single-stave uncertainty/authorization state.

The headline pair metric is strongly non-Gaussian by its own diagnostics:

- pair `sigma68 = 0.8985129399585929 ns`;
- pair bootstrap interval `[0.8123935669551073, 1.0723601562332614] ns`;
- tail fraction beyond 5 ns `0.15889830508474576`;
- full RMS `9.69875913667869 ns`;
- `RMS / sigma68 = 10.794`.

The naive numerical conversion is

`0.8985129399585929 / sqrt(2) = 0.6353445928285822 ns`.

That number is an assumption-dependent transformation, not an independently
measured B6 resolution. The pair data alone identify neither B6 nor B8 separately.
The source also says `assume equal`, while the recorded selected-pulse counts are
17,197 for B6 and 10,619 for B8 and the median widths above 10% are 8 and 10
samples. Those differences do not prove unequal timing resolution, but they show
that equality was not established by the recorded diagnostics.

The fail-closed audit returns `FLAWED` with eight findings:

1. pair `sigma68` divided by `sqrt(2)`;
2. pair-only result promoted to a single-stave claim;
3. no machine-readable inference authorization state;
4. no covariance/common-mode model;
5. no individual-stave deconvolution;
6. non-Gaussian pair width used for `sqrt(2)` scaling;
7. no single-stave uncertainty propagation;
8. equal-stave assumption unvalidated.

## Independent controls

Fixed-seed controls demonstrate that `pair sigma68 / sqrt(2)` is not a general
single-stave estimator. Relative error versus stave-A `sigma68` is:

| control | relative error |
|---|---:|
| independent identical normal | -0.53% |
| independent identical Laplace | +10.65% |
| independent identical heavy-tail mixture | +21.73% |
| unequal independent normal | +57.42% |
| equal normal with correlation 0.5 | -29.31% |

The normal control is the special case where the transformation is approximately
valid. The other controls isolate distribution-shape, unequal-resolution, and
covariance failure modes.

## Better method

The current result should remain a B6-B8 pair-only timing measurement. A
single-stave claim requires one of the following evidence-backed routes:

1. three-detector or multi-pair deconvolution with a solved covariance model;
2. an external reference detector with independently calibrated resolution;
3. a hierarchical likelihood that estimates per-stave resolution and common-mode
   jitter with uncertainty and held-out validation;
4. a preregistered distributional deconvolution validated by injection/recovery.

The output contract should record
`single_stave_inference.authorized=false` until those requirements are met.
If a model later authorizes the inference, it must record the estimator,
distribution assumptions, covariance treatment, per-stave constraints, propagated
interval, sensitivity to assumptions, and closure evidence.

## Validation

Executed:

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
pair-only fixture with `single_stave_inference.authorized=false` returned
`VALIDATED` with zero findings. The tests also cover the toy counterexamples,
invalid UTF-8, destructive aliasing, and failure-safe atomic JSON publication.
The JSON parsed and the SVG parsed as XML. Changed Python lines are at most 100
characters.

## Scientific boundary

No ROOT file was reprocessed. No event-key correction, channel map, pedestal,
CFD estimator, in-time selection, bootstrap coverage, single-stave resolution,
`CL-002` status, or detector-performance quantity was validated or changed.
The audit establishes that the pair-only evidence does not authorize the reported
single-stave conversion.
