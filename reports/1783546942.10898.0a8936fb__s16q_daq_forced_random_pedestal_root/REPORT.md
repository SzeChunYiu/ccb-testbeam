# S16q: DAQ-provenanced B-stack forced/random pedestal ROOT audit

## Abstract

Ticket `1783546942.10898.0a8936fb` asks whether true non-beam B-stack
forced/random pedestal ROOT exists with DAQ trigger-code provenance, and if so
whether the frozen S16k hidden-mode methods can be scored without timing-tail
labels.  I rescanned every accessible B-stack raw ROOT file in
`data/root/root`.  The direct forced/random target is **not estimable in the mounted data mirror**:
`0` entries have `TRIGGER != 1`, `0` B-stack ROOT
filenames carry forced/random/pedestal/no-pulse tokens, and all populated files
with a `TRIGGER` branch have code `1` only.

The raw selected-pulse reproduction gate passes exactly
(`reproduction_pass = true`), matching the canonical
`640,737` B-stave pulse count before any model scoring.  Because the direct
target is absent, the pre-registered fallback is the frozen S16k blinded
Sample-II timing-tail benchmark.  Its winner is **cnn1d**, with
post-veto tail fraction `0.00803` and run-block
95% CI `[0.00560, 0.00980]`.

## Scientific Question

The desired direct estimand is

\[
q_m^{FR} = \Pr\left(Y_i^{FR}=1 \mid s_m(x_i), R(i)\notin\mathcal{R}_{train}\right),
\]

where \(Y_i^{FR}\) is a DAQ-provenanced forced/random no-pulse electronics
disturbance label, \(s_m(x_i)\) is the frozen hidden-mode score from method
\(m\), and all thresholds are learned outside the held-out run.  Such an
estimand requires at least one populated non-beam B-stack ROOT entry or a
dedicated forced/random pedestal file.  If no such row exists, the estimand is
undefined; the script then reports the absence gate and scores the already
frozen independent timing-tail fallback,

\[
y_i = \mathbb{1}\left(|r_i - \tilde r_{p(i),-R(i)}| > 5\,\mathrm{ns}\right).
\]

## Raw ROOT Reproduction

The reproduction gate reads `h101/HRDv` directly from raw ROOT, reshapes the
waveform to B-stack channels and samples, subtracts the per-channel median over
samples `[0, 1, 2, 3]`, and selects B2/B4/B6/B8 pulses with
baseline-subtracted maximum amplitude above `1000`
ADC.  This is run before consuming any frozen prediction artifact.

| quantity                           |   report_value |   reproduced |   delta |   tolerance | pass   |
|:-----------------------------------|---------------:|-------------:|--------:|------------:|:-------|
| total selected B-stave pulses      |         640737 |       640737 |       0 |           0 | True   |
| sample_ii_analysis selected_pulses |         125096 |       125096 |       0 |           0 | True   |
| sample_ii_analysis B2              |          88213 |        88213 |       0 |           0 | True   |
| sample_ii_analysis B4              |          21229 |        21229 |       0 |           0 | True   |
| sample_ii_analysis B6              |          11148 |        11148 |       0 |           0 | True   |
| sample_ii_analysis B8              |           4506 |         4506 |       0 |           0 | True   |

## DAQ Provenance Audit

| quantity | value |
|---|---:|
| B-stack raw ROOT files scanned | 53 |
| populated B-stack files | 51 |
| total B-stack entries | 1649802 |
| files with trigger-like branch names | 53 |
| files with exact `TRIGGER` branch | 53 |
| entries with `TRIGGER != 1` | 0 |
| forced/random/pedestal filename-token hits | 0 |

The trigger-like branches found in the mounted mirror are recorded in
`forced_random_daq_audit.csv`.  The necessary direct-truth condition fails:
the visible B-stack ROOT mirror contains physics-trigger rows only.  This is a
data availability result, not a neural-network result.

## Methods

Since direct labels are absent, I score the frozen S16f/S16k held-out prediction
panel under the same Sample-II leave-one-run-out split.  The compared methods
cover a strong traditional comparator and the requested ML/NN families:

