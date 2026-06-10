# P04c A/B Event-Matched Charge Cross-Check

- **Ticket:** `1781011754.1327.31d87446`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw `data/root/root/{hrda,hrdb}_run_*.root`; no Monte Carlo.
- **Topology:** match by `(run, EVT)`, require selected B2 and at least one selected usable A-stack stave (`A1` or `A3`).
- **Target:** selected A1/A3 positive-lobe physical charge; predictors use B-stack even-channel waveforms and charge summaries only.
- **Split:** leave-one-run-out over all runs with matched rows; CIs are run-block bootstraps.

## Raw-ROOT Gates

B-stack S00 selected-pulse reproduction ran first: `640,737` vs expected `640,737` (delta `+0`).

| sample              |   events_with_selected |   selected_pulses |   A1 |   A3 |
|:--------------------|-----------------------:|------------------:|-----:|-----:|
| sample_iii_analysis |                   7168 |              9682 | 2799 | 6883 |
| sample_iv_analysis  |                    767 |               894 |  167 |  727 |

The A-stack analysis-count reproductions match the S18 expected values in the config. The A/B topology then yields `4,055` B2-and-A-any event-matched rows across `32` run blocks.

## Benchmark

| method                      |    n |   bias_median_frac | bias_ci95                                     |   res68_abs_frac | res68_ci95                               |   full_rms_frac |   within_25pct |
|:----------------------------|-----:|-------------------:|:----------------------------------------------|-----------------:|:-----------------------------------------|----------------:|---------------:|
| b2_loglinear                | 4055 |         -0.0476348 | [-0.06704591686872612, -0.023049455347289964] |         0.520285 | [0.5045081706761284, 0.5378712614682606] |        0.84526  |       0.344513 |
| charge_transfer_ridge       | 4055 |         -0.0474201 | [-0.07082738280365355, -0.020747716801188348] |         0.519271 | [0.5057702229993188, 0.5383365929112157] |        0.842762 |       0.343527 |
| b_waveform_extra_trees      | 4055 |         -0.0476885 | [-0.0697027352156057, -0.02493525104600864]   |         0.52094  | [0.5080138394858839, 0.5371296565571704] |        0.845049 |       0.345006 |
| shuffled_target_extra_trees | 4055 |         -0.048709  | [-0.069438734193852, -0.021743493860896645]   |         0.521041 | [0.5089559535987588, 0.5362243977700045] |        0.847953 |       0.34476  |

The best real method is `charge_transfer_ridge` with res68 `0.5193`. The strong traditional charge-transfer ridge gives `0.5193`, while waveform ExtraTrees gives `0.5209`. The shuffled-target sentinel is `0.5210`.

## Run And B2-Amplitude Checks

