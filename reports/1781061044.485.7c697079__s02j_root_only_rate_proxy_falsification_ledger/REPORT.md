# S02j: ROOT-only rate-proxy falsification ledger

Ticket `1781061044.485.7c697079`. Worker `testbeam-laptop-4`.

## Reproduction First

The raw HRD-B ROOT gate was reproduced before model fitting. The raw files live under `data/root/root` and were read directly with `uproot`; no sorted table is used for the count gate.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

The run-65 S02b anchors were rebuilt from raw ROOT-derived pulses in the same pipeline:

| quantity                      |   heldout_run |   reproduced_sigma68_ns |   reference_sigma68_ns |    delta_ns | pass   |
|:------------------------------|--------------:|------------------------:|-----------------------:|------------:|:-------|
| S02b global-template timewalk |            65 |                 1.63542 |                1.63542 | 1.46578e-11 | True   |
| S02b binned-template timewalk |            65 |                 3.4037  |                3.4037  | 1.15472e-11 | True   |

## Question

S02f/S02g found no usable external scaler or live-time table. S02j asks whether ROOT-only trigger-density, event-order, selected-pulse-density, current, and topology proxies are legitimate nuisance corrections or merely run/order leakage surrogates.

The estimand is the event-paired downstream timing residual

`r_ab(e;m) = [t_a(e;m) - z_a / v] - [t_b(e;m) - z_b / v]`,

where `a,b in {B4,B6,B8}`, `z` is the 2 cm stave coordinate, and `1/v = 0.078 ns/cm`. The headline width is

`sigma68(m) = (Q84(r_ab) - Q16(r_ab)) / 2`.

CIs are event bootstraps within each held-out run and a run-block bootstrap across the seven Sample-II analysis runs.

## ROOT-Only Proxies

Each proxy is computed before timing labels from `TRIGGER`, `EVENTNO`, and amplitude gates. Fold-local standardization uses only the six training runs.

|   run |   current_nA |   trigger_entry_density |   entries_per_eventno |   selected_multiplicity_per_event |   downstream_allhit_fraction |
|------:|-------------:|------------------------:|----------------------:|----------------------------------:|-----------------------------:|
|    58 |           20 |                0.997808 |              0.997808 |                          0.49152  |                   0.00213819 |
|    59 |           20 |                1        |              1        |                          0.505331 |                   0.0180365  |
|    60 |           20 |                1        |              1        |                          0.472057 |                   0.0223984  |
|    61 |           20 |                0.999945 |              0.999945 |                          0.519091 |                   0.0255372  |
|    62 |           20 |                1        |              1        |                          0.507902 |                   0.0214719  |
|    63 |           20 |                0.999973 |              0.999973 |                          0.508156 |                   0.0099919  |
|    65 |           20 |                1        |              1        |                          0.339319 |                   0.00171768 |

Proxy families tested one at a time:

| family                 | columns                                                                                                             |
|:-----------------------|:--------------------------------------------------------------------------------------------------------------------|
| current                | current_nA                                                                                                          |
| trigger_density        | trigger_entry_density                                                                                               |
| event_order_density    | entries_per_eventno                                                                                                 |
| selected_pulse_density | selected_multiplicity_per_event                                                                                     |
| topology_occupancy     | downstream_allhit_fraction                                                                                          |
| all_root_proxies       | current_nA, trigger_entry_density, entries_per_eventno, selected_multiplicity_per_event, downstream_allhit_fraction |

## Methods

Traditional comparators freeze the S02b global-template and binned-template branches. For each proxy family, a transparent linear residual correction adds only stave-specific powers of that proxy family to the established amplitude/template interaction basis. The no-proxy global branch is the strong traditional baseline.

The guarded ML/NN bakeoff uses the same `all_root_proxies` family plus event-order fractions and downstream stave indicator. It excludes waveform samples, event id, downstream timing labels, pair residuals as inputs, and all held-out-run rows from fitting. Models:

- `ridge`: standardized Ridge regression with grouped-run CV over alpha.
- `hgb`: histogram gradient-boosted regression trees.
- `mlp`: small scikit-learn MLP regressor.
- `cnn1d_proxy`: compact 1D-CNN over the ordered proxy vector, included to satisfy the neural architecture comparison without reading waveform samples.
- `gated_proxy`: new architecture mixing linear and nonlinear proxy branches with a learned gate.

Model audit:

