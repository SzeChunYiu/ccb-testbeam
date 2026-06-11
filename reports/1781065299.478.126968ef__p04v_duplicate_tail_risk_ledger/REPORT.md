# P04v duplicate-closure tail-risk ledger

Ticket `1781065299.478.126968ef` asks whether the small duplicate-readout central resolution hides rare charge tails before the duplicate closure is reused by saturation, PID, or energy studies.  The analysis is intentionally ROOT-first: the selected B-stave pulse population is rebuilt from `data/root/root/hrdb_run_*.root`, then every calibrator is trained without held-out runs `[57, 65]`.

## Raw reproduction

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| B-stack selected pulses with even amplitude > 1000 ADC | 640,737 | 640,737 | +0 | true |

## Estimands and notation

For selected pulse i, y_i is the positive odd duplicate-readout charge and x_i contains only even-readout waveform information.  Each method estimates \hat{y}_i = f(x_i) on held-out runs.  The fractional residual is

\[ r_i = (\hat{y}_i-y_i)/\max(y_i,1). \]

The central charge resolution is q_0.68(|r|), the full RMS is sqrt(E[r^2]), and charge-tail rates are P(|r|>0.10) and P(|r|>0.25).  Confidence intervals are percentile bootstraps; pooled rows use event resampling plus a run-block bootstrap over held-out runs, while atom rows resample events inside the atom.

## Methods

- **Frozen traditional baselines:** per-stave log-linear peak calibration, per-stave integral calibration, and an adaptive-template scale calibration built from train-only normalized median templates.
- **Strong traditional method:** per-stave Huber log-charge calibration on even summaries plus a train-only residual basis: normalized waveform PCs by stave/amplitude bin, peak-anchor residual, baseline moments, and tail moments.
- **ML and NN bakeoff:** ridge on the same strong-traditional feature set, histogram gradient-boosted trees, ExtraTrees, an MLP, a 1D-CNN over normalized waveforms, and a new residual-gated CNN that gates convolutional pulse features with the residual-basis/tabular branch.
- **Tail-risk layer:** ExtraTrees and HGB classifiers predict whether the winning model has |r|>0.10; a permuted-target sentinel and HGB feature-family knockouts probe leakage and atom dependence.

All tabular and neural features exclude run number, event number, and odd-channel target values.  Run labels are used only for splitting, bootstrapping, and reporting.

## Head-to-head charge benchmark

| method                   |     n |   charge_res68_abs_frac | run_block_charge_res68_ci95                  |   full_rms_frac |   tail_gt10_frac | tail_gt10_ci95                              |   tail_gt25_frac |   heldout_conformal_coverage |
|:-------------------------|------:|------------------------:|:---------------------------------------------|----------------:|-----------------:|:--------------------------------------------|-----------------:|-----------------------------:|
| extra_trees_regressor    | 26857 |              0.00469304 | [0.004620155846228424, 0.004781401110497678] |       0.0388965 |        0.0195107 | [0.01787243549167815, 0.021149048665152475] |       0.00346278 |                     0.921883 |
| strong_traditional_huber | 26857 |              0.0130532  | [0.012829166532866363, 0.013266521755885987] |       0.337888  |        0.0934207 | [0.08984622258629035, 0.09669732285810032]  |       0.0577875  |                     0.920914 |
| hgb_regressor            | 26857 |              0.0143332  | [0.014249657848848024, 0.014404104271007096] |       0.0481147 |        0.031798  | [0.02985999925531519, 0.034071191868041854] |       0.00431917 |                     0.928175 |
| ridge_residual_basis     | 26857 |              0.0365312  | [0.03597231621398551, 0.03713160253163381]   |       0.206694  |        0.137506  | [0.13359645530029415, 0.141695833488476]    |       0.0589418  |                     0.919611 |
| mlp_regressor            | 26857 |              0.0395404  | [0.037388249029401154, 0.0415897007512753]   |       1.24917   |        0.0759951 | [0.07294001563838107, 0.07929124623003314]  |       0.0141862  |                     0.929143 |
| residual_gated_cnn       | 26857 |              0.0972638  | [0.08425518957561381, 0.1069567982140111]    |       0.40269   |        0.302975  | [0.2971608891536657, 0.308411214953271]     |       0.0393194  |                     0.932569 |
| cnn1d                    | 26857 |              0.152246   | [0.11260585585191002, 0.21356487926676296]   |       2.73913   |        0.405593  | [0.3994116989983989, 0.4115714711248464]    |       0.242842   |                     0.89392  |
| integral_log_calibrated  | 26857 |              0.195415   | [0.16416378693423161, 0.21526713689001523]   |       1.66374   |        0.596679  | [0.5908329299623934, 0.6026557322113415]    |       0.202182   |                     0.923968 |
| peak_log_calibrated      | 26857 |              0.280162   | [0.26343192936017484, 0.305710222738322]     |       2.57878   |        0.870872  | [0.8667014186245672, 0.8748752652939643]    |       0.440593   |                     0.92326  |
| adaptive_template_scale  | 26857 |              0.564398   | [0.3999624144286479, 0.7161720752152709]     |       1.96918   |        0.820121  | [0.815913914435715, 0.8247384294597312]     |       0.489854   |                     0.904978 |

