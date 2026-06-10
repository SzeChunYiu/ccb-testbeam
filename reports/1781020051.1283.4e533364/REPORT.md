# S14c: saturation-corrected charge proxy energy ordering

- **Ticket ID:** 1781020051.1283.4e533364
- **Worker:** testbeam-laptop-2
- **Input:** raw `data/root/root/hrdb_run_*.root`; no Monte Carlo and no PID truth labels.
- **Split:** calibration/training runs are held out from analysis runs; CIs resample held-out run/depth-stave blocks.

## Raw reproduction gate

The first operation rebuilds selected B-stack pulses from `HRDv` using median samples 0..3 as the baseline and `A > 1000 ADC` on B2/B4/B6/B8.

| quantity | expected | reproduced | delta | pass |
|---|---:|---:|---:|:---|
| S00 selected B-stave pulse records | 640,737 | 640,737 | +0 | true |

## Methods

- **Observed even charge:** no saturation recovery; train-only log calibration to the paired odd duplicate readout.
- **Traditional saturated-excluded:** same observed charge but the primary control metrics are restricted to events without saturated selected pulses.
- **Traditional rising-edge template:** per-stave train-run templates recover saturated pulse amplitude from unclipped rising-edge samples, then convert recovered amplitude to charge.
- **ML P07/P04 corrected:** a P07b-style multi-ceiling ratio regressor is frozen on artificial clips from train runs, then a P04 duplicate-readout charge model predicts paired odd charge from even-channel waveform features only. Run, event, depth, PID, and odd samples are excluded from ML features.

PSTAR geometry is used only to define a monotonic depth-order envelope. It is not an absolute energy calibration.

## Nominal Head-to-Head

| method                         |      n |   n_saturated |   unsat_charge_bias_frac |   unsat_charge_res68_frac | unsat_charge_res68_ci95                     |   energy_proxy_res68_frac | energy_res68_ci95                            |   depth_order_violation_rate |   sat_minus_unsat_log_charge_delta | sat_minus_unsat_log_delta_ci95           |
|:-------------------------------|-------:|--------------:|-------------------------:|--------------------------:|:--------------------------------------------|--------------------------:|:---------------------------------------------|-----------------------------:|-----------------------------------:|:-----------------------------------------|
| observed_even_charge           | 332852 |        106217 |              -0.0496027  |                 0.139902  | [0.10613142713012962, 0.17484438825009535]  |                 0.0211892 | [0.019811619505209425, 0.022508958792442694] |                            0 |                           0.824709 | [0.7621722914503211, 0.9047631133946441] |
| traditional_saturated_excluded | 226635 |             0 |              -0.0496027  |                 0.139902  | [0.10945327577050513, 0.17287389023717378]  |                 0.0212946 | [0.0202678506881304, 0.022370314432876893]   |                            0 |                         nan        | [None, None]                             |
| traditional_template_corrected | 332852 |        106217 |              -0.0496027  |                 0.139902  | [0.10945327577050513, 0.17287389023717378]  |                 0.0288937 | [0.024777722320676814, 0.034959602398529716] |                            0 |                           1.12029  | [1.0509002705221604, 1.1832062865281376] |
| ml_p07_p04_corrected           | 332852 |        106217 |               0.00261642 |                 0.0663344 | [0.057907795384980185, 0.07682608010177744] |                 0.0145485 | [0.014165571606790666, 0.015005129327745377] |                            0 |                           0.919225 | [0.8541846718989742, 0.9950396186575234] |

## Held-out Run Checks