|   heldout_run | model       | proxy_family     |   n_train_pulses |   n_features | feature_policy                                                                                                                                       |
|--------------:|:------------|:-----------------|-----------------:|-------------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------|
|            58 | ridge       | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | hgb         | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | mlp         | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | cnn1d_proxy | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            58 | gated_proxy | all_root_proxies |            11241 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | ridge       | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | hgb         | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | mlp         | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | cnn1d_proxy | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            59 | gated_proxy | all_root_proxies |             9171 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | ridge       | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | hgb         | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | mlp         | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | cnn1d_proxy | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            60 | gated_proxy | all_root_proxies |             9036 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | ridge       | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | hgb         | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | mlp         | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | cnn1d_proxy | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            61 | gated_proxy | all_root_proxies |             8661 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | ridge       | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | hgb         | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | mlp         | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | cnn1d_proxy | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            62 | gated_proxy | all_root_proxies |             9039 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | ridge       | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | hgb         | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | mlp         | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | cnn1d_proxy | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            63 | gated_proxy | all_root_proxies |            10350 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | ridge       | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | hgb         | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | mlp         | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | cnn1d_proxy | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |
|            65 | gated_proxy | all_root_proxies |            11262 |           10 | ROOT-only run/event proxies plus downstream stave indicator; excludes waveform samples, event id, downstream timing labels, and held-out target rows |

## Run-Held-Out Results

Per-run event bootstrap table:

