# S14d: anomaly-veto energy-ordering sensitivity

- **Ticket ID:** 1781018820.3955.63293f84
- **Worker:** testbeam-laptop-3
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo.
- **Split:** train/calibration runs vs held-out analysis runs; bootstrap CIs resample held-out run/depth-stave blocks.

## Raw Reproduction

Raw ROOT reproduction ran first: S00 selected B-stave pulse records `640,737` vs expected `640,737` (delta `0`).

## Methods

Traditional charge proxies are peak sum, positive integral, adaptive-template charge, and rising-edge saturation-corrected charge. The frozen veto ladder cumulatively adds P09 anomaly, S10 pile-up/long-tail, S16 adaptive-lowering/baseline, and P07 saturation vetoes. The primary head-to-head uses the best held-out traditional proxy after the full ladder.

The ML method starts from P07/P04 charge estimates, adds calibrated train-run anomaly, pile-up, and baseline scores, and fits an event-level monotonic surrogate to duplicate-readout charge without run, event, depth, PID, or odd-channel feature inputs.

## Primary Head-to-Head

| veto_ladder     | charge_proxy                |   n_kept |   veto_acceptance |   median_charge_proxy_shift_log | charge_shift_ci95                           |   unsaturated_control_res68_frac | unsat_res68_ci95                           |   energy_proxy_res68_frac | energy_res68_ci95                          |   depth_ordering_violation_fraction | depth_violation_ci95   |
|:----------------|:----------------------------|---------:|------------------:|--------------------------------:|:--------------------------------------------|---------------------------------:|:-------------------------------------------|--------------------------:|:-------------------------------------------|------------------------------------:|:-----------------------|
| p09_s10_s16_p07 | traditional_integral        |   159074 |          0.477912 |                       -0.166174 | [-0.4646597173226229, -0.06131674978189547] |                        0.138788  | [0.096450052620731, 0.16624274354849886]   |                  0.113985 | [0.09452737742686117, 0.14225410836381203] |                                   0 | [0.0, 0.0]             |
| p09_s10_s16_p07 | ml_score_adjusted_monotonic |   159074 |          0.477912 |                       -0.169412 | [-0.5818236726550057, -0.04421943693451702] |                        0.0249409 | [0.02066013054985804, 0.03204243637172742] |                  0.119023 | [0.10211332998371457, 0.13857960824048374] |                                   0 | [0.0, 0.0]             |

## Veto Ladder Summary

| veto_ladder     | charge_proxy                     |   n_kept |   veto_acceptance |   median_charge_proxy_shift_log | charge_shift_ci95                           |   unsaturated_control_res68_frac | unsat_res68_ci95                             |   energy_proxy_res68_frac | energy_res68_ci95                            |   depth_ordering_violation_fraction | depth_violation_ci95   |
|:----------------|:---------------------------------|---------:|------------------:|--------------------------------:|:--------------------------------------------|---------------------------------:|:---------------------------------------------|--------------------------:|:---------------------------------------------|------------------------------------:|:-----------------------|
| no_veto         | traditional_saturation_corrected |   332852 |          1        |                       0         | [-0.24159867802721494, 0.1123504940393233]  |                        0.241331  | [0.19742803608195622, 0.2922137853901242]    |                0.0430563  | [0.040290599466704526, 0.045324594953255734] |                                   0 | [0.0, 0.0]             |
| p09             | traditional_saturation_corrected |   316214 |          0.950014 |                       0.0241321 | [-0.17683172939601502, 0.1327819373600583]  |                        0.215506  | [0.15651486218889962, 0.244860211694947]     |                0.057347   | [0.05619869464919278, 0.058178517329523616]  |                                   0 | [0.0, 0.0]             |
| p09_s10         | traditional_saturation_corrected |   275497 |          0.827686 |                       0.0804046 | [-0.1318432622231461, 0.16065016396109308]  |                        0.239356  | [0.19574671846357025, 0.29150347309427743]   |                0.0752628  | [0.0659525903184894, 0.07904123170908088]    |                                   0 | [0.0, 0.0]             |
| p09_s10_s16     | traditional_saturation_corrected |   274380 |          0.82433  |                       0.0791049 | [-0.1864029078732748, 0.15834428399007816]  |                        0.238936  | [0.17327409439394315, 0.3156664675009713]    |                0.0744775  | [0.06263529918913062, 0.07910354657399735]   |                                   0 | [0.0, 0.0]             |
| p09_s10_s16_p07 | traditional_saturation_corrected |   159074 |          0.477912 |                      -0.218133  | [-0.5042531702072406, -0.09468524403480447] |                        0.234858  | [0.17310095290747426, 0.27283376775142676]   |                0.120657   | [0.09283929330547826, 0.14232161743632657]   |                                   0 | [0.0, 0.0]             |
| no_veto         | ml_score_adjusted_monotonic      |   332852 |          1        |                       0         | [-0.22303520579234926, 0.0869525923643728]  |                        0.0302037 | [0.02545175751827287, 0.03702975320212914]   |                0.00868173 | [0.008401265079421247, 0.00893747933543489]  |                                   0 | [0.0, 0.0]             |
| p09             | ml_score_adjusted_monotonic      |   316214 |          0.950014 |                       0.0209225 | [-0.140762314372976, 0.09149421785833421]   |                        0.027168  | [0.022434376942825848, 0.032774938406234605] |                0.0274438  | [0.022523124228468847, 0.0314370871016416]   |                                   0 | [0.0, 0.0]             |
| p09_s10         | ml_score_adjusted_monotonic      |   275497 |          0.827686 |                       0.0546058 | [-0.10373352974907535, 0.1128139255222934]  |                        0.0258765 | [0.021419962441211353, 0.03168350709666907]  |                0.0400552  | [0.03654024007262368, 0.04294058667005656]   |                                   0 | [0.0, 0.0]             |
| p09_s10_s16     | ml_score_adjusted_monotonic      |   274380 |          0.82433  |                       0.0546058 | [-0.06764328296623297, 0.1057723020946586]  |                        0.0258044 | [0.021151578396479943, 0.03151792181020508]  |                0.0391928  | [0.03623766760737729, 0.04189170576022232]   |                                   0 | [0.0, 0.0]             |
| p09_s10_s16_p07 | ml_score_adjusted_monotonic      |   159074 |          0.477912 |                      -0.169412  | [-0.5818236726550057, -0.04421943693451702] |                        0.0249409 | [0.02066013054985804, 0.03204243637172742]   |                0.119023   | [0.10211332998371457, 0.13857960824048374]   |                                   0 | [0.0, 0.0]             |

