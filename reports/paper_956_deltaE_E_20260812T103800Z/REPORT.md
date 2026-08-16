# PAPER-956 corrected ΔE–E publication run

**Issue:** #956 / PAPER-A05  
**Producer:** `scripts/single_stave/paper_956_deltaE_E_publication.py`  
**Generated:** 2026-08-12T09:33:55Z (LUNARC)  
**Status:** PASS (`core_result.status`)

## Contract (#618)

| side | ΔE | E |
|------|----|---|
| DATA | A(B2) ADC | A(B4)+A(B6)+A(B8) ADC |
| MC 4-readout | Edep(B2) MeV | Edep(B4)+Edep(B6)+Edep(B8) MeV |
| MC full | Edep(B2) MeV | sum(all downstream physical B-layer Edep) MeV |

Composite event key: `(source_file_id, run_id, event_id)`. Missing downstream channels → 0 only after key validation.

## Inputs (SHA-256 bound)

| role | path | bytes | sha256 |
|------|------|------:|--------|
| pulse table | `reports/1780917628.../s00_selected_b_pulses.csv.gz` | 9,246,625 | `648c32d0…8b2f` |
| MC ROOT | `geant4/data/output_krakow_1M.root` | 677,221,620 | `2b62403f…42cc` |

## Key results (`tables/sample_summary.json`)

### DATA amplitude ΔE–E (Figure 7)

| sample | n | median ΔE [ADC] | median E [ADC] | Pearson r | run-bootstrap r [16–84%] | B2 saturation |
|--------|--:|----------------:|---------------:|----------:|-------------------------:|--------------:|
| I | 147,274 | 7101 | 0 | −0.042 | [−0.051, −0.030] | 51.8% |
| II | 69,174 | 3567 | 0 | −0.070 | [−0.091, −0.029] | 7.6% |

Sample I median downstream E is zero because most coincidence-selected events stop at B2.

### MC truth ΔE–E (Figure 8, `MC_TRIGGER_PROXY`, PrimaryWeight)

| sample | mode | n (ΔE+E>0) | Pearson r | Σw | ESS |
|--------|------|----------:|----------:|---:|----:|
| I | 4-readout | 46,992 | −0.697 | 30,294 | 23,099 |
| II | 4-readout | 203,459 | −0.465 | 357,482 | 102,463 |
| I | full downstream | 64,762 | +0.130 | 39,915 | 35,163 |
| II | full downstream | 237,098 | +0.045 | 387,271 | 114,158 |

### B2–B4 two-channel diagnostic (NOT ΔE–E)

n = 25,423; r = +0.151 (run-bootstrap [0.123, 0.178]); medians B2/B4 = 3640/2974 ADC.

## Figures (on LUNARC)

`figures/fig07_data_deltaE_E_per_sample.{png,pdf}`  
`figures/fig08_mc_deltaE_E_{I,II}.{png,pdf}`  
`figures/fig_segmentation_readout_phase.{png,pdf}`  
`figures/fig_b2_b4_two_channel_diagnostic.{png,pdf}`

Full artifact tree: `/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/paper_956_deltaE_E_20260812T103800Z/`
