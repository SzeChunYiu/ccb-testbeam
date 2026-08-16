# Geant4 Single-Stave Validation Results

**Date:** 2026-07-21T22:28:29Z
**Build:** Geant4 11.2.2 (GCC 12.3.0) on LUNARC GPU node (hpua40)
**Particle:** 100 MeV proton, 500 events per run
**Configuration:** `d05ae2327548c322` geometry hash, 7 optical tables with SHA256 provenance

## Validation Checks

### 1. Same-seed Event Reproducibility (1T vs 48T) — ✅ PASS
- 27/27 branches exact equal across all 500 events
- All event IDs match (no duplicates, no missing)
- Full metadata provenance match (geometry, seeds, optical tables)

### 2. Same-seed Photon Tree Reproducibility (1T vs 48T) — ✅ PASS
- 1,170,091 photon records in both runs
- All 6 fields (detected, event, path_len_mm, sensor, time_ns, wavelength_nm) exact equal
- Per-sensor counts match exactly: 88,557 / 88,651 / 87,854 / 88,097

### 3. Multiseed RNG Independence — ✅ CONFIRMED
- Different seeds produce different outputs (490-500/500 events differ)
- Cross-seed mean optical yield: 178.3 PE (RSE = 0.48%)

### 4. Optical Yield (~178 PE/event) — ✅ CONFIRMED
| Seed | Mean PE | Std PE | Median PE |
|------|---------|--------|-----------|
| 1    | 177.1   | 20.5   | 176.0     |
| 2    | 178.0   | 22.6   | 177.0     |
| 3    | 179.5   | 30.4   | 176.0     |
| 4    | 178.5   | 35.4   | 174.5     |
| **Cross-seed** | **178.3** | **0.9** | — |

### 5. Output Files
- `gpu_stave_1t.root` + `.meta.json` — 1-thread reference
- `gpu_stave_48t.root` + `.meta.json` — 48-thread same-seed
- `gpu_stave_48t_seed[2-4].root` + `.meta.json` — multiseed ensemble
- `validation_events_1t_vs_48t.json` + `.pdf` — event reproducibility report
- `validation_photons_1t_vs_48t.json` + `.pdf` — photon tree report

### Validation Scripts
From PR #868 branch `chatgpt/AUD-G4-001-mt-rng-seeding`:
- `scripts/compare_single_stave_mt_reproducibility.py`
- `scripts/compare_single_stave_photon_trees.py`
