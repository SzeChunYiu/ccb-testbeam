# MC Validation Repository Audit

Generated: 2026-06-23T21:25:53Z

## Environment

- Repository path: `/Users/billy/Desktop/projects/ccb-testbeam`
- Git branch: `feat/mc-validation-full-package`
- Git HEAD: `eacb21ea1a9c05bfecdf206bc75dbf7cba4cef9a`
- Python version: `3.9.6`

## Package layout

- MC validation package present: `True`
- Base config present: `True` (`configs/mc_validation/base.yaml`)

## Key inputs

- MC ROOT (`geant4/data/output_krakow_1M.root`): `False`
- Data pulse table (`data/tables/s00_selected_b_pulses.csv.gz`): `False`

## Phase A-B scope

This audit confirms repository scaffolding for the MC validation program:
packaging, strict config loading, unit helpers, schema records, CLI wiring,
and Tier-1 study entry points (MV1–MV3) plus truth-build inspection.

Tier-2 studies MV4–MV8 remain blocked until MV0 digitizer calibration lands.