|   run | method                 |   n |   bias_median_frac |   res68_abs_frac |   within_25pct |
|------:|:-----------------------|----:|-------------------:|-----------------:|---------------:|
|    31 | b2_loglinear           | 229 |        -0.0433072  |         0.560922 |       0.310044 |
|    31 | charge_transfer_ridge  | 229 |        -0.0474201  |         0.565817 |       0.305677 |
|    31 | b_waveform_extra_trees | 229 |        -0.0533906  |         0.563874 |       0.310044 |
|    32 | b2_loglinear           | 207 |         0.0114413  |         0.582706 |       0.318841 |
|    32 | charge_transfer_ridge  | 207 |         0.00386896 |         0.575603 |       0.318841 |
|    32 | b_waveform_extra_trees | 207 |         0.0168068  |         0.575624 |       0.333333 |
|    33 | b2_loglinear           |   8 |         0.23911    |         0.429418 |       0.25     |
|    33 | charge_transfer_ridge  |   8 |         0.228253   |         0.435272 |       0.25     |
|    33 | b_waveform_extra_trees |   8 |         0.234564   |         0.420708 |       0.25     |
|    34 | b2_loglinear           |  16 |         0.0559841  |         0.528114 |       0.25     |
|    34 | charge_transfer_ridge  |  16 |         0.0532699  |         0.528276 |       0.25     |
|    34 | b_waveform_extra_trees |  16 |         0.0588365  |         0.527775 |       0.25     |
|    35 | b2_loglinear           | 221 |         0.0264654  |         0.518046 |       0.334842 |
|    35 | charge_transfer_ridge  | 221 |         0.0285819  |         0.51833  |       0.325792 |
|    35 | b_waveform_extra_trees | 221 |         0.0231729  |         0.51941  |       0.339367 |
|    36 | b2_loglinear           | 295 |        -0.0251085  |         0.483137 |       0.386441 |
|    36 | charge_transfer_ridge  | 295 |        -0.0260202  |         0.488057 |       0.386441 |
|    36 | b_waveform_extra_trees | 295 |        -0.0311589  |         0.482759 |       0.389831 |
|    37 | b2_loglinear           | 292 |        -0.0744663  |         0.491934 |       0.39726  |
|    37 | charge_transfer_ridge  | 292 |        -0.0704722  |         0.491859 |       0.393836 |
|    37 | b_waveform_extra_trees | 292 |        -0.0761857  |         0.495178 |       0.390411 |
|    39 | b2_loglinear           | 324 |        -0.0918303  |         0.469456 |       0.345679 |
|    39 | charge_transfer_ridge  | 324 |        -0.0896222  |         0.474716 |       0.342593 |
|    39 | b_waveform_extra_trees | 324 |        -0.0906215  |         0.478711 |       0.345679 |
|    40 | b2_loglinear           | 265 |        -0.0601224  |         0.492012 |       0.384906 |
|    40 | charge_transfer_ridge  | 265 |        -0.0565598  |         0.489171 |       0.388679 |
|    40 | b_waveform_extra_trees | 265 |        -0.0548605  |         0.496847 |       0.377358 |
|    41 | b2_loglinear           | 295 |        -0.10651    |         0.530464 |       0.311864 |
|    41 | charge_transfer_ridge  | 295 |        -0.116519   |         0.53199  |       0.305085 |
|    41 | b_waveform_extra_trees | 295 |        -0.115322   |         0.522593 |       0.305085 |
|    42 | b2_loglinear           | 279 |        -0.0462399  |         0.505664 |       0.351254 |
|    42 | charge_transfer_ridge  | 279 |        -0.041031   |         0.509568 |       0.354839 |
|    42 | b_waveform_extra_trees | 279 |        -0.053475   |         0.511    |       0.34767  |
|    44 | b2_loglinear           |  30 |        -0.15752    |         0.474588 |       0.3      |
|    44 | charge_transfer_ridge  |  30 |        -0.155588   |         0.47566  |       0.3      |
|    44 | b_waveform_extra_trees |  30 |        -0.153411   |         0.475338 |       0.3      |
|    45 | b2_loglinear           | 302 |         0.00430212 |         0.520191 |       0.31457  |
|    45 | charge_transfer_ridge  | 302 |         0.0136887  |         0.519067 |       0.317881 |
|    45 | b_waveform_extra_trees | 302 |         0.00521761 |         0.522948 |       0.324503 |
|    47 | b2_loglinear           |  92 |        -0.0139105  |         0.487112 |       0.347826 |
|    47 | charge_transfer_ridge  |  92 |        -0.0143433  |         0.497201 |       0.347826 |
|    47 | b_waveform_extra_trees |  92 |        -0.0160928  |         0.501201 |       0.347826 |
|    48 | b2_loglinear           | 260 |        -0.106443   |         0.472925 |       0.361538 |
|    48 | charge_transfer_ridge  | 260 |        -0.109254   |         0.477792 |       0.373077 |
|    48 | b_waveform_extra_trees | 260 |        -0.11828    |         0.47925  |       0.369231 |
|    49 | b2_loglinear           | 288 |        -0.0971671  |         0.53912  |       0.305556 |
|    49 | charge_transfer_ridge  | 288 |        -0.0982932  |         0.530894 |       0.305556 |
|    49 | b_waveform_extra_trees | 288 |        -0.0960566  |         0.533321 |       0.305556 |
|    50 | b2_loglinear           |  61 |         0.0819027  |         0.599782 |       0.327869 |
|    50 | charge_transfer_ridge  |  61 |         0.0791226  |         0.596729 |       0.327869 |
|    50 | b_waveform_extra_trees |  61 |         0.0795382  |         0.601673 |       0.344262 |
|    51 | b2_loglinear           |  25 |        -0.0383946  |         0.686577 |       0.24     |
|    51 | charge_transfer_ridge  |  25 |        -0.0348113  |         0.682692 |       0.28     |
|    51 | b_waveform_extra_trees |  25 |        -0.0206524  |         0.685447 |       0.24     |
|    52 | b2_loglinear           |   6 |        -0.224578   |         0.363198 |       0.5      |
|    52 | charge_transfer_ridge  |   6 |        -0.228083   |         0.363836 |       0.333333 |
|    52 | b_waveform_extra_trees |   6 |        -0.219989   |         0.362825 |       0.5      |
|    53 | b2_loglinear           |  17 |         0.444804   |         1.02455  |       0.235294 |
|    53 | charge_transfer_ridge  |  17 |         0.433123   |         1.03177  |       0.235294 |
|    53 | b_waveform_extra_trees |  17 |         0.452661   |         1.03797  |       0.176471 |
|    54 | b2_loglinear           |  18 |         0.401566   |         0.658492 |       0.222222 |
|    54 | charge_transfer_ridge  |  18 |         0.402619   |         0.650739 |       0.222222 |
|    54 | b_waveform_extra_trees |  18 |         0.404713   |         0.656312 |       0.222222 |
|    55 | b2_loglinear           |  27 |        -0.119699   |         0.444979 |       0.296296 |
|    55 | charge_transfer_ridge  |  27 |        -0.118086   |         0.462035 |       0.296296 |
|    55 | b_waveform_extra_trees |  27 |        -0.115576   |         0.542274 |       0.296296 |
|    56 | b2_loglinear           |  68 |         0.0619644  |         0.648184 |       0.279412 |
|    56 | charge_transfer_ridge  |  68 |         0.0640765  |         0.646559 |       0.279412 |
|    56 | b_waveform_extra_trees |  68 |         0.067889   |         0.649392 |       0.294118 |
|    57 | b2_loglinear           | 276 |        -0.133479   |         0.537983 |       0.315217 |
|    57 | charge_transfer_ridge  | 276 |        -0.134282   |         0.538335 |       0.311594 |
|    57 | b_waveform_extra_trees | 276 |        -0.118378   |         0.526331 |       0.311594 |
|    58 | b2_loglinear           |  34 |         0.0283621  |         0.501095 |       0.352941 |
|    58 | charge_transfer_ridge  |  34 |        -0.00232207 |         0.552958 |       0.382353 |
|    58 | b_waveform_extra_trees |  34 |         0.0278104  |         0.515921 |       0.382353 |
|    59 | b2_loglinear           |   9 |        -0.117068   |         0.285191 |       0.555556 |
|    59 | charge_transfer_ridge  |   9 |        -0.11535    |         0.334798 |       0.444444 |
|    59 | b_waveform_extra_trees |   9 |        -0.0896346  |         0.251865 |       0.666667 |
|    60 | b2_loglinear           |  10 |         1.42047    |         1.89356  |       0.1      |
|    60 | charge_transfer_ridge  |  10 |         1.33984    |         1.90067  |       0.1      |
|    60 | b_waveform_extra_trees |  10 |         1.31199    |         1.9248   |       0.1      |
|    61 | b2_loglinear           |   6 |        -0.062651   |         0.533411 |       0.666667 |
|    61 | charge_transfer_ridge  |   6 |        -0.0560689  |         0.654274 |       0.5      |
|    61 | b_waveform_extra_trees |   6 |        -0.0721766  |         0.436166 |       0.5      |
|    62 | b2_loglinear           |   8 |         0.182622   |         0.44145  |       0.5      |
|    62 | charge_transfer_ridge  |   8 |         0.160495   |         0.441593 |       0.5      |
|    62 | b_waveform_extra_trees |   8 |         0.227414   |         0.450009 |       0.375    |
|    63 | b2_loglinear           |  39 |        -0.080162   |         0.24572  |       0.692308 |
|    63 | charge_transfer_ridge  |  39 |        -0.0769376  |         0.244099 |       0.692308 |
|    63 | b_waveform_extra_trees |  39 |        -0.0806368  |         0.245491 |       0.692308 |
|    64 | b2_loglinear           |  35 |         0.100485   |         0.74765  |       0.485714 |
|    64 | charge_transfer_ridge  |  35 |         0.104629   |         0.747953 |       0.457143 |
|    64 | b_waveform_extra_trees |  35 |         0.0931883  |         0.742219 |       0.457143 |
|    65 | b2_loglinear           |  13 |         0.0600044  |         0.502953 |       0.538462 |
|    65 | charge_transfer_ridge  |  13 |         0.0592778  |         0.513149 |       0.538462 |
|    65 | b_waveform_extra_trees |  13 |         0.0555958  |         0.498022 |       0.538462 |

