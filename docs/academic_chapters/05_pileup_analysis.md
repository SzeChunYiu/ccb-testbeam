# §5 — Pile-up Analysis: Measured Live-Time and the Unresolved Rate Limit

> **Claim-governance correction (2026-07-25).** This chapter is synchronized to
> canonical claim rows `CL-010`, `CL-011`, and `CL-012`. The S10b live-time result is
> a `DONE_DATA_ONLY` measurement. A numerical pile-up tolerance is not accepted while
> `S-STAT-003` remains open.

## 5.1 Scientific questions and acceptance boundary

Pile-up occurs when more than one detector pulse contributes to the same reconstruction
window. Two related quantities must be kept separate:

1. **The measured live10 estimand:** for a declared pulse selection, alignment rule,
   per-stave template construction, and run weighting, when does the fitted template
   fall below 10% of its amplitude relative to CFD20?
2. **A maximum acceptable rate, Rmax:** what occupancy, distortion, or recovery-failure
   criterion is acceptable for the intended physics analysis?

S10b measures the first quantity. It does not by itself define the second. The accepted
scientific state is therefore:

- `CL-011`: `DONE_DATA_ONLY`, `truth_type=data_measurement`, blocked by
  `BLK-S10B-001` from being promoted to independently validated detector-wide truth;
- `CL-010`: numerical Rmax withheld, `BLOCKED` by `S-STAT-003`;
- `CL-012`: the historical 3.0448717948717947 MHz number is `SUPERSEDED` and must not
  be used as an accepted rate limit.

No universal detector dead time, accepted ESS operating limit, calibration constant, or
performance guarantee follows from this chapter.

## 5.2 Primary S10b evidence and provenance

The primary measurement is the tracked S10b bundle, not the later MV5 simulation.

| Item | Canonical record |
|---|---|
| Study / ticket | `S10b` / `1781000867.546870.5c124aaf` |
| Source commit | `da9651c56ef6495ce9656d84b69b600daa6d8f86` |
| Report | `reports/1781000867.546870.5c124aaf/REPORT.md` |
| Producer | `reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py` |
| Result | `reports/1781000867.546870.5c124aaf/result.json` |
| Manifest | `reports/1781000867.546870.5c124aaf/manifest.json` |
| Run summary | `reports/1781000867.546870.5c124aaf/heldout_run_summary.csv` |
| Python / seed | Python 3.7.6 / `10102` |
| Input scope | fourteen ROOT files, runs 44–57, with SHA-256 values in the manifest |

The manifest binds the report, result, run summary, producer, and other outputs by
SHA-256. The raw ROOT bytes are external to Git, so this chapter records the tracked
hashes and does not claim to have reprocessed them in this documentation unit.

## 5.3 Measurand, selection, and estimator

### 5.3.1 Pulse construction

The producer reads the B-stack waveform tree for runs 44–57. For each instrumented
stave it:

1. estimates the baseline as the median of samples 0–3;
2. subtracts that baseline from the 18-sample waveform;
3. defines amplitude as the largest baseline-subtracted sample;
4. retains pulses with amplitude greater than 1000 ADC;
5. estimates CFD20 by interpolation on the rising edge.

These details define the population to which the result applies. The source does not
implement the different selection described in the former chapter (for example, an
isolated-pulse requirement with amplitude above 3000 ADC and an upper 7000 ADC cut).
Those former details are not used here.

### 5.3.2 Leave-one-run-out template estimate

For each held-out run, the remaining runs form the training sample. Median normalized
waveform templates are built separately for B2, B4, B6, and B8 on a 5 ns interpolation
grid. The post-peak template tail is fitted with

\[
  y(t) = c + a\exp(-t/\tau),
\]

and the fitted crossing of the 10% level is measured relative to CFD20. The per-stave
crossings are combined using that held-out run's observed stave composition. This
produces one live10 estimate per held-out run.

The canonical central estimate is the **equal-weight arithmetic mean of the fourteen
run-level values**. It is therefore a run-average estimand, not a pulse-weighted global
average and not a fitted scintillator decay constant.

### 5.3.3 Run bootstrap

The source uses a nonparametric bootstrap of the fourteen run-level estimates with
5,000 draws and percentile endpoints at 2.5% and 97.5%. The bootstrap unit is the run.
The recorded interval is a **95% run-bootstrap interval**, not a 68% pulse bootstrap.
It captures run-to-run variation under the observed run sample and source algorithm.
It is not a complete systematic uncertainty model.

