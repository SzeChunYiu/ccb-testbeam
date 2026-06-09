# Study report: S00b - downstream sensitivity to baseline estimator

- **Study ID:** S00b
- **Ticket:** `1781000826.539603.1a5d04dd`
- **Author:** `testbeam-laptop-1`
- **Date:** 2026-06-09
- **Depends on:** S00a
- **Input checksum(s):** raw B-stack ROOT hashes in `manifest.json`
- **Git commit:** `8fe8bbdbde5195345fcdf855e8404ea5bc262118`
- **Command:** `/home/billy/anaconda3/bin/python reports/1781000826.539603.1a5d04dd/s00b_downstream_sensitivity.py`

## 0. Question

Do timing and pile-up headline distributions change if low-amplitude B-stack pulses are selected with dynamic range rather than the S00 median-first-four baseline amplitude?

## 1. Reproduction

The S00 median-first-four gate was reproduced directly from raw ROOT before any downstream analysis.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| S00 median-first-four selected pulses | 640737 | 640737 | 0 | 0 | yes |
| S00a dynamic-range equivalent count | 706373 | 706373 | 0 | 0 | yes |
| Dynamic-only excess pulses | 65636 | 65636 | 0 | 0 | yes |
| Median-only pulses | 0 | 0 | 0 | 0 | yes |

The dynamic-range selector is a strict superset of the S00 selector in this data set. The excess is therefore a low-amplitude population admitted by baseline semantics, not a replacement population. The raw dynamic-range count exactly reproduces S00a's sorted `hrdMax > 1000` count.

## 2. Traditional Method

The traditional analysis is a deterministic raw-waveform comparison on held-out runs `55,57,63,65`. Timing uses baseline-subtracted CFD20 downstream B4/B6/B8 pair residuals, with the same fixed geometry correction used by prior timing studies. Pile-up/topology uses selected-event stave multiplicities.

| Held-out metric | Median-first-four | Dynamic range |
|---|---:|---:|
| selected pulses | 63075 | 69975 |
| selected events | 56465 | 61418 |
| multi-stave fraction | 0.0787 [0.0313, 0.1482] | 0.0937 [0.0451, 0.1635] |
| >=3-stave fraction | 0.0290 [0.0100, 0.0586] | 0.0343 [0.0148, 0.0643] |
| downstream-hit fraction | 0.0885 [0.0380, 0.1605] | 0.1037 [0.0524, 0.1750] |
| downstream all-hit fraction | 0.0096 [0.0032, 0.0205] | 0.0114 [0.0047, 0.0228] |
| downstream CFD20 pair sigma68 | 0.3109 [0.2826, 0.3159] samples | 0.3176 [0.2982, 0.3242] samples |

The normalized held-out timing histogram comparison gives chi2/ndf = 36.423 (109.27/3). The timing width shifts only modestly, while topology fractions move visibly because dynamic range admits extra downstream and multi-stave low-amplitude records.

## 3. ML Method

The ML method is a run-held-out logistic selector-shift classifier trained to identify dynamic-only pulses among dynamic-selected pulses. The primary model uses shape/timing features only: stave index, peak sample, area/amp, tail and early fractions, widths, and CFD20. It excludes median amplitude, dynamic amplitude, and their difference.

| Model | Held-out AUC | AP | Accuracy | Notes |
|---|---:|---:|---:|---|
| shape-only logistic | 0.9943 [0.9898, 0.9966] | 0.9839 [0.9716, 0.9908] | 0.9729 | primary non-leaky model |
| leaky amplitude logistic | 1.0000 | 1.0000 | 0.9970 | includes selector-defining amplitudes |
| within-run label shuffle | 0.9620 | 0.7972 | 0.7136 | run/composition confounding control |
| global label shuffle | 0.7738 | 0.4381 | 0.7131 | pipeline sanity control |

The leaky amplitude model is near-perfect because it sees variables that define the label. Both shuffled-label controls remain elevated, which is a leakage warning: run/topology composition and the sampled class mixture are strong enough that the shape-only classifier is not a clean individual-pulse proof. The ML result is therefore reported as a failed stress test for leakage-prone selector-shift modeling, not as support for adopting an ML selector.

## 4. Head-to-head Benchmark

Same held-out runs, same raw ROOT source:

| Method | Metric | Result | Interpretation |
|---|---|---:|---|
| Traditional deterministic gate comparison | dynamic-only excess / S00 pulses | 0.1024 | dynamic range over-selects by 10.24% |
| Traditional topology | held-out downstream fraction delta | 0.0152 | topology headline changes |
| Traditional timing | held-out sigma68 delta | 0.0067 samples | timing width changes less than topology |
| ML shape-only selector-shift model | held-out AUC | 0.9943 | too good; shuffled controls flag confounding |

Verdict: S00a's sorted `hrdMax` issue is not only bookkeeping for downstream selections. It mostly changes low-amplitude topology composition; the CFD20 timing headline is less sensitive but not exactly invariant.

## 5. Falsification

- **Pre-registered metric:** exact raw S00 count reproduction, exact dynamic-range equivalent reproduction, then held-out run-block bootstrap CIs for topology and timing metrics.
- **Failure criteria:** any S00 count delta or any evidence that the ML headline is only definition leakage without a valid raw deterministic comparison.
- **Result:** count reproduction passed exactly. The leaky model was identified as definition leakage and excluded. Both shuffled controls stayed elevated, so the ML headline is explicitly downgraded to a failed leakage stress test; the deterministic topology/timing comparison carries the result.

## 6. Threats to Validity

- **Benchmark/selection:** the traditional baseline is the deterministic selector comparison from raw ROOT. Timing uses CFD20, so a stronger template/timewalk timing analysis could change the timing-width sensitivity.
- **Data leakage:** all ML evaluation is by held-out run. Direct selector variables are isolated in the leaky ablation and are not included in the primary model.
- **Metric misuse:** ML predicts selector-induced population membership, not physics truth. The physics-facing outputs are the topology and timing distribution changes.
- **Post-hoc selection:** held-out runs and feature ablations are fixed in the script; no threshold scan is used for the headline result.

## 7. Provenance Manifest

`manifest.json` records raw input hashes, command, seed, environment, and output hashes.

## 8. Findings & Next Steps

Dynamic-range selection admits 65,636 additional B-stave records relative to S00. Those records are not harmless for downstream counting: multi-stave and downstream topology fractions shift on held-out runs. Timing residual widths are comparatively stable, but the selected all-hit sample is larger and not distribution-identical.

Queued follow-ups:

- **S00c:** add a CI/integrator regression that recomputes median and dynamic-range selected counts from raw ROOT and fails on accidental dynamic-range use.
- **S02c:** rerun the strongest template/timewalk timing method under the median-first-four and dynamic-range selectors to bound timing-systematic drift near threshold.

## 9. Reproducibility

Artifacts written: `counts_by_run.csv`, `timing_residuals.csv.gz`, `ml_selector_sample.csv.gz`, `traditional_summary.csv`, `ml_cv_scan.csv`, `ml_benchmark.csv`, `ml_reliability.csv`, figures, `result.json`, and `manifest.json`.
