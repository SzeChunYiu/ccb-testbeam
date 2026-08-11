# ADR-SIPM-DUALPATH-H2 — Legacy PE vs core ADC
Status: ACCEPTED (labelling contract)
Date: 2026-08-11
Issues: #1084
Related: #981 #976 #977

## Decision

The production detector-response path is **ccb-sipm-core** (`adc_*`).

`detected_*` and `pe_sat_*` remain an **INDEPENDENT_DIAGNOSTIC_DRAW** using a
separate Bernoulli PDE draw and analytic occupancy saturation. They must not
be treated as the latent microcell state that generated `adc_*`.

## Consequences

- Run metadata records `detector_response.legacy_pe_path = INDEPENDENT_DIAGNOSTIC_DRAW`.
- `sipm_sensitivity.py` labels PE slopes as diagnostic-only; causal elasticity
  uses `adc_*` only.
- A future H3 unification (single stochastic microcell state → all products)
  remains desirable but is out of scope until recovery/XT models are bound.
