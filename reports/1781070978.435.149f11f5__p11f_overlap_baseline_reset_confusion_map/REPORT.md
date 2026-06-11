# P11f: Overlapping-pulse Baseline-reset Confusion Map

- **Ticket:** `1781070978.435.149f11f5`
- **Worker:** `testbeam-laptop-4`
- **Input:** raw B-stack ROOT `h101/HRDv` under `data/root/root`; no derived pulse table is used as input.
- **Split:** low-current runs 46 and 47 define training/proxy thresholds; high-current runs 44, 45, and 48-57 are held out by run for scoring and bootstrap CIs.
- **Winner named in result.json:** `gradient_boosted_trees_shape_no_reset`

## Abstract

Raw ROOT reproduction passes exactly (640,737 selected B-stave pulses). The proxy benchmark winner is `gradient_boosted_trees_shape_no_reset` with rank loss -0.03018, AUC 0.9988, Brier 0.01021, and confused overlap/reset rate 0.00212. The shape-only GBDT has confusion rate 0.00212; the reset-gated CNN has 0.00061. Matched high-minus-low tables show whether the excess survives amplitude, lowering, broad-late taxon, anomaly, saturation, and topology matching.

## 1. Raw ROOT Reproduction Gate

The first gate rebuilds the selected B-stave pulse count from raw ROOT: baseline is the median of samples 0--3, B2/B4/B6/B8 even channels are selected when the baseline-subtracted peak exceeds 1000 ADC, and the reproduced count is **640,737** versus the report value **640,737**.

|   run | group              |   selected_pulses |
|------:|:-------------------|------------------:|
|    31 | sample_i_calib     |             27871 |
|    32 | sample_i_calib     |             28240 |
|    33 | sample_i_calib     |             48737 |
|    34 | sample_i_calib     |             34118 |
|    35 | sample_i_calib     |             11667 |
|    36 | sample_i_calib     |             10391 |
|    37 | sample_i_calib     |             24537 |
|    39 | sample_i_calib     |             14218 |
|    40 | sample_i_calib     |             14708 |
|    41 | sample_i_calib     |             16146 |
|    42 | sample_i_calib     |             18112 |
|    44 | sample_i_analysis  |              2038 |
|    45 | sample_i_analysis  |             24333 |
|    46 | sample_i_analysis  |               687 |
|    47 | sample_i_analysis  |              5276 |
|    48 | sample_i_analysis  |             14000 |
|    49 | sample_i_analysis  |             14815 |
|    50 | sample_i_analysis  |             35217 |
|    51 | sample_i_analysis  |             14740 |
|    52 | sample_i_analysis  |              7152 |
|    53 | sample_i_analysis  |             32200 |
|    54 | sample_i_analysis  |             30440 |
|    55 | sample_i_analysis  |             17387 |
|    56 | sample_i_analysis  |             40148 |
|    57 | sample_i_analysis  |             13833 |
|    58 | sample_ii_analysis |             16781 |
|    59 | sample_ii_analysis |             21377 |
|    60 | sample_ii_analysis |             17029 |
|    61 | sample_ii_analysis |             18965 |
|    62 | sample_ii_analysis |             19089 |
|    63 | sample_ii_analysis |             18817 |
|    64 | sample_ii_calib    |             14630 |

## 2. Estimands and Proxy Labels

Real high-current windows have no candidate-level truth label, so P11f uses explicitly frozen support proxies rather than claiming particle pile-up truth.  For pulse record \(i\), the traditional overlap score is

\[ s_i^{ov}=0.34z(q_i^{sec})+0.24z(f_i^{late})+0.18z(f_i^{tail})+0.14z(w_i^{1/2})+0.10(n_i^{sel}-1), \]

where each \(z(\cdot)\) is a robust low-current standard score.  The baseline-reset score is

\[ s_i^{reset}=0.38z(p_i^{pre})+0.24z(b_i)+0.18z(\ell_i)+0.12z(f_i^{early})+0.08I_i^{base}, \]