## Traditional Proxy Sweep

| veto_ladder     | charge_proxy                     |   n_kept |   veto_acceptance |   median_charge_proxy_shift_log | charge_shift_ci95                           |   unsaturated_control_res68_frac | unsat_res68_ci95                           |   energy_proxy_res68_frac | energy_res68_ci95                            |   depth_ordering_violation_fraction | depth_violation_ci95   |
|:----------------|:---------------------------------|---------:|------------------:|--------------------------------:|:--------------------------------------------|---------------------------------:|:-------------------------------------------|--------------------------:|:---------------------------------------------|------------------------------------:|:-----------------------|
| no_veto         | traditional_peak_sum             |   332852 |          1        |                       0         | [-0.3592969329543062, 0.12092863169553632]  |                         0.258692 | [0.24121838311849028, 0.3023366319735998]  |                 0.0317994 | [0.029429382563277408, 0.03531499189591652]  |                                   0 | [0.0, 0.0]             |
| p09             | traditional_peak_sum             |   316214 |          0.950014 |                       0.0246752 | [-0.19958116246367105, 0.1547050914672811]  |                         0.245435 | [0.23123713983039104, 0.2639717968969518]  |                 0.0481961 | [0.04213683816066852, 0.05255392725600708]   |                                   0 | [0.0, 0.0]             |
| p09_s10         | traditional_peak_sum             |   275497 |          0.827686 |                       0.0869006 | [-0.20569713598489464, 0.17797335586741106] |                         0.249772 | [0.22906973377170717, 0.2852548976896892]  |                 0.0559585 | [0.053915031247992934, 0.057912291118764184] |                                   0 | [0.0, 0.0]             |
| p09_s10_s16     | traditional_peak_sum             |   274380 |          0.82433  |                       0.0851375 | [-0.1621029309708725, 0.18221071674925893]  |                         0.2496   | [0.22119170540769958, 0.27917026920120835] |                 0.0552178 | [0.05339164522160926, 0.057258850422097766]  |                                   0 | [0.0, 0.0]             |
| p09_s10_s16_p07 | traditional_peak_sum             |   159074 |          0.477912 |                      -0.264515  | [-0.613015253964117, -0.12471508602245487]  |                         0.245029 | [0.2209276448671693, 0.26433273534956203]  |                 0.120807  | [0.0940067243712684, 0.1431410787906028]     |                                   0 | [0.0, 0.0]             |
| no_veto         | traditional_integral             |   332852 |          1        |                       0         | [-0.2608898693292161, 0.07502842891011358]  |                         0.139902 | [0.10930970130580367, 0.17547167048177748] |                 0.0211892 | [0.01988362327985016, 0.022505486660460736]  |                                   0 | [0.0, 0.0]             |
| p09             | traditional_integral             |   316214 |          0.950014 |                       0.0210424 | [-0.12568063058241422, 0.09402305852489375] |                         0.121763 | [0.0913946175784262, 0.14846884555376275]  |                 0.0441264 | [0.03755680019023217, 0.048368832640692076]  |                                   0 | [0.0, 0.0]             |
| p09_s10         | traditional_integral             |   275497 |          0.827686 |                       0.0569458 | [-0.13178753246887612, 0.1077312664993564]  |                         0.140341 | [0.10878320233839205, 0.17348136261492178] |                 0.0537023 | [0.05179163674759296, 0.05630322917210688]   |                                   0 | [0.0, 0.0]             |
| p09_s10_s16     | traditional_integral             |   274380 |          0.82433  |                       0.0567949 | [-0.09523790727540478, 0.1100769927974936]  |                         0.139959 | [0.097268005043909, 0.16905480924497002]   |                 0.0535762 | [0.051505893840365316, 0.0567219557729441]   |                                   0 | [0.0, 0.0]             |
| p09_s10_s16_p07 | traditional_integral             |   159074 |          0.477912 |                      -0.166174  | [-0.4646597173226229, -0.06131674978189547] |                         0.138788 | [0.096450052620731, 0.16624274354849886]   |                 0.113985  | [0.09452737742686117, 0.14225410836381203]   |                                   0 | [0.0, 0.0]             |
| no_veto         | traditional_adaptive_template    |   332852 |          1        |                       0         | [-0.2754761407646179, 0.12231372541113544]  |                         0.241331 | [0.2020951314544016, 0.30602884720090207]  |                 0.0313668 | [0.02926879219755289, 0.03462638236081417]   |                                   0 | [0.0, 0.0]             |
| p09             | traditional_adaptive_template    |   316214 |          0.950014 |                       0.0241321 | [-0.21277735571799364, 0.13040530557653984] |                         0.215506 | [0.1519166026914738, 0.25450949391622846]  |                 0.0478323 | [0.04218903049525741, 0.05276385107545089]   |                                   0 | [0.0, 0.0]             |
| p09_s10         | traditional_adaptive_template    |   275497 |          0.827686 |                       0.0804046 | [-0.1620139919174722, 0.16520154338517662]  |                         0.239356 | [0.20035898277123076, 0.29944294417366896] |                 0.0561902 | [0.054228271951076726, 0.05821884498917934]  |                                   0 | [0.0, 0.0]             |
| p09_s10_s16     | traditional_adaptive_template    |   274380 |          0.82433  |                       0.0791049 | [-0.13270957626488444, 0.1777999033226565]  |                         0.238936 | [0.18365801264082635, 0.28597983413999345] |                 0.055492  | [0.05357751649323342, 0.05742790452005251]   |                                   0 | [0.0, 0.0]             |
| p09_s10_s16_p07 | traditional_adaptive_template    |   159074 |          0.477912 |                      -0.218133  | [-0.6014603055094156, -0.1138132634488786]  |                         0.234858 | [0.1940525950950045, 0.2956089794103152]   |                 0.120657  | [0.08814269362586583, 0.13918889574846532]   |                                   0 | [0.0, 0.0]             |
| no_veto         | traditional_saturation_corrected |   332852 |          1        |                       0         | [-0.24159867802721494, 0.1123504940393233]  |                         0.241331 | [0.19742803608195622, 0.2922137853901242]  |                 0.0430563 | [0.040290599466704526, 0.045324594953255734] |                                   0 | [0.0, 0.0]             |
| p09             | traditional_saturation_corrected |   316214 |          0.950014 |                       0.0241321 | [-0.17683172939601502, 0.1327819373600583]  |                         0.215506 | [0.15651486218889962, 0.244860211694947]   |                 0.057347  | [0.05619869464919278, 0.058178517329523616]  |                                   0 | [0.0, 0.0]             |
| p09_s10         | traditional_saturation_corrected |   275497 |          0.827686 |                       0.0804046 | [-0.1318432622231461, 0.16065016396109308]  |                         0.239356 | [0.19574671846357025, 0.29150347309427743] |                 0.0752628 | [0.0659525903184894, 0.07904123170908088]    |                                   0 | [0.0, 0.0]             |
| p09_s10_s16     | traditional_saturation_corrected |   274380 |          0.82433  |                       0.0791049 | [-0.1864029078732748, 0.15834428399007816]  |                         0.238936 | [0.17327409439394315, 0.3156664675009713]  |                 0.0744775 | [0.06263529918913062, 0.07910354657399735]   |                                   0 | [0.0, 0.0]             |
| p09_s10_s16_p07 | traditional_saturation_corrected |   159074 |          0.477912 |                      -0.218133  | [-0.5042531702072406, -0.09468524403480447] |                         0.234858 | [0.17310095290747426, 0.27283376775142676] |                 0.120657  | [0.09283929330547826, 0.14232161743632657]   |                                   0 | [0.0, 0.0]             |

