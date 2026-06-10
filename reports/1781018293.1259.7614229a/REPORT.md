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
| s5       | gbr_masked           |        0.140568  | [0.13772993420955723, 0.14265372149911154] |         0.0201206  |
| s5       | mlp_masked           |        0.139765  | [0.13517486724456837, 0.144061138973626]   |         0.0170588  |
| s5       | traditional_template |        0.368196  | [0.3389884335803812, 0.4080012362153037]   |        -0.0877956  |
| s6       | gbr_masked           |        0.131896  | [0.1296182605336108, 0.13396412961462822]  |         0.0149367  |
| s6       | mlp_masked           |        0.137056  | [0.13198006731238393, 0.14358959828257728] |         0.010511   |
| s6       | traditional_template |        0.263869  | [0.25305609072725566, 0.2748510694591163]  |        -0.201197   |
| s7       | gbr_masked           |        0.141     | [0.13864038701618153, 0.14384087937095336] |         0.013476   |
| s7       | mlp_masked           |        0.144268  | [0.14144778023528878, 0.14691498385944224] |         0.00794239 |
| s7       | traditional_template |        0.267187  | [0.2578735305998991, 0.27723813824670523]  |        -0.207436   |
| w2_8     | gbr_masked           |        0.0814285 | [0.07907366552149397, 0.08413707848049133] |         0.0287616  |
| w2_8     | mlp_masked           |        0.108084  | [0.08945123115891876, 0.1385236982764985]  |         0.0112236  |
| w2_8     | traditional_template |        0.275113  | [0.256992506898616, 0.2907393401467324]    |        -0.0763872  |
| w3_7     | gbr_masked           |        0.0963924 | [0.09462219992819904, 0.09818938930794903] |         0.0332871  |
| w3_7     | mlp_masked           |        0.125029  | [0.09816149635457294, 0.1691588995310842]  |         0.0376229  |
| w3_7     | traditional_template |        0.576769  | [0.44779411160000343, 0.699715412211532]   |         0.0323685  |
| w4_6     | gbr_masked           |        0.0970779 | [0.09393111573189411, 0.09984853023874189] |         0.0301974  |
| w4_6     | mlp_masked           |        0.15222   | [0.11800251644417367, 0.21031659410321457] |         0.0680682  |
| w4_6     | traditional_template |        0.62365   | [0.4915427487780062, 0.7628399683621971]   |         0.0640459  |
| w5_7     | gbr_masked           |        0.11274   | [0.11061827453992623, 0.11454268190877208] |         0.0292757  |
| w5_7     | mlp_masked           |        0.156803  | [0.12528050206579883, 0.2107378815225932]  |         0.0532339  |
| w5_7     | traditional_template |        0.347993  | [0.3183033616293394, 0.38165671745207563]  |        -0.0787455  |

## Natural high-amplitude transfer

| window   | method               |   timing_tail_delta_vs_observed | timing_tail_delta_vs_observed_ci95            |   q_template_shift_vs_observed |
|:---------|:---------------------|--------------------------------:|:----------------------------------------------|-------------------------------:|
| s5       | gbr_masked           |                      0.0192687  | [-0.0012441012441012525, 0.04400183150183149] |                    0.0244246   |
| s5       | mlp_masked           |                      0.010989   | [0.0, 0.032967032967032996]                   |                    0.00343395  |
| s5       | traditional_template |                      0.0112559  | [-0.023863148863148855, 0.04867747211497211]  |                    0.135196    |
| s6       | gbr_masked           |                      0.0157509  | [-0.006349206349206359, 0.04090354090354093]  |                    0.025874    |
| s6       | mlp_masked           |                      0.0145068  | [0.0015873015873015817, 0.03648483648483652]  |                    0.00486849  |
| s6       | traditional_template |                     -0.0044187  | [-0.019047619047619074, 0.003861003861003885] |                    0.00028308  |
| s7       | gbr_masked           |                      0.0188034  | [-0.009523809523809537, 0.06593406593406594]  |                    0.0126252   |
| s7       | mlp_masked           |                      0.00961497 | [-0.006349206349206359, 0.030663878163878156] |                    0.00567154  |
| s7       | traditional_template |                      0          | [0.0, 0.0]                                    |                    0           |
| w2_8     | gbr_masked           |                      0.0111874  | [-0.013492063492063524, 0.04479548229548231]  |                    0.00385763  |
| w2_8     | mlp_masked           |                      0.0102608  | [-0.05326581902212151, 0.09065934065934067]   |                   -0.00103594  |
| w2_8     | traditional_template |                      0          | [0.0, 0.0]                                    |                    8.67621e-06 |
| w3_7     | gbr_masked           |                      0.00573912 | [-0.025995817245817246, 0.037778540903540915] |                    0.00873469  |
| w3_7     | mlp_masked           |                     -0.0076955  | [-0.015417504181549111, 0.0]                  |                    0.0066478   |
| w3_7     | traditional_template |                     -0.0108966  | [-0.026340626340626346, 0.0]                  |                    0.00649799  |
| w4_6     | gbr_masked           |                      0.00777687 | [-0.020614543114543075, 0.03983516483516485]  |                    0.0148665   |
| w4_6     | mlp_masked           |                      0.00836108 | [-0.02316602316602317, 0.04104172854172856]   |                    0.00683562  |
| w4_6     | traditional_template |                      0.00862291 | [-0.020657443157443195, 0.04287430287430285]  |                    0.13342     |
| w5_7     | gbr_masked           |                      0.0199176  | [0.0, 0.0439732142857143]                     |                    0.0104695   |
| w5_7     | mlp_masked           |                      0.0262519  | [-0.012483912483912483, 0.07408882783882781]  |                    0.00296311  |
| w5_7     | traditional_template |                     -0.0108966  | [-0.026385671385671387, 0.0]                  |                    0.00634986  |

