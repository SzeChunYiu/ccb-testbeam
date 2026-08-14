# Final / authorising figures

Only publication-authorising figures belong here.

At the Cycle-3 baseline the central ΔE-E and energy-reconstruction plots are deliberately **not** in this folder. New figures must arrive with a result manifest, source table, claim ID, evidence class, uncertainty definition and exact producer/input hashes.

## data_depth_profile.pdf

Beam-data B-stack depth profile (Sample I vs II). Copied verbatim from `reports/studies/paper_1318_depth_profile/results/depth_profile_thresh_0.pdf` (issue #1318).
- Claim ID: CL-1318-001 -- status GATED (`allowed_status_validated=NO`); bound via `\GatedFigure`, not rendered in the publication build.
- Result manifest: `reports/studies/paper_1318_depth_profile/manifest_8x16.json`
- Source table: `reports/studies/paper_1318_depth_profile/event_table_8x16.parquet` (1,096,728 events, 33 runs)
- Result JSON: `reports/studies/paper_1318_depth_profile/results/depth_profile_result_thresh_0.json`
- Uncertainty: run-block bootstrap, 1,000 replicates, seed 1318; threshold scan 0/500/750/1000 ADC in `results/threshold_sensitivity.json`
- Producer: `scripts/real_data/analyze_depth_profile_8x16.py` @ `a4908de2794249810c3c700a4903cfb1020ba67c`
## timing_b4_b6_residual.pdf

B4--B6 pair timing residual (Sample II). Copied verbatim from `reports/issue_1320_timing/timing_b4_b6_residual_sample_II.pdf` (issues #1320/#1335).
- Claim ID: CL-1320-001 -- status GATED (`allowed_status_validated=NO`); bound via `\GatedFigure`, not rendered in the publication build.
- Result: sigma68 8.748 ns (bootstrap 8.295--9.270 ns), median -44.254 ns, 10,776 events, 7 runs (58--63, 65)
- Producer: `scripts/issue_1320_timing_residual.py` @ `e455257127d598d6d8b86788e7722f108b5ea181`
- Gate: synthetic two-pulse component recovery failed (0.0%); PAIR RESIDUAL, not detector resolution; no sqrt(2) deconvolution
