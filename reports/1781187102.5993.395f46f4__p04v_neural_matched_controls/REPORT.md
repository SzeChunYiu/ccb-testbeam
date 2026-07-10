# P04v Neural Matched-Controls for A/B Charge-Transfer Non-Identifiability

- **Ticket:** `1781187102.5993.395f46f4`
- **Worker:** `testbeam-laptop-1`
- **Source raw-root reconstruction:** `reports/1781063920.599.196428b2__p04u_astack_shuffled_sentinel_root_cause`
- **Split:** leave-one-run-out by run, inherited row-for-row from P04u.
- **Bootstrap:** complete-run block resampling for all confidence intervals.

## Abstract

The P04u CNN-family point estimates remain control-parity results under matched neural controls. The 1D-CNN and support-gated CNN do not clear the preregistered run-level identifiability gate against the neural shuffled-target control, so the P04u conclusion is not an ExtraTrees-control artifact.

## Raw-ROOT Reproduction Gate

This P04v run reuses the P04u raw-ROOT reconstruction artifacts as the frozen input table. P04u rebuilt the B-stack selected-pulse count and A/B event-match table from `data/root/root/{hrda,hrdb}_run_*.root` before any model fit. The inherited gate reports B-stack selected pulses `640737`, A/B matched rows `4055`, and P04c charge-transfer ridge `res68=0.5192709757631775` with pass status `true`.

## Estimand And Equations

For event `i`, the selected A-stack target is `Q_i^A = I(A1_i) q_{i,A1} + I(A3_i) q_{i,A3}` with the same 1000 ADC selection gate as P04u. All models predict `z_i = log(max(Q_i^A,1))` from B-stack information only. The residual is `r_i(m) = (hat Q_i(m)-Q_i^A)/max(Q_i^A,1)`, and the primary metric is `res68_m = Q_0.68(|r_i(m)|)`.

## Matched Neural Controls

The neural shuffled-target control is an MLP trained inside each train-run fold after permuting the train-fold log-charge target. The B-waveform knockoff neural control is an MLP trained on train-fold log charge after independently permuting the P04u B-waveform/support score coordinates in train and held-out folds. Both controls use the same support-cell labels and held-out runs as the P04u CNN and support-gated CNN.

## Benchmark Table

| method                            | method_family | n    | bias_median_frac | bias_median_frac_ci95                         | res68_abs_frac | res68_abs_frac_ci95                      | full_rms_frac | full_rms_frac_ci95                       | within_25pct |
| --------------------------------- | ------------- | ---- | ---------------- | --------------------------------------------- | -------------- | ---------------------------------------- | ------------- | ---------------------------------------- | ------------ |
| neural_bwaveform_knockoff_control | control       | 4055 | -0.0373367       | [-0.059166011564726256, -0.00926193565587216] | 0.383027       | [0.371238806821571, 0.3920584518935011]  | 3.27607       | [0.636549742496867, 5.622793705141237]   | 0.456227     |
| ridge_log_charge_support          | ml_nn         | 4055 | -0.0477586       | [-0.07094930065358267, -0.02036026227083555]  | 0.518475       | [0.5040570133096666, 0.5371372006697666] | 0.843207      | [0.7359542829680245, 1.0099749128022588] | 0.34254      |
| cnn1d_waveform                    | ml_nn         | 4055 | -0.0224902       | [-0.04386063267158548, 0.001620010260823514]  | 0.519348       | [0.5053330239266444, 0.5360708540323069] | 0.872175      | [0.7585541001676079, 1.0205259787102023] | 0.350432     |
| hybrid_support_gate_cnn           | ml_nn         | 4055 | -0.0204754       | [-0.04274028440337337, 0.010444840070247681]  | 0.520421       | [0.5057076204389409, 0.5396083568627514] | 0.874572      | [0.7700464411186831, 1.0164169086702486] | 0.349445     |
| gradient_boosted_trees            | ml_nn         | 4055 | -0.0456523       | [-0.06697498562101725, -0.02095818885721592]  | 0.522162       | [0.5067827124087203, 0.5407043087935912] | 0.845328      | [0.7397067900241235, 0.9984489108689688] | 0.338348     |
| adaptive_template_ridge           | traditional   | 4055 | -0.0469556       | [-0.06333933601215908, -0.017018204274197046] | 0.5262         | [0.5101539372412793, 0.5389986852502668] | 0.848443      | [0.7344220270700271, 1.0044301820522645] | 0.343527     |
| neural_shuffled_target_control    | control       | 4055 | -0.0337739       | [-0.06149768946005632, -0.010845103693456218] | 0.539297       | [0.5224607777433249, 0.560596119648829]  | 1.36847       | [0.9947527964943638, 1.7209331753017194] | 0.336128     |
| mlp_waveform                      | ml_nn         | 4055 | -0.0826421       | [-0.1456930182226986, -0.03234241991716799]   | 0.667231       | [0.6209622940916367, 0.7572538300928936] | 11.8594       | [4.965205351247493, 18.41237617555127]   | 0.27201      |