## Adoption screen

| window   | best_artificial_method   |   best_res68_abs_frac | best_res68_abs_frac_ci95                   | tail_delta_ci95                               | adoptable   |
|:---------|:-------------------------|----------------------:|:-------------------------------------------|:----------------------------------------------|:------------|
| w2_8     | gbr_masked               |             0.0814285 | [0.07907366552149397, 0.08413707848049133] | [-0.013492063492063524, 0.04479548229548231]  | False       |
| w3_7     | gbr_masked               |             0.0963924 | [0.09462219992819904, 0.09818938930794903] | [-0.025995817245817246, 0.037778540903540915] | False       |
| w4_6     | gbr_masked               |             0.0970779 | [0.09393111573189411, 0.09984853023874189] | [-0.020614543114543075, 0.03983516483516485]  | False       |
| w3_5     | gbr_masked               |             0.107202  | [0.10079506033212289, 0.11347844880383526] | [-0.034362934362934396, 0.023479853479853457] | False       |
| w5_7     | gbr_masked               |             0.11274   | [0.11061827453992623, 0.11454268190877208] | [0.0, 0.0439732142857143]                     | False       |
| s6       | gbr_masked               |             0.131896  | [0.1296182605336108, 0.13396412961462822]  | [-0.006349206349206359, 0.04090354090354093]  | False       |
| s5       | mlp_masked               |             0.139765  | [0.13517486724456837, 0.144061138973626]   | [0.0, 0.032967032967032996]                   | False       |
| s7       | gbr_masked               |             0.141     | [0.13864038701618153, 0.14384087937095336] | [-0.009523809523809537, 0.06593406593406594]  | False       |
| s3       | mlp_masked               |             0.143532  | [0.14124646815100364, 0.14609012163863325] | [-0.009523809523809537, 0.0]                  | False       |
| s4       | mlp_masked               |             0.143657  | [0.140883332791306, 0.14701080150552437]   | [-0.01428571428571433, 0.0]                   | False       |
| w2_4     | gbr_masked               |             0.143921  | [0.1412809417127404, 0.1456944609135679]   | [-0.004427284427284424, 0.04283404283404287]  | False       |

A retained window is marked adoptable only when its best artificial recovery has a run-block 95% CI upper bound below 8% and its natural timing-tail delta has a 95% CI upper bound at or below zero.

## Permutation importance

For the best broad window, features were permuted inside each held-out run after training on the other runs. Positive deltas mean the model relied on that feature.

| feature                |   delta_res68_abs_frac | delta_res68_abs_frac_ci95                     |
|:-----------------------|-----------------------:|:----------------------------------------------|
| diff_4_5               |             0.0486448  | [0.041171713816785374, 0.05675300131274554]   |
| diff_3_4               |             0.0407188  | [0.0374658669784011, 0.04431488523847287]     |
| sample_8_over_obs      |             0.0131508  | [0.010455769415615553, 0.016362777357695937]  |
| sample_5_over_obs      |             0.010396   | [0.006583296577624359, 0.013735872825258857]  |
| diff_6_7               |             0.0102582  | [0.00790436514182401, 0.012587832060928113]   |
| sample_6_over_obs      |             0.00921952 | [0.007167849852005507, 0.011334932451031988]  |
| diff_7_8               |             0.00849053 | [0.005016902107857397, 0.012321030147433258]  |
| diff_5_6               |             0.0078685  | [0.002933462725742673, 0.012110942706571858]  |
| window_charge_over_obs |             0.00477992 | [0.003610957397398106, 0.006046235715767095]  |
| diff_2_3               |             0.00345925 | [0.0015783318225636193, 0.005208087428347237] |

## Ceiling and observed-amplitude probes

The best-window GBR was retrained with feature subsets to test explicit ceiling/observed-amplitude dependence.

| window   | probe                |   res68_abs_frac | res68_abs_frac_ci95                        |   bias_median_frac |
|:---------|:---------------------|-----------------:|:-------------------------------------------|-------------------:|
| w2_8     | full_features        |         0.081806 | [0.0789534290387362, 0.0847577571293705]   |          0.0295843 |
| w2_8     | observed_amp_only    |         0.146858 | [0.1447832660440257, 0.14833988535073356]  |          0.0146369 |
| w2_8     | without_observed_amp |         0.198236 | [0.19055387541482324, 0.20828610482441964] |          0.132538  |

## Leakage checks

- The split is leave-one-run-out over runs `[58, 59, 60, 61, 62, 63, 65]`; run id, event id, downstream timing, and true amplitude are excluded from ML features.
- The best artificial score is `w2_8`/`gbr_masked` with res68 `0.0814`, not a near-zero result.
- A shuffled-label check on that same window gave res68 `0.2632`; the real/shuffled ratio is `0.309`.
- The observed-amplitude-only probe on `w2_8` scored res68 `0.1469`, worse than the full feature model.
- Removing the explicit observed-amplitude feature scored res68 `0.1982`.
- Too-good-to-be-true leakage flag: `False`.

## Headline

Single samples 5-7 carry useful but incomplete information; the best artificial held-out recovery uses the broader leading-edge window `w2_8` with `gbr_masked` at res68 `0.0814` (95% CI `0.0791`-`0.0841`) and median bias `0.0288`. Natural transfer does not pass the adoption screen because the best window's timing-tail delta CI is `-0.0135` to `0.0448`.

## Follow-up

- No ticket appended: the queue already contains open ticket `1781019500.1759.55e62bed`, `P07f: calibrate natural B2 saturation knees with odd-channel duplicates`.