The winner by charge res68 is `extra_trees_regressor`.  The strong traditional reference for tail deltas is `strong_traditional_huber`.

## Split-by-run check

| method                   |   run |     n |   charge_res68_abs_frac | charge_res68_ci95                             |   tail_gt10_frac |   tail_gt25_frac |
|:-------------------------|------:|------:|------------------------:|:----------------------------------------------|-----------------:|-----------------:|
| strong_traditional_huber |    57 | 13819 |              0.0132673  | [0.012815257534464225, 0.013722233489495165]  |        0.106013  |       0.0662855  |
| strong_traditional_huber |    65 | 13038 |              0.0128294  | [0.012468940138459348, 0.013257222106085586]  |        0.0800736 |       0.0487805  |
| ridge_residual_basis     |    57 | 13819 |              0.0371322  | [0.036061069199442866, 0.03838283628311611]   |        0.14936   |       0.0671539  |
| ridge_residual_basis     |    65 | 13038 |              0.0359778  | [0.03503973006021961, 0.036834978730403686]   |        0.124942  |       0.0502378  |
| hgb_regressor            |    57 | 13819 |              0.01425    | [0.013931780197946489, 0.01458938658167747]   |        0.0363992 |       0.00535495 |
| hgb_regressor            |    65 | 13038 |              0.0144041  | [0.014066838695818965, 0.014807826098602867]  |        0.0269213 |       0.00322135 |
| extra_trees_regressor    |    57 | 13819 |              0.00478142 | [0.0046286397647540296, 0.004908277194967215] |        0.0224329 |       0.00470367 |
| extra_trees_regressor    |    65 | 13038 |              0.0046203  | [0.00447235431236417, 0.004769860063567178]   |        0.0164136 |       0.00214757 |
| mlp_regressor            |    57 | 13819 |              0.0373886  | [0.03639152739310514, 0.03837616704691151]    |        0.08387   |       0.0169332  |
| mlp_regressor            |    65 | 13038 |              0.0415899  | [0.04078812795908739, 0.0423781245145027]     |        0.0676484 |       0.0112747  |
| cnn1d                    |    57 | 13819 |              0.112609   | [0.10800242549939809, 0.11526868122927768]    |        0.344598  |       0.193068   |
| cnn1d                    |    65 | 13038 |              0.213579   | [0.20179821307573395, 0.22561840515363316]    |        0.470241  |       0.295597   |
| residual_gated_cnn       |    57 | 13819 |              0.106957   | [0.10593833441746, 0.10792077004796218]       |        0.373761  |       0.0443592  |
| residual_gated_cnn       |    65 | 13038 |              0.0842558  | [0.08299825185053814, 0.08557218198781746]    |        0.227949  |       0.0339776  |

## Tail-risk classifier and conformal support

| model                                 |   heldout_auc |   heldout_positive_rate |   risk_threshold_train_negative_q95 |   accepted_support_fraction |   accepted_tail_gt10_rate |   rejected_tail_gt10_rate |
|:--------------------------------------|--------------:|------------------------:|------------------------------------:|----------------------------:|--------------------------:|--------------------------:|
| extra_trees_tail_risk                 |      0.983929 |               0.0195107 |                           0.0187281 |                    0.907138 |               0.000369413 |                  0.206496 |
| hgb_tail_risk                         |      0.978415 |               0.0195107 |                           0.0184361 |                    0.908515 |               0.00110656  |                  0.202279 |
| permuted_target_extra_trees_tail_risk |      0.502037 |               0.0195107 |                         nan         |                  nan        |             nan           |                nan        |