## Held-out Run Summary

|   run | charge_proxy                     |   n_kept |   acceptance |   unsaturated_control_res68_frac |   energy_proxy_res68_frac |   depth_ordering_violation_fraction |
|------:|:---------------------------------|---------:|-------------:|---------------------------------:|--------------------------:|------------------------------------:|
|    44 | traditional_saturation_corrected |     1039 |     0.543694 |                        0.274251  |                 0.0959835 |                                   0 |
|    44 | ml_score_adjusted_monotonic      |     1039 |     0.543694 |                        0.0289394 |                 0.103145  |                                   0 |
|    45 | traditional_saturation_corrected |    11478 |     0.499065 |                        0.255852  |                 0.101489  |                                   0 |
|    45 | ml_score_adjusted_monotonic      |    11478 |     0.499065 |                        0.0268228 |                 0.106759  |                                   0 |
|    46 | traditional_saturation_corrected |      378 |     0.559172 |                        0.261157  |                 0.0851744 |                                   0 |
|    46 | ml_score_adjusted_monotonic      |      378 |     0.559172 |                        0.0227332 |                 0.101574  |                                   0 |
|    47 | traditional_saturation_corrected |     2771 |     0.537016 |                        0.256133  |                 0.0924965 |                                   0 |
|    47 | ml_score_adjusted_monotonic      |     2771 |     0.537016 |                        0.0226109 |                 0.104811  |                                   0 |
|    48 | traditional_saturation_corrected |     7258 |     0.550892 |                        0.284832  |                 0.0894449 |                                   0 |
|    48 | ml_score_adjusted_monotonic      |     7258 |     0.550892 |                        0.0278983 |                 0.101224  |                                   0 |
|    49 | traditional_saturation_corrected |     7699 |     0.553049 |                        0.276308  |                 0.0901492 |                                   0 |
|    49 | ml_score_adjusted_monotonic      |     7699 |     0.553049 |                        0.0275911 |                 0.101309  |                                   0 |
|    50 | traditional_saturation_corrected |    11704 |     0.341683 |                        0.107276  |                 0.163146  |                                   0 |
|    50 | ml_score_adjusted_monotonic      |    11704 |     0.341683 |                        0.0159102 |                 0.159133  |                                   0 |
|    51 | traditional_saturation_corrected |     5397 |     0.377571 |                        0.125814  |                 0.15951   |                                   0 |
|    51 | ml_score_adjusted_monotonic      |     5397 |     0.377571 |                        0.0177547 |                 0.153053  |                                   0 |
|    52 | traditional_saturation_corrected |     2549 |     0.367662 |                        0.123865  |                 0.157037  |                                   0 |
|    52 | ml_score_adjusted_monotonic      |     2549 |     0.367662 |                        0.017523  |                 0.150249  |                                   0 |
|    53 | traditional_saturation_corrected |    14330 |     0.456631 |                        0.0869171 |                 0.161572  |                                   0 |
|    53 | ml_score_adjusted_monotonic      |    14330 |     0.456631 |                        0.0142028 |                 0.161217  |                                   0 |
|    54 | traditional_saturation_corrected |    13485 |     0.454591 |                        0.0883881 |                 0.161582  |                                   0 |
|    54 | ml_score_adjusted_monotonic      |    13485 |     0.454591 |                        0.0141932 |                 0.161307  |                                   0 |
|    55 | traditional_saturation_corrected |     6459 |     0.383642 |                        0.122935  |                 0.16004   |                                   0 |
|    55 | ml_score_adjusted_monotonic      |     6459 |     0.383642 |                        0.0169729 |                 0.154263  |                                   0 |
|    56 | traditional_saturation_corrected |    13647 |     0.350597 |                        0.114534  |                 0.162092  |                                   0 |
|    56 | ml_score_adjusted_monotonic      |    13647 |     0.350597 |                        0.0166969 |                 0.156943  |                                   0 |
|    57 | traditional_saturation_corrected |     7279 |     0.563041 |                        0.273106  |                 0.0899616 |                                   0 |
|    57 | ml_score_adjusted_monotonic      |     7279 |     0.563041 |                        0.0273313 |                 0.10112   |                                   0 |
|    58 | traditional_saturation_corrected |     9977 |     0.626735 |                        0.262285  |                 0.0826756 |                                   0 |
|    58 | ml_score_adjusted_monotonic      |     9977 |     0.626735 |                        0.0284019 |                 0.106209  |                                   0 |
|    59 | traditional_saturation_corrected |     8024 |     0.57889  |                        0.355198  |                 0.0676424 |                                   0 |
|    59 | ml_score_adjusted_monotonic      |     8024 |     0.57889  |                        0.0465309 |                 0.072396  |                                   0 |
|    60 | traditional_saturation_corrected |     5292 |     0.522254 |                        0.34932   |                 0.0606493 |                                   0 |
|    60 | ml_score_adjusted_monotonic      |     5292 |     0.522254 |                        0.043464  |                 0.0717734 |                                   0 |
|    61 | traditional_saturation_corrected |     6103 |     0.540711 |                        0.335217  |                 0.0628548 |                                   0 |
|    61 | ml_score_adjusted_monotonic      |     6103 |     0.540711 |                        0.0456962 |                 0.0749025 |                                   0 |
|    62 | traditional_saturation_corrected |     6768 |     0.568214 |                        0.356615  |                 0.0603147 |                                   0 |
|    62 | ml_score_adjusted_monotonic      |     6768 |     0.568214 |                        0.0455088 |                 0.0702007 |                                   0 |
|    63 | traditional_saturation_corrected |     9305 |     0.62961  |                        0.337763  |                 0.0734531 |                                   0 |
|    63 | ml_score_adjusted_monotonic      |     9305 |     0.62961  |                        0.0389142 |                 0.088576  |                                   0 |
|    65 | traditional_saturation_corrected |     8132 |     0.683132 |                        0.377799  |                 0.062266  |                                   0 |
|    65 | ml_score_adjusted_monotonic      |     8132 |     0.683132 |                        0.0374347 |                 0.0799787 |                                   0 |