## 5.4 Exact result and independent reconstruction

The source-backed result is:

\[
  \tau_{\mathrm{live10}} = 124.79018394263471\ \mathrm{ns},
\]

with run-bootstrap 95% interval

\[
  [123.33094981246663,\ 126.35875117626817]\ \mathrm{ns}.
\]

The held-out summary contains:

- **14 unique runs**;
- **252266 selected pulses** in total;
- one stave-composition-weighted live10 value per run.

The unweighted mean of those fourteen values reproduces
`124.79018394263471 ns`. Replaying the recorded random-number stream reproduces the
tracked percentile endpoints. The exact value and interval are retained rather than
rounded values because the ledger binds to the machine-readable result.

| Quantity | Value | Interpretation |
|---|---:|---|
| Run-average live10 | 124.79018394263471 ns | data measurement for the declared S10b procedure |
| Run-bootstrap 95% low | 123.33094981246663 ns | percentile endpoint across resampled runs |
| Run-bootstrap 95% high | 126.35875117626817 ns | percentile endpoint across resampled runs |
| Runs | 14 | bootstrap and averaging unit |
| Selected pulses | 252266 | total pulses entering the held-out summaries |
| Canonical status | `DONE_DATA_ONLY` | no independent closure or accepted systematic model |

The source provides **no statistical/systematic/total uncertainty decomposition**.
The former `0.5 ns`, `1.0 ns`, and `1.12 ns` fields are unsupported and are not used.

## 5.5 Interpretation and limitations

The measured quantity is threshold-, selection-, alignment-, fit-window-, stave-mix-,
and run-weighting-specific. It is not a detector-wide universal dead time and must not be described as one. Important unresolved sensitivities include:

- the choice of 10% crossing rather than another distortion criterion;
- baseline, amplitude threshold, saturation, and waveform-window effects;
- fit-model and fit-range sensitivity;
- equal-run weighting versus pulse or exposure weighting;
- temporal, stave, current, and operating-condition transfer;
- independent cross-method or external-data closure;
- an accepted systematic uncertainty model.

The empirical per-pulse width and the ML predictor in the S10b bundle are diagnostic
cross-checks, not independent validation of the canonical run-average template
measurement. Their targets and assumptions are not interchangeable with `CL-011`.

## 5.6 What MV5 does and does not establish

MV5 stores `tau_eff_new_ns = 124.8` as an input to analytic and simulated pile-up
calculations. The rounded value is reused from S10b; MV5 does **not** independently
measure or validate the S10b live10 estimand.

The tracked MV5 summary reports recovery-failure rates between 0.028 and 0.03475 over
0.5–4.0 MHz and records:

```text
rmax_from_failure_ceiling_mhz = null
failure_ceiling = 0.17
```

Thus no simulated recovery-failure-ceiling crossing is present in the tracked range.
The value `3.0448717948717947 MHz` instead comes from

\[
  (1 / 124.8\ \mathrm{ns}) \times 0.38,
\]

where `0.38` is the recorded beam duty factor. A duty factor is not an accepted
occupancy-quality or reconstruction-failure criterion. This arithmetic is retained only
as superseded history under `CL-012`.

## 5.7 Why Rmax remains withheld

For a Poisson model, a rate derived from a live-time requires a declared criterion. For
example, if a maximum companion probability \(p_{\max}\) were accepted, one possible
relationship would be

\[
  R_{\max} = -\ln(1-p_{\max}) / \tau_{\mathrm{live10}}.
\]

If a different occupancy or reconstruction-quality statistic is used, its mapping to
rate is different. S10b measures the denominator-like timescale; it does not authorize
the criterion in the numerator. Because the measurand, threshold, failure ceiling,
normalization across staves, and uncertainty propagation have not been preregistered
and closed, `CL-010` correctly withholds a numerical Rmax under `S-STAT-003`.

The former 4.22 MHz and 3.044–3.05 MHz values must not be cited as accepted limits.
No ESS shielding or operational-rate requirement should be derived from them until the
criterion and transfer model are validated.

## 5.8 Better-method comparison and closure plan

A stronger program should compare methods rather than treating a newer method as
automatically superior.