|   heldout_run | method                                   | family            |   sigma68_ns |   ci_low |   ci_high |   full_rms_ns |   tail_frac_abs_gt5ns |   bias_vs_log_amp_slope_ns |
|--------------:|:-----------------------------------------|:------------------|-------------:|---------:|----------:|--------------:|----------------------:|---------------------------:|
|            58 | ml_gated_proxy_all_root_proxies          | ml                |      1.18406 |  1.00378 |   1.40456 |       2.69213 |            0.0228311  |                 -0.162664  |
|            58 | ml_cnn1d_proxy_all_root_proxies          | ml                |      1.1936  |  1.02065 |   1.42044 |       2.68985 |            0.0228311  |                 -0.157968  |
|            58 | ml_ridge_all_root_proxies                | ml                |      1.35072 |  1.17057 |   1.54308 |       2.78318 |            0.0182648  |                 -0.162287  |
|            58 | traditional_proxy_current                | traditional_proxy |      1.52279 |  1.25287 |   1.84709 |       2.75002 |            0.0228311  |                 -0.162287  |
|            58 | traditional_global_no_proxy              | traditional       |      1.52279 |  1.28584 |   1.85678 |       2.75002 |            0.0228311  |                 -0.162287  |
|            58 | traditional_proxy_selected_pulse_density | traditional_proxy |      1.55859 |  1.28634 |   1.90372 |       2.76267 |            0.0228311  |                 -0.185761  |
|            58 | ml_hgb_all_root_proxies                  | ml                |      1.5746  |  1.36946 |   1.82077 |       2.89938 |            0.0228311  |                 -0.191269  |
|            58 | ml_mlp_all_root_proxies                  | ml                |      1.67855 |  1.46819 |   1.84398 |       2.92758 |            0.0228311  |                 -0.162288  |
|            58 | traditional_proxy_topology_occupancy     | traditional_proxy |      2.0943  |  1.82203 |   2.35786 |       2.95579 |            0.0410959  |                 -0.0449365 |
|            58 | traditional_binned_no_proxy              | traditional       |      3.63484 |  3.15014 |   4.07082 |       4.61474 |            0.191781   |                  1.09287   |
|            58 | traditional_proxy_all_root_proxies       | traditional_proxy |     23.4087  | 23.2257  |  23.6155  |      21.6942  |            0.365297   |                 -0.112697  |
|            58 | traditional_proxy_event_order_density    | traditional_proxy |     25.6288  | 25.4414  |  25.8071  |      23.8418  |            0.365297   |                 -0.193704  |
|            58 | traditional_proxy_trigger_density        | traditional_proxy |     25.6288  | 25.4     |  25.813   |      23.8418  |            0.365297   |                 -0.193704  |
|            59 | ml_mlp_all_root_proxies                  | ml                |      1.22065 |  1.15577 |   1.29065 |       2.2936  |            0.0117955  |                 -0.782358  |
|            59 | ml_cnn1d_proxy_all_root_proxies          | ml                |      1.25579 |  1.19033 |   1.34622 |       2.31888 |            0.0126693  |                 -0.80201   |
|            59 | ml_gated_proxy_all_root_proxies          | ml                |      1.25691 |  1.19149 |   1.31693 |       2.30876 |            0.0122324  |                 -0.780125  |
|            59 | ml_hgb_all_root_proxies                  | ml                |      1.32807 |  1.25833 |   1.38175 |       2.32884 |            0.0126693  |                 -0.754345  |
|            59 | ml_ridge_all_root_proxies                | ml                |      1.36017 |  1.31122 |   1.42448 |       2.35102 |            0.0126693  |                 -0.812811  |
|            59 | traditional_proxy_selected_pulse_density | traditional_proxy |      1.57523 |  1.52464 |   1.62408 |       2.47218 |            0.0122324  |                 -0.83008   |
|            59 | traditional_proxy_event_order_density    | traditional_proxy |      1.59401 |  1.54222 |   1.64779 |       2.48192 |            0.0126693  |                 -0.812919  |
|            59 | traditional_proxy_trigger_density        | traditional_proxy |      1.59401 |  1.54116 |   1.64727 |       2.48192 |            0.0126693  |                 -0.812919  |
|            59 | traditional_global_no_proxy              | traditional       |      1.59676 |  1.54168 |   1.64807 |       2.48616 |            0.0126693  |                 -0.812811  |
|            59 | traditional_proxy_current                | traditional_proxy |      1.59676 |  1.54295 |   1.6542  |       2.48616 |            0.0126693  |                 -0.812811  |
|            59 | traditional_proxy_all_root_proxies       | traditional_proxy |      1.6297  |  1.58057 |   1.68737 |       2.49493 |            0.013543   |                 -0.740327  |
|            59 | traditional_proxy_topology_occupancy     | traditional_proxy |      1.66048 |  1.60741 |   1.7109  |       2.50944 |            0.0139799  |                 -0.722984  |
|            59 | traditional_binned_no_proxy              | traditional       |      3.63793 |  3.47783 |   3.79479 |       4.00546 |            0.158148   |                 -2.92922   |
|            60 | ml_mlp_all_root_proxies                  | ml                |      1.14348 |  1.08941 |   1.1998  |       2.12023 |            0.0107261  |                 -0.871356  |
|            60 | ml_gated_proxy_all_root_proxies          | ml                |      1.31942 |  1.24729 |   1.38631 |       2.20918 |            0.0107261  |                 -0.873579  |
|            60 | traditional_proxy_all_root_proxies       | traditional_proxy |      1.35265 |  1.30395 |   1.4013  |       2.2095  |            0.0107261  |                 -0.737801  |
|            60 | ml_hgb_all_root_proxies                  | ml                |      1.36706 |  1.28678 |   1.44139 |       2.23327 |            0.0111386  |                 -0.990804  |
|            60 | traditional_proxy_topology_occupancy     | traditional_proxy |      1.41591 |  1.36724 |   1.45656 |       2.23955 |            0.0107261  |                 -0.750891  |
|            60 | ml_ridge_all_root_proxies                | ml                |      1.41665 |  1.35041 |   1.48332 |       2.26218 |            0.0103135  |                 -0.862527  |
|            60 | traditional_proxy_event_order_density    | traditional_proxy |      1.46242 |  1.41791 |   1.51412 |       2.26615 |            0.0107261  |                 -0.861097  |
|            60 | traditional_proxy_trigger_density        | traditional_proxy |      1.46242 |  1.41636 |   1.51746 |       2.26615 |            0.0107261  |                 -0.861097  |
|            60 | traditional_global_no_proxy              | traditional       |      1.4719  |  1.42399 |   1.52127 |       2.27149 |            0.0107261  |                 -0.862527  |
|            60 | traditional_proxy_current                | traditional_proxy |      1.4719  |  1.42855 |   1.52056 |       2.27149 |            0.0107261  |                 -0.862527  |
|            60 | ml_cnn1d_proxy_all_root_proxies          | ml                |      1.53951 |  1.47371 |   1.59381 |       2.3238  |            0.0119637  |                 -0.859128  |
|            60 | traditional_proxy_selected_pulse_density | traditional_proxy |      1.563   |  1.51584 |   1.60485 |       2.31623 |            0.0123762  |                 -0.831864  |
|            60 | traditional_binned_no_proxy              | traditional       |      2.12741 |  2.05051 |   2.19898 |       2.5748  |            0.0383663  |                 -2.27427   |
|            61 | ml_cnn1d_proxy_all_root_proxies          | ml                |      1.27141 |  1.20131 |   1.32596 |       2.45962 |            0.0146481  |                  0.974541  |
|            61 | ml_ridge_all_root_proxies                | ml                |      1.277   |  1.22523 |   1.33645 |       2.4529  |            0.0150054  |                  0.975056  |
|            61 | ml_gated_proxy_all_root_proxies          | ml                |      1.27921 |  1.22727 |   1.33395 |       2.45441 |            0.0146481  |                  0.97234   |
|            61 | ml_mlp_all_root_proxies                  | ml                |      1.30189 |  1.24207 |   1.35843 |       2.45444 |            0.0146481  |                  0.979427  |
|            61 | ml_hgb_all_root_proxies                  | ml                |      1.33122 |  1.25592 |   1.39249 |       2.48529 |            0.0157199  |                  0.982255  |
|            61 | traditional_proxy_selected_pulse_density | traditional_proxy |      2.16057 |  2.06474 |   2.24232 |       2.92229 |            0.0275098  |                  0.971145  |
|            61 | traditional_proxy_topology_occupancy     | traditional_proxy |      2.16476 |  2.07106 |   2.24656 |       2.92767 |            0.0275098  |                  0.998472  |
|            61 | traditional_proxy_all_root_proxies       | traditional_proxy |      2.1821  |  2.0959  |   2.26532 |       2.93649 |            0.0271526  |                  0.991428  |
|            61 | traditional_proxy_event_order_density    | traditional_proxy |      2.18716 |  2.10179 |   2.26927 |       2.93562 |            0.0275098  |                  0.972721  |
|            61 | traditional_proxy_trigger_density        | traditional_proxy |      2.18716 |  2.09508 |   2.28063 |       2.93562 |            0.0275098  |                  0.972721  |
|            61 | traditional_proxy_current                | traditional_proxy |      2.18842 |  2.08532 |   2.2731  |       2.93618 |            0.0275098  |                  0.975056  |
|            61 | traditional_global_no_proxy              | traditional       |      2.18842 |  2.09724 |   2.26783 |       2.93618 |            0.0275098  |                  0.975056  |
|            61 | traditional_binned_no_proxy              | traditional       |      3.06904 |  2.93062 |   3.16836 |       3.72776 |            0.110397   |                 -1.40188   |
|            62 | ml_hgb_all_root_proxies                  | ml                |      1.28927 |  1.22509 |   1.3428  |       2.31867 |            0.0103263  |                 -0.23532   |
|            62 | ml_cnn1d_proxy_all_root_proxies          | ml                |      1.31357 |  1.26765 |   1.37137 |       2.34558 |            0.0103263  |                 -0.204701  |
|            62 | ml_mlp_all_root_proxies                  | ml                |      1.31547 |  1.24874 |   1.38895 |       2.34622 |            0.0107394  |                 -0.191547  |
|            62 | ml_ridge_all_root_proxies                | ml                |      1.33562 |  1.27477 |   1.40475 |       2.35998 |            0.0107394  |                 -0.208499  |
|            62 | ml_gated_proxy_all_root_proxies          | ml                |      1.41735 |  1.35813 |   1.48486 |       2.38834 |            0.0107394  |                 -0.196744  |
|            62 | traditional_proxy_all_root_proxies       | traditional_proxy |      1.57629 |  1.5242  |   1.62793 |       2.46912 |            0.0111524  |                 -0.117695  |
|            62 | traditional_proxy_selected_pulse_density | traditional_proxy |      1.58778 |  1.53999 |   1.64113 |       2.47655 |            0.0111524  |                 -0.227796  |
|            62 | traditional_proxy_topology_occupancy     | traditional_proxy |      1.59334 |  1.54821 |   1.64544 |       2.47844 |            0.0111524  |                 -0.105207  |
|            62 | traditional_proxy_event_order_density    | traditional_proxy |      1.62774 |  1.56858 |   1.67075 |       2.49613 |            0.0115655  |                 -0.210074  |
|            62 | traditional_proxy_trigger_density        | traditional_proxy |      1.62774 |  1.56966 |   1.66534 |       2.49613 |            0.0115655  |                 -0.210074  |
|            62 | traditional_proxy_current                | traditional_proxy |      1.62995 |  1.58026 |   1.6769  |       2.50074 |            0.0111524  |                 -0.208499  |
|            62 | traditional_global_no_proxy              | traditional       |      1.62995 |  1.57773 |   1.67741 |       2.50074 |            0.0111524  |                 -0.208499  |
|            62 | traditional_binned_no_proxy              | traditional       |      2.962   |  2.82089 |   3.06765 |       3.44045 |            0.0912846  |                 -2.15014   |
|            63 | ml_cnn1d_proxy_all_root_proxies          | ml                |      1.1626  |  1.07515 |   1.26669 |       2.36042 |            0.0144144  |                 -0.602992  |
|            63 | ml_mlp_all_root_proxies                  | ml                |      1.16538 |  1.05548 |   1.27346 |       2.3437  |            0.0153153  |                 -0.630371  |
|            63 | ml_gated_proxy_all_root_proxies          | ml                |      1.25804 |  1.14705 |   1.35686 |       2.3756  |            0.0153153  |                 -0.692539  |
|            63 | ml_hgb_all_root_proxies                  | ml                |      1.29074 |  1.19434 |   1.42309 |       2.36875 |            0.0162162  |                 -0.633271  |
|            63 | ml_ridge_all_root_proxies                | ml                |      1.35337 |  1.25525 |   1.43567 |       2.42486 |            0.0153153  |                 -0.612822  |
|            63 | traditional_proxy_selected_pulse_density | traditional_proxy |      1.5068  |  1.44535 |   1.58353 |       2.51523 |            0.018018   |                 -0.630888  |
|            63 | traditional_proxy_event_order_density    | traditional_proxy |      1.53855 |  1.47836 |   1.60723 |       2.53171 |            0.0171171  |                 -0.61346   |
|            63 | traditional_proxy_trigger_density        | traditional_proxy |      1.53855 |  1.47286 |   1.61124 |       2.53171 |            0.0171171  |                 -0.61346   |
|            63 | traditional_proxy_current                | traditional_proxy |      1.54092 |  1.4742  |   1.60866 |       2.53459 |            0.0171171  |                 -0.612822  |
|            63 | traditional_global_no_proxy              | traditional       |      1.54092 |  1.48201 |   1.61063 |       2.53459 |            0.0171171  |                 -0.612822  |
|            63 | traditional_proxy_all_root_proxies       | traditional_proxy |      1.8826  |  1.80117 |   1.95728 |       2.70696 |            0.0225225  |                 -0.511598  |
|            63 | traditional_proxy_topology_occupancy     | traditional_proxy |      1.90704 |  1.82253 |   1.96993 |       2.71741 |            0.0225225  |                 -0.544794  |
|            63 | traditional_binned_no_proxy              | traditional       |      3.20453 |  3.01223 |   3.44457 |       3.58591 |            0.123423   |                 -1.82541   |
|            65 | ml_gated_proxy_all_root_proxies          | ml                |      1.30393 |  1.0707  |   1.5657  |       1.44218 |            0.010101   |                  0.770387  |
|            65 | ml_mlp_all_root_proxies                  | ml                |      1.38688 |  1.13896 |   1.59955 |       1.47126 |            0.0151515  |                  0.797795  |
|            65 | ml_cnn1d_proxy_all_root_proxies          | ml                |      1.42217 |  1.24196 |   1.66738 |       1.50866 |            0.010101   |                  0.798951  |
|            65 | ml_hgb_all_root_proxies                  | ml                |      1.45644 |  1.21317 |   1.63516 |       1.4541  |            0.00505051 |                  0.586956  |
|            65 | ml_ridge_all_root_proxies                | ml                |      1.50445 |  1.27023 |   1.72563 |       1.57998 |            0.0151515  |                  0.779159  |
|            65 | traditional_proxy_event_order_density    | traditional_proxy |      1.63527 |  1.46706 |   1.90723 |       1.76599 |            0.00505051 |                  0.773835  |
|            65 | traditional_proxy_trigger_density        | traditional_proxy |      1.63527 |  1.46527 |   1.90772 |       1.76599 |            0.00505051 |                  0.773835  |
|            65 | traditional_global_no_proxy              | traditional       |      1.63542 |  1.48317 |   1.90826 |       1.77195 |            0.00505051 |                  0.779159  |
|            65 | traditional_proxy_current                | traditional_proxy |      1.63542 |  1.4635  |   1.92984 |       1.77195 |            0.00505051 |                  0.779159  |
|            65 | traditional_proxy_topology_occupancy     | traditional_proxy |      2.2355  |  2.00686 |   2.44107 |       2.20607 |            0.020202   |                  0.853792  |
|            65 | traditional_binned_no_proxy              | traditional       |      3.4037  |  2.86356 |   4.02715 |       3.72618 |            0.141414   |                 -3.50281   |
|            65 | traditional_proxy_selected_pulse_density | traditional_proxy |      3.686   |  3.414   |   3.86447 |       3.39145 |            0.217172   |                  0.649775  |
|            65 | traditional_proxy_all_root_proxies       | traditional_proxy |      4.23354 |  4.01076 |   4.42403 |       3.87439 |            0.333333   |                  0.765739  |