## Veto Counts

| veto                  |   pulse_count |   heldout_event_acceptance_after_cumulative |
|:----------------------|--------------:|--------------------------------------------:|
| P09 anomaly           |         34084 |                                    0.950014 |
| S10 pileup            |         80082 |                                    0.827686 |
| S16 baseline/lowering |          5469 |                                    0.82433  |
| P07 saturation        |        208015 |                                    0.477912 |

## ML-minus-Traditional Deltas

| veto_ladder     | traditional_reference_proxy   |   ml_minus_traditional_energy_res68_delta |   ml_minus_traditional_ordering_violation_delta | ordering_delta_ci95   |
|:----------------|:------------------------------|------------------------------------------:|------------------------------------------------:|:----------------------|
| no_veto         | traditional_integral          |                               -0.0125075  |                                               0 | [0.0, 0.0]            |
| p09             | traditional_integral          |                               -0.0166827  |                                               0 | [0.0, 0.0]            |
| p09_s10         | traditional_integral          |                               -0.0136471  |                                               0 | [0.0, 0.0]            |
| p09_s10_s16     | traditional_integral          |                               -0.0143834  |                                               0 | [0.0, 0.0]            |
| p09_s10_s16_p07 | traditional_integral          |                                0.00503805 |                                               0 | [0.0, 0.0]            |

## Leakage Audit

| check                                                         | value    | pass   |
|:--------------------------------------------------------------|:---------|:-------|
| train_heldout_run_overlap                                     | []       | True   |
| train_heldout_event_key_overlap                               | 0        | True   |
| ml_features_exclude_run_event_depth_stave_pid_and_odd_samples | true     | True   |
| shuffled_target_ml_unsat_res68_not_too_good                   | 0.538645 | True   |
| too_good_ml_unsat_res68_leakage_review                        | 0.024941 | True   |

## Finding

Raw ROOT reproduction passed at 640,737 selected pulses. The full P09/S10/S16/P07 ladder keeps 0.478 of held-out events and shifts the best traditional proxy (traditional_integral) log charge median by -0.166. Its unsaturated-control res68 changes from 0.1399 without vetoes to 0.1388 after the full ladder. Depth-ordering violation stays 0.0000 traditional and 0.0000 ML; ML-minus-traditional energy res68 delta after the full ladder is 0.0050. Thus the vetoes mainly change acceptance and charge-scale composition, not the coarse depth ordering envelope.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14d_1781018820_3955_63293f84_anomaly_veto_energy_ordering.py --config configs/s14d_1781018820_3955_63293f84.yaml
```
