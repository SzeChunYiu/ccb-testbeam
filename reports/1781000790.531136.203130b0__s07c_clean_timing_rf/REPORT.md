# Study report: S07c - clean-timing RF vs q_template/downstream-span baseline

- **Ticket:** 1781000790.531136.203130b0
- **Author:** testbeam-laptop-2
- **Date:** 2026-06-09
- **Inputs:** raw B-stack ROOT plus S01 q_template table; checksums in `input_sha256.csv`
- **Command:** `.venv/bin/python /home/billy/.tb-workers/testbeam-laptop-2/reports/1781000790.531136.203130b0__s07c_clean_timing_rf/s07c_clean_timing_rf.py`
- **Git commit at run:** `f79140bd74d5bb923cf8d23ef832a40b5ba5deba`

## 0. Question
Does the App.A clean-timing RF add information beyond strong conventional `q_template` and downstream-span cuts without label leakage?

## 1. Reproduction first
The raw S00 selected-pulse gate reproduces exactly:

| quantity              |   report_value |   reproduced |   delta |   tolerance | pass   |
|:----------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_pulses |         640737 |       640737 |       0 |           0 | True   |
| sample_i_calib        |         248745 |       248745 |       0 |           0 | True   |
| sample_i_analysis     |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_calib       |          14630 |        14630 |       0 |           0 | True   |
| sample_ii_analysis    |         125096 |       125096 |       0 |           0 | True   |

The ticket body contains no numeric target. The only numeric App.A target found in the repository is in `docs/07_ml_methods.md`: 12,147 labelled events, 10,636 clean and 1,511 violating. Recomputing the documented weak labels directly from raw `HRDv` with CFD20 gives:

| quantity        |   documented |   raw_cfd20 |   delta |
|:----------------|-------------:|------------:|--------:|
| labelled_events |        12147 |        9897 |   -2250 |
| clean           |        10636 |        7583 |   -3053 |
| violating       |         1511 |        2314 |     803 |

This does **not** reproduce the historical App.A number. I therefore treat the historical count as documentation drift or a missing derived-table definition, and the rest of the benchmark is explicitly scoped to this raw-CFD20-labelled dataset.

## 2. Dataset
Rows are events with at least two downstream selected staves. Labels are clean if downstream span <5 ns and all-span <10 ns; violating if downstream span >10 ns or B2 is displaced by >20 ns. Ambiguous events are excluded. The event table has 9897 labelled rows across 32 runs.

## 3. Traditional methods
The strong conventional baseline is a fold-local standardized score using downstream span plus `q_template` candidates. This is powerful but label-overlapping because downstream span is part of the weak-label definition. I also report a de-leaked q_template-only traditional score, with no timing span feature.

## 4. ML method
The ML method is a random forest evaluated out-of-fold by run. Features include amplitudes, log-amplitudes, hit flags, multiplicities, waveform-shape summaries, and S01 `q_template`; they exclude run, sample, absolute peak sample, downstream span, all-span, pair residuals, and B2 displacement. Two labelled raw events had no S01 q_template match and use train-blind column medians for q features. Best RF parameters:

{"n_estimators": 300, "max_depth": 7, "min_samples_leaf": 15}

RF CV scan:

|   max_depth |   min_samples_leaf |   n_estimators |   roc_auc |   average_precision |     brier |
|------------:|-------------------:|---------------:|----------:|--------------------:|----------:|
|           7 |                 15 |            300 |  0.993473 |            0.997787 | 0.0268407 |
|           5 |                 20 |            250 |  0.990232 |            0.996487 | 0.0343248 |
|           4 |                 25 |            150 |  0.98584  |            0.994762 | 0.0443435 |

## 5. Head-to-head benchmark
Metrics use run-bootstrap 95% CIs over held-out out-of-fold predictions.

| method                      |   roc_auc |   roc_auc_ci_low |   roc_auc_ci_high |   average_precision |   average_precision_ci_low |   average_precision_ci_high | note                                                      |        brier |   brier_ci_low |   brier_ci_high |
|:----------------------------|----------:|-----------------:|------------------:|--------------------:|---------------------------:|----------------------------:|:----------------------------------------------------------|-------------:|---------------:|----------------:|
| traditional_span_q_template |  0.9123   |         0.883017 |          0.929095 |            0.960569 |                   0.915408 |                    0.976633 | Uses downstream span; overlaps weak-label definition      | nan          |   nan          |    nan          |
| traditional_q_template_only |  0.717051 |         0.691238 |          0.74028  |            0.881935 |                   0.817574 |                    0.907882 | No timing-span feature                                    | nan          |   nan          |    nan          |
| rf_clean_timing             |  0.993473 |         0.991384 |          0.995262 |            0.997787 |                   0.995892 |                    0.998559 | RF excludes timing spans, pair residuals, run, and sample |   0.0268407  |     0.0244111  |      0.0302598  |
| leaky_rf_control            |  1        |         1        |          1        |            1        |                   1        |                    1        | RF with forbidden label-defining timing spans             |   0.00236243 |     0.00214159 |      0.00266429 |

RF minus q_template-only AUC = 0.276 [0.254, 0.300]. RF minus span+q_template AUC = 0.081 [0.064, 0.110].

## 6. Leakage hunt
- The RF feature list has 46 columns and no forbidden timing-span or absolute peak-sample columns: `[]`.
- The `leaky_rf_control` deliberately includes downstream span, all-span, and B2 displacement. Its score is a ceiling/control, not an admissible model.
- Because the strong span+q_template baseline uses a label-defining variable, neither its score nor the RF-vs-baseline gain is evidence of external clean-timing truth. The RF appears to add non-span proxy information on this weak label, but adoption still needs an independent timing-tail validation.

## 7. Verdict
On the raw-CFD20 reproduction, the RF beats both the q_template-only and downstream-span + q_template traditional scores. However, the historical 12,147-event App.A count is not reproduced, the target is still a timing-derived weak label, and the leaky-control ceiling is essentially perfect. S03/S04/S09 should therefore not consume this RF score as an adoption-ready clean-timing probability; use it only as a non-timing-shape ranking cross-check until the historical App.A label source is recovered and an external timing-tail validation is run.

## 8. Follow-ups
- S07d: recover the historical App.A 12,147-event table or retire that number; expected information gain: separates documentation drift from a detector result.
- S03b: validate q_template-only clean-timing cuts against held-out downstream timing tails; expected information gain: tests whether shape quality adds independent timing rejection without span leakage.