| Method | Strength | Main sensitivity | Required evidence |
|---|---|---|---|
| Run-held-out fitted 10% crossing | Directly tied to tracked data templates and run variation | fit form/range, threshold, stave mix | current S10b baseline; sensitivity scans |
| Direct empirical width quantile | Minimal tail-model assumption | sample censoring and noise threshold | run/stave distributions and uncertainty |
| Alternative tail models | Tests exponential-model bias | model selection and extrapolation | held-out predictive diagnostics |
| Threshold scan (5–30%) | Exposes definition dependence | no unique physical criterion | preregistered distortion mapping |
| Injected two-pulse recovery | Connects waveform overlap to reconstruction harm | simulation/data transfer | truth-labelled injection and data closure |
| Independent operating-condition sample | Tests external transfer | changed detector/beam state | content-addressed new data and fixed method |

Before promoting `CL-011` or restoring Rmax, the next analysis must:

1. freeze the target distortion or failure measurand before inspecting the final scan;
2. repeat S10b with content-addressed inputs and current software;
3. report run-, stave-, current-, threshold-, fit-range-, and weighting sensitivity;
4. compare at least one non-exponential and one empirical method;
5. quantify bias and coverage using controlled injection/recovery;
6. validate transfer on independent data or a clearly separated control sample;
7. propagate the accepted live-time and criterion uncertainties to the rate;
8. publish machine-readable tables and residual, stability, and sensitivity plots.

## 5.9 Required visual evidence

The following plots are required for scientific closure. They are specifications until
content-addressed input bytes and compute are available.

| Plot | Inputs and selections | Required display | Success / failure meaning |
|---|---|---|---|
| Run-level live10 stability | fourteen S10b held-out rows | estimate by run, exact 95% interval, run pulse counts | exposes run dependence and influential runs |
| Stave-by-run crossing map | `template_fit_by_run_stave.csv` | B2/B4/B6/B8 crossings, fit failures, pulse weights | tests stave transfer and missingness |
| Tail-fit diagnostics | median templates and fitted residuals | data, model, residual/pull, fit range, 10% crossing | detects model or fit-window bias |
| Threshold sensitivity | fixed templates, preregistered thresholds | crossing versus threshold with run intervals | quantifies definition dependence |
| Weighting sensitivity | run-, pulse-, and exposure-weighted estimates | before/after estimates and deltas | detects estimand changes from weighting |
| Injection/recovery closure | truth-labelled synthetic or overlaid pairs | bias, resolution, failure versus separation/rate | connects live-time definition to reconstruction harm |
| Rmax criterion scan | accepted criterion and propagated nuisance draws | rate, uncertainty band, failure/quality curve | required before any numerical rate is restored |

Every generated figure must record axes, units, selections, normalization, uncertainty
meaning, generation command, input/output hashes, and a falsifiable interpretation.

## 5.10 Reproducibility

Primary historical command:

```text
/home/billy/anaconda3/bin/python \
  reports/1781000867.546870.5c124aaf/s10b_tau_eff_template_fit.py
```

Public-claim validation command for the current repository:

```text
python tools/audit/validate_chapter5_tau_eff_rmax.py \
  --chapter docs/academic_chapters/05_pileup_analysis.md \
  --ledger docs/claim_ledger.csv \
  --result reports/1781000867.546870.5c124aaf/result.json \
  --manifest reports/1781000867.546870.5c124aaf/manifest.json \
  --heldout reports/1781000867.546870.5c124aaf/heldout_run_summary.csv \
  --mv5 reports/mv5_pileup_1782678353/mv5_pileup_summary.json \
  --output-json docs/validation/chapter5_tau_eff_rmax_validation.json
```

The validator checks exact source identity, ledger binding, independent arithmetic,
public wording, the MV5 null failure crossing, and the absence of superseded claims.

## 5.11 Chapter verdict

### Evidence-backed

- S10b measures a run-average 10% template crossing relative to CFD20 of
  `124.79018394263471 ns` with run-bootstrap 95% interval
  `[123.33094981246663, 126.35875117626817] ns`.
- The estimate uses fourteen runs and 252266 selected pulses.
- The claim is `DONE_DATA_ONLY`, not independently validated detector-wide truth.

### Withheld or superseded

- Numerical Rmax is `BLOCKED` under `S-STAT-003`.
- `3.0448717948717947 MHz` is superseded duty-factor arithmetic, not a recovery-ceiling
  crossing or accepted rate limit.
- MV5 reuse of rounded `124.8 ns` is not independent validation.
- No unsupported uncertainty decomposition or universal dead-time interpretation is
  authorized.

### Next accepted unit

Execute the preregistered sensitivity and independent-closure program, then update the
ledger and public surfaces only if the resulting evidence satisfies the declared gate.