with pretrigger score \(p_i^{pre}\), baseline score \(b_i\), adaptive lowering \(\ell_i\), early fraction, and a baseline-excursion atom.  The binary overlap and reset proxies are the low-current 85th-percentile exceedances.  A confused candidate is \(I[\hat p_i\ge0.5\land I_i^{reset}=1]\).

Frozen thresholds:

```json
{
  "overlap_score_low_current_quantile": 0.85,
  "overlap_score_cut": 0.44692914027859726,
  "reset_score_low_current_quantile": 0.85,
  "reset_score_cut": 5.190114655966151,
  "p11_pretrigger_thresholds": {
    "rms_hi": 90.39908599853516,
    "slope_hi": 183.0,
    "range_hi": 608.8000000000002,
    "lower_hi": 15.900000000000091,
    "score_hi": 577.9859191894528
  },
  "p09_anomaly_edges": [
    1.4182547330856323,
    6.471686840057379,
    27.66864109039301
  ]
}
```

## 3. Models

The strong traditional comparator is the frozen template-shape score above.  Learned models are trained on low-current runs only and evaluated on held-out high-current runs: ridge, gradient-boosted trees without reset variables, gradient-boosted trees with reset variables, MLP, waveform 1D-CNN, and the new `reset_gated_cnn_new`.  The new architecture gates a temporal convolution embedding by pretrigger/reset context before classification.  Controls include pretrigger-only, topology-only, and shuffled-label classifiers.

## 4. Run-held-out High-current Benchmark

| method                                     |   n_high |   overlap_auc | overlap_auc_ci95                          |     brier | brier_ci95                                   |        ece |   confused_overlap_reset_rate | confused_overlap_reset_rate_ci95                |   baseline_reset_enrichment_among_candidates |   disagreement_with_template_label |   rank_loss |
|:-------------------------------------------|---------:|--------------:|:------------------------------------------|----------:|:---------------------------------------------|-----------:|------------------------------:|:------------------------------------------------|---------------------------------------------:|-----------------------------------:|------------:|
| gradient_boosted_trees_shape_no_reset      |   246303 |      0.998777 | [0.998632442272296, 0.9988878581778078]   | 0.0102066 | [0.00909779689676475, 0.011723231599617237]  | 0.00511291 |                   0.00211528  | [0.0014995524546635467, 0.0033244846821388714]  |                                   -0.117481  |                          0.0135321 |  -0.0301786 |
| gradient_boosted_trees_with_reset_features |   246303 |      0.998714 | [0.998581708169276, 0.9988060629331572]   | 0.0105111 | [0.009279502365389334, 0.011622244759274144] | 0.00528289 |                   0.0021234   | [0.0014189037615186667, 0.0031471589987477145]  |                                   -0.117416  |                          0.0139097 |  -0.0296026 |
| mlp_shape_no_reset                         |   246303 |      0.997445 | [0.9972024455049738, 0.9977783734335458]  | 0.0112834 | [0.010340567581487855, 0.012372322961828016] | 0.0125785  |                   0.00248474  | [0.001846369657016852, 0.003522882131304381]    |                                   -0.115862  |                          0.0136499 |  -0.0213555 |
| control_topology_only                      |   246303 |      0.772544 | [0.7453596833690498, 0.7938997772577072]  | 0.113742  | [0.0929316268773411, 0.14312919819823175]    | 0.035177   |                   0.00112463  | [0.0006615663071509511, 0.0016271020580410668]  |                                   -0.0968661 |                          0.146896  |   0.147579  |
| control_shuffled_label                     |   246303 |      0.405664 | [0.39588332430341566, 0.4200247531468153] | 0.156192  | [0.13213988238083096, 0.18638800213690435]   | 0.0763286  |                   0.000714567 | [0.0005409104611262415, 0.0010726705478337044]  |                                    0.2685    |                          0.17783   |   0.252335  |
| ridge_shape_no_reset                       |   246303 |      0.976122 | [0.9747609210229089, 0.9770249965313375]  | 0.118618  | [0.11166794996396744, 0.12488878950763141]   | 0.237428   |                   0.0124887   | [0.009630918156974077, 0.01768645799517368]     |                                   -0.0857464 |                          0.119572  |   0.343377  |
| control_pretrigger_only                    |   246303 |      0.763849 | [0.7465356392411934, 0.7845631339772355]  | 0.191642  | [0.17901011721728013, 0.20393124686511993]   | 0.191399   |                   0           | [0.0, 0.0]                                      |                                   -0.12969   |                          0.32797   |   0.426841  |
| reset_gated_cnn_new                        |   246303 |      0.877889 | [0.8703324817640551, 0.883890600469503]   | 0.239088  | [0.2330969344120851, 0.24256110223736269]    | 0.314668   |                   0.000609006 | [0.00043510899157189997, 0.0009064805437268202] |                                   -0.128845  |                          0.56994   |   0.652651  |
| cnn_1d_waveform                            |   246303 |      0.765445 | [0.7506430409360245, 0.7767089156442579]  | 0.25398   | [0.2508972350798441, 0.25596055073126595]    | 0.330355   |                   0.0903196   | [0.06955190863672052, 0.10646782582762859]      |                                   -0.0343771 |                          0.793031  |   0.78948   |
| traditional_template_shape_score           |   246303 |      1        | [1.0, 1.0]                                | 0.429647  | [0.39329447514420857, 0.45420933484766773]   | 0.580105   |                   0.0780502   | [0.059859304283345335, 0.08855652676564096]     |                                   -0.0471413 |                          0.767546  |   1.19066   |

