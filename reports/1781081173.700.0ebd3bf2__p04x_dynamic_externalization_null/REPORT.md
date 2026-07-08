# P04x Dynamic-Only Charge Externalization Null

- **Ticket:** `1781081173.700.0ebd3bf2`
- **Worker:** `testbeam-laptop-3`
- **Input:** raw B-stack ROOT files under `data/root/root`; no release table is used for the reproduction gate.
- **Split:** runs 57 and 65 are held out; bootstrap intervals resample held-out run/stave blocks.
- **Primary target:** odd-channel duplicate-readout positive charge.
- **External stress target:** mean odd charge from the other selected B staves in the same event, available only where another selected stave exists.

## Abstract

This ticket retests P04k's dynamic-only charge closure under a stricter externalization null. Raw ROOT selector counts reproduce exactly, then traditional and ML/NN estimators are trained without held-out runs. The best duplicate-readout model is named in result.json, but the same prediction is much broader against the event-external proxy, which argues that the result is primarily duplicate-readout electronics closure inside a selector-induced population.

## 1. Raw-ROOT Reproduction Gate

For every configured `hrdb_run_*.root` file, `h101/HRDv` is reshaped to eight 18-sample channels. The median of samples 0--3 is subtracted per channel. The S00 median selector is

`A_med = max_t(x_t - median(x_0,x_1,x_2,x_3)) > 1000 ADC`,

and the dynamic selector is

`A_dyn = max_t(x_t) - min_t(x_t) > 1000 ADC`.

| quantity                   |   expected |   reproduced |   delta | pass   |
|:---------------------------|-----------:|-------------:|--------:|:-------|
| median_first_four_selected |     640737 |       640737 |       0 | True   |
| dynamic_range_selected     |     706373 |       706373 |       0 | True   |
| dynamic_only               |      65636 |        65636 |       0 | True   |
| median_only                |          0 |            0 |       0 | True   |

The gate is exact before invalid duplicate targets are removed and before any fit, bootstrap, or matching step.

## 2. Estimators

Traditional estimators are peak calibration, positive-lobe integral calibration, adaptive shifted-template scale calibration, and a strong Huber/ridge-style diagnostic stack using log amplitude, log charge, template scale, template loss, baseline excursion, pre-trigger RMS, and peak phase. The calibration objective is fold-local log duplicate charge:

`min_beta sum_i rho_delta(log q_i - beta^T z_i) + lambda ||beta||_2^2`.

ML/NN estimators are ridge with target-stave one-hot excluded, histogram gradient-boosted trees, an MLP, a compact 1D-CNN, and a residual-gated CNN. Models are trained separately on median-selected rows and dynamic-selector rows. Shuffled-target HGB sentinels use the same features with permuted log charge.

## 3. Duplicate-Readout Held-Out Results