- `traditional_quantile`: train-run empirical quantile envelope over hand-built
  pretrigger disturbance proxies.
- `ridge`: regularized linear classifier on standardized pretrigger summaries.
- `gradient_boosted_trees`: histogram gradient-boosted trees.
- `mlp`: feed-forward neural network on summary features.
- `cnn1d`: compact temporal convolution over the paired pretrigger traces.
- `siamese_cnn_meta`: new pair-symmetric convolutional architecture with shared
  waveform branches, absolute branch-difference features, and scalar metadata
  fusion.

No model is retrained on the claimed ticket.  This preserves the frozen
thresholds and prevents tuning to the S16q result after the direct target was
found absent.

## Metrics and Bootstrap CIs

For each method \(m\), the held-out veto is
\(v_i(m)=\mathbb{1}[s_m(x_i)>t_{m,-R(i)}]\).  The primary fallback metric is

\[
\hat q_m =
\frac{\sum_i (1-v_i(m)) y_i}{\sum_i (1-v_i(m))},
\]

the post-veto timing-tail fraction.  Secondary metrics are veto fraction,
timing efficiency, tail capture, ROC AUC, and average precision.  Confidence
intervals use `800` non-parametric
bootstrap replicates over held-out runs, preserving run blocks rather than
resampling individual correlated pair rows.

## Fallback Benchmark

| method                 |   n_pairs |   n_events |   veto_fraction |   tail_fraction_after |   tail_fraction_after_ci_low |   tail_fraction_after_ci_high |   tail_capture |    auc |   average_precision |
|:-----------------------|----------:|-----------:|----------------:|----------------------:|-----------------------------:|------------------------------:|---------------:|-------:|--------------------:|
| cnn1d                  |     11460 |       3820 |          0.0979 |                0.008  |                       0.0056 |                        0.0098 |         0.523  | 0.7387 |              0.316  |
| gradient_boosted_trees |     11460 |       3820 |          0.1021 |                0.0082 |                       0.0058 |                        0.01   |         0.5172 | 0.745  |              0.2477 |
| siamese_cnn_meta       |     11460 |       3820 |          0.0974 |                0.0082 |                       0.0056 |                        0.0101 |         0.5115 | 0.7421 |              0.3022 |
| mlp                    |     11460 |       3820 |          0.1015 |                0.0084 |                       0.006  |                        0.0104 |         0.5    | 0.7418 |              0.2897 |
| ridge                  |     11460 |       3820 |          0.1005 |                0.0086 |                       0.0053 |                        0.0111 |         0.4885 | 0.7316 |              0.1486 |
| traditional_quantile   |     11460 |       3820 |          0.1003 |                0.0115 |                       0.0076 |                        0.0138 |         0.3161 | 0.7012 |              0.0506 |

## Shuffled-Proxy Control

The shuffled control keeps labels and run membership fixed while breaking the
training association between pretrigger proxies and labels.

| method                 |   veto_fraction |   tail_fraction_after |   tail_capture |    auc |   average_precision |
|:-----------------------|----------------:|----------------------:|---------------:|-------:|--------------------:|
| cnn1d                  |          0.0939 |                0.0145 |         0.1322 | 0.3569 |              0.0143 |
| gradient_boosted_trees |          0.0972 |                0.0141 |         0.1609 | 0.4528 |              0.0172 |
| mlp                    |          0.1017 |                0.0145 |         0.1437 | 0.4608 |              0.0181 |
| ridge                  |          0.0831 |                0.0137 |         0.1724 | 0.4274 |              0.0384 |
| siamese_cnn_meta       |          0.0606 |                0.0141 |         0.1264 | 0.4117 |              0.0356 |
| traditional_quantile   |          0.1013 |                0.0149 |         0.1207 | 0.522  |              0.0167 |

Honest-minus-shuffled contrasts:

