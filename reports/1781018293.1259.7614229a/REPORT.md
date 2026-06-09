# P07e: leading-edge sample ablation for saturation recovery

Ticket `1781018293.1259.7614229a`. Raw B-stack ROOT was read from `data/root/root`; no Monte Carlo was used.

## Reproduction gate

P07c was recomputed from raw ROOT before the P07e ablation loop:

| quantity                                                   | expected                |   reproduced | delta                  | pass   |
|:-----------------------------------------------------------|:------------------------|-------------:|:-----------------------|:-------|
| P07 fixed-ceiling C=4000 ML res68                          | 0.03243177807776981     |    0.0324318 | 0.0                    | True   |
| P07c/P07b multi-ceiling artificial res68                   | 0.03931517116488385     |    0.0393152 | 4.163336342344337e-17  | True   |
| P07c/P07b natural A>=7000 q_template shift                 | -0.0896770876224819     |   -0.0896733 | 3.7589315090014175e-06 | True   |
| P07c boundary 6500-7500 shape-only q_template shift        | raw-root P07c recompute |   -0.083233  |                        | True   |
| P07c application A>=7000 explicit-ceiling q_template shift | raw-root P07c recompute |   -0.0896733 |                        | True   |

The local Sample-II B2 selected-pulse rebuild then checked the P07e input population:

| quantity                              | expected     |   reproduced | delta   | pass   |
|:--------------------------------------|:-------------|-------------:|:--------|:-------|
| sample_ii_analysis B2 selected pulses | 88213        |        88213 | 0       | True   |
| B2 pulses >= 7000 ADC                 | data-derived |         5351 |         | True   |

These gates are deliberately first in the script: P07c and the Sample-II B2 selected-pulse count must match before any ablation result is written.

## Method

Clean B2 pulses (`1500 <= A <= 6500` ADC, peak samples 4-12) were artificially clipped at a fixed 4000 ADC ceiling for held-out amplitude truth. Each held-out run was predicted by models trained on the other Sample-II runs only.

- Traditional: train-run median B2 template, least-squares scaled only on retained, non-plateau samples.
- ML: P07-style gradient-boosted regressor and a one-hidden-layer masked-sample MLP, both trained on identical retained-sample features.
- Natural transfer: the same retained-sample masks were applied to observed `A_B2 >= 7000` ADC events with at least two selected downstream staves; no natural truth label was used.

## Artificial fixed-ceiling recovery

| window   | method               |   res68_abs_frac | res68_abs_frac_ci95                        |   bias_median_frac |
|:---------|:---------------------|-----------------:|:-------------------------------------------|-------------------:|
| s5       | gbr_masked           |        0.140099  | [0.13708389329542287, 0.1432434273662391]  |         0.0192708  |
| s5       | mlp_masked           |        0.14004   | [0.13382523210543004, 0.1452231795779677]  |         0.020342   |
| s5       | traditional_template |        0.367062  | [0.3350245705921343, 0.4066510813043628]   |        -0.0889758  |
| s6       | gbr_masked           |        0.131034  | [0.12992095487626762, 0.13218735410788454] |         0.0143096  |
| s6       | mlp_masked           |        0.140713  | [0.13474075541461916, 0.1479551160756048]  |         0.0086912  |
| s6       | traditional_template |        0.264116  | [0.2538482256069836, 0.27696143098297965]  |        -0.201686   |
| s7       | gbr_masked           |        0.140625  | [0.13794326722784853, 0.14297761567856015] |         0.013923   |
| s7       | mlp_masked           |        0.141773  | [0.1399991958565546, 0.1435455697059416]   |         0.00493391 |
| s7       | traditional_template |        0.267499  | [0.25786978133735766, 0.27854812436988224] |        -0.207608   |
| w2_8     | gbr_masked           |        0.0812097 | [0.07932581229244448, 0.08295661889138492] |         0.0291684  |
| w2_8     | mlp_masked           |        0.105461  | [0.08244974032269173, 0.13670727422131548] |         0.0149422  |
| w2_8     | traditional_template |        0.274675  | [0.2579978483512164, 0.2940569625590832]   |        -0.0768309  |
| w3_7     | gbr_masked           |        0.0957544 | [0.09411505348005499, 0.09713279786497006] |         0.0325423  |
| w3_7     | mlp_masked           |        0.102878  | [0.09720807377191787, 0.10827444677824986] |         0.0226297  |
| w3_7     | traditional_template |        0.572626  | [0.43649386533853385, 0.7199814416279623]  |         0.0331552  |
| w4_6     | gbr_masked           |        0.0969447 | [0.094117845993417, 0.09957148331683842]   |         0.0297976  |
| w4_6     | mlp_masked           |        0.120427  | [0.1110583152840398, 0.12959137782474556]  |         0.0282645  |
| w4_6     | traditional_template |        0.617677  | [0.47580291238044026, 0.7614016116194616]  |         0.0636681  |
| w5_7     | gbr_masked           |        0.111189  | [0.10895695593288784, 0.11323206494333199] |         0.0262826  |
| w5_7     | mlp_masked           |        0.121333  | [0.1183315415450245, 0.12329213204629182]  |         0.00522933 |
| w5_7     | traditional_template |        0.346928  | [0.3176723536914082, 0.3803689823475055]   |        -0.0792492  |