|   run | method                         |     n |   n_saturated |   unsat_charge_res68_frac |   energy_proxy_res68_frac |   depth_order_violation_rate |   sat_minus_unsat_log_charge_delta |
|------:|:-------------------------------|------:|--------------:|--------------------------:|--------------------------:|-----------------------------:|-----------------------------------:|
|    44 | traditional_template_corrected |  1911 |           334 |                 0.168475  |                 0.0242777 |                            0 |                           1.43299  |
|    45 | traditional_template_corrected | 22999 |          5472 |                 0.160306  |                 0.0256275 |                            0 |                           1.25452  |
|    46 | traditional_template_corrected |   676 |           144 |                 0.136139  |                 0.0234844 |                            0 |                           1.1565   |
|    47 | traditional_template_corrected |  5160 |          1268 |                 0.133459  |                 0.0238392 |                            0 |                           1.66042  |
|    48 | traditional_template_corrected | 13175 |          1991 |                 0.167925  |                 0.023645  |                            0 |                           1.27117  |
|    49 | traditional_template_corrected | 13921 |          2154 |                 0.168553  |                 0.0237072 |                            0 |                           1.29614  |
|    50 | traditional_template_corrected | 34254 |         19492 |                 0.0618891 |                 0.0490012 |                            0 |                           1.12348  |
|    51 | traditional_template_corrected | 14294 |          7248 |                 0.0805657 |                 0.0445427 |                            0 |                           1.1786   |
|    52 | traditional_template_corrected |  6933 |          3625 |                 0.0802622 |                 0.0465261 |                            0 |                           1.0267   |
|    53 | traditional_template_corrected | 31382 |         13961 |                 0.0464496 |                 0.0348055 |                            0 |                           1.09847  |
|    54 | traditional_template_corrected | 29664 |         13282 |                 0.0465494 |                 0.0351533 |                            0 |                           1.0882   |
|    55 | traditional_template_corrected | 16836 |          8330 |                 0.0800971 |                 0.0440234 |                            0 |                           1.12975  |
|    56 | traditional_template_corrected | 38925 |         21645 |                 0.0681204 |                 0.0498034 |                            0 |                           1.1288   |
|    57 | traditional_template_corrected | 12928 |          1843 |                 0.166926  |                 0.0233956 |                            0 |                           1.25905  |
|    58 | traditional_template_corrected | 15919 |          1618 |                 0.136619  |                 0.0221992 |                            0 |                           1.06593  |
|    59 | traditional_template_corrected | 13861 |           809 |                 0.224977  |                 0.0250197 |                            0 |                           0.936347 |
|    60 | traditional_template_corrected | 10133 |           382 |                 0.215357  |                 0.0246428 |                            0 |                           0.70894  |
|    61 | traditional_template_corrected | 11287 |           420 |                 0.20226   |                 0.0247991 |                            0 |                           0.915316 |
|    62 | traditional_template_corrected | 11911 |           513 |                 0.215431  |                 0.0245604 |                            0 |                           0.8602   |
|    63 | traditional_template_corrected | 14779 |          1232 |                 0.196143  |                 0.0241507 |                            0 |                           0.942684 |
|    65 | traditional_template_corrected | 11904 |           454 |                 0.216844  |                 0.0240323 |                            0 |                           1.20135  |
|    44 | ml_p07_p04_corrected           |  1911 |           334 |                 0.0770486 |                 0.0148624 |                            0 |                           1.07517  |
|    45 | ml_p07_p04_corrected           | 22999 |          5472 |                 0.074006  |                 0.0148142 |                            0 |                           1.07488  |
|    46 | ml_p07_p04_corrected           |   676 |           144 |                 0.0625952 |                 0.0133889 |                            0 |                           0.944611 |
|    47 | ml_p07_p04_corrected           |  5160 |          1268 |                 0.0619136 |                 0.0129407 |                            0 |                           1.41903  |
|    48 | ml_p07_p04_corrected           | 13175 |          1991 |                 0.0741782 |                 0.014135  |                            0 |                           1.13542  |
|    49 | ml_p07_p04_corrected           | 13921 |          2154 |                 0.0740795 |                 0.0142688 |                            0 |                           1.12917  |
|    50 | ml_p07_p04_corrected           | 34254 |         19492 |                 0.0486876 |                 0.0140814 |                            0 |                           0.938942 |
|    51 | ml_p07_p04_corrected           | 14294 |          7248 |                 0.0521844 |                 0.0146219 |                            0 |                           0.890576 |
|    52 | ml_p07_p04_corrected           |  6933 |          3625 |                 0.0526875 |                 0.0146895 |                            0 |                           0.916979 |
|    53 | ml_p07_p04_corrected           | 31382 |         13961 |                 0.0430393 |                 0.0140038 |                            0 |                           0.799037 |
|    54 | ml_p07_p04_corrected           | 29664 |         13282 |                 0.0425773 |                 0.0138768 |                            0 |                           0.788941 |
|    55 | ml_p07_p04_corrected           | 16836 |          8330 |                 0.0528399 |                 0.0143478 |                            0 |                           0.924993 |
|    56 | ml_p07_p04_corrected           | 38925 |         21645 |                 0.0511092 |                 0.0148011 |                            0 |                           0.921038 |
|    57 | ml_p07_p04_corrected           | 12928 |          1843 |                 0.075747  |                 0.0144119 |                            0 |                           1.07315  |
|    58 | ml_p07_p04_corrected           | 15919 |          1618 |                 0.0560913 |                 0.0161364 |                            0 |                           0.77821  |
|    59 | ml_p07_p04_corrected           | 13861 |           809 |                 0.103211  |                 0.0155354 |                            0 |                           0.794917 |
|    60 | ml_p07_p04_corrected           | 10133 |           382 |                 0.0945183 |                 0.0132454 |                            0 |                           0.627226 |
|    61 | ml_p07_p04_corrected           | 11287 |           420 |                 0.0994083 |                 0.0142039 |                            0 |                           0.773464 |
|    62 | ml_p07_p04_corrected           | 11911 |           513 |                 0.0981084 |                 0.0144119 |                            0 |                           0.70732  |
|    63 | ml_p07_p04_corrected           | 14779 |          1232 |                 0.0886539 |                 0.0161412 |                            0 |                           0.775732 |
|    65 | ml_p07_p04_corrected           | 11904 |           454 |                 0.0863275 |                 0.0160427 |                            0 |                           0.975536 |

