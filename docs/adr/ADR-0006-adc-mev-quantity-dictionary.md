# ADR-0006: Truth-type-specific ADC/MeV quantity dictionary

**Status:** accepted (infrastructure); consumer migration **BLOCKED**  
**Date:** 2026-08-11  
**Lane:** Wave B Lane 05  
**Issues:** #994

## Context

Public surfaces mix ~119.17 ADC/MeV digitizer scales with CL-013's gated
~92 ADC/MeV ±30% median-match proxy under ambiguous names (“gain”,
“calibration”).

## Decision

1. Maintain a machine-readable dictionary at
   `configs/response/quantities/adc_mev_quantity_dictionary.yaml`.
2. Each quantity encodes domain, input energy type, ADC definition, estimator,
   validity population, and claim authorization.
3. Compatibility test fails if distinct truth types share one public
   `short_label`.
4. Do **not** auto-apply the ±30% proxy envelope to digitizer parameters.

## Consequences

- Callers must reference `quantity_id`, not prose “ADC/MeV”.
- Full README/WIKI/figure relabeling remains **BLOCKED** until consumers migrate.
