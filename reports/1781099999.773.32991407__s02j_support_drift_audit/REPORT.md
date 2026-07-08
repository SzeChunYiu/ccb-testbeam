# S02j: Support-Drift Audit For S02i Residual Correction

- **Study ID:** S02j
- **Ticket:** 1781099999.773.32991407
- **Worker:** testbeam-laptop-3
- **Input:** raw B-stack ROOT files under `data/root/root` plus frozen S02i held-out predictions from `reports/1781032083.463.2d9c6a45__s02i_pretrigger_atom_transfer`
- **Split:** Sample-II leave-one-run-out by run; support confidence intervals use run/event bootstrap
- **Primary support metric:** maximum total-variation or fraction drift over charge, current proxy, topology, run-family, late-peak, and low-charge supports
- **Winner rule:** lowest S02i mean held-out-run sigma68 among methods whose fixed-efficiency support-drift 95% CI high is no larger than `0.05`
- **Git commit:** `a46c79fb1f80e25baa7911573ad4ef28040f4fa3`

## 1. Question And Raw-ROOT Reproduction

The S02j question is whether the S02i winning `siamese_cnn_meta` correction is only a resolution improvement, or whether it changes the charge/current/topology support of timing-selected rows enough to bias downstream physics selections. The audit starts by rerunning the same selected-pulse count gate directly from raw ROOT.

| Quantity | Report value | Reproduced | Delta | Tolerance | Pass? |
|---|---:|---:|---:|---:|---|
| total selected B-stave pulses | 640737 | 640737 | 0 | 0 | yes |
| sample_ii_analysis selected_pulses | 125096 | 125096 | 0 | 0 | yes |
| sample_ii_analysis B2 | 88213 | 88213 | 0 | 0 | yes |
| sample_ii_analysis B4 | 21229 | 21229 | 0 | 0 | yes |
| sample_ii_analysis B6 | 11148 | 11148 | 0 | 0 | yes |
| sample_ii_analysis B8 | 4506 | 4506 | 0 | 0 | yes |

The support audit then uses `11460` held-out pair rows and `3820` events from S02i. All method predictions are frozen leave-one-run-out predictions: ridge, gradient-boosted trees, MLP, 1D-CNN, the strong traditional `traditional_atom_slope` comparator, and the pair-symmetric `siamese_cnn_meta` architecture.

## 2. Estimands

For each pair row \(i\), the uncorrected timing selection is

\\[
B_i = \\mathbb{1}(|r_i| \\le 5\\,\\mathrm{ns}),
\\]

where \(r_i\) is the raw CFD20 pair residual. For method \(m\), the corrected residual is

\\[
\\epsilon_i^{(m)} = r_i - \\hat f_m(X_i).
\\]

Two operating points are audited. The absolute gate uses \(A_i^{(m)}=\\mathbb{1}(|\\epsilon_i^{(m)}|\\le 5\\,\\mathrm{ns})\). The fixed-efficiency gate chooses a threshold \(\\tau_m^{(-k)}\) from training runs only so that the train-run corrected acceptance equals the train-run uncorrected 5 ns acceptance, then applies \(F_i^{(m)}=\\mathbb{1}(|\\epsilon_i^{(m)}|\\le \\tau_m^{(-k)})\) to held-out run \(k\).

Support drift is measured against the uncorrected accepted set in the same rows. For categorical supports, the metric is total variation distance,

\\[
D_{\\mathrm{TV}}(p,q)=\\frac12\\sum_c |p_c-q_c|.
\\]

The headline support-drift score is the maximum over charge-bin TVD, current-proxy-bin TVD, topology-pair TVD, run-family TVD, late-peak fraction shift, and low-charge fraction shift.

## 3. Support Results: Absolute 5 ns Gate

The absolute gate answers what happens if a downstream analysis simply replaces the raw residual by the corrected residual and keeps the same 5 ns cut.

