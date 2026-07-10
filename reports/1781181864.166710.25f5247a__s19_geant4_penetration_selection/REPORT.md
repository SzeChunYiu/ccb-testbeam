# S19 Geant4 sim-vs-data penetration and EDep selection closure

Ticket `1781181864.166710.25f5247a` asks whether Geant4 truth reproduces the CCB HRD B-stack penetration profile once the data A>1000 ADC selection is matched. The analysis was run directly from raw `h101/HRDv` under `data/root/root` for documented Sample-I/II B-stack runs `[31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65]` and `Sci_bar` truth in `/home/billy/ccb-geant4/output_krakow_1M.root`.

## Methods

For each raw HRD event, the waveform tensor is reshaped to `(event, channel, sample)`. The analysed B-stack physical channels are `(B2,B4,B6,B8)=(0,2,4,6)`. The baseline is `b_{e,s}=median_{j=0..3} V_{e,s,j}`, the amplitude is `A_{e,s}=max_j(V_{e,s,j}-b_{e,s})`, and a selected pulse satisfies `A_{e,s}>1000 ADC`. Event penetration is the deepest selected stave.

In simulation, B-stack hits are selected by `Sci_bar_LayerID1=1`; the natural analysed-stave mapping is `(B2,B4,B6,B8)=(LayerID 0,2,4,6)`. For threshold `tau`, event-layer energy is `E_{e,l}=sum_i EDep_i 1(LayerID_i=l)`, a layer is hit when `E_{e,l}>tau`, and simulated penetration is the deepest hit analysed layer. Data uncertainty is a non-parametric bootstrap over runs. Simulation uncertainty is a bootstrap over 100 contiguous entry blocks.

## Raw-data reproduction gate

| quantity                              | expected | observed | delta |
| ------------------------------------- | -------- | -------- | ----- |
| selected B-stave pulse records        | 640737   | 640737   | 0     |
| Sample I analysis B2 selected pulses  | 241422   | 241422   | 0     |
| Sample II analysis B4 selected pulses | 21229    | 21229    | 0     |
| Sample II analysis B6 selected pulses | 11148    | 11148    | 0     |
| Sample II analysis B8 selected pulses | 4506     | 4506     | 0     |

The gate reproduces the documented S00 selected-pulse total and spot checks exactly.

## Data penetration profile

| source | threshold_MeV | stave | deepest_fraction     | ci95                                        |
| ------ | ------------- | ----- | -------------------- | ------------------------------------------- |
| data   | nan           | B2    | 0.9304330125452872   | [0.8943016660825558, 0.9563717186426904]    |
| data   | nan           | B4    | 0.03621438175031902  | [0.023562925107335653, 0.05345600428816644] |
| data   | nan           | B6    | 0.020947584852600572 | [0.01271622490146284, 0.032714147513779344] |
| data   | nan           | B8    | 0.012405020851793186 | [0.007094190953361517, 0.020139026948233]   |

## Simulation threshold scan

| threshold_MeV | sim_B8_over_B2       | sim_B8_over_B2_ci95                          | data_B8_over_B2      | data_B8_over_B2_ci95                         | ratio_gap_sim_over_data | ratio_gap_sim_over_data_ci95            |
| ------------- | -------------------- | -------------------------------------------- | -------------------- | -------------------------------------------- | ----------------------- | --------------------------------------- |
| 50.0          | 0.008593495050581965 | [0.007637081553757578, 0.009587232561580044] | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 0.6445512332250689      | [0.3825970295502876, 1.189361369134437] |
| 40.0          | 0.11695952306244117  | [0.11430900369967235, 0.11962099318861207]   | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 8.772496450347878       | [5.27934619753047, 15.877256305891734]  |
| 30.0          | 0.22218678956085217  | [0.2187467913639951, 0.2255581810463605]     | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 16.66502027112562       | [9.912987077305502, 30.212642020407714] |
| 25.0          | 0.29003971891231284  | [0.2861738901384281, 0.29372679203526403]    | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 21.754298735125627      | [12.906427840145557, 39.09586736224079] |
| 20.0          | 0.3375360125006104   | [0.33345658807682504, 0.3414310400876825]    | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 25.31673688465175       | [15.286254338132666, 45.46681987852202] |
| 15.0          | 0.5379679144385027   | [0.5327261771391081, 0.5431020404672164]     | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 40.35004158911722       | [24.20078702300995, 72.24420951823075]  |
| 10.0          | 0.539435465852387    | [0.5344115457638079, 0.5445961049688804]     | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 40.46011462320551       | [23.818355470391708, 73.1430499597352]  |
| 5.0           | 0.55506436094136     | [0.5497815743419909, 0.5604125830569519]     | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 41.63235287367854       | [24.658189641316852, 73.84980488121653] |
| 2.0           | 0.562514510721682    | [0.5570154658574485, 0.5679110065227643]     | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 42.191148008877086      | [25.04166755641133, 75.96023744201553]  |
| 1.0           | 0.5668643349872927   | [0.5615848382545998, 0.5724915366376123]     | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 42.517404622537654      | [25.595658141278275, 76.24600530216317] |
| 0.0           | 0.5788835407814087   | [0.5733246589591072, 0.5843869004799392]     | 0.013332524410175519 | [0.007421140291036791, 0.022505252975974072] | 43.41889975011775       | [26.095622632062394, 80.57906533675252] |

The best threshold in this discrete scan by B8/B2 closure is `50.0 MeV`; there the simulated B8/B2 penetration ratio is 0.00859 versus 0.0133 in data, leaving a 0.64x ratio gap on this scalar diagnostic.

## Simulation penetration profile at best threshold

| source | threshold_MeV | stave | deepest_fraction     | ci95                                          |
| ------ | ------------- | ----- | -------------------- | --------------------------------------------- |
| sim    | 50.0          | B2    | 0.7714027984644108   | [0.7676013682904531, 0.775159951348728]       |
| sim    | 50.0          | B4    | 0.20407392645115274  | [0.20024871601946478, 0.20788902849176494]    |
| sim    | 50.0          | B6    | 0.017894228953827435 | [0.016823120576948018, 0.01893892274847176]   |
| sim    | 50.0          | B8    | 0.006629046130608991 | [0.005893137593069865, 0.0073620410475879645] |

## Per-layer EDep profile

| stave | hit_events | edep_sum_MeV       | edep_mean_MeV      |
| ----- | ---------- | ------------------ | ------------------ |
| B2    | 237122     | 6674567.424757     | 28.148306010370344 |
| B4    | 130089     | 2917493.0845308127 | 22.42608949005012  |
| B6    | 87628      | 1707982.183090477  | 19.490362886120025 |
| B8    | 61577      | 1575630.2631418374 | 25.589948326837483 |

## Systematics and caveats

- The ADC-to-MeV relation is not known event by event; the EDep threshold scan is an emulation of `A>1000 ADC`, not a calibrated digitization.
- The LayerID mapping uses the established even-layer convention from the repository docs. A detector construction map would reduce this geometry systematic.
- Simulation has no run labels, so its bootstrap uses contiguous entry blocks rather than true run splits.
- The raw-data selected pulse count is a pulse-level count; the penetration profile is event-level deepest selected stave, so both are reported separately.

## Conclusion

Selection thresholding explains most of the B8/B2 scalar discrepancy only at a high 50 MeV truth-EDep threshold. Because this is an uncalibrated truth-level threshold rather than detector digitization, and because the full layer profile must be checked beyond one scalar ratio, the conservative S19 answer is **partial closure only**: raw Geant4 truth is too penetrating, while a high EDep selection can make the deepest-layer ratio numerically close to data.
