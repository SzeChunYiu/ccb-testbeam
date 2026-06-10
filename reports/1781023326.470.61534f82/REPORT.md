# P04h A-Stack Charge-Transfer Support Map

- **Ticket:** `1781023326.470.61534f82`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.
- **Split:** leave-one-run-out by run; confidence intervals resample held-out run blocks.
- **Target:** selected A1/A3 positive-lobe charge on `(run, EVT)` rows with selected B2 and selected A1 or A3.

## Raw Reproduction First

B-stack S00 selected-pulse anchor: `640,737` vs `640,737`.

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

P04c A-stack charge-transfer number reproduced before the support map: traditional res68 `0.5193` and waveform ExtraTrees res68 `0.5197` on `4,055` rows.

## Head-To-Head

| method                       |    n |   bias_median_frac | bias_ci95                                     |   res68_abs_frac | res68_ci95                               |   full_rms_frac |   within_25pct |   calibration_coverage68 |
|:-----------------------------|-----:|-------------------:|:----------------------------------------------|-----------------:|:-----------------------------------------|----------------:|---------------:|-------------------------:|
| b2_loglinear                 | 4055 |         -0.0476348 | [-0.06586588295839484, -0.024568095893275355] |         0.520285 | [0.5043523407499432, 0.5394287779532742] |        0.84526  |       0.344513 |                 0.678422 |
| peak_integral_topology_ridge | 4055 |         -0.0478954 | [-0.06285705472863264, -0.014291010558317479] |         0.526743 | [0.5124923383606044, 0.5408191974893906] |        0.848154 |       0.343773 |                 0.671517 |
| adaptive_template_ridge      | 4055 |         -0.0469556 | [-0.06561142221105139, -0.016734132858004836] |         0.5262   | [0.5123154771189777, 0.5383269444903384] |        0.848443 |       0.343527 |                 0.67127  |
| b_waveform_extra_trees       | 4055 |         -0.0474265 | [-0.06959686299862128, -0.025545541551236322] |         0.519123 | [0.5060907882069829, 0.538263498483186]  |        0.843922 |       0.346239 |                 0.672996 |
| topology_only_sentinel       | 4055 |         -0.0459289 | [-0.06822917466556225, -0.022091432504367042] |         0.520682 | [0.5069475800596663, 0.5360931372406941] |        0.84339  |       0.344266 |               nan        |
| shuffled_target_extra_trees  | 4055 |         -0.0437131 | [-0.06627595033257982, -0.019344998988680473] |         0.517323 | [0.5032804452428276, 0.5326504400173007] |        0.83833  |       0.344266 |               nan        |

The strongest traditional method is the train-fold adaptive-template ridge: res68 `0.5262` with 68% calibration coverage `0.671`. The ML waveform ExtraTrees gives `0.5191` with coverage `0.673`. The shuffled-target sentinel is `0.5173`.

## Support Map

