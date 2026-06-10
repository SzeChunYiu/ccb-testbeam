# S10k operational Rmax failure-definition frontier

- **Ticket:** `1781029239.771.51c16bca`
- **Worker:** `testbeam-laptop-1`
- **Inputs:** raw B-stack ROOT runs 44-57 plus frozen raw-root-derived S10e/S10g/S10i artifacts; no Monte Carlo.
- **Split:** source-run-held-out S10e/S10d/S10g/S10i method outputs; CIs are held-out/source-run bootstrap intervals propagated through the frontier.

## Reproduction first

The script first rereads raw ROOT `HRDv` waveforms and reproduces the S10 topology/downstream gates before using any frozen artifacts. The gate passed 6/6 checks.

| quantity                                 |   report_value |   reproduced |        delta |   tolerance | pass   |
|:-----------------------------------------|---------------:|-------------:|-------------:|------------:|:-------|
| low_2nA multi_stave_per_selected_event   |         0.0156 |    0.0155875 | -1.247e-05   |      0.0015 | True   |
| low_2nA three_stave_per_selected_event   |         0.0041 |    0.004111  |  1.09969e-05 |      0.0015 | True   |
| low_2nA downstream_per_selected_event    |         0.0231 |    0.0231244 |  2.43577e-05 |      0.0015 | True   |
| high_20nA multi_stave_per_selected_event |         0.0268 |    0.0268063 |  6.29596e-06 |      0.0015 | True   |
| high_20nA three_stave_per_selected_event |         0.0085 |    0.0085379 |  3.78959e-05 |      0.0015 | True   |
| high_20nA downstream_per_selected_event  |         0.0334 |    0.0334141 |  1.41048e-05 |      0.0015 | True   |

The frozen S10e high-stat anchor used here is:

| anchor                                                                |     value |   ci95_low |   ci95_high |   reproduction_delta_vs_s10d_traditional |
|:----------------------------------------------------------------------|----------:|-----------:|------------:|-----------------------------------------:|
| S10e dominant high-stat traditional secondary fraction high-minus-low | 0.0330105 |  0.0191867 |   0.0487578 |                                        0 |

## Frontier construction

For each 5%, 10%, 20%, and noise-floor live-time definition, the operational window is `max(live-time tau, required two-pulse recovery delay)`. Rmax is the downstream Poisson planning constant 380.0 divided by that operational tau in ns.

Best Rmax per live-time source and method:

| live_time_source           | analysis_method   | threshold_label   | failure_definition              |   operational_tau_ns |   rmax_mhz |   rmax_ci95_low_mhz |   rmax_ci95_high_mhz | dominant_limit   |
|:---------------------------|:------------------|:------------------|:--------------------------------|---------------------:|-----------:|--------------------:|---------------------:|:-----------------|
| censored_exponential       | ml                | 20%               | combined_planning               |              690.892 |   0.550013 |            0.412686 |             0.811197 | live_time        |
| censored_exponential       | traditional       | 20%               | timing_bias2ns_charge_bias20pct |              690.892 |   0.550013 |            0.412686 |             0.811197 | live_time        |
| ml_ipcw_aft                | ml                | 20%               | timing_bias2ns_charge_bias20pct |              127.377 |   2.98326  |            2.80288  |             3.17665  | live_time        |
| ml_ipcw_aft                | traditional       | 20%               | sigma68_8ns_charge_res68_12pct  |              127.377 |   2.98326  |            2.80288  |             3.17665  | live_time        |
| template_exponential_cross | ml                | 20%               | timing_bias1ns_charge_bias20pct |              101.865 |   3.73042  |            3.69474  |             3.76585  | live_time        |
| template_exponential_cross | traditional       | 20%               | combined_planning               |              101.865 |   3.73042  |            3.69474  |             3.76585  | live_time        |

Template-crossing tau definitions give Rmax values from 2.358 to 3.730 MHz. Censored-exponential tau definitions give 0.134 to 0.550 MHz, while ML-IPCW tau gives 0.937 to 2.983 MHz.

## ML versus traditional

For the headline bias1/area20 criterion under template live-times:

| threshold_definition   |   ml_minus_traditional_rmax_mhz |   ml_minus_traditional_timing_rms_ns |   ml_minus_traditional_charge_bias_fraction |   ml_minus_traditional_charge_res68_fraction |   ml_minus_traditional_failure_rate |
|:-----------------------|--------------------------------:|-------------------------------------:|--------------------------------------------:|---------------------------------------------:|------------------------------------:|
| 10pct                  |                               0 |                             -4.41844 |                                   0.0222756 |                                   -0.0152727 |                            0.151667 |
| 20pct                  |                               0 |                             -4.41844 |                                   0.0222756 |                                   -0.0152727 |                            0.151667 |
| 5pct                   |                               0 |                             -4.41844 |                                   0.0222756 |                                   -0.0152727 |                            0.151667 |
| noise_floor            |                               0 |                             -4.41844 |                                   0.0222756 |                                   -0.0152727 |                            0.151667 |

The ML recovery arm has lower accepted-event timing RMS and smaller charge bias/res68, but a higher fit-failure rate. Rmax deltas are mostly zero because all S10g live-time choices are longer than the 20-60 ns recovery frontier, so threshold/live-time definitions dominate the operational limit.

## Leakage review

| source         | check                                       |   value | flag   | note                                                                              |
|:---------------|:--------------------------------------------|--------:|:-------|:----------------------------------------------------------------------------------|
| s10e_highstat  | leakage_flags                               |       0 | False  | S10e high-stat leakage table                                                      |
| s10g_censored  | leakage_flags                               |       0 | False  | S10g censored ML leakage table                                                    |
| s10i_real_pair | leakage_flags                               |       0 | False  | S10i real-pair leakage table                                                      |
| s10k_frontier  | live_time_dominates_all_crossed_definitions |       1 | False  | Not leakage: explains why ML-minus-traditional Rmax deltas are zero in many rows. |

## Conclusion

The stable planning frontier is not a single pooled Rmax. With template crossing live-times it is 2.36-3.73 MHz depending on threshold; explicit censoring lowers that to 0.13-0.55 MHz. Changing the two-pulse failure criterion changes the required recovery delay, but in this S10k cross-product every 5%/10%/20%/noise-floor live-time tau exceeds the recovery delays, so live-time/threshold choice dominates Rmax. No leakage flags were found.

## Artifacts

`result.json`, `manifest.json`, `input_sha256.csv`, `raw_topology_by_run.csv`, `reproduction_match_table.csv`, `live_time_definitions.csv`, `failure_requirements.csv`, `operational_frontier.csv`, `ml_minus_traditional_deltas.csv`, and `leakage_checks.csv` are in this folder.

Runtime: 2.36 s.
