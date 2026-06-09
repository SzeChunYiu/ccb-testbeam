# Study report: S00a - sorted hrdMax vs raw HRDv selection semantics

- **Study ID:** S00a
- **Ticket:** `1780997954.15097.28a25ecb`
- **Author (worker label):** testbeam-laptop-2
- **Date:** 2026-06-09
- **Depends on:** S00
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `696daf4c4b7df48eae2ff23b7f6a08be4e0dcc1b`
- **Config:** embedded in `s00a_sorted_hrdmax_semantics.py`

## 0. Question

Can sorted even-channel `hrdMax` be used as a count proxy for the S00 raw `HRDv` gate, and what exact branch semantics explain the overcount?

Pre-registered metric and cuts from the ticket: match raw S00 `A > 1000 ADC` counts, then compare sorted even-channel `hrdMax > 1000 ADC` on matched `(run, event, stave)` records. The falsification test is the exact identity `hrdMax == max(HRDv) - min(HRDv)` with zero mismatches over the configured S00 B-stack runs.

## 1. Reproduction (mandatory - gate)

The S00 raw gate is reproduced exactly from raw ROOT, then the sorted semantic identity is tested.

| Quantity                                                   |   Report value |   Reproduced |   Delta |   Tolerance | Pass   |
|:-----------------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| raw HRDv selected B-stave pulses                           |         640737 |       640737 |       0 |           0 | True   |
| sorted hrdMax equals max(HRDv)-min(HRDv) for even channels |              0 |            0 |       0 |           0 | True   |
| sorted hrdMaxTS equals raw argmax sample for even channels |              0 |            0 |       0 |           0 | True   |

Gate result: **PASSED** for the raw S00 count (`640,737` selected pulses). The sorted semantic identity also passes with zero formula and timestamp mismatches over `4,386,912` matched even-channel records.

## 2. Traditional (non-ML) method

For every configured S00 B run, I matched `h101/EVT` to sorted `tree/hrdEvtNo`, reshaped `HRDv` into eight 18-sample channels, and evaluated two deterministic amplitudes on physical even channels `{0,2,4,6}`:

- raw S00 gate amplitude: `A_raw = max(HRDv) - median(HRDv[0:4])`
- sorted branch amplitude: `hrdMax = max(HRDv) - min(HRDv)`

Counting `hrdMax > 1000` gives `706,373` pulses, which is `65,636` more than the raw gate (`10.24%` relative overcount). Event-level sorted selection exceeds raw event selection by `48,337` events. Because this is a fixed-count data-integrity comparison, statistical uncertainty and chi2/ndf are not applicable; the relevant uncertainty is semantic/systematic, and the exact identity above resolves it.

The overcount mechanism is threshold migration: if the waveform minimum is below the median of samples 0-3, `hrdMax` is larger than the raw S00 amplitude. Sorted-only pulses have a median raw margin of `674.8` ADC below the 1000 ADC cut and a median `(median(samples 0:4) - waveform minimum)` of `3054.0` ADC across runs.

Key artifacts: `counts_by_run.csv`, `counts_by_stave.csv`, `distribution_quantiles.csv`, `fig_overcount_by_run.png`, `fig_raw_vs_sorted_hmax.png`, and `fig_sorted_only_threshold_margin.png`.

## 3. ML method

The ML method is a run-split sanity check that asks whether sorted-only branches can learn the raw gate. It is not used for the production count. Features are `hrdMax`, `hrdMaxTS`, `hrdSum`, `hrdTrMax`, and stave index. Labels are the raw `HRDv` gate. Runs 57 and 65 are held out. A calibrated logistic regression scans `C in {0.01, 0.1, 1.0, 10.0}` with 3-fold CV on non-held-out runs and isotonic calibration. Held-out CIs use 300 bootstrap resamples.

Hyperparameter scan:

|         C |   cv_roc_auc_mean |   cv_roc_auc_std |
|----------:|------------------:|-----------------:|
|  0.010000 |          0.999016 |         0.000129 |
|  0.100000 |          0.999222 |         0.000040 |
|  1.000000 |          0.999263 |         0.000017 |
| 10.000000 |          0.999262 |         0.000019 |