## Feature-family knockouts

| removed_family   |   charge_res68_abs_frac |   full_rms_frac |   tail_gt10_frac |   tail_gt25_frac |
|:-----------------|------------------------:|----------------:|-----------------:|-----------------:|
| waveform         |               0.0206775 |       0.0756411 |        0.0600588 |       0.0142235  |
| shape            |               0.0652273 |       0.126971  |        0.214618  |       0.040064   |
| residual_basis   |               0.0193421 |       0.0687482 |        0.0496332 |       0.00964367 |
| stave            |               0.0190251 |       0.0605245 |        0.0469524 |       0.00886175 |
| atoms            |               0.0189571 |       0.0616252 |        0.047846  |       0.00942026 |

## Atomized tail ledger

| axis            | atom               |     n |   charge_res68_abs_frac |   full_rms_frac |   tail_gt10_frac | tail_gt10_ci95                                |   tail_gt25_frac |   ml_minus_traditional_tail_gt10_delta | ml_minus_traditional_tail_gt10_delta_ci95       |
|:----------------|:-------------------|------:|------------------------:|----------------:|-----------------:|:----------------------------------------------|-----------------:|---------------------------------------:|:------------------------------------------------|
| peak_phase      | 0                  |   337 |              0.0571882  |       0.132651  |       0.189911   | [0.14977744807121662, 0.2314540059347181]     |      0.0712166   |                            -0.700297   | [-0.7493323442136498, -0.6468842729970327]      |
| anomaly_atom    | anomalous_residual |  1240 |              0.0695898  |       0.134967  |       0.212903   | [0.19032258064516128, 0.23590725806451612]    |      0.0467742   |                            -0.684677   | [-0.714133064516129, -0.6552217741935484]       |
| peak_phase      | 1                  |   102 |              0.0466546  |       0.127462  |       0.107843   | [0.049019607843137254, 0.16666666666666666]   |      0.0392157   |                            -0.803922   | [-0.8823529411764706, -0.7254901960784313]      |
| dropout_atom    | dropout_like       |  1556 |              0.0651732  |       0.121958  |       0.193445   | [0.17352185089974292, 0.21499035989717222]    |      0.0366324   |                            -0.594473   | [-0.6221079691516709, -0.5652152956298201]      |
| pretrigger_atom | pretrigger_noisy   |  1328 |              0.0493179  |       0.120874  |       0.128765   | [0.11069277108433735, 0.1460843373493976]     |      0.0248494   |                            -0.671687   | [-0.701449548192771, -0.6453313253012047]       |
| peak_phase      | 2                  |   241 |              0.048917   |       0.0800008 |       0.128631   | [0.08910788381742739, 0.16815352697095426]    |      0.0207469   |                            -0.767635   | [-0.8215767634854773, -0.7095435684647302]      |
| peak_phase      | 15                 |   128 |              0.010668   |       0.0805468 |       0.0234375  | [0.0, 0.0546875]                              |      0.015625    |                            -0.0078125  | [-0.0390625, 0.015625]                          |
| peak_phase      | 4                  |   987 |              0.0285491  |       0.0824678 |       0.070922   | [0.05572441742654509, 0.08713272543059777]    |      0.0151976   |                            -0.37386    | [-0.40580040526849037, -0.3404255319148936]     |
| peak_phase      | 3                  |   732 |              0.0583004  |       0.0899966 |       0.155738   | [0.12978142076502733, 0.18442622950819673]    |      0.0150273   |                            -0.740437   | [-0.7739412568306011, -0.7035519125683061]      |
| q_template      | 1000_1500          |  3042 |              0.0132889  |       0.0638367 |       0.0644313  | [0.05621301775147929, 0.07297830374753451]    |      0.0128205   |                            -0.171598   | [-0.1863905325443787, -0.1576183431952663]      |
| peak_phase      | 10                 |   266 |              0.00513734 |       0.0437809 |       0.0150376  | [0.0037593984962406013, 0.03007518796992481]  |      0.0112782   |                             0          | [-0.018796992481203006, 0.018796992481203006]   |
| peak_phase      | 13                 |   139 |              0.00989803 |       0.0741022 |       0.0143885  | [0.0, 0.03597122302158273]                    |      0.00719424  |                            -0.0503597  | [-0.08633093525179857, -0.021582733812949638]   |
| peak_phase      | 17                 |   427 |              0.032238   |       0.0603488 |       0.0819672  | [0.05731850117096019, 0.11129976580796247]    |      0.00702576  |                            -0.400468   | [-0.4473067915690867, -0.351288056206089]       |
| peak_phase      | 11                 |   154 |              0.00812422 |       0.0263531 |       0.012987   | [0.0, 0.032467532467532464]                   |      0.00649351  |                            -0.025974   | [-0.06493506493506493, 0.012987012987012986]    |
| saturation      | saturated          |   334 |              0.00431025 |       0.107174  |       0.00898204 | [0.0, 0.020958083832335328]                   |      0.00598802  |                            -0.0449102  | [-0.06886227544910178, -0.023952095808383235]   |
| q_template      | 9000_inf           |   334 |              0.00431025 |       0.107174  |       0.00898204 | [0.0, 0.020958083832335328]                   |      0.00598802  |                            -0.0449102  | [-0.06744011976047903, -0.020958083832335328]   |
| run             | 57                 | 13819 |              0.00478142 |       0.0442574 |       0.0224329  | [0.019972501628193067, 0.024893262898907302]  |      0.00470367  |                            -0.0835806  | [-0.08842897460018814, -0.07844272378609161]    |
| stave           | B4                 |  1498 |              0.0093753  |       0.0434167 |       0.0246996  | [0.016688918558077435, 0.03271028037383177]   |      0.0046729   |                            -0.0674232  | [-0.08179238985313751, -0.05372162883845128]    |
| q_template      | 1500_2000          |  2512 |              0.00833228 |       0.0410174 |       0.031051   | [0.024681528662420384, 0.037818471337579616]  |      0.00437898  |                            -0.121815   | [-0.1337579617834395, -0.10788216560509553]     |
| q_template      | 2000_3000          |  5153 |              0.00571486 |       0.0412566 |       0.0223171  | [0.018333980205705414, 0.02619833106928003]   |      0.00388123  |                            -0.0694741  | [-0.07675625849019989, -0.062293809431399186]   |
| stave           | B2                 | 24528 |              0.00438508 |       0.0389081 |       0.0193249  | [0.01761252446183953, 0.021058586105675146]   |      0.0035062   |                            -0.0745271  | [-0.07787222765818656, -0.07116254892367906]    |
| saturation      | not_saturated      | 26523 |              0.00469802 |       0.0372471 |       0.0196433  | [0.01811540926742827, 0.02139746634996041]    |      0.00343098  |                            -0.0742752  | [-0.07797006371828225, -0.07074331712098933]    |
| peak_phase      | 5                  |  2255 |              0.00757197 |       0.0583795 |       0.016408   | [0.011086474501108648, 0.021729490022172948]  |      0.00310421  |                            -0.0203991  | [-0.028824833702882482, -0.01286031042128603]   |
| pretrigger_atom | quiet_pretrigger   | 25529 |              0.00420249 |       0.0288378 |       0.0138274  | [0.012534764385600689, 0.01537565122018097]   |      0.00235027  |                            -0.0428141  | [-0.04551882173214775, -0.04022875945003721]    |
| run             | 65                 | 13038 |              0.0046203  |       0.0322562 |       0.0164136  | [0.014072327044025158, 0.018867924528301886]  |      0.00214757  |                            -0.0636601  | [-0.06784207700567572, -0.0594013652400675]     |
| q_template      | 3000_4000          |  5586 |              0.0039479  |       0.0358428 |       0.0105621  | [0.007876834944504118, 0.013341389187253845]  |      0.00179019  |                            -0.0578231  | [-0.06390977443609022, -0.05137844611528822]    |
| peak_phase      | 9                  |   595 |              0.00646619 |       0.0239339 |       0.00840336 | [0.0016806722689075631, 0.01680672268907563]  |      0.00168067  |                            -0.0134454  | [-0.025210084033613446, -0.0016806722689075623] |
| q_template      | 7000_9000          |  1965 |              0.00354786 |       0.0229094 |       0.00712468 | [0.0035623409669211198, 0.011195928753180661] |      0.00152672  |                            -0.0580153  | [-0.06846055979643766, -0.04783715012722646]    |
| dropout_atom    | ordinary_tail      | 25301 |              0.00407926 |       0.0262917 |       0.00881388 | [0.007667681119323347, 0.009960080629224141]  |      0.00142287  |                            -0.0418956  | [-0.0445851942610964, -0.03924746057468084]     |
| anomaly_atom    | ordinary_residual  | 25617 |              0.00420238 |       0.0265409 |       0.0101495  | [0.008957918569699809, 0.011398680563688176]  |      0.00136628  |                            -0.0443456  | [-0.04711714876839599, -0.04165007612132569]    |
| peak_phase      | 6                  |  6286 |              0.00284996 |       0.0207449 |       0.0087496  | [0.006522430798600064, 0.011294941139039135]  |      0.00111359  |                            -0.0187719  | [-0.02235523385300668, -0.01511294941139039]    |
| q_template      | 5500_7000          |  3054 |              0.0025358  |       0.0189479 |       0.00851343 | [0.005239030779305829, 0.011787819253438114]  |      0.000982318 |                            -0.0353635  | [-0.04223968565815324, -0.028814669286182055]   |
| q_template      | 4000_5500          |  5211 |              0.0028608  |       0.0200688 |       0.00633276 | [0.00422183841872961, 0.00844367683745922]    |      0.000959509 |                            -0.0458645  | [-0.05229802341201305, -0.0401986183074266]     |
| peak_phase      | 7                  |  8237 |              0.00271694 |       0.0186373 |       0.00667719 | [0.004977540366638339, 0.00849823965035814]   |      0.000849824 |                            -0.0169965  | [-0.020031564890129902, -0.01401906033750152]   |
| peak_phase      | 8                  |  5542 |              0.00419209 |       0.014083  |       0.00469145 | [0.003067484662576687, 0.006495849873691808]  |      0.000360881 |                            -0.00992422 | [-0.012991699747383614, -0.006856730422230242]  |
| peak_phase      | 14                 |   121 |              0.0127574  |       0.0425715 |       0.0495868  | [0.01652892561983471, 0.09090909090909091]    |      0           |                             0          | [-0.049586776859504134, 0.04132231404958678]    |

