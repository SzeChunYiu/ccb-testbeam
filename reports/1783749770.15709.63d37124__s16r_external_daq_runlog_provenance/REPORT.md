# S16r: external DAQ runlog provenance for B-stack forced/random pedestal mirror

## Abstract

S16r asks whether external DAQ runlog, scaler, or converter metadata can identify non-beam B-stack forced/random pedestal triggers outside the mounted ROOT mirror. I rescanned the mounted B-stack ROOT files, inventoried ROOT trigger codes and branch metadata, searched the mounted data tree for runlog/scaler/DAQ/converter-like files and filename tokens, and then ran the requested run-split traditional/ML/NN benchmark as a **quiet beam-triggered proxy** because the direct forced/random target is `absent`.

The raw ROOT reproduction gate gives **640,737** selected B-stack pulses versus the canonical **640,737** (delta `+0`). The provenance audit finds **0** non-beam `TRIGGER != 1` entries and **0** forced/random/pedestal keyword ROOT files. Thus the current data folder supports a mirror-absence conclusion, not a direct electronics-pedestal validation.

## Data and Reproduction

The count was recomputed from `h101/HRDv` in `/home/billy/ccb-data/extracted/root/root`. For event `e`, channel `c`, sample `s`, the waveform is reshaped to `8 x 18`; the baseline is

`b_ec = median(x_ecs : s in {0,1,2,3})`.

The selected-pulse indicator is

`I_ec = 1[max_s(x_ecs - b_ec) > 1000 ADC]`

for even B-stack staves B2/B4/B6/B8. The reproduction number is

`N_sel = sum_e sum_c I_ec = 640,737`.

| quantity | expected | observed | delta | pass |
|---|---:|---:|---:|---|
| selected B-stack pulses, A > 1000 ADC | 640,737 | 640,737 | +0 | True |

## External Provenance Audit

The audit tested three observable routes to an external forced/random sample:

1. `TRIGGER` branch values in every visible B-stack ROOT file.
2. Filename/path tokens: forced, random, pedestal, no-pulse, trigger, scaler, runlog, daq, converter.
3. Text-like sidecars under configured data roots that could be DAQ logs, scaler tables, converter manifests, or run-control exports.

| audit target | observed |
|---|---:|
| B-stack ROOT files scanned | 53 |
| total ROOT entries | 1,649,802 |
| unique trigger values | [1] |
| non-beam trigger entries | 0 |
| keyword source files | 3 |
| keyword ROOT files | 0 |
| external text-like files | 16 |

No mounted runlog, scaler, or converter metadata provides an independent run-mode label for non-beam B-stack forced/random triggers. This does not prove such data were never acquired; it proves they are not discoverable in the mounted data tree and ROOT metadata scanned here.

## Proxy Benchmark Estimand

Because no direct labels exist, the model comparison is explicitly a stress test of local electronics-pedestal predictability in quiet beam-triggered events. Events enter the proxy panel when all configured B staves have baseline-corrected maximum below `80` ADC. For target samples `t in [4, 5, 6, 7, 8, 9]`, the target is

`y_i = x_i,t - median(x_i,0:3)`.

Models use only target-excluded pretrigger summaries and categorical stave/sample encodings. Training uses runs `[44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57]`; held-out evaluation uses runs `[58, 59, 60, 61, 62, 63, 65]`. Confidence intervals are nonparametric run-block bootstrap intervals over held-out runs.

## Methods

The traditional comparator is `traditional_pretrigger_median`, i.e.

`yhat_i = median(x_i,0:3 - b_i)`.

The learned methods are ridge regression, histogram gradient-boosted trees, an MLP, a compact 1D-CNN over the standardized feature sequence, and a new `pretrigger_gated_cnn` that gates convolutional features with a learned sigmoid function of the same target-excluded metadata. The gating architecture is sensible here because the S16 lineage suspects hidden pedestal modes; it tests whether a low-capacity nonlinear gate can adapt to run/stave/sample-dependent offsets without using the target sample.

## Results

The quiet-proxy panel has `135,000` rows; `45,000` are used for training and `45,906` are held out by run. The direct forced/random winner is `none` because there are no direct labels. For the proxy benchmark, `result.json` names **gradient_boosted_trees** as the winner by lowest held-out MAE.

| method | MAE ADC, run-bootstrap 95% CI | RMSE ADC, run-bootstrap 95% CI | bias ADC | held-out rows |
|---|---:|---:|---:|---:|
| gradient_boosted_trees | 14.899 [14.460, 15.369] | 32.304 [26.986, 37.604] | -0.573 | 45906 |
| mlp | 15.486 [15.096, 15.847] | 31.192 [27.089, 35.778] | 1.980 | 45906 |
| one_dimensional_cnn | 17.228 [16.590, 17.722] | 46.479 [34.963, 56.477] | 1.476 | 45906 |
| pretrigger_gated_cnn | 17.260 [16.740, 17.794] | 46.522 [36.546, 55.947] | 2.069 | 45906 |
| traditional_pretrigger_median | 17.391 [16.707, 17.936] | 46.698 [35.364, 58.039] | 2.642 | 45906 |
| ridge | 21.710 [21.163, 22.151] | 40.830 [34.517, 46.922] | -2.604 | 45906 |

## Systematics and Caveats

- The primary S16r conclusion is an availability/provenance result: the mounted data tree lacks external DAQ/runlog/scaler/converter evidence for non-beam B-stack forced/random pedestal triggers.
- The proxy benchmark is not a direct validation of forced/random electronics pedestals. It is conditioned on beam-triggered quiet events and can inherit trigger selection, pile-up veto, and baseline-window biases.
- The raw ROOT count reproduction is exact, so the absence result is not caused by a failed B-stack loader or a mismatched run list.
- The CNN methods use a compact CPU-budget architecture. A negative neural result is a reproducible benchmark outcome under this budget, not a theorem about waveform architectures.
- The next useful ticket is data-provenance recovery, not another proxy-only benchmark.

## Artifacts

`result.json`, `manifest.json`, `reproduction_match_table.csv`, `selected_counts_by_run.csv`, `root_trigger_audit.csv`, `root_branch_inventory.csv`, `external_source_inventory.csv`, `quiet_proxy_panel_preview.csv`, `heldout_predictions.csv.gz`, `per_run_method_summary.csv`, and `method_summary.csv` are in this report directory.