| method                                             |    n |   bias_median_frac |   res68_abs_frac | res68_abs_frac_ci95                        |   full_rms_frac |   within_10pct |   within_25pct |
|:---------------------------------------------------|-----:|-------------------:|-----------------:|:-------------------------------------------|----------------:|---------------:|---------------:|
| gradient_boosted_trees_train_dynamic_selector      | 3715 |         0.00192976 |        0.0877043 | [0.06934370243307625, 0.09511998389914317] |        0.160807 |      0.721131  |      0.925707  |
| mlp_train_dynamic_selector                         | 3715 |        -0.0448766  |        0.142278  | [0.1230477040397202, 0.1526438443115182]   |        0.168199 |      0.559085  |      0.879139  |
| residual_gated_cnn_train_dynamic_selector          | 3715 |        -0.0403035  |        0.184455  | [0.14389775600102303, 0.19568783112618018] |        0.291484 |      0.44926   |      0.774966  |
| 1d_cnn_train_dynamic_selector                      | 3715 |         0.00201061 |        0.268609  | [0.22612397749980923, 0.2861498177302266]  |        0.41996  |      0.366891  |      0.653567  |
| ridge_target_stave_excluded_train_dynamic_selector | 3715 |        -0.126241   |        0.454572  | [0.40663314419718866, 0.47096780363174945] |        0.960904 |      0.140781  |      0.389233  |
| strong_traditional_huber                           | 3715 |        -0.281805   |        0.695973  | [0.6424828012925509, 0.8789420337466232]   |        1.33517  |      0.0990579 |      0.256258  |
| mlp_train_median_selector                          | 3715 |        -0.436884   |        0.707642  | [0.5155489022753067, 0.7911716816461363]   |        0.621513 |      0.148318  |      0.300135  |
| integral_calibrated                                | 3715 |        -0.510845   |        0.75213   | [0.6363519041048166, 0.7766307311164086]   |        1.37352  |      0.0379542 |      0.0982503 |
| gradient_boosted_trees_train_median_selector       | 3715 |         0.410184   |        0.83483   | [0.7502791660287144, 1.0333058506655985]   |        1.31003  |      0.173351  |      0.351279  |
| adaptive_template_charge                           | 3715 |         0.247562   |        0.97039   | [0.6623625415571477, 4.342774578881235]    |       14.8875   |      0.0963661 |      0.231225  |
| residual_gated_cnn_train_median_selector           | 3715 |        -0.755892   |        0.990036  | [0.9055951211913946, 0.9931269782422739]   |      160.152    |      0.0605653 |      0.153432  |
| peak_calibrated                                    | 3715 |         0.462853   |        1.19107   | [0.8168460167028802, 1.6359925569721696]   |        2.88099  |      0.0656797 |      0.168775  |
| 1d_cnn_train_median_selector                       | 3715 |         0.378905   |        1.28035   | [0.5652826376438885, 1.9174527192100688]   |      448.14     |      0.0896366 |      0.248991  |
| ridge_target_stave_excluded_train_median_selector  | 3715 |         0.183094   |        2.59558   | [0.5968723927981419, 7.168516891406232]    |      788.39     |      0.104711  |      0.23284   |
| shuffled_target_hgb_train_dynamic_selector         | 3715 |        44.8927     |       63.6104    | [52.52063161242522, 69.40690276560092]     |       75.9474   |      0         |      0         |
| shuffled_target_hgb_train_median_selector          | 3715 |        64.0794     |       89.2452    | [74.65192778862054, 95.97898045493294]     |      106.394    |      0         |      0         |

## 4. Externalization Stress Test

The same predictions are scored against the event-external proxy. This is not deposited-energy truth; it is deliberately a harder cross-stave support test that should reject pure same-channel electronics closure if it cannot transfer to another selected B stave.

| method                                             |    n |   bias_median_frac |   res68_abs_frac | res68_abs_frac_ci95                      |   full_rms_frac |   within_10pct |   within_25pct |
|:---------------------------------------------------|-----:|-------------------:|-----------------:|:-----------------------------------------|----------------:|---------------:|---------------:|
| residual_gated_cnn_train_dynamic_selector          | 1113 |         -0.331619  |         0.893642 | [0.8145967723037245, 0.938680323755696]  |         1.19484 |      0.100629  |      0.242588  |
| 1d_cnn_train_dynamic_selector                      | 1113 |         -0.280315  |         0.893794 | [0.7988039705815811, 0.930573395129171]  |         1.23271 |      0.108715  |      0.243486  |
| mlp_train_dynamic_selector                         | 1113 |         -0.355082  |         0.901521 | [0.8242355365733008, 0.943797480229156]  |         1.40554 |      0.100629  |      0.234501  |
| gradient_boosted_trees_train_dynamic_selector      | 1113 |         -0.301082  |         0.902909 | [0.8398577191338414, 0.9373356825706426] |         1.42355 |      0.109614  |      0.226415  |
| ridge_target_stave_excluded_train_dynamic_selector | 1113 |         -0.386805  |         0.905732 | [0.8438200933656331, 0.9449102034364811] |         1.18016 |      0.0772686 |      0.196765  |
| integral_calibrated                                | 1113 |         -0.604632  |         0.937944 | [0.8965535928504519, 0.9588552274526477] |         1.55703 |      0.0377358 |      0.111411  |
| gradient_boosted_trees_train_median_selector       | 1113 |          0.0986341 |         0.946907 | [0.926468989567118, 0.9732622924685728]  |         1.85495 |      0.0745732 |      0.195867  |
| strong_traditional_huber                           | 1113 |         -0.686133  |         0.959061 | [0.9272342175725651, 0.9732064679806044] |         1.26999 |      0.0530099 |      0.130279  |
| mlp_train_median_selector                          | 1113 |         -0.665908  |         0.963346 | [0.9387792942319638, 0.9776771103565797] |         1.20922 |      0.0386343 |      0.109614  |
| 1d_cnn_train_median_selector                       | 1113 |         -0.290793  |         0.973346 | [0.9612494257536887, 1.0329138733888863] |      1440.91    |      0.0539084 |      0.154537  |
| ridge_target_stave_excluded_train_median_selector  | 1113 |         -0.345099  |         0.982059 | [0.9705547018560623, 0.9907591555322118] |      2544.99    |      0.0395328 |      0.116801  |
| adaptive_template_charge                           | 1113 |          0.0105016 |         0.984868 | [0.8716433050411933, 1.841512024877454]  |        18.258   |      0.0637916 |      0.166217  |
| peak_calibrated                                    | 1113 |         -0.393168  |         0.986568 | [0.9601328389024675, 1.5606405081592623] |         2.38326 |      0.0359389 |      0.100629  |
| residual_gated_cnn_train_median_selector           | 1113 |         -0.91043   |         0.99291  | [0.9870436926394961, 0.9967131311551155] |      1243.81    |      0.0260557 |      0.0763702 |
| shuffled_target_hgb_train_dynamic_selector         | 1113 |         30.0985    |        42.6239   | [37.7498976127703, 49.66841739989125]    |        56.5493  |      0.0188679 |      0.0485175 |
| shuffled_target_hgb_train_median_selector          | 1113 |         42.1995    |        60.3169   | [52.753095327736155, 68.2737145621356]   |        79.4497  |      0.0107817 |      0.032345  |