| stratum_category       | stratum               |    n |   n_runs | best_real_method   |   best_real_res68 |   ml_minus_traditional_res68 | ml_minus_traditional_res68_ci95                 |   shuffled_res68_abs_frac | support_call         |
|:-----------------------|:----------------------|-----:|---------:|:-------------------|------------------:|-----------------------------:|:------------------------------------------------|--------------------------:|:---------------------|
| topology_pattern       | B2_B4                 |  102 |       21 | traditional        |          0.477994 |                   0.0329721  | [-0.0024336714233342688, 0.05927131882911473]   |                  0.483114 | support_only_or_weak |
| downstream_coincidence | downstream_one        |  109 |       21 | traditional        |          0.481162 |                   0.0317577  | [-0.049902115210350366, 0.060676493301877334]   |                  0.488326 | support_only_or_weak |
| b2_amp_bin             | 1000_2000             |  496 |       26 | ml                 |          0.501828 |                  -0.00987374 | [-0.031238174140148605, 0.0030216179310725184]  |                  0.49708  | support_only_or_weak |
| b2_amp_bin             | 2000_3000             |  474 |       28 | ml                 |          0.505818 |                  -0.0140107  | [-0.02173560742954183, 0.010929919658709765]    |                  0.507442 | support_only_or_weak |
| anomaly_stratum        | late_tail_high        | 1349 |       32 | ml                 |          0.506564 |                  -0.00626316 | [-0.017545759417289898, 0.00312923338787947]    |                  0.508344 | support_only_or_weak |
| saturation_stratum     | all_B_amp_lt7000      | 3134 |       32 | ml                 |          0.51725  |                  -0.00431102 | [-0.010663003509627367, 0.0014543081905047301]  |                  0.513546 | support_only_or_weak |
| b2_amp_bin             | 3000_5000             | 1212 |       31 | ml                 |          0.517662 |                  -0.00306623 | [-0.010858156391747262, 0.00877329827972586]    |                  0.508694 | support_only_or_weak |
| downstream_coincidence | downstream_none       | 3889 |       32 | ml                 |          0.519128 |                  -0.0088674  | [-0.010539419539618965, -0.0015948942021591754] |                  0.517706 | support_only_or_weak |
| topology_pattern       | B2_only               | 3889 |       32 | ml                 |          0.519128 |                  -0.0088674  | [-0.010359808841276168, -0.0025254248144686627] |                  0.517706 | support_only_or_weak |
| anomaly_stratum        | dropout_like          |  401 |       26 | ml                 |          0.519972 |                  -0.0128777  | [-0.027764235082894904, 0.0023477889899927266]  |                  0.514605 | support_only_or_weak |
| anomaly_stratum        | broad_saturation_like | 2271 |       32 | ml                 |          0.526571 |                  -0.00317568 | [-0.007319312195494435, 0.004087439732698293]   |                  0.524442 | support_only_or_weak |
| b2_amp_bin             | 5000_7000             |  953 |       30 | ml                 |          0.528433 |                  -0.00225896 | [-0.014441034183668888, 0.010052370210855107]   |                  0.534315 | support_only_or_weak |
| saturation_stratum     | any_B_amp_ge7000      |  921 |       28 | ml                 |          0.537324 |                  -0.00371772 | [-0.01359117767544032, 0.007316861486751123]    |                  0.532488 | support_only_or_weak |
| b2_amp_bin             | 7000_inf              |  920 |       28 | ml                 |          0.537425 |                  -0.00379302 | [-0.013477745713598877, 0.006770365437380026]   |                  0.533083 | support_only_or_weak |
| downstream_coincidence | downstream_multi      |   57 |       19 | traditional        |          0.555514 |                   0.0329774  | [-0.05467456457875945, 0.18462870107724985]     |                  0.564111 | support_only_or_weak |
| topology_pattern       | B2_multi_downstream   |   57 |       19 | traditional        |          0.555514 |                   0.0329774  | [-0.0350418971580004, 0.17573031730017183]      |                  0.564111 | support_only_or_weak |

Largest matched support cells:

| stratum                                                                  |   n |   n_runs | best_real_method   |   best_real_res68 |   shuffled_res68_abs_frac | support_call         |
|:-------------------------------------------------------------------------|----:|---------:|:-------------------|------------------:|--------------------------:|:---------------------|
| B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none | 957 |       30 | ml                 |          0.524775 |                  0.521476 | support_only_or_weak |
| B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|downstream_none | 888 |       30 | ml                 |          0.528259 |                  0.532712 | support_only_or_weak |
| B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|downstream_none         | 606 |       28 | traditional        |          0.546111 |                  0.53986  | support_only_or_weak |
| B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none        | 278 |       22 | ml                 |          0.506042 |                  0.50547  | support_only_or_weak |
| B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none        | 253 |       23 | ml                 |          0.49425  |                  0.495019 | support_only_or_weak |
| B2_only|7000_inf|any_B_amp_ge7000|broad_saturation_like|downstream_none  | 240 |       23 | ml                 |          0.517572 |                  0.512766 | support_only_or_weak |
| B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none          | 184 |       20 | ml                 |          0.513217 |                  0.494005 | support_only_or_weak |
| B2_only|3000_5000|all_B_amp_lt7000|late_tail_high|downstream_none        | 125 |       20 | ml                 |          0.417667 |                  0.427901 | support_only_or_weak |
| B2_only|2000_3000|all_B_amp_lt7000|dropout_like|downstream_none          |  88 |       18 | ml                 |          0.5022   |                  0.50005  | support_only_or_weak |
| B2_only|2000_3000|all_B_amp_lt7000|broad_saturation_like|downstream_none |  75 |       17 | traditional        |          0.529062 |                  0.527963 | support_only_or_weak |
| B2_only|3000_5000|all_B_amp_lt7000|dropout_like|downstream_none          |  54 |       18 | ml                 |          0.452395 |                  0.452491 | support_only_or_weak |

## Leakage Audit

- Train/held-out run overlap: `0`.
- Feature matrices exclude run id, event id, A charge, A selected flags, and the target.
- Topology-only sentinel res68: `0.5207`.
- Shuffled-target ExtraTrees res68: `0.5173`.
- No result is flagged as too-good: `False`.

## Finding

No B-stack topology, amplitude, saturation, anomaly, or downstream-coincidence stratum passes the preregistered identifiability criteria with both strong run support and a clear real-versus-shuffled separation. The P04c number reproduces at about 0.52 res68, and P04h gives traditional 0.5262, ML 0.5191, and shuffled 0.5173. The A-stack charge proxy is therefore topology-limited noise for this raw ROOT mirror rather than a physics-facing charge transfer.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `raw_reproduction_counts.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `p04c_reproduction_summary.csv`, `p04h_head_to_head.csv`, `p04h_support_map.csv`, and `p04h_predictions.csv`.