| method                 |   delta_auc_vs_shuffled |   delta_tail_after_vs_shuffled |   delta_tail_capture_vs_shuffled |
|:-----------------------|------------------------:|-------------------------------:|---------------------------------:|
| cnn1d                  |                  0.3817 |                        -0.0065 |                           0.3908 |
| gradient_boosted_trees |                  0.2922 |                        -0.0059 |                           0.3563 |
| mlp                    |                  0.281  |                        -0.006  |                           0.3563 |
| ridge                  |                  0.3041 |                        -0.0051 |                           0.3161 |
| siamese_cnn_meta       |                  0.3304 |                        -0.0059 |                           0.3851 |
| traditional_quantile   |                  0.1792 |                        -0.0033 |                           0.1954 |

## Per-Run Stability

|   run | method                 |   n_pairs |   veto_fraction |   tail_fraction_after |   tail_capture | auc    |
|------:|:-----------------------|----------:|----------------:|----------------------:|---------------:|:-------|
|    58 | cnn1d                  |       219 |          0.0502 |                0      |         1      | 0.9816 |
|    58 | gradient_boosted_trees |       219 |          0.1096 |                0      |         1      | 0.9954 |
|    58 | mlp                    |       219 |          0.0639 |                0      |         1      | 1.0000 |
|    58 | ridge                  |       219 |          0.0822 |                0      |         1      | 1.0000 |
|    58 | siamese_cnn_meta       |       219 |          0.0731 |                0      |         1      | 1.0000 |
|    58 | traditional_quantile   |       219 |          0.0868 |                0      |         1      | 0.9355 |
|    59 | cnn1d                  |      2289 |          0.076  |                0.0066 |         0.6111 | 0.8219 |
|    59 | gradient_boosted_trees |      2289 |          0.1009 |                0.0073 |         0.5833 | 0.7829 |
|    59 | mlp                    |      2289 |          0.1022 |                0.0073 |         0.5833 | 0.7639 |
|    59 | ridge                  |      2289 |          0.0878 |                0.0067 |         0.6111 | 0.8360 |
|    59 | siamese_cnn_meta       |      2289 |          0.0699 |                0.008  |         0.5278 | 0.7926 |
|    59 | traditional_quantile   |      2289 |          0.0834 |                0.0124 |         0.2778 | 0.7134 |
|    60 | cnn1d                  |      2424 |          0.12   |                0.0103 |         0.4359 | 0.7009 |
|    60 | gradient_boosted_trees |      2424 |          0.113  |                0.0098 |         0.4615 | 0.7414 |
|    60 | mlp                    |      2424 |          0.111  |                0.0097 |         0.4615 | 0.7262 |
|    60 | ridge                  |      2424 |          0.1167 |                0.0117 |         0.359  | 0.6877 |
|    60 | siamese_cnn_meta       |      2424 |          0.1205 |                0.0103 |         0.4359 | 0.7267 |
|    60 | traditional_quantile   |      2424 |          0.1308 |                0.0128 |         0.3077 | 0.6478 |
|    61 | cnn1d                  |      2799 |          0.0957 |                0.0107 |         0.5263 | 0.7335 |
|    61 | gradient_boosted_trees |      2799 |          0.0915 |                0.0106 |         0.5263 | 0.7684 |
|    61 | mlp                    |      2799 |          0.0882 |                0.0114 |         0.4912 | 0.7571 |
|    61 | ridge                  |      2799 |          0.1029 |                0.0119 |         0.4737 | 0.7340 |
|    61 | siamese_cnn_meta       |      2799 |          0.1004 |                0.0107 |         0.5263 | 0.7539 |
|    61 | traditional_quantile   |      2799 |          0.1033 |                0.0151 |         0.3333 | 0.7059 |
|    62 | cnn1d                  |      2421 |          0.1082 |                0.0051 |         0.5217 | 0.7231 |
|    62 | gradient_boosted_trees |      2421 |          0.1053 |                0.0046 |         0.5652 | 0.7377 |
|    62 | mlp                    |      2421 |          0.1074 |                0.0051 |         0.5217 | 0.7610 |
|    62 | ridge                  |      2421 |          0.102  |                0.0046 |         0.5652 | 0.7505 |
|    62 | siamese_cnn_meta       |      2421 |          0.1016 |                0.0041 |         0.6087 | 0.7601 |
|    62 | traditional_quantile   |      2421 |          0.1041 |                0.0065 |         0.3913 | 0.7271 |
|    63 | cnn1d                  |      1110 |          0.091  |                0.0089 |         0.4706 | 0.7694 |
|    63 | gradient_boosted_trees |      1110 |          0.1    |                0.011  |         0.3529 | 0.6336 |
|    63 | mlp                    |      1110 |          0.109  |                0.0111 |         0.3529 | 0.7245 |
|    63 | ridge                  |      1110 |          0.0982 |                0.01   |         0.4118 | 0.6609 |
|    63 | siamese_cnn_meta       |      1110 |          0.1009 |                0.01   |         0.4118 | 0.6700 |
|    63 | traditional_quantile   |      1110 |          0.0712 |                0.0136 |         0.1765 | 0.7088 |
|    65 | cnn1d                  |       198 |          0.0758 |                0      |         0      |        |
|    65 | gradient_boosted_trees |       198 |          0.096  |                0      |         0      |        |
|    65 | mlp                    |       198 |          0.0909 |                0      |         0      |        |
|    65 | ridge                  |       198 |          0.0303 |                0      |         0      |        |
|    65 | siamese_cnn_meta       |       198 |          0.0455 |                0      |         0      |        |
|    65 | traditional_quantile   |       198 |          0.0101 |                0      |         0      |        |