## 5. B2 Versus Non-B2 Support

| support_split   | method                                             |    n |   res68_abs_frac | res68_abs_frac_ci95                        |   within_25pct |
|:----------------|:---------------------------------------------------|-----:|-----------------:|:-------------------------------------------|---------------:|
| B2              | gradient_boosted_trees_train_dynamic_selector      | 2859 |        0.0921366 | [0.0877774122182518, 0.1038523905215995]   |      0.920252  |
| B2              | mlp_train_dynamic_selector                         | 2859 |        0.14341   | [0.12203422068355076, 0.15201940029730887] |      0.874432  |
| B2              | residual_gated_cnn_train_dynamic_selector          | 2859 |        0.195139  | [0.1886162147418416, 0.20944081022959432]  |      0.758657  |
| B2              | 1d_cnn_train_dynamic_selector                      | 2859 |        0.278125  | [0.24432250235948383, 0.29395876349259903] |      0.642183  |
| B2              | ridge_target_stave_excluded_train_dynamic_selector | 2859 |        0.454666  | [0.40293248134551624, 0.4719257471713352]  |      0.388248  |
| B2              | strong_traditional_huber                           | 2859 |        0.633172  | [0.6062792643330474, 0.6579521764823038]   |      0.288213  |
| B2              | adaptive_template_charge                           | 2859 |        0.726136  | [0.6716698924960667, 0.7696179674978688]   |      0.26198   |
| B2              | mlp_train_median_selector                          | 2859 |        0.741477  | [0.4848578322226701, 0.8237628890832485]   |      0.299405  |
| B2              | integral_calibrated                                | 2859 |        0.766468  | [0.6950585740846001, 0.7805076260745444]   |      0.0779993 |
| B2              | gradient_boosted_trees_train_median_selector       | 2859 |        0.78239   | [0.616314734806224, 0.8545536477242432]    |      0.352921  |
| B2              | residual_gated_cnn_train_median_selector           | 2859 |        0.991071  | [0.8317382561507646, 0.9937106918238994]   |      0.155999  |
| B2              | peak_calibrated                                    | 2859 |        1.46531   | [1.2345726650481734, 2.0644860379826775]   |      0.157048  |
| B2              | 1d_cnn_train_median_selector                       | 2859 |        1.5014    | [0.6392348501283367, 2.280427837084176]    |      0.258132  |
| B2              | ridge_target_stave_excluded_train_median_selector  | 2859 |        3.82906   | [0.661278881593593, 9.050224263378615]     |      0.218608  |
| B2              | shuffled_target_hgb_train_dynamic_selector         | 2859 |       64.1231    | [46.97293040621705, 70.35784748154659]     |      0         |
| B2              | shuffled_target_hgb_train_median_selector          | 2859 |       89.6544    | [67.57614429231306, 96.38142062109907]     |      0         |
| non_B2          | gradient_boosted_trees_train_dynamic_selector      |  856 |        0.0736147 | [0.06373709718646098, 0.09306151477384686] |      0.943925  |
| non_B2          | mlp_train_dynamic_selector                         |  856 |        0.136051  | [0.11426969140747797, 0.1726621791541199]  |      0.89486   |
| non_B2          | residual_gated_cnn_train_dynamic_selector          |  856 |        0.146577  | [0.12026035449939881, 0.17754824807400862] |      0.829439  |
| non_B2          | 1d_cnn_train_dynamic_selector                      |  856 |        0.238418  | [0.19936651085561494, 0.2713375279125945]  |      0.691589  |
| non_B2          | ridge_target_stave_excluded_train_dynamic_selector |  856 |        0.451632  | [0.38615601414593725, 0.5264274355309893]  |      0.392523  |
| non_B2          | mlp_train_median_selector                          |  856 |        0.561483  | [0.5059797494338286, 0.6348697595225816]   |      0.30257   |
| non_B2          | 1d_cnn_train_median_selector                       |  856 |        0.609632  | [0.5184299798647812, 0.7736840331575459]   |      0.218458  |
| non_B2          | ridge_target_stave_excluded_train_median_selector  |  856 |        0.626881  | [0.5376670754465835, 1.0699241646969717]   |      0.280374  |
| non_B2          | integral_calibrated                                |  856 |        0.659307  | [0.5597244998220366, 0.7743641876941362]   |      0.165888  |
| non_B2          | peak_calibrated                                    |  856 |        0.82983   | [0.777015523329886, 0.9021894464907285]    |      0.207944  |
| non_B2          | strong_traditional_huber                           |  856 |        0.868312  | [0.8296797727704256, 0.8991636205727317]   |      0.149533  |
| non_B2          | residual_gated_cnn_train_median_selector           |  856 |        0.973043  | [0.9395396647948105, 0.9868319624338965]   |      0.14486   |
| non_B2          | gradient_boosted_trees_train_median_selector       |  856 |        0.979069  | [0.8853147535994065, 1.1604473567704947]   |      0.345794  |
| non_B2          | adaptive_template_charge                           |  856 |        3.25021   | [0.5604429940517105, 13.27668289966386]    |      0.128505  |
| non_B2          | shuffled_target_hgb_train_dynamic_selector         |  856 |       61.7428    | [56.96383678531506, 69.46200768614628]     |      0         |
| non_B2          | shuffled_target_hgb_train_median_selector          |  856 |       86.875     | [79.58199928509606, 98.1084879504969]      |      0         |