## Natural high-amplitude transfer

| window   | method               |   timing_tail_delta_vs_observed | timing_tail_delta_vs_observed_ci95            |   q_template_shift_vs_observed |
|:---------|:---------------------|--------------------------------:|:----------------------------------------------|-------------------------------:|
| s5       | gbr_masked           |                      0.0176814  | [-0.0031746031746031794, 0.04283404283404287] |                    0.024262    |
| s5       | mlp_masked           |                      0.010989   | [0.0, 0.032967032967032996]                   |                    0.00256919  |
| s5       | traditional_template |                      0.00728764 | [-0.03279172029172028, 0.04638352638352636]   |                    0.135071    |
| s6       | gbr_masked           |                      0.00792166 | [-0.012698412698412717, 0.03389957264957266]  |                    0.0253156   |
| s6       | mlp_masked           |                      0.0216348  | [-0.0038610038610038533, 0.06593406593406594] |                    0.00211852  |
| s6       | traditional_template |                     -0.0044187  | [-0.019047619047619074, 0.005791505791505828] |                    0.000275844 |
| s7       | gbr_masked           |                      0.00691351 | [-0.01587301587301588, 0.033642708642708616]  |                    0.0127861   |
| s7       | mlp_masked           |                      0.0300057  | [-0.005662805662805684, 0.07486263736263736]  |                    0.00632481  |
| s7       | traditional_template |                      0          | [0.0, 0.0]                                    |                    0           |
| w2_8     | gbr_masked           |                      0.0280752  | [-0.007593307593307611, 0.07877190377190375]  |                    0.00379823  |
| w2_8     | mlp_masked           |                     -0.00589346 | [-0.04061739768662369, 0.028166564630750044]  |                   -0.00454113  |
| w2_8     | traditional_template |                      0          | [0.0, 0.0]                                    |                    8.67621e-06 |
| w3_7     | gbr_masked           |                      0.0135684  | [-0.012698412698412717, 0.04189560439560442]  |                    0.00806558  |
| w3_7     | mlp_masked           |                     -0.00877365 | [-0.03884504631896284, 0.026119469971797385]  |                    0.00392754  |
| w3_7     | traditional_template |                     -0.0108966  | [-0.026340626340626346, 0.0]                  |                    0.00609017  |
| w4_6     | gbr_masked           |                      0.00584637 | [-0.026769626769626798, 0.04189560439560442]  |                    0.0151333   |
| w4_6     | mlp_masked           |                      0.0180136  | [-0.003847354268702592, 0.04382610632610636]  |                    0.00213584  |
| w4_6     | traditional_template |                      0.00862291 | [-0.021535821535821547, 0.04671814671814672]  |                    0.133276    |
| w5_7     | gbr_masked           |                      0.0218481  | [0.0019305019305019425, 0.045906964656964686] |                    0.0101985   |
| w5_7     | mlp_masked           |                      0.0245508  | [-0.015426659489159477, 0.06282623626373622]  |                    0.00469576  |
| w5_7     | traditional_template |                     -0.0108966  | [-0.026385671385671387, 0.0]                  |                    0.00593713  |