| b2_amp_bin   | method                 |    n |   bias_median_frac |   res68_abs_frac |   within_25pct |
|:-------------|:-----------------------|-----:|-------------------:|-----------------:|---------------:|
| 1000_2000    | b2_loglinear           |  496 |         -0.0532619 |         0.503114 |       0.366935 |
| 1000_2000    | charge_transfer_ridge  |  496 |         -0.0458755 |         0.505113 |       0.362903 |
| 1000_2000    | b_waveform_extra_trees |  496 |         -0.051541  |         0.499992 |       0.370968 |
| 2000_3000    | b2_loglinear           |  474 |         -0.049678  |         0.50894  |       0.333333 |
| 2000_3000    | charge_transfer_ridge  |  474 |         -0.0554974 |         0.51826  |       0.329114 |
| 2000_3000    | b_waveform_extra_trees |  474 |         -0.0485917 |         0.510532 |       0.337553 |
| 3000_5000    | b2_loglinear           | 1212 |         -0.0390143 |         0.517293 |       0.342409 |
| 3000_5000    | charge_transfer_ridge  | 1212 |         -0.0386829 |         0.516007 |       0.344059 |
| 3000_5000    | b_waveform_extra_trees | 1212 |         -0.0416489 |         0.518282 |       0.344884 |
| 5000_7000    | b2_loglinear           |  953 |         -0.0601224 |         0.527913 |       0.350472 |
| 5000_7000    | charge_transfer_ridge  |  953 |         -0.0584408 |         0.528032 |       0.350472 |
| 5000_7000    | b_waveform_extra_trees |  953 |         -0.0561186 |         0.527374 |       0.345226 |
| 7000_inf     | b2_loglinear           |  920 |         -0.0416372 |         0.539958 |       0.334783 |
| 7000_inf     | charge_transfer_ridge  |  920 |         -0.0390225 |         0.541597 |       0.332609 |
| 7000_inf     | b_waveform_extra_trees |  920 |         -0.0334445 |         0.541504 |       0.334783 |

## Leakage Audit

- Each held-out run is predicted only by models trained on other runs.
- Feature matrices exclude run id, event id, A selected flags, A charge columns, and the target.
- Shuffled-target ExtraTrees res68 is `0.5210`, so the real ML result is not a trivial split artifact.
- Matching uses `EVT`; `EVENTNO` is not used because HRDA/HRDB row numbering differs within a run.

## Finding

The opposite-stack A-charge target does not reproduce the one-percent P04 duplicate-readout closure: B2-only log-linear transfer has res68 0.5203, the strong traditional B-charge ridge has 0.5193 [0.5058, 0.5383], and waveform ExtraTrees has 0.5209 [0.5080, 0.5371]. The best method is charge_transfer_ridge at 0.5193, while the shuffled-target sentinel is 0.5210. This supports the P04b conclusion: duplicate-readout closure is strong, but transfer to an external charge-energy proxy is broad and topology-limited.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `b_s00_counts_by_run.csv`, `astack_gate_counts.csv`, `ab_topology_counts_by_run.csv`, `external_ab_summary.csv`, `external_ab_by_run.csv`, `external_ab_by_b2_amp.csv`, and `external_ab_predictions.csv`.
