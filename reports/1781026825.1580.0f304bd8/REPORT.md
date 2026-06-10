# S14d: external range-energy calibration requirements audit

- **Ticket ID:** 1781026825.1580.0f304bd8
- **Worker:** testbeam-laptop-4
- **Input:** raw `data/root/root/hrdb_run_*.root` plus the referenced S14b/S14d report artifacts; checksums in `manifest.json` and `input_sha256.csv`.
- **No Monte Carlo / no per-event energy claim.** This is a requirements audit for what must exist before such a claim.

## 1. Raw reproduction gate

The script rebuilds selected B-stack pulses from `HRDv`: median(samples 0..3) baseline, positive channels B2/B4/B6/B8, and `A > 1000 ADC`.

| quantity | expected | reproduced | delta | pass |
| --- | --- | --- | --- | --- |
| S00 selected B-stave pulse records | 640737 | 640737 | 0 | True |

## 2. Referenced S14b held-out methods

- **Train runs:** 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42, 64.
- **Held-out runs:** 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 65. Bootstrap CIs resample held-out runs as blocks in S14b.
- **Traditional:** PSTAR depth plus per-depth monotonic even-charge quantile lookup.
- **ML:** monotonic `HistGradientBoostingRegressor` on even amplitude/charge, penetration depth, multiplicity, and saturation flags.

| method | n | res68_abs_frac | res68_ci95 | combined_energy_proxy_res68 | combined_energy_proxy_res68_ci95 |
| --- | --- | --- | --- | --- | --- |
| traditional_depth_charge_lookup | 332852 | 0.0211892254 | [0.019759173376975067, 0.022616709286844058] | 0.2462373359 | [0.22370987434311201, 0.2516689108488624] |
| ml_monotonic_hgb | 332852 | 0.0250078102 | [0.022795672304338082, 0.02847725106827667] | 0.1885071235 | [0.1656324364654218, 0.1980872051573958] |

S14b leakage checks: no train/held-out run overlap, no event-key overlap, explicit exclusion of run/event/odd-readout features, depth-only res68 0.261461, and shuffled-target ML res68 0.319485.

## 3. Decision table

| ingredient | raw_hrd_constraint | evidence | needed_for_per_event_proton_energy | status |
| --- | --- | --- | --- | --- |
| HRD raw pulse selection and B-stack penetration depth | yes | Raw ROOT gate reproduces S00 selected B-stave pulse records exactly; depth order is B2/B4/B6/B8 hit depth. | Keep as internal observable; not sufficient for absolute incident or stopping energy. | available from raw HRD |
| Even-vs-odd duplicate readout closure | yes, internally | S14b nominal held-out res68: traditional 0.021189, ML 0.025008; run-block CIs are [0.019759173376975067, 0.022616709286844058] and [0.022795672304338082, 0.02847725106827667]. | Useful quality gate, but duplicate readout is not external truth. | available from raw HRD |
| External charge-proxy uncertainty from downstream stack | partial | S14b propagated P04b charge term gives combined nominal res68 0.246237 traditional and 0.188507 ML, both above 0.10. | Must be replaced or anchored by calibrated light-yield/energy-deposit response. | insufficient for per-event claim |
| Material budget before and inside the HRD stack | no | Prior S14d material scan changes the raw-only proxy envelope; traditional res68 span 0.017251773416181122 to 0.02877029809629374, ML span 0.02079760407409461 to 0.03222012616130544. | Surveyed thicknesses, dead layers, support material, target-to-stack path length, and uncertainties. | requires external detector survey or validated model |
| Stave geometry and stopping-depth convention | partial | Raw data identify which stave fired last, but not the absolute front-face, center, active thickness, or inactive gap convention. | Coordinate convention tied to physical stave positions and active volumes. | requires external geometry definition |
| PSTAR/range-energy table applicability | no | S14b uses a configured plastic-scintillator PSTAR table only as a monotonic depth-order lookup. | Material-specific stopping powers and validation for the actual scintillator/support mixture. | requires external reference and uncertainty |
| Birks/quenching and nonlinear scintillator response | no | No Birks constant, quenching curve, or ADC-to-light-yield calibration is present in the raw HRD ROOT. | Bench calibration or validated Birks/quenching model with uncertainty propagation. | missing external calibration |
| Particle identity / proton truth | no | The run condition is 190 MeV p on CD2, but HRD-only selected pulses do not label event-level proton, deuteron, fragment, or background species. | Independent PID, beamline tag, or validated stopping-depth truth sample. | missing external truth |
| Stopping-depth validation | no | Depth-order violation is zero by construction for the raw proxy, but no external range telescope or MC truth validates true stopping depth. | External range/stopping validation or simulation validated against calibration data. | missing external validation |
| Leakage controls | yes | S14b reports no train/held-out run overlap, no event-key overlap, feature exclusion of run/event/odd readout, and shuffled-target ML res68 0.319485. | Keep these controls, then repeat them against external truth/calibration targets. | available, but target remains proxy-only |

## 4. Finding

The raw HRD reproduction gate matches S14b/S00 exactly at 640,737 selected B-stave pulses. The S14b run-held-out proxy closure remains strong for the internal duplicate-readout target (traditional res68 0.0212, ML res68 0.0250), but the propagated external charge-proxy uncertainty gives combined nominal range-energy proxy res68 0.2462 traditional and 0.1885 ML, both failing the 0.10 preflight threshold. Raw HRD data can constrain pulse selection, penetration ordering, duplicate-readout closure, and leakage controls; a per-event proton energy claim still requires external material budget, stave geometry/active-depth convention, Birks/quenching or light-yield calibration, proton/PID truth, and stopping-depth validation.

## 5. Reproducibility

```bash
/home/billy/anaconda3/bin/python scripts/s14d_1781026825_1580_0f304bd8_external_requirements_audit.py --config configs/s14d_1781026825_1580_0f304bd8_external_requirements_audit.yaml
```