Run-block summary:

| method                                   | family            |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |   mean_full_rms_ns |   mean_tail_frac_abs_gt5ns |   mean_bias_vs_log_amp_slope_ns |
|:-----------------------------------------|:------------------|------------------:|---------:|----------:|--------------------------:|---------------:|----------------:|-------------------:|---------------------------:|--------------------------------:|
| ml_gated_proxy_all_root_proxies          | ml                |           1.28842 |  1.24297 |   1.33788 |              -0.366747    |   -0.555821    |    -0.234529    |            2.26723 |                  0.013799  |                      -0.137561  |
| ml_cnn1d_proxy_all_root_proxies          | ml                |           1.30838 |  1.22408 |   1.40052 |              -0.346784    |   -0.568792    |    -0.165045    |            2.28669 |                  0.0138506 |                      -0.121901  |
| ml_mlp_all_root_proxies                  | ml                |           1.31604 |  1.21109 |   1.45567 |              -0.33912     |   -0.565611    |    -0.130908    |            2.27958 |                  0.0144581 |                      -0.122957  |
| ml_ridge_all_root_proxies                | ml                |           1.37114 |  1.32599 |   1.42424 |              -0.284025    |   -0.50839     |    -0.138456    |            2.3163  |                  0.0139227 |                      -0.129247  |
| ml_hgb_all_root_proxies                  | ml                |           1.37677 |  1.31255 |   1.45254 |              -0.278394    |   -0.505197    |    -0.114536    |            2.29833 |                  0.0134217 |                      -0.176542  |
| traditional_proxy_current                | traditional_proxy |           1.65516 |  1.53133 |   1.85002 |              -6.40199e-12 |   -5.58256e-11 |     4.25918e-11 |            2.46445 |                  0.0152938 |                      -0.129247  |
| traditional_global_no_proxy              | traditional       |           1.65516 |  1.53671 |   1.83945 |               0           |    0           |     0           |            2.46445 |                  0.0152938 |                      -0.129247  |
| traditional_proxy_topology_occupancy     | traditional_proxy |           1.86733 |  1.65499 |   2.07263 |               0.212171    |    0.0223035   |     0.420256    |            2.57634 |                  0.021027  |                      -0.0452213 |
| traditional_proxy_selected_pulse_density | traditional_proxy |           1.94828 |  1.5516  |   2.55997 |               0.293117    |   -0.024463    |     0.890521    |            2.6938  |                  0.0458988 |                      -0.155067  |
| traditional_binned_no_proxy              | traditional       |           3.14849 |  2.76567 |   3.45563 |               1.49333     |    1.10395     |     1.84493     |            3.6679  |                  0.122116  |                      -1.85584   |
| traditional_proxy_event_order_density    | traditional_proxy |           5.09628 |  1.55136 |  11.9768  |               3.44112     |   -0.00494394  |    10.3301      |            5.47418 |                  0.0642764 |                      -0.134957  |
| traditional_proxy_trigger_density        | traditional_proxy |           5.09628 |  1.55914 |  11.9768  |               3.44112     |   -0.00476826  |    10.3302      |            5.47418 |                  0.0642764 |                      -0.134957  |
| traditional_proxy_all_root_proxies       | traditional_proxy |           5.18079 |  1.65033 |  11.4469  |               3.52563     |    0.00321403  |     9.79401     |            5.48366 |                  0.111961  |                      -0.066136  |

