# Study report: S05a - A-stack external control for B-stack timing covariance

- **Study ID:** S05a
- **Ticket:** 1781001480.696013.4ac50583
- **Author (worker label):** testbeam-laptop-2
- **Date:** 2026-06-09
- **Input checksum(s):** `input_sha256.csv`
- **Git commit:** `c2e1948502902d05b01adee271ff05b8fa931132`
- **Config:** `configs/s05a_astack_external_control.yaml`

## 0. Question

Do event-matched A-stack waveform/timing features explain B-stack pair residual components that would otherwise look like detector-local covariance in a B-only variance decomposition?

The analysis first reproduces raw-count anchors from `HRDv`, then builds `(run, EVENTNO)` matched A/B events. The modeled target is the CFD20 B-stack pair residual after the fixed 2 cm/layer TOF correction. Training and evaluation are leave-one-run-out.

## 1. Reproduction from raw ROOT

| quantity                                        |   report_value |   reproduced |   delta |   tolerance | pass   |
|:------------------------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total_selected_b_pulses                         |         640737 |       640737 |       0 |           0 | True   |
| sample_i_analysis_b_selected_pulses             |         252266 |       252266 |       0 |           0 | True   |
| sample_ii_analysis_b_selected_pulses            |         125096 |       125096 |       0 |           0 | True   |
| astack_sample_iii_analysis_events_with_selected |           7168 |         7168 |       0 |           0 | True   |
| astack_sample_iii_analysis_selected_pulses      |           9682 |         9682 |       0 |           0 | True   |
| astack_sample_iv_analysis_events_with_selected  |            767 |          767 |       0 |           0 | True   |
| astack_sample_iv_analysis_selected_pulses       |            894 |          894 |       0 |           0 | True   |

The B-stack S00 count and A-stack S18 count anchors reproduce exactly before the external-control study. The main modeling table uses B pairs selected with `A > 1000 ADC`; A-stack features are read for the matched event whether or not the A pulse is above threshold, because requiring A1/A3 selected coincidences leaves only a small control sample.

Pair-row counts:

| pair   |   n_pair_rows |
|:-------|--------------:|
| B2-B4  |         26373 |
| B2-B6  |         12621 |
| B2-B8  |          4942 |
| B4-B6  |         12191 |
| B4-B8  |          4541 |
| B6-B8  |          4789 |

## 2. Traditional method

The traditional method is a leave-run-out Ridge residual model. The B-only baseline uses pair identity plus B-pair amplitude/shape terms. The external-control version adds A1/A3 amplitudes, peak samples, tails, CFD20 times, A3-A1 residual, A mean time, and A amplitude-balance terms. It receives no run id, event id, or target residual feature.

| method               | subset          |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                     |
|:---------------------|:----------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:---------------------------------------------------------|
| raw_pair_median      | all             |         65457 |       21 |      2.08192 |             1.76676 |              6.74167 |      20.6765  |             0.141635  | pair-median centered raw CFD20 residual                  |
| raw_pair_median      | A_any_selected  |           380 |       17 |      3.42713 |             2.12168 |             17.5898  |      28.8808  |             0.202632  | pair-median centered raw CFD20 residual                  |
| raw_pair_median      | downstream_only |         21521 |       21 |      1.73237 |             1.68933 |              1.76338 |       6.53758 |             0.0171925 | pair-median centered raw CFD20 residual                  |
| traditional_b_only   | all             |         65457 |       21 |      7.74366 |             7.03322 |              9.58308 |      12.6104  |             0.478574  | run-held-out Ridge using B pair amplitude/shape features |
| traditional_b_only   | A_any_selected  |           380 |       17 |      9.19674 |             7.44069 |             13.7647  |      15.0136  |             0.565789  | run-held-out Ridge using B pair amplitude/shape features |
| traditional_b_only   | downstream_only |         21521 |       21 |      7.27529 |             6.82633 |              8.20252 |       9.18088 |             0.467032  | run-held-out Ridge using B pair amplitude/shape features |
| traditional_b_plus_a | all             |         65457 |       21 |      7.74558 |             7.07698 |              9.65657 |      12.6129  |             0.478283  | same Ridge plus event-matched A-stack controls           |
| traditional_b_plus_a | A_any_selected  |           380 |       17 |      9.10574 |             7.57063 |             13.8157  |      15.0432  |             0.547368  | same Ridge plus event-matched A-stack controls           |
| traditional_b_plus_a | downstream_only |         21521 |       21 |      7.26762 |             6.81044 |              8.27663 |       9.18339 |             0.467497  | same Ridge plus event-matched A-stack controls           |

Run-held-out Ridge hyperparameters:

|   heldout_run |   n_pair_rows |   ridge_alpha_b |   ridge_alpha_b_plus_a |
|--------------:|--------------:|----------------:|-----------------------:|
|            44 |           169 |              10 |                     10 |
|            45 |          1786 |              10 |                     10 |
|            46 |            13 |              10 |                     10 |
|            47 |           156 |              10 |                     10 |
|            48 |          1098 |              10 |                     10 |
|            49 |          1186 |              10 |                     10 |
|            50 |          1289 |              10 |                     10 |
|            51 |           616 |              10 |                     10 |
|            52 |           312 |              10 |                     10 |
|            53 |          1120 |              10 |                     10 |
|            54 |          1050 |              10 |                     10 |
|            55 |           755 |              10 |                     10 |
|            56 |          1669 |              10 |                     10 |
|            57 |          1220 |              10 |                     10 |
|            58 |          1207 |              10 |                     10 |
|            59 |         11187 |              10 |                     10 |
|            60 |         10523 |              10 |                     10 |
|            61 |         11851 |              10 |                     10 |
|            62 |         10935 |              10 |                     10 |
|            63 |          5802 |              10 |                     10 |
|            65 |          1513 |              10 |                     10 |

