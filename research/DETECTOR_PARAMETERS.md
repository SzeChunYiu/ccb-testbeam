# Detector parameters (single-stave optical model)

Canonical machine-readable priors live in:

- `geant4/single_stave/optical/optical_constants_ledger.conf` (#979)
- `geant4/single_stave/optical/*.csv` (spectra / PDE / reflectivity / attenuation)

Status vocabulary:

- `MANUFACTURER_REPRESENTATIVE` — datasheet/class prior, not CCB batch assay
- `ASSUMPTION_UNIT_YIELD` — explicit model assumption (#1088)
- `HYPOTHESIS_*` — nuisance configuration, not authorised detector truth
- `BLOCKED_UNVERIFIED_HARDWARE` — waiting on construction/measurement evidence
- `UNKNOWN_EXTERNAL` — interface/material not recovered from hardware records

See `docs/stave_sim/ADR-OPT-WAVEA-BLOCKED.md`.