## 6. Matched-Control Delta

Dynamic-only rows are not exchangeable with median-selected rows. The control delta therefore compares dynamic-only rows to same-run/same-stave median-selected rows sampled with the same cardinality.

| method                                             |      delta | ci95                                       |   n_pairs |
|:---------------------------------------------------|-----------:|:-------------------------------------------|----------:|
| gradient_boosted_trees_train_dynamic_selector      |  0.0657638 | [0.06079954104873041, 0.07551200632065609] |      3715 |
| mlp_train_dynamic_selector                         |  0.120151  | [0.10280680468490046, 0.12842277219534692] |      3715 |
| residual_gated_cnn_train_dynamic_selector          |  0.164746  | [0.15837700232933413, 0.1729682030681137]  |      3715 |
| 1d_cnn_train_dynamic_selector                      |  0.243935  | [0.2176837521626653, 0.2589618045744087]   |      3715 |
| ridge_target_stave_excluded_train_dynamic_selector |  0.33635   | [0.30573641066895624, 0.3532308837300473]  |      3715 |
| adaptive_template_charge                           |  0.52287   | [0.4563462862922616, 0.7934374470773713]   |      3715 |
| integral_calibrated                                |  0.557176  | [0.48582877247155754, 0.5837991412457033]  |      3715 |
| strong_traditional_huber                           |  0.674144  | [0.6514341355236506, 0.7338299165727141]   |      3715 |
| mlp_train_median_selector                          |  0.689047  | [0.4846227956396049, 0.7710490140123446]   |      3715 |
| gradient_boosted_trees_train_median_selector       |  0.81389   | [0.7424111954920017, 0.8649060595277155]   |      3715 |
| peak_calibrated                                    |  0.908389  | [0.7378729384842223, 1.244189304387184]    |      3715 |
| residual_gated_cnn_train_median_selector           |  0.972374  | [0.8575634208681319, 0.9777687777807973]   |      3715 |
| 1d_cnn_train_median_selector                       |  1.2649    | [0.5930848822342112, 1.8559057195413455]   |      3715 |
| ridge_target_stave_excluded_train_median_selector  |  2.54387   | [0.5722221277981514, 6.74113648878688]     |      3715 |
| shuffled_target_hgb_train_dynamic_selector         | 62.974     | [52.55862364046648, 67.42075410825508]     |      3715 |
| shuffled_target_hgb_train_median_selector          | 88.2419    | [74.08030801300573, 94.53576084022717]     |      3715 |