## Leakage and systematics checks

| check                                 | value                                                                               | pass   |
|:--------------------------------------|:------------------------------------------------------------------------------------|:-------|
| raw_selected_pulse_reproduction       | 640737                                                                              | True   |
| train_heldout_run_overlap             | 0                                                                                   | True   |
| train_heldout_event_stave_key_overlap | 0                                                                                   | True   |
| exact_even_waveform_hash_overlap      | 0                                                                                   | True   |
| features_exclude_run_event_odd_target | even waveform, even summaries, train-only residual basis, stave one-hot, atom flags | True   |
| permuted_tail_risk_auc_near_random    | 0.5020372878427585                                                                  | True   |
| torch_available_for_cnn               | True                                                                                | True   |

The largest systematic limitation is that duplicate closure remains a same-scintillator, two-readout proxy, not an external calorimetric truth.  The train/test split prevents run leakage, and the shuffled-target/risk sentinels reject memorization at the model-family level, but residual tails can still encode detector-specific behavior that may not transfer to a different geometry, range-energy observable, or PID selection.  The run-block intervals are intentionally shown because event-only intervals understate uncertainty when only two runs are held out.

## Finding

The charge-closure winner is extra_trees_regressor with res68=0.0047, full RMS=0.0389, tail10=0.0195, and tail25=0.0035.  The strong traditional Huber residual-basis reference gives res68=0.0131 and tail10=0.0934; HGB gives res68=0.0143, the plain 1D-CNN gives 0.1522, and the residual-gated CNN gives 0.0973.  The largest held-out tail25 atom is peak_phase=0 (n=337, tail25=0.0712).  Therefore P04f-like central closure does hide localized charge-tail risk; reuse should require the atom ledger or conformal support filter rather than only a central res68 threshold.

## Reproducibility

```bash
/home/billy/.tb-workers/testbeam-laptop-1/.venv/bin/python scripts/p04v_1781065299_478_126968ef_duplicate_tail_risk_ledger.py --config configs/p04v_1781065299_478_126968ef_duplicate_tail_risk_ledger.json
```