## Systematics and Caveats

1. **Direct truth is absent locally.**  The claimed direct forced/random
   electronics-pedestal estimand is not measurable from the mounted data folder.
   The fallback winner must not be interpreted as a direct pedestal-truth
   winner.
2. **Mirror completeness.**  Absence in `data/root/root` does not prove the DAQ
   never acquired forced/random pedestals.  It only proves the accessible mirror
   lacks such entries or filenames.
3. **Trigger-code semantics.**  The necessary trigger criterion uses
   `TRIGGER != 1` and explicit filename tokens.  If DAQ provenance is encoded in
   an external log not mounted here, this audit cannot see it.
4. **Fallback target scope.**  The timing-tail label is an independent
   detector-quality target, not a no-pulse electronics label.  It can validate a
   nuisance covariate, not promote it to a pedestal substitute.
5. **Correlated rows.**  Pair rows share events, so CIs bootstrap by run.  This
   captures run transfer but does not fully model within-event dependence.

## Conclusion

The current data folder does not contain DAQ-provenanced B-stack forced/random
pedestal ROOT suitable for direct hidden-mode validation.  The reproduced raw
ROOT number is exact, and the direct audit returns `0` non-beam B-stack entries.
On the explicitly labeled fallback benchmark, **cnn1d** remains the
winner by the frozen rule.  The practical decision is to keep S16 hidden-mode
scores as timing-tail nuisance covariates only until a real forced/random
pedestal acquisition is mirrored with trigger provenance.

## Reproducibility

Command:

```bash
/home/billy/anaconda3/bin/python scripts/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.py --config configs/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.json
```

Input hashes:

| artifact             | path                                                                                     | sha256                                                           |
|:---------------------|:-----------------------------------------------------------------------------------------|:-----------------------------------------------------------------|
| config               | configs/s16q_1783546942_10898_0a8936fb_daq_forced_random_pedestal_root.json              | f78eb915245d3aec0a59ee732a72975fedec5c5ce9b195158bf38c6d7b2f62b8 |
| source_s16k_config   | configs/s16k_1781095392_2104_2cc76ed8_hidden_mode_independent_truth.json                 | 6191e191189a82a25d64ccbc2d31094c5b7ebd9b9a51a126f52582626efdbbb7 |
| source_s16f_config   | configs/s16f_1781031083_1784_78066bc6_pretrigger_veto_loro.json                          | d1e4218a9f321ab64695310682226ab0225d4214cd5804221967045ed2e60d3c |
| heldout_predictions  | reports/1781031083.1784.78066bc6__s16f_pretrigger_veto_loro/heldout_predictions.csv.gz   | 8819128323ee1524337b52890c0620b00fe724e548042aa63572e947156ab194 |
| sample_ii_pair_table | reports/1781031083.1784.78066bc6__s16f_pretrigger_veto_loro/sample_ii_pair_table.csv.gz  | 9ae0d5e9e0a30548b21c92c1dae38f845535c88785faabb85795f85cd6c0525f |
| source_head_to_head  | reports/1781031083.1784.78066bc6__s16f_pretrigger_veto_loro/head_to_head_benchmark.csv   | 19026a75af094f31d8bd362d57492383172698b7ff58260b4fb4db43efbebb3e |
| source_reproduction  | reports/1781031083.1784.78066bc6__s16f_pretrigger_veto_loro/reproduction_match_table.csv | 0cf3bb0ef000657eb7e95142aa27ed387d13c1bb2f716892b22cf2ce3bd52020 |
| source_manifest      | reports/1781031083.1784.78066bc6__s16f_pretrigger_veto_loro/manifest.json                | fb60e412fa5145cc2e9c034dc75326ccd2d101b957e1bc48900519fb54312dc4 |
| source_result        | reports/1781031083.1784.78066bc6__s16f_pretrigger_veto_loro/result.json                  | 45ff0fc85b93890926c790e38ad20c3ba213f0d3612a5992df847009e1e5f0b6 |
| raw_hrdb_run_0012    | data/root/root/hrdb_run_0012.root                                                        | 84f09fe5eabb8f0af30907c82be33dfae19cf1b78d2799ac7141da7e98649cf9 |
| raw_hrdb_run_0013    | data/root/root/hrdb_run_0013.root                                                        | 197371909cb36ea89946a68ece98137bf49a3e349f9b6839b8b29dc4ba2adaef |
| raw_hrdb_run_0014    | data/root/root/hrdb_run_0014.root                                                        | 7c9844c61e99f8f62a395218dcacc26e002e6f7d5b9577c78193999ae367721d |
| raw_hrdb_run_0015    | data/root/root/hrdb_run_0015.root                                                        | a229b6ef8651735b2de0ba40770c497cadfc0203a66b68483c493973eae92b45 |
| raw_hrdb_run_0016    | data/root/root/hrdb_run_0016.root                                                        | 95be7d907516b8bb0f9b39c2ed8acea42e875ee9abe69bc23d08dcac5cacf89f |
| raw_hrdb_run_0017    | data/root/root/hrdb_run_0017.root                                                        | 1d3f22478e067daadaf46e5abd56d855fd051ea96b60c0bbf51309bfee80caa8 |
| raw_hrdb_run_0018    | data/root/root/hrdb_run_0018.root                                                        | 860a6ca70cdb62a751904e3386144500b4062a174e54dc92d6f40f2a15509f13 |
| raw_hrdb_run_0019    | data/root/root/hrdb_run_0019.root                                                        | 3adb7099d18eb008578f661b5549dea8494d55f822ddc5874ea7a318ae90f388 |
| raw_hrdb_run_0020    | data/root/root/hrdb_run_0020.root                                                        | 4e270cfa9eb6b2ae7e26c8df7eb93d807dd1e26db5094935e956d60f6c175fa0 |
| raw_hrdb_run_0021    | data/root/root/hrdb_run_0021.root                                                        | 38b898ee1b21d205ffa22f452b3db93f0db452b873733faf101b3cf8ce3cbd26 |
| raw_hrdb_run_0022    | data/root/root/hrdb_run_0022.root                                                        | 6ab44f4b8c26f8fcd6ca30c2dddebe73d931952f2b666d1bfd68008bdcea0cd2 |
| raw_hrdb_run_0023    | data/root/root/hrdb_run_0023.root                                                        | ec7bfad1c22184d21c1b3a90e48e60ffa1aed323593f529f038f3489ad1eea50 |
| raw_hrdb_run_0024    | data/root/root/hrdb_run_0024.root                                                        | 892b473418d486354346906d502939db8829edaa40e5f7dd09c71726cb497483 |
| raw_hrdb_run_0025    | data/root/root/hrdb_run_0025.root                                                        | 2efd146fc1a059e943ece30b5e73064a75204e9a75c48808471d1574a3f54f1a |
| raw_hrdb_run_0026    | data/root/root/hrdb_run_0026.root                                                        | 72c8d6c536fe74cf3a1cf06657613d1b043a846168a758fe3ac021b00b8d6950 |
| raw_hrdb_run_0027    | data/root/root/hrdb_run_0027.root                                                        | b2b40fa970ef8d3dd3e44d9d71b6e77c740c441bb8429dc7ed6097caf9c92994 |
| raw_hrdb_run_0028    | data/root/root/hrdb_run_0028.root                                                        | ebe54de23d611f7583fe617785802098a116a8c4884e8e3d8ec7ee254e28a503 |
| raw_hrdb_run_0029    | data/root/root/hrdb_run_0029.root                                                        | e166cdf5ddfcb8ce09a34b2a749f6e48cab7334b485c8144bf98e591b0e36c95 |
| raw_hrdb_run_0030    | data/root/root/hrdb_run_0030.root                                                        | 9fea50513af1897c3710b90ffa7541532533da1eca050c3ef844b5a67fd36c70 |
| raw_hrdb_run_0031    | data/root/root/hrdb_run_0031.root                                                        | 9921aa75c062d0b8994573299a201cbe2725673319fdf1b8cffb711fb9adcea7 |
| raw_hrdb_run_0032    | data/root/root/hrdb_run_0032.root                                                        | 649983bf173352b638bf57c099dc92741b70483feba8981172b26319fc9047ff |
| raw_hrdb_run_0033    | data/root/root/hrdb_run_0033.root                                                        | 1b8f1dcda0e53b8c7b702f00801555f6d317a87bed8efef6d228b49146dbf973 |
| raw_hrdb_run_0034    | data/root/root/hrdb_run_0034.root                                                        | 69ef29a8d879aaa908ab4a076c82b3d10ac7b3e2622e491e017eb368290bdf51 |
| raw_hrdb_run_0035    | data/root/root/hrdb_run_0035.root                                                        | a6e08e36ab103e76b53741b55ea7cd3e648d1800508d6144b96ab80820e156ea |
| raw_hrdb_run_0036    | data/root/root/hrdb_run_0036.root                                                        | 1160bee157e233eb63421597b415f1aaf4dea2c1e7e4a804836c487704852fee |
| raw_hrdb_run_0037    | data/root/root/hrdb_run_0037.root                                                        | 6bcebe85c0b1e38a42cc326cbcdc2107ccaee877372bffd537ce71baa1b22fd3 |
| raw_hrdb_run_0039    | data/root/root/hrdb_run_0039.root                                                        | b875c8d45a62a39933d7d4648518040a645629e6fb60c9111a7d05c4d982c568 |
| raw_hrdb_run_0040    | data/root/root/hrdb_run_0040.root                                                        | 0d4ebb2f14673aea000c454fd8a4be2c56d6028c31e26a82c1ecd85578128f17 |
| raw_hrdb_run_0041    | data/root/root/hrdb_run_0041.root                                                        | 72f7a53810bcc4858c2d56e64bdc3bcbb94b9f8e34d35b79c202a77328eb8010 |
| raw_hrdb_run_0042    | data/root/root/hrdb_run_0042.root                                                        | b941a6a777414912a0db865a87f68370accf916348340d2249972018f2e61898 |
| raw_hrdb_run_0043    | data/root/root/hrdb_run_0043.root                                                        | 74e64f1ffa2afcdb179cc8bf1b5d28d6c277f408992aa7077f104edf10eef81e |
| raw_hrdb_run_0044    | data/root/root/hrdb_run_0044.root                                                        | 0ac6d667ebf7c1b47d037dde649e5977cdc6012d80abb6a311516bc67d03ad50 |
| raw_hrdb_run_0045    | data/root/root/hrdb_run_0045.root                                                        | b7bf2921edc3f776390cf50efe6901cb99f9807d7ae04ab5d8925348b74eb96b |
| raw_hrdb_run_0046    | data/root/root/hrdb_run_0046.root                                                        | 7a1f8b5c0e478739401425f3e80bb5469433064137ccbd30266f8e42da135bf3 |
| raw_hrdb_run_0047    | data/root/root/hrdb_run_0047.root                                                        | f73d9328de01147826d0c142caa38baa7d6577ce88b6c6566b57039919015bc3 |
| raw_hrdb_run_0048    | data/root/root/hrdb_run_0048.root                                                        | 73de7b2c54394585869fce573aeeae1075af130741524484dd79a6823183eaf8 |
| raw_hrdb_run_0049    | data/root/root/hrdb_run_0049.root                                                        | 78de20d813d501dfc9881ec9ee7e8297a9c26929d6ed71400238ca4f29664744 |
| raw_hrdb_run_0050    | data/root/root/hrdb_run_0050.root                                                        | 5fa46e1f0ab4eb605501ccf952bfca46eb46be2dffd66672beadd01305dfe799 |
| raw_hrdb_run_0051    | data/root/root/hrdb_run_0051.root                                                        | 6ffc099d12f495df759033caef8c53c05aa24acada928392afe796f3a72c011e |
| raw_hrdb_run_0052    | data/root/root/hrdb_run_0052.root                                                        | 3305bb0a1604afe6c83783d0e5d576d729c217c203eedf3bc44f304dab5fe0af |
| raw_hrdb_run_0053    | data/root/root/hrdb_run_0053.root                                                        | 62307716ee4b31dc7ab0b114401e684508d6f18beb59721a50a9aeddf4feb43c |
| raw_hrdb_run_0054    | data/root/root/hrdb_run_0054.root                                                        | 445650d124d7758e8d3a69d2c3e215e9b95f3acccc213fd9c14bbabacc763e5c |
| raw_hrdb_run_0055    | data/root/root/hrdb_run_0055.root                                                        | 134da5c9a3acb056d5bbed66f057110c506c43d3e0524936906002e56d74007c |
| raw_hrdb_run_0056    | data/root/root/hrdb_run_0056.root                                                        | 4f99f5168a4c02c6d6c2984a53ce979dbfce7ce2790fed220d6957194135d3cb |
| raw_hrdb_run_0057    | data/root/root/hrdb_run_0057.root                                                        | ed7c738068ecb1f6b71ce76da170fc280262a84571fe2ba6129e5015b0b4de16 |
| raw_hrdb_run_0058    | data/root/root/hrdb_run_0058.root                                                        | d2324f6ffa4c05b387c18ff8b48b8589592a1bb9e30d9b3c67d7f5f3f1fe39a1 |
| raw_hrdb_run_0059    | data/root/root/hrdb_run_0059.root                                                        | 64fced477c9c45f9726cde0d466c15a6d776b8bb1b22a0043510dc73c884ae0e |
| raw_hrdb_run_0060    | data/root/root/hrdb_run_0060.root                                                        | f466b5af260d9fadba426280f6313bac1381c1441c569c7094a8a9d61373030d |
| raw_hrdb_run_0061    | data/root/root/hrdb_run_0061.root                                                        | c57d1f18f79f11fb0d3a0bbbf42f978cff1ec704dc08337c600c17354099d61d |
| raw_hrdb_run_0062    | data/root/root/hrdb_run_0062.root                                                        | 2530c56acb462473c6b5c316c0689491ec044f01a8c623624eebafbd271fdfbe |
| raw_hrdb_run_0063    | data/root/root/hrdb_run_0063.root                                                        | 3fd42501e2c53a914b535616bc7bb7b8fb5554cd4f46d890023db6877a720a53 |
| raw_hrdb_run_0064    | data/root/root/hrdb_run_0064.root                                                        | e6661362dc89d934f42d1fa177bcb99e9c89e294b2f157a09ec1df4e50c89252 |
| raw_hrdb_run_0065    | data/root/root/hrdb_run_0065.root                                                        | fd443fd416e8e64b25f4358754c1cc7042a8c3b61c5a13fd82276873807e07bb |