## 7. Conformal Abstention

| method                                             |   accepted_fraction |   risk_threshold_abs_frac |   res68_abs_frac | res68_abs_frac_ci95                         |   within_25pct |
|:---------------------------------------------------|--------------------:|--------------------------:|-----------------:|:--------------------------------------------|---------------:|
| gradient_boosted_trees_train_dynamic_selector      |            1        |               4.44233     |        0.0877043 | [0.0722007432848301, 0.0947184774083008]    |      0.925707  |
| mlp_train_dynamic_selector                         |            1        |               1.51432     |        0.142278  | [0.12245467941576359, 0.15386081364891735]  |      0.879139  |
| residual_gated_cnn_train_dynamic_selector          |            1        |               2.62162     |        0.184455  | [0.15335611259710025, 0.19607169795579246]  |      0.774966  |
| 1d_cnn_train_dynamic_selector                      |            1        |               3.62612     |        0.268609  | [0.215046987001051, 0.28393491124975]       |      0.653567  |
| ridge_target_stave_excluded_train_dynamic_selector |            1        |              29.5142      |        0.454572  | [0.4163541839293388, 0.4715969786375992]    |      0.389233  |
| strong_traditional_huber                           |            1        |               9.39119     |        0.695973  | [0.6391196136688301, 0.8722858707320174]    |      0.256258  |
| mlp_train_median_selector                          |            1        |               2.75223     |        0.707642  | [0.524430891807911, 0.8033629068985447]     |      0.300135  |
| integral_calibrated                                |            1        |              12.6589      |        0.75213   | [0.647130875718147, 0.7758014912190069]     |      0.0982503 |
| gradient_boosted_trees_train_median_selector       |            1        |               7.89788     |        0.83483   | [0.734140781833233, 1.0335932062808766]     |      0.351279  |
| adaptive_template_charge                           |            1        |             162.29        |        0.97039   | [0.675747023264407, 8.333947308341394]      |      0.231225  |
| residual_gated_cnn_train_median_selector           |            1        |               4.2935e+06  |        0.990036  | [0.9056351323825502, 0.9931625809590975]    |      0.153432  |
| peak_calibrated                                    |            1        |              36.1384      |        1.19107   | [0.8093377075367295, 1.674779622369726]     |      0.168775  |
| 1d_cnn_train_median_selector                       |            1        |               4.2935e+06  |        1.28035   | [0.5920999011121031, 1.8978563741566499]    |      0.248991  |
| ridge_target_stave_excluded_train_median_selector  |            1        |               4.80361e+06 |        2.59558   | [0.5671082795380888, 6.588573282107694]     |      0.23284   |
| shuffled_target_hgb_train_dynamic_selector         |            1        |             248.372       |       63.6104    | [52.26461979589516, 68.31518783460163]      |      0         |
| shuffled_target_hgb_train_median_selector          |            1        |             325.673       |       89.2452    | [73.5797080841772, 95.34371286796879]       |      0         |
| gradient_boosted_trees_train_dynamic_selector      |            0.749933 |               0.111711    |        0.0519564 | [0.04864159343842991, 0.053702027469624644] |      1         |
| mlp_train_dynamic_selector                         |            0.749933 |               0.171149    |        0.0850844 | [0.06795161629437738, 0.09025070840565311]  |      1         |
| residual_gated_cnn_train_dynamic_selector          |            0.749933 |               0.224387    |        0.118953  | [0.09563126528065435, 0.12906490577108126]  |      1         |
| 1d_cnn_train_dynamic_selector                      |            0.749933 |               0.333148    |        0.164643  | [0.14158443210751942, 0.1720733599101963]   |      0.8715    |
| ridge_target_stave_excluded_train_dynamic_selector |            0.749933 |               0.517691    |        0.323698  | [0.28720166980079487, 0.33867922524151495]  |      0.519024  |
| gradient_boosted_trees_train_median_selector       |            0.749933 |               1.13197     |        0.442226  | [0.3656595403916804, 0.48224677246702347]   |      0.468413  |
| mlp_train_median_selector                          |            0.749933 |               0.830395    |        0.494167  | [0.39945607203492667, 0.5346267473170951]   |      0.400215  |
| strong_traditional_huber                           |            0.749933 |               0.816936    |        0.519122  | [0.501566485330448, 0.607247233528269]      |      0.341709  |
| 1d_cnn_train_median_selector                       |            0.749933 |               2.06832     |        0.521821  | [0.46695914120563925, 0.5644506105116514]   |      0.332017  |
| adaptive_template_charge                           |            0.749933 |               1.46591     |        0.5691    | [0.5438989817604658, 0.8180144704918734]    |      0.308327  |
| ridge_target_stave_excluded_train_median_selector  |            0.749933 |               8.76479     |        0.588816  | [0.4797518399062627, 0.6629778360514085]    |      0.310481  |
| integral_calibrated                                |            0.749933 |               0.817789    |        0.609881  | [0.49821027932111667, 0.6336175563332035]   |      0.131012  |
| peak_calibrated                                    |            0.749933 |               1.59399     |        0.762652  | [0.7273039506540724, 0.7925612463828309]    |      0.225054  |
| residual_gated_cnn_train_median_selector           |            0.749933 |               0.994444    |        0.866042  | [0.7411920811506434, 0.9148315384407479]    |      0.204594  |
| shuffled_target_hgb_train_dynamic_selector         |            0.749933 |              76.4535      |       45.777     | [39.81978589089221, 47.64541216616316]      |      0         |
| shuffled_target_hgb_train_median_selector          |            0.749933 |             105.607       |       65.6007    | [56.58142768773223, 68.40722631674309]      |      0         |
| gradient_boosted_trees_train_dynamic_selector      |            0.500135 |               0.050657    |        0.0307657 | [0.027978420714127015, 0.03217197272037143] |      1         |
| mlp_train_dynamic_selector                         |            0.500135 |               0.0828901   |        0.0473699 | [0.04143939163931087, 0.05128282906678811]  |      1         |
| residual_gated_cnn_train_dynamic_selector          |            0.500135 |               0.116055    |        0.0739925 | [0.06716629307402057, 0.07869157497739482]  |      1         |
| 1d_cnn_train_dynamic_selector                      |            0.500135 |               0.160316    |        0.0917287 | [0.08280489785687868, 0.09584138403216272]  |      1         |
| ridge_target_stave_excluded_train_dynamic_selector |            0.500135 |               0.318386    |        0.220222  | [0.2136940789263894, 0.23933131729368068]   |      0.778256  |
| gradient_boosted_trees_train_median_selector       |            0.500135 |               0.424341    |        0.238621  | [0.21684909090671797, 0.25328571045079196]  |      0.702368  |
| mlp_train_median_selector                          |            0.500135 |               0.480919    |        0.296915  | [0.27545450683726763, 0.351698612914958]    |      0.600108  |
| 1d_cnn_train_median_selector                       |            0.500135 |               0.503273    |        0.342312  | [0.31147177567559614, 0.40570457209114685]  |      0.497847  |