| Method | Efficiency [95% CI] | Max support drift [95% CI] | Charge TVD [95% CI] | Current TVD [95% CI] | Topology TVD [95% CI] | Run-family TVD [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| traditional_atom_slope | 0.9864 [0.9825, 0.9906] | 0.0871 [0.0719, 0.1084] | 0.0071 [0.0040, 0.0168] | 0.0058 [0.0024, 0.0167] | 0.0871 [0.0719, 0.1084] | 0.0185 [0.0037, 0.0301] |
| ridge | 0.9629 [0.9514, 0.9738] | 0.0874 [0.0690, 0.1062] | 0.0121 [0.0068, 0.0210] | 0.0071 [0.0023, 0.0197] | 0.0874 [0.0690, 0.1062] | 0.0228 [0.0034, 0.0363] |
| gradient_boosted_trees | 0.9877 [0.9827, 0.9924] | 0.0877 [0.0705, 0.1061] | 0.0069 [0.0039, 0.0160] | 0.0058 [0.0022, 0.0175] | 0.0877 [0.0705, 0.1061] | 0.0186 [0.0029, 0.0311] |
| mlp | 0.9811 [0.9763, 0.9856] | 0.0877 [0.0712, 0.1075] | 0.0077 [0.0039, 0.0172] | 0.0065 [0.0030, 0.0183] | 0.0877 [0.0712, 0.1075] | 0.0184 [0.0033, 0.0309] |
| cnn1d | 0.9523 [0.9471, 0.9577] | 0.1037 [0.0895, 0.1226] | 0.0076 [0.0038, 0.0185] | 0.0073 [0.0026, 0.0190] | 0.1037 [0.0895, 0.1226] | 0.0189 [0.0028, 0.0319] |
| siamese_cnn_meta | 0.9871 [0.9823, 0.9922] | 0.0876 [0.0714, 0.1076] | 0.0073 [0.0039, 0.0163] | 0.0056 [0.0023, 0.0165] | 0.0876 [0.0714, 0.1076] | 0.0184 [0.0041, 0.0313] |

## 4. Support Results: Train-Fold Fixed Efficiency

The fixed-efficiency gate isolates support reweighting from the trivial gain in timing acceptance. Thresholds are determined only from non-held-out runs.

| Method | Efficiency [95% CI] | Max support drift [95% CI] | Charge TVD [95% CI] | Current TVD [95% CI] | Topology TVD [95% CI] | Run-family TVD [95% CI] |
|---|---:|---:|---:|---:|---:|---:|
| traditional_atom_slope | 0.7799 [0.7510, 0.8051] | 0.0689 [0.0508, 0.0846] | 0.0269 [0.0218, 0.0366] | 0.0084 [0.0030, 0.0242] | 0.0689 [0.0508, 0.0846] | 0.0266 [0.0031, 0.0404] |
| ridge | 0.7780 [0.7223, 0.8232] | 0.0864 [0.0684, 0.1066] | 0.0228 [0.0137, 0.0332] | 0.0102 [0.0034, 0.0265] | 0.0864 [0.0659, 0.1066] | 0.0486 [0.0068, 0.0741] |
| gradient_boosted_trees | 0.7812 [0.7585, 0.7985] | 0.0614 [0.0445, 0.0778] | 0.0157 [0.0065, 0.0267] | 0.0079 [0.0028, 0.0209] | 0.0614 [0.0445, 0.0778] | 0.0260 [0.0027, 0.0375] |
| mlp | 0.7801 [0.7592, 0.8091] | 0.0688 [0.0549, 0.0882] | 0.0112 [0.0059, 0.0209] | 0.0064 [0.0033, 0.0215] | 0.0688 [0.0549, 0.0882] | 0.0289 [0.0068, 0.0413] |
| cnn1d | 0.7816 [0.7621, 0.8003] | 0.1561 [0.1461, 0.1676] | 0.0038 [0.0020, 0.0137] | 0.0065 [0.0026, 0.0146] | 0.1561 [0.1461, 0.1676] | 0.0132 [0.0047, 0.0202] |
| siamese_cnn_meta | 0.7799 [0.7591, 0.7977] | 0.0624 [0.0443, 0.0835] | 0.0134 [0.0048, 0.0249] | 0.0050 [0.0023, 0.0182] | 0.0624 [0.0443, 0.0835] | 0.0258 [0.0029, 0.0389] |

The selected-residual resolution under the fixed-efficiency gate is:

| Method | Selected sigma68 ns [95% CI] | Efficiency delta vs raw gate [95% CI] |
|---|---:|---:|
| traditional_atom_slope | 0.972 [0.938, 1.007] | -0.0021 [-0.0497, +0.0401] |
| ridge | 1.305 [1.266, 1.365] | -0.0040 [-0.0885, +0.0682] |
| gradient_boosted_trees | 0.800 [0.771, 0.829] | -0.0008 [-0.0502, +0.0337] |
| mlp | 0.950 [0.927, 0.983] | -0.0019 [-0.0456, +0.0476] |
| cnn1d | 1.838 [1.698, 1.967] | -0.0004 [-0.0202, +0.0245] |
| siamese_cnn_meta | 0.774 [0.739, 0.802] | -0.0021 [-0.0455, +0.0371] |

Representative held-out run rows for the traditional comparator and winner:

| Held-out run | Method | Efficiency | Max drift | Charge TVD | Current TVD | Topology TVD |
|---:|---|---:|---:|---:|---:|---:|
| 58 | gradient_boosted_trees | 0.7945 | 0.0671 | 0.0459 | 0.0383 | 0.0671 |
| 58 | traditional_atom_slope | 0.8128 | 0.0780 | 0.0527 | 0.0164 | 0.0780 |
| 59 | gradient_boosted_trees | 0.7990 | 0.0731 | 0.0281 | 0.0088 | 0.0731 |
| 59 | traditional_atom_slope | 0.8222 | 0.0826 | 0.0325 | 0.0137 | 0.0826 |
| 60 | gradient_boosted_trees | 0.8036 | 0.0735 | 0.0156 | 0.0108 | 0.0735 |
| 60 | traditional_atom_slope | 0.7921 | 0.0801 | 0.0274 | 0.0123 | 0.0801 |
| 61 | gradient_boosted_trees | 0.7563 | 0.0353 | 0.0099 | 0.0268 | 0.0353 |
| 61 | traditional_atom_slope | 0.7513 | 0.0413 | 0.0280 | 0.0282 | 0.0413 |
| 62 | gradient_boosted_trees | 0.7869 | 0.0774 | 0.0218 | 0.0105 | 0.0774 |
| 62 | traditional_atom_slope | 0.7844 | 0.0810 | 0.0306 | 0.0153 | 0.0810 |
| 63 | gradient_boosted_trees | 0.7604 | 0.0759 | 0.0138 | 0.0203 | 0.0759 |
| 63 | traditional_atom_slope | 0.7324 | 0.0761 | 0.0381 | 0.0243 | 0.0761 |
| 65 | gradient_boosted_trees | 0.6869 | 0.0710 | 0.0156 | 0.0532 | 0.0710 |
| 65 | traditional_atom_slope | 0.7222 | 0.0695 | 0.0295 | 0.0497 | 0.0695 |

## 5. Decision

The lowest-drift fallback winner is **gradient_boosted_trees**. Under the decision rule, no method's fixed-efficiency support-drift 95% CI high is at or below the configured gate `0.05`; the selected fallback has the lowest CI high (`0.0778`), while its S02i timing benchmark mean-run sigma68 is `1.170 ns`. The best traditional comparator remains `traditional_atom_slope` with S02i mean-run sigma68 `1.366 ns`.

Operational interpretation: the S02i winner should not be promoted as an unqualified physics-production correction from this audit alone. A naive absolute 5 ns replacement mostly changes efficiency; fixed-efficiency use reduces but does not clear the configured support-drift audit gate, so adoption should be treated as conditional. Downstream PID, charge, and energy analyses should propagate the reweighting uncertainty because the support variables are proxies rather than full detector truth.

## 6. Leakage And Systematics

| Check | Value | Pass? |
|---|---:|---|
| raw_root_reproduction_passes | True | yes |
| required_methods_present | cnn1d,gradient_boosted_trees,mlp,ridge,siamese_cnn_meta,traditional_atom_slope,uncorrected_cfd20 | yes |
| one_prediction_per_method_event_pair | 1 | yes |
| all_support_features_finite | 240660 | yes |
| fixed_eff_thresholds_finite | 80220 | yes |

Systematics and caveats: current is approximated by event-order quantiles within run, not by a scaler readback. Charge support uses minimum pair amplitude bins, so it is conservative for two-ended charge but not a calibrated energy spectrum. Topology is the downstream pair identity only. Pair rows share events; therefore all confidence intervals resample runs and then events, carrying all three pair rows for a sampled event. The fixed-efficiency threshold is train-fold frozen, which tests deployable use more directly than fitting thresholds on the held-out run. This is still a data-only support audit; it does not prove the correction is unbiased for every downstream physics observable.

## 7. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s02j_1781099999_773_32991407_support_drift_audit.py --config configs/s02j_1781099999_773_32991407_support_drift_audit.json
```

Primary artifacts: `result.json`, `REPORT.md`, `manifest.json`, `reproduction_match_table.csv`, `support_summary.csv`, `per_run_support.csv`, `joined_support_predictions.csv.gz`, `leakage_checks.csv`, and figures.