## 4. Head-to-head benchmark (mandatory)

Same held-out runs, same raw-gate selection metric:

| method                                            | metric                      |   accuracy |   accuracy_ci_low |   accuracy_ci_high |   false_positive_rate |   false_positive_rate_ci_low |   false_positive_rate_ci_high |   false_negative_rate |   precision |   recall |
|:--------------------------------------------------|:----------------------------|-----------:|------------------:|-------------------:|----------------------:|-----------------------------:|------------------------------:|----------------------:|------------:|---------:|
| sorted hrdMax > 1000 proxy                        | raw-gate selection accuracy |   0.985446 |          0.985048 |           0.985832 |              0.016106 |                     0.015674 |                      0.016548 |              0.000000 |    0.868796 | 1.000000 |
| calibrated logistic regression on sorted branches | raw-gate selection accuracy |   0.994269 |          0.993946 |           0.994549 |              0.005247 |                     0.004945 |                      0.005558 |              0.010271 |    0.952645 | 0.989729 |

Verdict: ML reduces the sorted-proxy false-positive rate from `0.0161` to `0.0052` on the held-out benchmark, but it still does not beat the exact raw waveform gate. Downstream workers should not use sorted `hrdMax` as a count proxy; if a gate count matters, read raw `HRDv`.

## 5. Falsification (mandatory - guards against p-hacking)

- **Pre-registration:** metric is raw-gate selection agreement at the fixed `1000 ADC` threshold; no cut scan.
- **Falsification test:** any mismatch in `hrdMax == max(HRDv) - min(HRDv)` for even channels would falsify the derived-semantics claim.
- **Result:** zero mismatches in `4,386,912` records. Sorted counts exceed raw counts in all `33` configured runs; a two-sided sign-test reference gives `p=2.33e-10`. Number of tried semantic formulas: 1.

## 6. Threats to validity

- **Benchmark/selection:** the baseline is the exact S00 raw gate, not a weak threshold proxy.
- **Data leakage:** ML split is by run. The ML labels come from raw `HRDv`, while features are sorted branches only. The ML result is a branch-correction sanity check, not physics truth.
- **Metric misuse:** the decision metric is raw-gate agreement. Full count distributions and run/stave tables are reported; no fit is used, so chi2/ndf is not applicable.
- **Post-hoc selection:** threshold and runs are inherited from S00/ticket. I tested one semantic formula after inspecting branch definitions: dynamic range versus median-first-four baseline.

## 7. Provenance manifest

Machine-readable provenance is in `manifest.json`; machine-readable verdict is in `result.json`.

## 8. Findings & next steps

Finding: sorted `hrdMax` is not the S00 amplitude. It is the full waveform dynamic range, whereas S00 uses a median-first-four baseline. This makes sorted `hrdMax > 1000` a systematic overcount by `65,636` pulses for the S00 runs. The result agrees with the fleet summary that S00 must remain pinned to raw ROOT; it sharpens the previous open question by identifying the exact derived-branch semantic.

Hypothesis: threshold-near pulse counts are especially sensitive to baseline estimator choice, so any downstream quantity that uses low-amplitude selected pulses can shift if workers silently swap raw median-baselined amplitudes for sorted dynamic-range amplitudes. Confirmation would be a timing/pile-up sensitivity scan that reruns a downstream result with both definitions; falsification would show no material change outside the S00 count gate.

Proposed next tickets:

- S00b: downstream sensitivity to baseline estimator. Question: do timing/pile-up headline distributions change if low-amplitude pulses are selected with dynamic-range versus median-first-four amplitudes? Expected information gain: bounds whether this S00a semantic difference is only a bookkeeping issue or a physics-analysis systematic.
- S16b: independent pedestal estimator closure. Question: which early-sample baseline estimator is least biased by pre-trigger activity? Expected information gain: directly informs S16 pedestal validation and prevents derived-branch semantics from being mistaken for detector behavior.

## 9. Reproducibility

Exact command:

```bash
python reports/1780997954.15097.28a25ecb__s00a_sorted_hrdmax_semantics/s00a_sorted_hrdmax_semantics.py
```

Generated artifacts are listed in `manifest.json`.
