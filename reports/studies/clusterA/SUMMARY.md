# Cluster A — ΔE-E / PID / stopping-depth diagnostic study

This study contains two distinct evidence domains:

- a Krakow Monte Carlo event-level analysis in MeV;
- a derived beam-data table in ADC that contains multiple rows per composite event key.

**Scripts:** `scripts/studies/clusterA_dE_PID_stopping.py` (MC) and
`scripts/studies/clusterA_data_side.py` (data-row diagnostics).

**Inputs:** `geant4/data/output_krakow_1M.root` and the derived
`deltaE_E_events_data.csv` produced from
`reports/1781014251.574.7a497937/pulse_taxonomy_table.csv.gz`.

## Evidence-backed results

### Monte Carlo event-level diagnostics

- The beam primaries are protons on CD2. Recoil deuterons, alphas, and heavier ions can
  deposit energy in the B arm; the PID target is the energy-dominant depositing species,
  not the beam-particle label.
- The canonical GEO-001 pair-merge selection contains 131,198 ΔE-E events. The reported
  PrimaryWeight-weighted medians are ΔE = 24.13 MeV and E = 101.03 MeV, with
  corr(ΔE,E) = -0.533.
- The truth-labelled-MC proton-versus-deuteron classifier has full AUC 0.898. Its poor
  saturated-ΔE and deepest-layer slices remain explicit limitations.
- Stopping, escaping, and censored categories use the TRU-003 residual-energy rule; the
  deepest observed layer is not automatically labelled as a stop.

These are simulation diagnostics. They do not establish beam-data PID transfer or detector
performance.

### Derived beam-data row diagnostics

The staged table has 632,939 rows but only 385,984 unique
`(source_file_id, run, evt)` composite keys. It is therefore a multi-row table, not a
one-row-per-event sample.

The previously published B2/B4/B6/B8 row counts and the +0.18 ΔE-E correlation are
**row-level descriptive quantities**. They are not event-level stopping fractions or an
accepted data/MC topology-closure test. Event-level inference remains blocked until the
canonical composite merge is run on immutable, hash-bound inputs.

The corrected data-side script now rejects missing, nonnumeric, NaN, infinite, and empty
selected samples; records exact input size and SHA-256; labels row and event denominators
separately; and withholds event-level authorization. The MC panel now sums `PrimaryWeight`
within each hexbin instead of silently drawing an unweighted density.

A later, separate raw-beam study under `reports/studies/data_side/` constructs a distinct
one-row-per-event B2/B4 sample. Its results and claim-ledger upgrades are not substitutes for
this multi-row-table contract and require their own estimand, uncertainty, and provenance
audit.

## Visual evidence

| ID | File | Interpretation |
|---|---|---|
| VIS-DE-001 | `VIS-DE-001_dE_E_density_quantiles.png` | MC event-level, PrimaryWeight-aware ΔE-E diagnostic. |
| VIS-DE-001-DATA | `VIS-DE-001-DATA_deltaE_E_adc.png` | Derived beam-data **row** distribution in ADC; not unique events. |
| VIS-DE-002 | `VIS-DE-002_species_bands.png` | Truth-labelled-MC species-band diagnostic. |
| VIS-DE-003 | `VIS-DE-003_mc_vs_data.png` | Topology display with different units and different statistical units; not a scale or closure test. |
| VIS-PID-001 | `VIS-PID-001_roc_pr.png` | Truth-labelled-MC ROC/precision-recall diagnostic. |
| VIS-PID-002 | `VIS-PID-002_calibration.png` | Truth-labelled-MC score calibration diagnostic. |
| VIS-PID-003 | `VIS-PID-003_robustness.png` | MC slice robustness, including failure slices. |
| VIS-STOP-001 | `VIS-STOP-001_geometry_material.png` | Nominal B-arm geometry/material diagnostic. |
| VIS-STOP-002 | `VIS-STOP-002_stopping_censoring.png` | MC stopping/escape/censoring diagnostic. |

The existing Cluster A data-side PNGs predate the corrected script and are stale for
acceptance purposes. They must be regenerated from immutable source bytes before use.

## Validation of the software correction

```text
python -m py_compile \
  scripts/studies/clusterA_data_side.py \
  tests/test_clusterA_data_side_contract.py \
  tools/audit/render_clusterA_data_side_semantics_evidence.py

pytest -q tests/test_clusterA_data_side_contract.py
7 passed in 0.36s
```

See:

- `docs/validation/clusterA_data_side_semantics_audit.md`;
- `docs/validation/clusterA_data_side_semantics_validation.json`;
- `docs/validation/clusterA_data_side_semantics.svg`.

## Remaining scientific work

1. Preserve and record immutable hashes for the production derived CSV and Krakow ROOT.
2. Regenerate the corrected row-level plots and inspect their source metadata.
3. Run the canonical composite merge to obtain exactly one accepted event record per key.
4. Define selections and denominators before computing event-level stopping fractions,
   correlations, efficiency, or data/MC comparisons.
5. Validate beam-data PID and detector transfer on independent data; simulation closure alone
   is insufficient.
6. Audit the separate raw-beam Rmax claim so measured occupancy is not conflated with the
   assumed `mu_max` and live-time model.
