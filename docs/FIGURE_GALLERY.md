# CCB paper-grade figure gallery

Generated from `docs/figures/paper/manifest.json`. Captions are external to the image so the plot area remains uncluttered. PDF and SVG versions sit beside every PNG.

## FIG-WIKI-001 — Selected-pulse inventory

**Question:** How are the exact S00 analysis pulses distributed across samples and staves?

![Selected-pulse inventory](figures/paper/selected_pulse_inventory.png)

**Status:** `GATED` · **Evidence:** `DATA_MEASUREMENT`

Exact S00 reproduction. Sample I is dominated by B2; Sample II reaches deeper staves more often. Counts are deterministic for the fixed raw inputs and selection; CL-001 remains GATED pending data-contract closure (#952/#953/#954), so this figure is not an authorising ledger row.

[PDF](figures/paper/selected_pulse_inventory.pdf) · [SVG](figures/paper/selected_pulse_inventory.svg) · [source CSV](figures/paper/source_tables/selected_pulse_inventory_source.csv)

## FIG-WIKI-002 — Claim ledger is mostly gated or blocked

**Question:** What fraction of the project claim surface is currently publication-authorized?

![Claim ledger is mostly gated or blocked](figures/paper/claim_status_overview.png)

**Status:** `REVIEW` · **Evidence:** `GOVERNANCE_LEDGER`

Status counts from the canonical claim ledger (docs/claim_ledger.csv). Visual polish must not promote gated, blocked, flawed or superseded evidence.

[PDF](figures/paper/claim_status_overview.pdf) · [SVG](figures/paper/claim_status_overview.svg) · [source CSV](figures/paper/source_tables/claim_status_overview_source.csv)

## FIG-WIKI-003 — Timing estimator closure on MC

**Question:** How much does the four-sensor estimator improve the MC residual width?

![Timing estimator closure on MC](figures/paper/timing_mc_method_closure.png)

**Status:** `MC_METHOD_CLOSURE` · **Evidence:** `MC_METHOD_CLOSURE`

Krakow MC method closure. The combined four-sensor estimator reaches σ68 = 0.089 ns; this is not a detector timing measurement on beam data.

[PDF](figures/paper/timing_mc_method_closure.pdf) · [SVG](figures/paper/timing_mc_method_closure.svg) · [source CSV](figures/paper/source_tables/timing_mc_method_closure_source.csv)

## FIG-WIKI-004 — Grouped-fold PID stability on MC

**Question:** Is the realistic-chain proton/deuteron AUC stable across grouped folds?

![Grouped-fold PID stability on MC](figures/paper/pid_mc_validation.png)

**Status:** `SIMULATION_RESULT` · **Evidence:** `SIMULATION_RESULT`

Five contiguous event-block folds from the realistic ΔE–E MC chain. Fold ordering is categorical, so points are deliberately not connected. Transfer to beam data remains unvalidated.

[PDF](figures/paper/pid_mc_validation.pdf) · [SVG](figures/paper/pid_mc_validation.svg) · [source CSV](figures/paper/source_tables/pid_mc_validation_source.csv)

## FIG-WIKI-005 — Gain closure and gated data/MC proxy

**Question:** How does MC digitizer closure compare with the gated MV0 data/MC proxy?

![Gain closure and gated data/MC proxy](figures/paper/adc_mc_calibration.png)

**Status:** `GATED` · **Evidence:** `MC_CLOSURE_PLUS_GATED_DATA_MC_PROXY`

MC fits recover 119.168 ADC/MeV for both species near the configured 120 ADC/MeV. The separate MV0 proxy is 92 ADC/MeV with a 28 ADC/MeV heuristic systematic envelope, not a confidence interval, and remains gated.

[PDF](figures/paper/adc_mc_calibration.pdf) · [SVG](figures/paper/adc_mc_calibration.svg) · [source CSV](figures/paper/source_tables/adc_mc_calibration_source.csv)

## FIG-WIKI-006 — Birks-model dependence on MC

**Question:** How strongly does the inferred Birks coefficient depend on the fitting observable?

![Birks-model dependence on MC](figures/paper/birks_mc_comparison.png)

**Status:** `SIMULATION_RESULT` · **Evidence:** `SIMULATION_RESULT`

The per-track dE/dx fit gives kB = 0.0156 cm/MeV, above both the total-deposit proxy and the digitizer default. The spread is model dependence, not a confidence interval.

[PDF](figures/paper/birks_mc_comparison.pdf) · [SVG](figures/paper/birks_mc_comparison.svg) · [source CSV](figures/paper/source_tables/birks_mc_comparison_source.csv)

## FIG-WIKI-007 — Digitizer-domain overlap scan

**Question:** Which event rates correspond to the stored 5% and 10% overlap scan points?

![Digitizer-domain overlap scan](figures/paper/pileup_digitizer_mc.png)

**Status:** `SIMULATION_RESULT` · **Evidence:** `SIMULATION_RESULT`

Poisson overlap for the 180 ns acquisition window. The stored nearest scan points are 0.289 MHz (5.06%, not exactly 5%) and 0.605 MHz (10.31%, not exactly 10%). These are simulation-domain criteria; canonical detector Rmax remains blocked.

[PDF](figures/paper/pileup_digitizer_mc.pdf) · [SVG](figures/paper/pileup_digitizer_mc.svg) · [source CSV](figures/paper/source_tables/pileup_digitizer_mc_source.csv)

## FIG-WIKI-008 — B8 stopping assignment disagrees

**Question:** How large is the exact B8 fraction mismatch in the legacy data/MC stopping profile?

![B8 stopping assignment disagrees](figures/paper/stopping_b8_tension.png)

**Status:** `TENSION` · **Evidence:** `LEGACY_DATA_MC_DIAGNOSTIC`

Exact tracked counts give 2.30% in selected data and 22.29% in thresholded MC. Wilson intervals show counting uncertainty only; unresolved geometry, trigger, gain and selection transfer dominate the scientific interpretation.

[PDF](figures/paper/stopping_b8_tension.pdf) · [SVG](figures/paper/stopping_b8_tension.svg) · [source CSV](figures/paper/source_tables/stopping_b8_tension_source.csv)

## FIG-WIKI-009 — Early-peak morphology in truth MC

**Question:** How frequent is the early-peak morphology overall and within truth-labelled C12 tracks?

![Early-peak morphology in truth MC](figures/paper/anomaly_truth_mc.png)

**Status:** `TRUTH_LEVEL_MC_ONLY` · **Evidence:** `TRUTH_LEVEL_MC_ONLY`

Truth-labelled MC rates with Wilson 95% intervals: 283/87,555 overall and 156/7,302 within C12. C12 forms 156/283 early-peak tracks, but the separate beam-data anomaly is not identified as C12.

[PDF](figures/paper/anomaly_truth_mc.pdf) · [SVG](figures/paper/anomaly_truth_mc.svg) · [source CSV](figures/paper/source_tables/anomaly_truth_mc_source.csv)

## FIG-WIKI-010 — Synthetic-waveform PCA compression

**Question:** How much variance is captured by compact PCA representations of the MC waveforms?

![Synthetic-waveform PCA compression](figures/paper/pca_truth_mc.png)

**Status:** `TRUTH_LEVEL_MC_ONLY` · **Evidence:** `SYNTHETIC_WAVEFORM_MC`

Fixed synthetic-waveform MC output: three components explain 72.5% and eight explain 82.2%. These values supersede stale 0.89/0.997 statements and are not beam-data PCA results.

[PDF](figures/paper/pca_truth_mc.pdf) · [SVG](figures/paper/pca_truth_mc.svg) · [source CSV](figures/paper/source_tables/pca_truth_mc_source.csv)

## FIG-WIKI-011 — ADC-response sensitivity inputs

**Question:** Which dimensionless nuisance elasticities dominate the current MC sensitivity scan?

![ADC-response sensitivity inputs](figures/paper/systematic_sensitivity_inputs.png)

**Status:** `REVIEW` · **Evidence:** `SENSITIVITY_INPUTS`

Dimensionless cluster-D ADC-response elasticities only. Mixed-unit rows (gain envelope, kB span and missing material) are excluded rather than combined. This is a sensitivity inventory, not a propagated uncertainty budget.

[PDF](figures/paper/systematic_sensitivity_inputs.pdf) · [SVG](figures/paper/systematic_sensitivity_inputs.svg) · [source CSV](figures/paper/source_tables/systematic_sensitivity_inputs_source.csv)