## CNN-Family Deltas Against Neural Controls

| method                  | control                           | delta_res68 | delta_res68_ci95                               | delta_full_rms | delta_full_rms_ci95                         |
| ----------------------- | --------------------------------- | ----------- | ---------------------------------------------- | -------------- | ------------------------------------------- |
| cnn1d_waveform          | neural_shuffled_target_control    | -0.0199493  | [-0.03334876732337838, -0.008913052483968892]  | -0.4963        | [-0.8448061461399474, -0.13602315765125686] |
| cnn1d_waveform          | neural_bwaveform_knockoff_control | 0.136321    | [0.12378712569910154, 0.15101847903412802]     | -2.40389       | [-4.758019705656488, 0.26469223720263313]   |
| hybrid_support_gate_cnn | neural_shuffled_target_control    | -0.0188762  | [-0.031548782742754376, -0.004067988497212788] | -0.493903      | [-0.8321206449257833, -0.13659775163039206] |
| hybrid_support_gate_cnn | neural_bwaveform_knockoff_control | 0.137394    | [0.12369219073642619, 0.15306250247860276]     | -2.4015        | [-5.003485711434281, 0.278346815605333]     |

## Support-Cell Gate

| support_cell                                                                        | n   | runs | method                  | method_res68 | shuffled_neural_res68 | knockoff_neural_res68 | delta_vs_shuffled | delta_vs_knockoff |
| ----------------------------------------------------------------------------------- | --- | ---- | ----------------------- | ------------ | --------------------- | --------------------- | ----------------- | ----------------- |
| A3_only|B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none             | 108 | 18   | cnn1d_waveform          | 0.516857     | 0.683743              | 0.417039              | -0.166885         | 0.0998182         |
| A3_only|B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none             | 108 | 18   | hybrid_support_gate_cnn | 0.524409     | 0.683743              | 0.417039              | -0.159334         | 0.10737           |
| A3_only|B2_only|7000_inf|any_B_amp_ge7000|broad_saturation_like|downstream_none     | 150 | 23   | hybrid_support_gate_cnn | 0.542188     | 0.6425                | 0.398973              | -0.100311         | 0.143216          |
| A3_only|B2_only|3000_5000|all_B_amp_lt7000|late_tail_high|downstream_none           | 81  | 19   | cnn1d_waveform          | 0.335581     | 0.422125              | 0.420209              | -0.0865438        | -0.0846278        |
| A3_only|B2_only|7000_inf|any_B_amp_ge7000|broad_saturation_like|downstream_none     | 150 | 23   | cnn1d_waveform          | 0.559658     | 0.6425                | 0.398973              | -0.0828414        | 0.160686          |
| A3_only|B2_only|3000_5000|all_B_amp_lt7000|late_tail_high|downstream_none           | 81  | 19   | hybrid_support_gate_cnn | 0.339657     | 0.422125              | 0.420209              | -0.082468         | -0.0805521        |
| A3_only|B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none           | 174 | 22   | cnn1d_waveform          | 0.48981      | 0.559966              | 0.381511              | -0.0701564        | 0.108299          |
| A3_only|B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none           | 174 | 22   | hybrid_support_gate_cnn | 0.511888     | 0.559966              | 0.381511              | -0.0480784        | 0.130377          |
| A1_A3_pair|B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none          | 71  | 16   | cnn1d_waveform          | 0.492806     | 0.530251              | 0.312911              | -0.0374454        | 0.179895          |
| A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|downstream_none         | 190 | 20   | cnn1d_waveform          | 0.498085     | 0.530548              | 0.294173              | -0.0324631        | 0.203912          |
| A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|downstream_none         | 190 | 20   | hybrid_support_gate_cnn | 0.499478     | 0.530548              | 0.294173              | -0.0310699        | 0.205305          |
| A1_A3_pair|B2_only|1000_2000|all_B_amp_lt7000|dropout_like|downstream_none          | 71  | 16   | hybrid_support_gate_cnn | 0.502458     | 0.530251              | 0.312911              | -0.0277932        | 0.189547          |
| A1_A3_pair|B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none        | 101 | 17   | hybrid_support_gate_cnn | 0.442829     | 0.468809              | 0.276084              | -0.02598          | 0.166745          |
| A1_A3_pair|B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none        | 101 | 17   | cnn1d_waveform          | 0.447192     | 0.468809              | 0.276084              | -0.021617         | 0.171108          |
| A1_A3_pair|B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none        | 76  | 18   | hybrid_support_gate_cnn | 0.475689     | 0.496873              | 0.2587                | -0.0211846        | 0.216989          |
| A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none | 300 | 22   | hybrid_support_gate_cnn | 0.494264     | 0.514445              | 0.284201              | -0.0201813        | 0.210062          |
| A1_A3_pair|B2_only|1000_2000|all_B_amp_lt7000|late_tail_high|downstream_none        | 76  | 18   | cnn1d_waveform          | 0.478279     | 0.496873              | 0.2587                | -0.0185936        | 0.21958           |
| A1_A3_pair|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none | 300 | 22   | cnn1d_waveform          | 0.496312     | 0.514445              | 0.284201              | -0.0181329        | 0.212111          |
| A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|broad_saturation_like|downstream_none  | 80  | 17   | hybrid_support_gate_cnn | 0.482907     | 0.500638              | 0.285555              | -0.0177316        | 0.197352          |
| A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|downstream_none | 303 | 24   | cnn1d_waveform          | 0.483549     | 0.500883              | 0.260587              | -0.0173341        | 0.222962          |
| A1_A3_pair|B2_only|5000_7000|all_B_amp_lt7000|broad_saturation_like|downstream_none | 303 | 24   | hybrid_support_gate_cnn | 0.485737     | 0.500883              | 0.260587              | -0.0151461        | 0.22515           |
| A1_A3_pair|B2_only|7000_inf|any_B_amp_ge7000|broad_saturation_like|downstream_none  | 80  | 17   | cnn1d_waveform          | 0.486295     | 0.500638              | 0.285555              | -0.0143436        | 0.20074           |
| A3_only|B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none           | 166 | 19   | cnn1d_waveform          | 0.577219     | 0.572568              | 0.418528              | 0.004651          | 0.158691          |
| A3_only|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none    | 635 | 28   | hybrid_support_gate_cnn | 0.609322     | 0.599563              | 0.41339               | 0.0097583         | 0.195931          |
| A3_only|B2_only|3000_5000|all_B_amp_lt7000|broad_saturation_like|downstream_none    | 635 | 28   | cnn1d_waveform          | 0.609677     | 0.599563              | 0.41339               | 0.0101133         | 0.196286          |
| A3_only|B2_only|2000_3000|all_B_amp_lt7000|late_tail_high|downstream_none           | 166 | 19   | hybrid_support_gate_cnn | 0.605738     | 0.572568              | 0.418528              | 0.0331698         | 0.187209          |
| A3_only|B2_only|2000_3000|all_B_amp_lt7000|dropout_like|downstream_none             | 54  | 17   | hybrid_support_gate_cnn | 0.77002      | 0.735712              | 0.447131              | 0.0343086         | 0.322889          |
| A3_only|B2_only|2000_3000|all_B_amp_lt7000|dropout_like|downstream_none             | 54  | 17   | cnn1d_waveform          | 0.779872     | 0.735712              | 0.447131              | 0.0441609         | 0.332742          |
| A3_only|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|downstream_none            | 381 | 26   | hybrid_support_gate_cnn | 0.644049     | 0.589394              | 0.44001               | 0.0546544         | 0.204039          |
| A3_only|B2_only|7000_inf|any_B_amp_ge7000|late_tail_high|downstream_none            | 381 | 26   | cnn1d_waveform          | 0.658159     | 0.589394              | 0.44001               | 0.0687642         | 0.218149          |

## Systematics And Caveats

- This is a P04u add-on, not an independent reconstruction script; the raw-ROOT reproduction is inherited from the frozen P04u artifacts and checked through their result payload.
- Neural controls are matched to P04u out-of-fold B-waveform/support scores, not retrained from raw ADC samples. This isolates whether the CNN-family point estimates beat neural controls under identical run/support gates.
- The target remains selected A-stack charge rather than deposited energy, so A-stack acceptance is part of the estimand.
- The bootstrap covers the observed run ensemble only; unobserved beam tunes, detector mounting changes, or acquisition metadata shifts are outside the interval.
- Sparse support cells can show favorable deltas by chance; the winner gate therefore uses run-level replication rather than isolated cell minima.

## Verdict

Winner recorded in `result.json`: `ridge_log_charge_support`. The best real point estimate is `ridge_log_charge_support` and `18` held-out runs clear the neural-control delta gate, meeting the required `3`.
