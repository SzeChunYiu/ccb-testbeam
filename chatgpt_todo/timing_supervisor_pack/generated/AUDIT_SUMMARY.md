# Generated timing-claim audit

- Fraction table source: `parsed_from_result_json`
- Channel-map status: `RETRACTED_20260816_TRUNCATED_STAGING_DESYNC`
- Audit status: **GATED_NOT_PHYSICAL_RESOLUTION**
- Pair residual authorized as detector timing: **False**
- Single-stave resolution authorized: **False**

## Recommended headline

The published sub-nanosecond number is an analysis-level B4-B6 pair-core diagnostic from a retracted waveform interpretation; no intrinsic stave timing resolution is currently authorized.

## Findings

### CRITICAL: RETRACTED_POLARITY_MAP

The result consumes a channel map whose repository status is retracted.

```json
{
  "status": "RETRACTED_20260816_TRUNCATED_STAGING_DESYNC"
}
```

### CRITICAL: STRONGLY_NON_GAUSSIAN_RESIDUAL

The full RMS is many times the central-68% width.

```json
{
  "max_rms_over_sigma68": 47.967445959255606,
  "range_rms_over_sigma68": [
    24.32868317071204,
    47.967445959255606
  ]
}
```

### CRITICAL: GAUSSIAN_CORE_FIT_REJECTED

The reported Gaussian-core fit has unacceptable chi2/ndf at every fraction.

```json
{
  "minimum_chi2_ndf": 766.5
}
```

### HIGH: CORE_TAIL_TRADEOFF

Increasing CFD fraction narrows the central core while widening the full distribution.

```json
{
  "rms_first_last_ns": [
    3.9221,
    4.6267
  ],
  "sigma68_first_last_ns": [
    0.161213,
    0.096455
  ]
}
```

### MEDIUM: WAVEFORM_ROWS_LABELLED_AS_EVENTS

The selected total is two waveform rows per complete B4-B6 event.

```json
{
  "complete_pair_events": 228834.0,
  "ratio": 2.0,
  "selected_total": 457668.0
}
```

### CRITICAL: PAIR_ONLY_UNDERDETERMINED

One B4-B6 residual cannot identify B4 and B6 resolutions separately.

```json
{
  "model": "Var(dt_B4B6)=sigma_B4^2+sigma_B6^2-2*Cov(B4,B6)",
  "unknowns": [
    "sigma_B4",
    "sigma_B6",
    "Cov(B4,B6)"
  ]
}
```

### HIGH: SIGMA68_NOT_QUADRATURE_ADDITIVE

A robust interquantile width cannot generally be divided by sqrt(2).

```json
{}
```

## Fixed-seed sqrt(2) counterexamples

| case | true stave-A sigma68 | pair sigma68 | pair/sqrt(2) | relative error |
|---|---:|---:|---:|---:|
| equal independent normal | 0.9940 | 1.4048 | 0.9933 | -0.07% |
| unequal independent normal | 0.9925 | 2.2271 | 1.5748 | +58.67% |
| equal with common jitter | 1.4034 | 1.4063 | 0.9944 | -29.14% |
| equal independent Laplace | 1.1427 | 1.7735 | 1.2540 | +9.74% |

## Interpretation boundary

This audit does not reprocess immutable ROOT inputs. It diagnoses the published result contract and demonstrates why the current pair statistic cannot be promoted to an intrinsic stave resolution. Raw-data promotion requires every gate in `diagnostic_plot_manifest.csv` to pass.