## 8. Systematics And Caveats

- The duplicate target is electronics closure, not deposited-charge truth.
- The external proxy is cross-stave event support, not an independent calorimeter or GEANT4 label.
- Dynamic-only rows are selected by baseline/dynamic range semantics and live close to a population boundary.
- Held-out support is limited to runs 57 and 65, so run/stave-block CIs are intentionally conservative but not a replacement for more beam configurations.
- Neural models are capped by train-row budgets for reproducibility; failure to beat the external proxy should be interpreted as a null for this support, not a universal architecture theorem.
- Shuffled-target sentinels and target-stave-excluded ridge are included to catch leakage and stave-identity shortcuts.

## 9. Finding

The duplicate-readout dynamic-only winner is gradient_boosted_trees_train_dynamic_selector with res68=0.0877 (95% run/stave-block CI [0.06934370243307625, 0.09511998389914317]). Its external-proxy res68 is 0.9029, so the strong duplicate closure does not externalize to cross-stave charge support. The real-minus-shuffled duplicate separation is -63.5227; this supports a real electronics-closure signal, but not a deposited-charge truth claim.

## Reproducibility

```bash
python3 scripts/p04x_1781081173_700_0ebd3bf2_dynamic_externalization_null.py --config configs/p04x_1781081173_700_0ebd3bf2_dynamic_externalization_null.json
```
