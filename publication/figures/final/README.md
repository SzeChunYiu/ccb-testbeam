# Final / authorising figures

Only publication-authorising figures belong here.

At the Cycle-3 baseline the central ΔE-E and energy-reconstruction plots are deliberately **not** in this folder. New figures must arrive with a result manifest, source table, claim ID, evidence class, uncertainty definition and exact producer/input hashes.

## data_depth_profile.pdf

Beam-data B-stack depth profile (Sample I vs II). Copied verbatim from `reports/studies/paper_1318_depth_profile/results/depth_profile_thresh_0.pdf` (issues #1318/#1383, regenerated under measured polarity v2).
- Claim ID: CL-1318-002 -- status GATED (`allowed_status_validated=NO`); bound via `\GatedFigure`, not rendered in the publication build. Supersedes CL-1318-001 (FLAWED: produced under polarity v1, falsified for channels 2-7 by #954).
- Key numbers (threshold 0, canonical even channel map): B2 share 35.3% (I) vs 15.3% (II); B8/B2 ratio 0.71 (I) vs 1.94 (II); duplicate-channel (odd) nuisance envelope in `results/duplicate_channel_parity.json` preserves the direction.
- Result manifest: `reports/studies/paper_1318_depth_profile/manifest_8x16.json` (polarity source `configs/channel_polarity_v2.json`)
- Source table: `reports/studies/paper_1318_depth_profile/event_table_8x16.parquet` (1,096,728 events, 33 runs)
- Result JSON: `reports/studies/paper_1318_depth_profile/results/depth_profile_result_thresh_0.json`
- Uncertainty: run-block bootstrap, 1,000 replicates, seed 1318; threshold scan 0/500/750/1000 ADC in `results/threshold_sensitivity.json`
- Producer: `scripts/real_data/build_8x16_event_product.py` + `scripts/real_data/analyze_depth_profile_8x16.py` (v2 regeneration #1383; build head recorded in the result JSON)
## timing_b4_b6_residual.pdf

B4--B6 pair timing residual (Sample II). Copied verbatim from `reports/issue_1320_timing/timing_b4_b6_residual_sample_II.pdf` (issues #1320/#1335, regenerated under measured polarity v2 by #1383).
- Claim ID: CL-1320-002 -- status GATED (`allowed_status_validated=NO`); bound via `\GatedFigure`, not rendered in the publication build. Supersedes CL-1320-001 (FLAWED: consumed polarity-v1 waveforms with wrong-signed B4/B6 channels).
- Result: sigma68 0.146 ns (bootstrap 0.144--0.148 ns), median -9.673 ns (uncalibrated channel skew), 228,697 complete pairs, 7 runs (58--63, 65), amplitude cut 1000 ADC
- Producer: `scripts/issue_1320_timing_residual.py` (polarity `configs/channel_polarity_v2.json`; run head recorded in `reports/issue_1320_timing/result.json`)
- Gates: synthetic two-pulse and wrong-component validations PASS under v2, but the constant -9.7 ns inter-channel offset, real-pulse component identity and timing-reference definitions are unresolved; PAIR RESIDUAL, not detector resolution; no sqrt(2) deconvolution
- 1303_stage_accounting.pdf -- #1303 optical stage accounting (MC_MODEL_DEPENDENT)
- 1303_pe_per_mev.pdf -- #1303 per-point PE/MeV_vis + PE/MeV_raw yields (MC_MODEL_DEPENDENT)
- 1303_edep_vs_pe.pdf -- #1303 detected PE vs deposited energy scatter (MC_MODEL_DEPENDENT)
- ccb_layout.pdf -- #1317 two-arm CCB layout schematic, BOM-annotated (SIM_CONFIG)
- stave_geometry.pdf -- #1317 B-stack stave geometry, BOM-annotated (DESIGN_SPEC)
- channel_map.pdf -- #1317 B2/B4/B6/B8 channel-to-layer map with #869 parity caveat (SIM_CONFIG)
- mc_depth_profile.pdf -- #1319 MC depth profile, species-resolved + B2/B4/B6/B8 parity nuisance (SIMULATION_RESULT)
