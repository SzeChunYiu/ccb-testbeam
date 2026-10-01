# Paper Gap Audit 2026-08-16

## Summary

Audit of paper state against merged main artifacts (commit cec9edc2).

## Findings

### 1. Figure Path Mismatch (FILLABLE)

**Issue:** SCH-01 in paper/figures.yaml references docs/figures/geometry_tof.png but file exists at publication/figures/illustrative/geometry_tof.png

**Status:** FILLABLE - File exists, wrong path in registry

**Action:** Update paper/figures.yaml path

---

### 2. All Other Figures - PRESENT

MC Method Closure (clusterB):
- timing_mc_method_closure.png ✓ EXISTS

PID (clusterA):
- pid_mc_validation.png ✓ EXISTS

ADC/Calibration (clusterC):
- adc_mc_calibration.png ✓ EXISTS
- birks_mc_comparison.png ✓ EXISTS  
- pileup_digitizer_mc.png ✓ EXISTS

Data figures:
- selected_pulse_inventory.png ✓ EXISTS
- stopping_b8_tension.png ✓ EXISTS
- systematic_sensitivity_inputs.png ✓ EXISTS

Optical grid (#1303):
- 1303_stage_accounting.pdf ✓ EXISTS
- 1303_pe_per_mev.pdf ✓ EXISTS
- edep_reconstruction_heldout_E_vis.pdf ✓ EXISTS

DeltaE-E (#956):
- All fig07/fig08 figures ✓ EXISTS (symlinks)

Species/Penetration (#618):
- All 618_*.pdf/png figures ✓ EXISTS

Depth profile (#1318):
- data_depth_profile.pdf ✓ EXISTS
- mc_depth_profile.pdf ✓ EXISTS

---

### 3. S44-S59 Benchmark Series

These merged PRs contain ML/benchmark studies that are **separate from the physics results paper**. The paper focuses on MC method closure, DeltaE-E topology, optical response, and timing residuals. No gap - these belong to a separate research track.

---

### 4. Claim Ledger Validation

All 26 ledger rows are properly backed. No unbacked claims found.

---

### 5. Section-Reference Audit

All paper chapters reference merged studies. No unmerged references found.

---

## Gap Summary

| Category | Count | Fillable | Blocked |
|----------|-------|----------|---------|
| Path mismatches | 1 | 1 | 0 |
| Missing figures | 0 | 0 | 0 |
| Unmerged references | 0 | 0 | 0 |
| Unbacked claims | 0 | 0 | 0 |

## Required Action

Fix SCH-01 geometry_tof.png path in paper/figures.yaml
