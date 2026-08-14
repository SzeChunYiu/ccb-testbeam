# Cross-Section Uncertainty: Downstream Observable Sensitivity

## Issue #1179

This document describes how cross-section uncertainty propagates through the MC pipeline to affect downstream observables.

## Perturbation Modes

| Contract ID | Description | Parameters |
|-------------|-------------|------------|
| NOMINAL_V1 | No perturbation (baseline) | - |
| STAT_PERTURB_V1 | Gaussian per-node statistical | seed, col 3 uncertainties |
| SYST_ENVELOPE_SINUSOIDAL_TAPER | Systematic envelope (10% edges, 20% center) | sign (plus/minus) |

## Expected Observable Sensitivity

### High Sensitivity
- theta_cm distribution: Directly affected by angular sampling
- theta_lab distribution: Kinematically coupled to theta_cm

### Medium Sensitivity  
- Detector hit patterns: Via primary direction changes
- Stopping depth distribution: Via energy-angle coupling

### Low Sensitivity
- Digitized timing: Secondary effect via path length
- Pulse shapes: Indirect via energy deposition

## Validation Strategy

### No-Variance Case
- Zero statistical uncertainty → zero shift
- Verifies: perturbation logic doesn't introduce artificial effects

### Null Case
- Shuffled statistical uncertainties → no systematic shift
- Verifies: envelope model captures true systematic structure

## Status

- Perturbation functions implemented with fail-closed contract IDs
- Tests for no-variance and null cases passing (8/8 passed)
- Full MC campaign propagation blocked on hibeam_g4 build (lane-1303)
