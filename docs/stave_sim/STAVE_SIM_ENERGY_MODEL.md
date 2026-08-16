# Single-Stave Energy Response Model — Issue #796

> **Date:** 2026-07-16 | **Status:** First-order analytical model complete

## Geometry (per David Milstead, Issue #796)

| Parameter | Value |
|---|---|
| Scintillator | Extruded polystyrene (BC-408 equivalent) |
| Length | 50 cm |
| Width | 5.18 cm |
| Thickness (along particle path) | **2.0 cm** |
| Coating | TiO₂ reflective |
| WLS holes | Two longitudinal holes, 2.0 mm diameter, 2 cm apart |
| WLS fibres | Two Kuraray Y-11, 1.8 mm diameter |
| Readout | **Only one WLS read out at one end** (1 of 4 possible channels) |
| Photosensor | Hamamatsu S13360-3050CS SiPM on carrier board |

## Energy Loss Model (NIST PSTAR + Bethe-Bloch)

### Proton dE/dx in 2 cm polystyrene
| Beam energy (MeV) | dE/dx (MeV/cm) | edep in 2cm (MeV) | Typical stave |
|---|---|---|---|
| 180 | 4.0 | 8.0 | B2 (first stave) |
| 100 | 5.7 | 11.4 | B4 |
| 50 | 8.1 | 16.2 | B6/B8 (deep) |

### Deuteron dE/dx in 2 cm polystyrene
| Beam energy (MeV) | dE/dx (MeV/cm) | edep in 2cm (MeV) | Typical stave |
|---|---|---|---|
| 90 | 8.5 | 17.0 | B2 |
| 50 | 12.0 | 24.0 | B4 |

## Photon Transport Model

### Parameters
| Parameter | Value | Source |
|---|---|---|
| BC-408 light yield | 10,000 photons/MeV | Saint-Gobain datasheet (64% anthracene) |
| WLS capture (one fibre) | ~1.5% | Geometric + spectral matching estimate |
| Y-11 attenuation length | 3.5 m | Kuraray datasheet |
| Average light travel (one-end) | 25 cm | Half bar length |
| Attenuation factor | exp(−25/350) = 0.931 | |
| SiPM PDE at 500 nm | 40% | Hamamatsu S13360 datasheet |
| **Total efficiency** | **0.56%** | Scint photon → photoelectron |

### Expected Signals
| Particle + stave | edep (MeV) | Scint photons | At WLS end | PE at SiPM | Expected ADC |
|---|---|---|---|---|---|
| p 180 MeV → B2 | 8.0 | 80,000 | 1,117 | 447 | ~920 |
| p 100 MeV → B4 | 11.4 | 114,000 | 1,592 | 637 | ~1,310 |
| p 50 MeV → B6/B8 | 16.2 | 162,000 | 2,262 | 905 | ~1,860 |
| d 90 MeV → B2 | 17.0 | 170,000 | 2,374 | 950 | ~1,950 |
| d 50 MeV → B4 | 24.0 | 240,000 | 3,352 | 1,341 | ~2,760 |

## Comparison with Data

**MV0 v2 digitizer gain:** 92 ± 28 ADC/MeV
**Observed B-stack amplitudes:** 1,000–4,000 ADC (A > 1000 gate)
**Model predictions:** 900–2,800 ADC

The first-order model matches the data amplitude range within uncertainties.

## Open Questions
1. Full GEANT4 optical photon simulation needed for exact WLS transport
2. TiO₂ coating reflectivity not modeled (increases light collection)
3. WLS cladding efficiency not separately modeled
4. Birks quenching at high dE/dx (especially deuterons) not included
5. SiPM saturation at high photon flux not modeled

## Next Steps
- [ ] Build standalone GEANT4 simulation with optical photon transport (requires fixing Qt5/ICU link issue on Lunarc)
- [ ] Run proton/deuteron beam at multiple energies
- [ ] Produce edep vs PE scatter plots
- [ ] Calibrate absolute energy scale per stave

## Related
- [Issue #796](https://github.com/SzeChunYiu/ccb-testbeam/issues/796)
- [MV0 calibration](../../reports/mv0_calibration_1782677847/REPORT.md)
- [G4-08 truth bridge](../../reports/1783883140.39222.3c4045b1__g4_08_keyed_digitized_geant4_native_join/)

<!-- waveB-lane02-quenching -->

## Quenching model status (Wave B Lane 02 / #1008)

Executable quenching is `birks_geant4` with status `HYPOTHESIS` (`quenching_claims_authorized=false`). Within-form `kB` scans are nuisance variation only. Multi-model closure (Chou/Wright/Voltz or CCB-calibrated response tables) is **BLOCKED** until scintillator identity (#1000) and the #1008 programme are closed. See `docs/adr/ADR-0004-quenching-model-hypothesis.md`.