## Adoption screen

| window   | best_artificial_method   |   best_res68_abs_frac | best_res68_abs_frac_ci95                   | tail_delta_ci95                               | adoptable   |
|:---------|:-------------------------|----------------------:|:-------------------------------------------|:----------------------------------------------|:------------|
| w2_8     | gbr_masked               |             0.0812097 | [0.07932581229244448, 0.08295661889138492] | [-0.007593307593307611, 0.07877190377190375]  | False       |
| w3_7     | gbr_masked               |             0.0957544 | [0.09411505348005499, 0.09713279786497006] | [-0.012698412698412717, 0.04189560439560442]  | False       |
| w4_6     | gbr_masked               |             0.0969447 | [0.094117845993417, 0.09957148331683842]   | [-0.026769626769626798, 0.04189560439560442]  | False       |
| w3_5     | gbr_masked               |             0.107165  | [0.10060311519990857, 0.11285814997912366] | [-0.04105534105534108, 0.02524502524502527]   | False       |
| w5_7     | gbr_masked               |             0.111189  | [0.10895695593288784, 0.11323206494333199] | [0.0019305019305019425, 0.045906964656964686] | False       |
| s6       | gbr_masked               |             0.131034  | [0.12992095487626762, 0.13218735410788454] | [-0.012698412698412717, 0.03389957264957266]  | False       |
| s5       | mlp_masked               |             0.14004   | [0.13382523210543004, 0.1452231795779677]  | [0.0, 0.032967032967032996]                   | False       |
| s7       | gbr_masked               |             0.140625  | [0.13794326722784853, 0.14297761567856015] | [-0.01587301587301588, 0.033642708642708616]  | False       |
| w2_4     | gbr_masked               |             0.142872  | [0.1403780889163982, 0.14527322432423515]  | [-0.004418704418704416, 0.042615995115995134] | False       |
| s4       | gbr_masked               |             0.144534  | [0.14237336208999227, 0.14673012732058285] | [-0.009523809523809554, 0.04090354090354093]  | False       |
| s3       | mlp_masked               |             0.145253  | [0.14218079412778778, 0.1482445076576693]  | [-0.009523809523809537, 0.0]                  | False       |

A retained window is marked adoptable only when its best artificial recovery has a run-block 95% CI upper bound below 8% and its natural timing-tail delta has a 95% CI upper bound at or below zero.

## Leakage checks

- The split is leave-one-run-out over runs `[58, 59, 60, 61, 62, 63, 65]`; run id, event id, downstream timing, and true amplitude are excluded from ML features.
- The best artificial score is `w2_8`/`gbr_masked` with res68 `0.0812`, not a near-zero result.
- A shuffled-label check on that same window gave res68 `0.2668`; the real/shuffled ratio is `0.304`.
- Too-good-to-be-true leakage flag: `False`.

## Headline

Single samples 5-7 carry useful but incomplete information; the best artificial held-out recovery uses the broader leading-edge window `w2_8` with `gbr_masked` at res68 `0.0812` (95% CI `0.0793`-`0.0830`) and median bias `0.0292`. Natural transfer does not pass the adoption screen because the best window's timing-tail delta CI is `-0.0076` to `0.0788`.

## Follow-up

- No ticket appended: the queue already contains open ticket `1781019500.1759.55e62bed`, `P07f: calibrate natural B2 saturation knees with odd-channel duplicates`.
