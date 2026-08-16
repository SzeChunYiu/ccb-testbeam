# MV5 — Pile-up toy diagnostic

- status: **BLOCKED / TOY_DIAGNOSTIC**
- generated: 2026-07-25 18:34:49
- truth file: `truth_tracks.npz` (23,452 proton and 27,838 deuteron single-stave amplitudes)
- seed: 42

## Question and boundary

This study checks analytic exponential-gap pile-up arithmetic and a toy two-pulse
overlay. It reuses the rounded S10b live-time value `124.8 ns`; it does not
independently validate that data measurement and does not define or validate Rmax.
Canonical Rmax remains withheld by `CL-010` under `S-STAT-003`.

## Duty-factor products under three live-time inputs

| tau_eff [ns] | 1/tau_eff [MHz] | multiplied by 0.38 [MHz] |
|---:|---:|---:|
| 90.0 | 11.11 | 4.22 |
| 124.8 | 8.01 | 3.0448717948717947 |
| 179.0 | 5.59 | 2.12 |

The 3.0448717948717947 MHz number is arithmetic `(1/tau_eff) × 0.38`. The
tracked ledger classifies it as `SUPERSEDED`; the 0.38 beam duty factor is not an
accepted occupancy-quality threshold. In the machine-readable result,
`rmax_from_failure_ceiling_mhz is null` because the stated recovery-failure
ceiling is not reached in the scanned range.

## Pile-up fraction versus rate

The toy draws exponential inter-arrival gaps and reproduces
`1 - exp(-R × tau_eff)` within finite toy statistics. This is a closure test of
code against the same analytic model, not empirical detector validation.

## Data-comparison arithmetic

Inverting an observed anomaly fraction through the same Poisson model gives a
model-dependent implied average rate. It does not prove that the data anomaly is
pile-up or not pile-up because the anomaly selection, time structure, trigger
acceptance, and recovery model are not closed against data.

## Artifacts

- `mv5_pileup_summary.json`
- `mv5_pileup.png`
- `mv5_example_waveforms.png`

## Verdict

The analytic/toy calculations are reproducible diagnostics. They do not authorize
an Rmax value, do not establish the instantaneous spill-rate distribution, and do
not exclude pile-up as a contributor to the beam-data anomaly. Resolve
`S-STAT-003`, use the exact S10b estimand and interval, define an accepted capacity
criterion, and validate a production waveform/recovery model before publishing a
capacity claim.