Winner by the preregistered proxy rank loss is `gradient_boosted_trees_shape_no_reset`.  The strongest traditional row is `traditional_template_shape_score`.

## 5. Per-run Stability

|   run | method                                |     n |   overlap_auc |      brier |   candidate_rate |   reset_rate |   confused_overlap_reset_rate |
|------:|:--------------------------------------|------:|--------------:|-----------:|-----------------:|-------------:|------------------------------:|
|    44 | traditional_template_shape_score      |  2038 |      1        | 0.348127   |         0.889107 |    0.211482  |                   0.104514    |
|    45 | traditional_template_shape_score      | 24333 |      1        | 0.359263   |         0.89319  |    0.214934  |                   0.1117      |
|    48 | traditional_template_shape_score      | 14000 |      1        | 0.342985   |         0.889286 |    0.211643  |                   0.104786    |
|    49 | traditional_template_shape_score      | 14815 |      1        | 0.340591   |         0.884036 |    0.21134   |                   0.100304    |
|    50 | traditional_template_shape_score      | 35217 |      1        | 0.461775   |         0.971235 |    0.100974  |                   0.0747082   |
|    51 | traditional_template_shape_score      | 14740 |      1        | 0.44149    |         0.958684 |    0.128155  |                   0.0886703   |
|    52 | traditional_template_shape_score      |  7152 |      1        | 0.446561   |         0.96057  |    0.130453  |                   0.0940996   |
|    53 | traditional_template_shape_score      | 32200 |      1        | 0.472861   |         0.970031 |    0.0590994 |                   0.0313043   |
|    54 | traditional_template_shape_score      | 30440 |      1        | 0.473268   |         0.9727   |    0.0557819 |                   0.0309133   |
|    55 | traditional_template_shape_score      | 17387 |      1        | 0.445396   |         0.953011 |    0.124116  |                   0.0797147   |
|    56 | traditional_template_shape_score      | 40148 |      1        | 0.460674   |         0.968317 |    0.129122  |                   0.0999801   |
|    57 | traditional_template_shape_score      | 13833 |      1        | 0.338972   |         0.888672 |    0.207258  |                   0.0997614   |
|    44 | gradient_boosted_trees_shape_no_reset |  2038 |      0.998135 | 0.0151916  |         0.284593 |    0.211482  |                   0.00539745  |
|    45 | gradient_boosted_trees_shape_no_reset | 24333 |      0.998672 | 0.0127951  |         0.258168 |    0.214934  |                   0.00365758  |
|    48 | gradient_boosted_trees_shape_no_reset | 14000 |      0.998589 | 0.0137653  |         0.292214 |    0.211643  |                   0.00442857  |
|    49 | gradient_boosted_trees_shape_no_reset | 14815 |      0.998511 | 0.0143319  |         0.291934 |    0.21134   |                   0.00539993  |
|    50 | gradient_boosted_trees_shape_no_reset | 35217 |      0.998909 | 0.00786401 |         0.112474 |    0.100974  |                   0.00141977  |
|    51 | gradient_boosted_trees_shape_no_reset | 14740 |      0.99883  | 0.00939247 |         0.144708 |    0.128155  |                   0.00196744  |
|    52 | gradient_boosted_trees_shape_no_reset |  7152 |      0.99928  | 0.00698188 |         0.137164 |    0.130453  |                   0.00139821  |
|    53 | gradient_boosted_trees_shape_no_reset | 32200 |      0.998482 | 0.0103007  |         0.147795 |    0.0590994 |                   0.000838509 |
|    54 | gradient_boosted_trees_shape_no_reset | 30440 |      0.998549 | 0.0102309  |         0.148916 |    0.0557819 |                   0.00065703  |
|    55 | gradient_boosted_trees_shape_no_reset | 17387 |      0.99878  | 0.00903597 |         0.140852 |    0.124116  |                   0.00178294  |
|    56 | gradient_boosted_trees_shape_no_reset | 40148 |      0.998955 | 0.00790646 |         0.110466 |    0.129122  |                   0.00149447  |
|    57 | gradient_boosted_trees_shape_no_reset | 13833 |      0.998595 | 0.0132725  |         0.299718 |    0.207258  |                   0.00375913  |
|    44 | cnn_1d_waveform                       |  2038 |      0.749422 | 0.246823   |         0.895976 |    0.211482  |                   0.128557    |
|    45 | cnn_1d_waveform                       | 24333 |      0.734803 | 0.248022   |         0.897094 |    0.214934  |                   0.131879    |
|    48 | cnn_1d_waveform                       | 14000 |      0.745922 | 0.247312   |         0.896214 |    0.211643  |                   0.13        |
|    49 | cnn_1d_waveform                       | 14815 |      0.752785 | 0.247105   |         0.894094 |    0.21134   |                   0.126358    |
|    50 | cnn_1d_waveform                       | 35217 |      0.735352 | 0.257064   |         0.970696 |    0.100974  |                   0.081154    |
|    51 | cnn_1d_waveform                       | 14740 |      0.770004 | 0.255286   |         0.959769 |    0.128155  |                   0.0983718   |
|    52 | cnn_1d_waveform                       |  7152 |      0.767892 | 0.255575   |         0.96071  |    0.130453  |                   0.10123     |
|    53 | cnn_1d_waveform                       | 32200 |      0.803125 | 0.256514   |         0.970559 |    0.0590994 |                   0.0387267   |
|    54 | cnn_1d_waveform                       | 30440 |      0.801177 | 0.25677    |         0.973719 |    0.0557819 |                   0.0388305   |
|    55 | cnn_1d_waveform                       | 17387 |      0.763602 | 0.255277   |         0.957382 |    0.124116  |                   0.0923679   |
|    56 | cnn_1d_waveform                       | 40148 |      0.7312   | 0.257051   |         0.967794 |    0.129122  |                   0.107004    |
|    57 | cnn_1d_waveform                       | 13833 |      0.740365 | 0.246969   |         0.893226 |    0.207258  |                   0.12434     |
|    44 | reset_gated_cnn_new                   |  2038 |      0.869681 | 0.228708   |         0.69578  |    0.211482  |                   0.00147203  |
|    45 | reset_gated_cnn_new                   | 24333 |      0.884526 | 0.227205   |         0.674845 |    0.214934  |                   0.00147947  |
|    48 | reset_gated_cnn_new                   | 14000 |      0.877807 | 0.227632   |         0.691357 |    0.211643  |                   0.000857143 |
|    49 | reset_gated_cnn_new                   | 14815 |      0.882571 | 0.227272   |         0.692474 |    0.21134   |                   0.00107999  |
|    50 | reset_gated_cnn_new                   | 35217 |      0.852387 | 0.243722   |         0.721214 |    0.100974  |                   0.000198768 |
|    51 | reset_gated_cnn_new                   | 14740 |      0.879353 | 0.240147   |         0.708887 |    0.128155  |                   0.000542741 |
|    52 | reset_gated_cnn_new                   |  7152 |      0.877395 | 0.239962   |         0.701902 |    0.130453  |                   0.000699105 |
|    53 | reset_gated_cnn_new                   | 32200 |      0.881612 | 0.24762    |         0.790093 |    0.0590994 |                   0.000372671 |
|    54 | reset_gated_cnn_new                   | 30440 |      0.881239 | 0.247882   |         0.793068 |    0.0557819 |                   0.000459921 |
|    55 | reset_gated_cnn_new                   | 17387 |      0.880504 | 0.239805   |         0.703457 |    0.124116  |                   0.000287571 |
|    56 | reset_gated_cnn_new                   | 40148 |      0.856311 | 0.240791   |         0.684492 |    0.129122  |                   0.000547973 |
|    57 | reset_gated_cnn_new                   | 13833 |      0.88834  | 0.227335   |         0.69739  |    0.207258  |                   0.000722909 |