Traditional proxy family ranking:

| method                                   |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |
|:-----------------------------------------|------------------:|---------:|----------:|--------------------------:|---------------:|----------------:|
| traditional_proxy_current                |           1.65516 |  1.53133 |   1.85002 |              -6.40199e-12 |   -5.58256e-11 |     4.25918e-11 |
| traditional_proxy_topology_occupancy     |           1.86733 |  1.65499 |   2.07263 |               0.212171    |    0.0223035   |     0.420256    |
| traditional_proxy_selected_pulse_density |           1.94828 |  1.5516  |   2.55997 |               0.293117    |   -0.024463    |     0.890521    |
| traditional_proxy_event_order_density    |           5.09628 |  1.55136 |  11.9768  |               3.44112     |   -0.00494394  |    10.3301      |
| traditional_proxy_trigger_density        |           5.09628 |  1.55914 |  11.9768  |               3.44112     |   -0.00476826  |    10.3302      |
| traditional_proxy_all_root_proxies       |           5.18079 |  1.65033 |  11.4469  |               3.52563     |    0.00321403  |     9.79401     |

ML/NN ranking:

| method                          |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |   delta_ci_low |   delta_ci_high |
|:--------------------------------|------------------:|---------:|----------:|--------------------------:|---------------:|----------------:|
| ml_gated_proxy_all_root_proxies |           1.28842 |  1.24297 |   1.33788 |                 -0.366747 |      -0.555821 |       -0.234529 |
| ml_cnn1d_proxy_all_root_proxies |           1.30838 |  1.22408 |   1.40052 |                 -0.346784 |      -0.568792 |       -0.165045 |
| ml_mlp_all_root_proxies         |           1.31604 |  1.21109 |   1.45567 |                 -0.33912  |      -0.565611 |       -0.130908 |
| ml_ridge_all_root_proxies       |           1.37114 |  1.32599 |   1.42424 |                 -0.284025 |      -0.50839  |       -0.138456 |
| ml_hgb_all_root_proxies         |           1.37677 |  1.31255 |   1.45254 |                 -0.278394 |      -0.505197 |       -0.114536 |