## Geometry Envelope

| geometry   |   observed_even_charge |   traditional_template_corrected | traditional_template_energy_ci95             |   ml_p07_p04_corrected | ml_p07_p04_energy_ci95                       |   ml_minus_traditional_template_res68 |   traditional_template_minus_observed_res68 |
|:-----------|-----------------------:|---------------------------------:|:---------------------------------------------|-----------------------:|:---------------------------------------------|--------------------------------------:|--------------------------------------------:|
| center_2cm |              0.0191036 |                        0.0269262 | [0.02214684590192434, 0.03262421112251109]   |              0.0133793 | [0.013089787196226508, 0.013745135525996368] |                            -0.0135469 |                                  0.00782266 |
| center_4cm |              0.0211892 |                        0.0288937 | [0.024777722320676814, 0.034959602398529716] |              0.0145485 | [0.014165571606790666, 0.015005129327745377] |                            -0.0143453 |                                  0.00770451 |
| zero_4cm   |              0.0663057 |                        0.100666  | [0.09033992794660173, 0.11007543984855175]   |              0.0383461 | [0.03397967291549161, 0.04801158063442073]   |                            -0.0623203 |                                  0.0343606  |

## Leakage Audit

| check                                                   | value    | pass   |
|:--------------------------------------------------------|:---------|:-------|
| train_heldout_run_overlap                               | []       | True   |
| train_heldout_event_key_overlap                         | 0        | True   |
| ml_features_exclude_run_event_depth_pid_and_odd_samples | true     | True   |
| shuffled_target_p04_unsat_charge_res68                  | 0.507706 | True   |
| observed_even_charge_energy_res68_nominal               | 0.021189 | True   |

## Finding

Raw ROOT reproduction passed exactly at 640,737 selected B-stave pulses. On nominal 4 cm geometry, observed even charge gives energy-proxy res68 0.0212; the traditional rising-edge saturation correction gives 0.0289, and ML P07/P04 correction gives 0.0145 (ML - traditional -0.0143). Unsaturated-control charge res68 is 0.1399 for traditional and 0.0663 for ML. The saturation-minus-unsaturated log-charge delta is 1.1203 traditional versus 0.9192 ML. The correction changes internal ordering diagnostics, but this remains a charge-proxy/PSTAR-ordering study, not an absolute energy or PID calibration.

## Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14c_1781020051_1283_4e533364_saturation_energy_ordering.py --config configs/s14c_1781020051_1283_4e533364.yaml
```