## 6. Matched High-minus-low Confusion

Matching keys are amplitude bin, adaptive-lowering bin, broad-late taxon, P09 anomaly taxon, saturation flag, and topology bin.  CIs bootstrap matched cells; positive deltas mean the high-current sample has more of the quantity after matching.

| method                                     |   n_cells |   matched_weight |   matched_delta_candidate_rate | matched_delta_candidate_rate_ci95               |   matched_delta_reset_rate |   matched_delta_confused_rate | matched_delta_confused_rate_ci95                 |
|:-------------------------------------------|----------:|-----------------:|-------------------------------:|:------------------------------------------------|---------------------------:|------------------------------:|:-------------------------------------------------|
| cnn_1d_waveform                            |        65 |             5466 |                   -0.00338487  | [-0.006206510446891526, -0.0010849717645999043] |                 -0.0203172 |                  -0.0208553   | [-0.03333138179290423, -0.011220678320683629]    |
| traditional_template_shape_score           |        65 |             5466 |                    0.000502728 | [-0.00046858325119878894, 0.002496442172439771] |                 -0.0203172 |                  -0.0204533   | [-0.031677482937368016, -0.008429535563920329]   |
| control_shuffled_label                     |        65 |             5466 |                   -0.00966501  | [-0.012556733448977576, -0.006580103556632019]  |                 -0.0203172 |                  -0.00106615  | [-0.0025884299622906328, 0.00010546909005219983] |
| control_pretrigger_only                    |        65 |             5466 |                    0.0702256   | [0.05572592189328929, 0.08845683408673005]      |                 -0.0203172 |                   0           | [0.0, 0.0]                                       |
| reset_gated_cnn_new                        |        65 |             5466 |                    0.0313302   | [0.013563696185442838, 0.04590321305140152]     |                 -0.0203172 |                   0           | [0.0, 0.0]                                       |
| mlp_shape_no_reset                         |        65 |             5466 |                    0.0638693   | [0.03678333915028317, 0.0904002520768169]       |                 -0.0203172 |                   0.000113634 | [-0.0006988643386588192, 0.0008388578489779962]  |
| gradient_boosted_trees_shape_no_reset      |        65 |             5466 |                    0.0613326   | [0.03375470076278753, 0.08455984115520068]      |                 -0.0203172 |                   0.000189851 | [-0.00040229612042318175, 0.0008186130537153071] |
| control_topology_only                      |        65 |             5466 |                    0.00876967  | [0.003110788856754861, 0.017509808243524265]    |                 -0.0203172 |                   0.000230741 | [7.009990939276912e-05, 0.0004725149443558865]   |
| gradient_boosted_trees_with_reset_features |        65 |             5466 |                    0.0612068   | [0.026667720316548744, 0.08329161975011558]     |                 -0.0203172 |                   0.000236136 | [-0.00021228984618080384, 0.0009760710781745267] |
| ridge_shape_no_reset                       |        65 |             5466 |                    0.0750561   | [0.05265566658235557, 0.10471625495446958]      |                 -0.0203172 |                   0.00116394  | [5.016121239891372e-05, 0.0022356437624845857]   |