## Controls and Systematics

Leakage ledger:

|   heldout_run | check                                                     |      value | pass   |
|--------------:|:----------------------------------------------------------|-----------:|:-------|
|            58 | train_heldout_run_overlap                                 |  0         | True   |
|            58 | train_heldout_event_id_overlap                            |  0         | True   |
|            58 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            58 | covariates_derived_before_timing_labels                   |  1         | True   |
|            58 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            58 | final_fit_train_rows_only                                 |  1         | True   |
|            58 | shuffled_target_no_better:ml_hgb_all_root_proxies         | -0.0521016 | False  |
|            58 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.329929  | True   |
|            58 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.176997  | True   |
|            58 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.396228  | True   |
|            58 | shuffled_target_no_better:ml_mlp_all_root_proxies         | -0.0637244 | False  |
|            59 | train_heldout_run_overlap                                 |  0         | True   |
|            59 | train_heldout_event_id_overlap                            |  0         | True   |
|            59 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            59 | covariates_derived_before_timing_labels                   |  1         | True   |
|            59 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            59 | final_fit_train_rows_only                                 |  1         | True   |
|            59 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.36665   | True   |
|            59 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.260722  | True   |
|            59 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.342364  | True   |
|            59 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.260438  | True   |
|            59 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.399112  | True   |
|            60 | train_heldout_run_overlap                                 |  0         | True   |
|            60 | train_heldout_event_id_overlap                            |  0         | True   |
|            60 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            60 | covariates_derived_before_timing_labels                   |  1         | True   |
|            60 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            60 | final_fit_train_rows_only                                 |  1         | True   |
|            60 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.284953  | True   |
|            60 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies | -0.0750436 | False  |
|            60 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.103216  | True   |
|            60 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.176292  | True   |
|            60 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.108933  | True   |
|            61 | train_heldout_run_overlap                                 |  0         | True   |
|            61 | train_heldout_event_id_overlap                            |  0         | True   |
|            61 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            61 | covariates_derived_before_timing_labels                   |  1         | True   |
|            61 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            61 | final_fit_train_rows_only                                 |  1         | True   |
|            61 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.751967  | True   |
|            61 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.819477  | True   |
|            61 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.892224  | True   |
|            61 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.89108   | True   |
|            61 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.883807  | True   |
|            62 | train_heldout_run_overlap                                 |  0         | True   |
|            62 | train_heldout_event_id_overlap                            |  0         | True   |
|            62 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            62 | covariates_derived_before_timing_labels                   |  1         | True   |
|            62 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            62 | final_fit_train_rows_only                                 |  1         | True   |
|            62 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.331403  | True   |
|            62 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.308664  | True   |
|            62 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.206001  | True   |
|            62 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.298429  | True   |
|            62 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.349522  | True   |
|            63 | train_heldout_run_overlap                                 |  0         | True   |
|            63 | train_heldout_event_id_overlap                            |  0         | True   |
|            63 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            63 | covariates_derived_before_timing_labels                   |  1         | True   |
|            63 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            63 | final_fit_train_rows_only                                 |  1         | True   |
|            63 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.154454  | True   |
|            63 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.357094  | True   |
|            63 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.253368  | True   |
|            63 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.381917  | True   |
|            63 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.475386  | True   |
|            65 | train_heldout_run_overlap                                 |  0         | True   |
|            65 | train_heldout_event_id_overlap                            |  0         | True   |
|            65 | covariate_basis_contains_run_one_hot                      |  0         | True   |
|            65 | covariates_derived_before_timing_labels                   |  1         | True   |
|            65 | ml_features_exclude_waveform_event_id_downstream_labels   |  1         | True   |
|            65 | final_fit_train_rows_only                                 |  1         | True   |
|            65 | shuffled_target_no_better:ml_mlp_all_root_proxies         |  0.0669553 | True   |
|            65 | shuffled_target_no_better:ml_cnn1d_proxy_all_root_proxies |  0.212702  | True   |
|            65 | shuffled_target_no_better:ml_hgb_all_root_proxies         |  0.180633  | True   |
|            65 | shuffled_target_no_better:ml_ridge_all_root_proxies       |  0.1514    | True   |
|            65 | shuffled_target_no_better:ml_gated_proxy_all_root_proxies |  0.369917  | True   |