The bootstrap delta for adding A controls to the traditional model is [-0.017, 0.017] ns on sigma68, with p=0.936. A negative delta would mean A controls narrowed the B residuals.

## 3. ML method

The ML method is leave-run-out ExtraTrees regression. The B-only version tests whether nonlinear B amplitude/shape features explain residual structure; the B-plus-A version tests whether event-matched A controls add anything beyond that.

| method                  | subset          |   n_pair_rows |   n_runs |   sigma68_ns |   sigma68_ci_low_ns |   sigma68_ci_high_ns |   full_rms_ns |   tail_frac_abs_gt5ns | note                                                     |
|:------------------------|:----------------|--------------:|---------:|-------------:|--------------------:|---------------------:|--------------:|----------------------:|:---------------------------------------------------------|
| ml_extra_trees_b_only   | all             |         65457 |       21 |      1.64344 |             1.46808 |              2.2409  |       6.37491 |             0.109919  | run-held-out ExtraTrees using B features only            |
| ml_extra_trees_b_only   | A_any_selected  |           380 |       17 |      2.43124 |             1.86286 |              3.1079  |       5.3073  |             0.152632  | run-held-out ExtraTrees using B features only            |
| ml_extra_trees_b_only   | downstream_only |         21521 |       21 |      1.16442 |             1.12068 |              1.25715 |       4.06619 |             0.0187259 | run-held-out ExtraTrees using B features only            |
| ml_extra_trees_b_plus_a | all             |         65457 |       21 |      1.66413 |             1.48936 |              2.35479 |       6.42693 |             0.111126  | run-held-out ExtraTrees using B features plus A controls |
| ml_extra_trees_b_plus_a | A_any_selected  |           380 |       17 |      2.45899 |             1.82496 |              3.0336  |       5.57251 |             0.160526  | run-held-out ExtraTrees using B features plus A controls |
| ml_extra_trees_b_plus_a | downstream_only |         21521 |       21 |      1.175   |             1.13915 |              1.24093 |       4.09507 |             0.0187259 | run-held-out ExtraTrees using B features plus A controls |

The ML B-plus-A minus ML B-only bootstrap delta is [-0.007, 0.042] ns, p=0.116. The ML B-plus-A minus traditional-A bootstrap delta is [-7.256, -5.582] ns, p=0.000.

## 4. Leakage checks

| check                       |   sigma68_ns | interpretation                                             |
|:----------------------------|-------------:|:-----------------------------------------------------------|
| actual_ml_b_plus_a          |      1.66413 | nominal run-held-out ML residual width                     |
| runwise_shuffled_a_controls |      1.66843 | A controls lose event matching but preserve run marginals  |
| intentional_target_echo     |      0       | positive leakage sentinel; should be unrealistically small |

The runwise-shuffled A-control check preserves A feature marginals inside each run but breaks event matching. If the nominal result were driven by true event-level A/B timing, it should outperform this shuffled control. The target-echo check is an intentional positive leakage sentinel.

## 5. Residual covariance

Compact pair-pair covariance summary by method; the full run/pair table is `pair_covariance_by_run.csv`.

| method                  |   n_covariances |   mean_abs_cov_ns2 |   median_abs_cov_ns2 |   max_abs_cov_ns2 |
|:------------------------|----------------:|-------------------:|---------------------:|------------------:|
| ml_extra_trees_b_only   |             300 |            18.0442 |              3.55663 |           462.379 |
| ml_extra_trees_b_plus_a |             300 |            18.5211 |              3.14907 |           477.711 |
| raw_pair_median         |             300 |           231.113  |             15.1896  |          2219.75  |
| traditional_b_only      |             300 |            82.6494 |             45.2045  |           571.989 |
| traditional_b_plus_a    |             300 |            82.6746 |             45.2831  |           572.052 |

## 6. Finding

S05a finds no statistically secure evidence that event-matched A-stack controls remove a common B-stack pair-residual component. The A-control Ridge delta CI crosses zero, the ML B-plus-A improvement over ML B-only is not secure unless its CI is wholly below zero, and the runwise-shuffled A-control check is essentially identical to the nominal A-control result. This favors a detector-local or B-topology explanation for the observed B-pair covariance under the current raw selection, with an important caveat: threshold-selected A/B coincidences are sparse, so the A control is mostly a low-amplitude waveform/timing proxy rather than a clean A1-A3 selected telescope.

## 7. Follow-up tickets

- S05b: repeat A-stack external-control covariance on sorted ROOT with looser pulse-quality tiers; expected information gain is separating low A/B coincidence statistics from a true null external-control result.
- S05c: fit a hierarchical run/stave covariance model for B-stack pair residuals with B2-containing pairs separated; expected information gain is quantifying detector-local covariance without relying on A-stack coincidences.

## 8. Reproducibility

```bash
.venv/bin/python scripts/s05a_astack_external_control.py --config configs/s05a_astack_external_control.yaml
```