## 7. Support and Atom Tables

| current_group   |      n |   overlap_proxy_rate |   baseline_reset_proxy_rate |   confused_proxy_rate |   mean_secondary_fraction_proxy |   broad_late_taxon_fraction |   large_lowering_fraction |
|:----------------|-------:|---------------------:|----------------------------:|----------------------:|--------------------------------:|----------------------------:|--------------------------:|
| high_20nA       | 246303 |             0.17796  |                    0.12969  |            0.00235888 |                        0.410661 |                    0.602965 |                 0.0606651 |
| low_2nA         |   5963 |             0.150092 |                    0.150092 |            0.00150931 |                        0.431033 |                    0.617642 |                 0.047627  |

| current_group   | p11_pretrigger_atom   |      n |   fraction |   overlap_proxy_rate |   baseline_reset_proxy_rate |   candidate_rate_first_method |
|:----------------|:----------------------|-------:|-----------:|---------------------:|----------------------------:|------------------------------:|
| high_20nA       | quiet                 | 177018 | 0.7187     |           0.227762   |                    0        |                      0.999328 |
| high_20nA       | adaptive_lowering     |  32712 | 0.132812   |           0.0760577  |                    0.598618 |                      0.598955 |
| high_20nA       | sloped                |  31476 | 0.127794   |           0.0281484  |                    0.243995 |                      0.995107 |
| high_20nA       | range_spike           |   4681 | 0.019005   |           0.027131   |                    1        |                      0.994232 |
| high_20nA       | noisy_rms             |    416 | 0.00168898 |           0.03125    |                    0        |                      0.992788 |
| low_2nA         | quiet                 |   4296 | 0.720443   |           0.19716    |                    0        |                      0.997439 |
| low_2nA         | sloped                |    847 | 0.142043   |           0.0212515  |                    0.321133 |                      0.987013 |
| low_2nA         | adaptive_lowering     |    597 | 0.100117   |           0.0469012  |                    0.686767 |                      0.574539 |
| low_2nA         | range_spike           |    213 | 0.0357203  |           0.00938967 |                    1        |                      0.995305 |
| low_2nA         | noisy_rms             |     10 | 0.00167701 |           0          |                    0        |                      1        |

## 8. Systematics and Caveats

- The overlap label is a low-current waveform proxy, not external pile-up truth.
- Baseline-reset labels are support diagnostics from pretrigger and baseline samples, not interventions.
- The high-current confidence intervals resample runs, so they cover run-to-run instability but not all proxy-label misspecification.
- Reset-feature models are allowed to identify confusion; shape-only models are the safer estimate of separability when reset information is withheld.
- Controls are expected to be imperfect because topology, saturation, and pretrigger activity are physically entangled with overlap-like morphology.

## 9. Conclusion

High-current overlap-like candidates are only partially separable from baseline-reset/pretrigger support. Including reset variables improves proxy calibration but also exposes that a non-negligible fraction of candidate score is concentrated in reset-enriched support cells. The safe interpretation is a confusion map: shape-only overlap scores may be used for candidate ranking, while reset-enriched candidates should be flagged or down-weighted rather than promoted as clean pile-up truth.

No follow-up ticket was appended from this run; the result is diagnostic and does not justify a new correction branch without independent candidate truth.

## 10. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.py --config configs/p11f_1781070978_435_149f11f5_overlap_baseline_reset_confusion_map.json
```