Shuffled-target controls:

| method                                   |   mean_sigma68_ns |   ci_low |   ci_high |   delta_vs_traditional_ns |
|:-----------------------------------------|------------------:|---------:|----------:|--------------------------:|
| ml_mlp_all_root_proxies_shuffled         |           1.6368  |  1.4984  |   1.82985 |               -0.0183686  |
| ml_hgb_all_root_proxies_shuffled         |           1.63809 |  1.53377 |   1.80031 |               -0.0170786  |
| ml_cnn1d_proxy_all_root_proxies_shuffled |           1.6502  |  1.53442 |   1.82989 |               -0.00496155 |
| ml_ridge_all_root_proxies_shuffled       |           1.65259 |  1.54988 |   1.80779 |               -0.00257767 |
| ml_gated_proxy_all_root_proxies_shuffled |           1.70471 |  1.58698 |   1.86815 |                0.0495412  |

Non-shuffled structural guards pass: `True`.

Systematic caveats:

- ROOT-only proxies are not calibrated wall-clock rates; `TRIGGER` density and `EVENTNO` span can encode DAQ/run structure.
- Held-out run 65 is sparse, so the run-block CI is more relevant than a pooled event-only CI.
- The ML/NN models deliberately exclude waveform samples for this ticket; the `cnn1d_proxy` is therefore a proxy-sequence CNN, not a waveform CNN.
- Shuffled-target rows that match nominal performance are treated as false-improvement warnings, not production candidates.
- The target is same-event downstream timing closure, not an external truth time.

## Verdict

Winner named in `result.json`: `ml_gated_proxy_all_root_proxies` with run-block mean `sigma68 = 1.288 ns` and CI `[1.243, 1.338] ns`.

The no-proxy global S02b traditional branch remains the adoption baseline at 1.655 ns. The best ROOT-proxy traditional branch is traditional_proxy_current with delta -0.000 ns, and the best guarded ML/NN branch is ml_gated_proxy_all_root_proxies with delta -0.367 ns. A non-baseline method wins the raw width table, but it should be interpreted through the shuffled-target and proxy-leakage controls before adoption. 3 shuffled-target checks beat their nominal model, so those rows are false-improvement warnings.

No novel follow-up ticket is appended: the calibrated external-rate search is already covered by prior S02 follow-ups, and this ticket exhausts the ROOT-only proxy ledger in the current data mirror.
