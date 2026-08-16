# LUNARC results — CCB-796 unblocked (2026-07-20)

Real Geant4 build/run + full-MC extraction on LUNARC (cosmos3, Geant4 11.2.2,
`output_krakow_1M.root`). Turns the previously `BLOCKED_COMPUTE`/`BLOCKED_EXTERNAL`
items into verified results.

## CCB-796-RUN — single-stave sim builds + runs (DONE)
- Builds 100% on Geant4 11.2.2 (`module load GCC/12.3.0 Geant4/11.2.2`), 3/3 ctests pass.
- **Charged physics validated:** 100 MeV protons deposit `edep_scint = 16.8 MeV` mean over the 2.0 cm normal path (dE/dx ≈ 8 MeV/cm) — confirms the geometry the audit questioned.
- **Scintillation validated:** ~148k photons/event (~10k/MeV) after fixing the shared-material MPT clobber (PR #862).
- Provenance sidecar (`.meta.json`) records commit, geometry hash, seed, optical-table sha256.

## CCB-796-ENTRY — empirical stave-entry energy spectra (DONE)
Extracted from the 1M-event krakow MC (1,106,319 entry hits / 237,449 events),
earliest Sci_bar hit per (event,arm,track,layer). Full grid in
`entry_energies/entry_energies_summary_MeV.csv`. Highlights (B-arm layer 0, all):

| species | p05 | p16 | median | p84 | p95 | mean±std (MeV) |
|---|--:|--:|--:|--:|--:|--:|
| proton (2212) | 6.7 | 118.7 | **129.0** | 154.5 | 158.8 | 122.5 ± 40.4 |
| deuteron (1000010020) | 49.8 | 62.5 | **80.6** | 124.2 | 128.0 | 89.9 ± 31.8 |

Physically sensible for the ~190 MeV beam after upstream losses. These are the
empirical inputs that must replace the hand-picked calibration energies in
`geant4/single_stave/slurm/points_example.csv` for the production calibration grid.

## Bugs found ONLY by running (all fixed + merged)
| PR | bug (invisible to blind compile) |
|---|---|
| #861 | proton/deuteron ternary needed `static_cast<G4ParticleDefinition*>` (GCC 12) |
| #862 | scintillator + fibre core shared NIST `G4_POLYSTYRENE` → WLS MPT clobbered scintillation → 0 photons |
| #863 | extractor didn't recognize `Sci_bar_Momentum_X/Y/Z` branch names |
| #864 | krakow momenta are GeV/c not MeV/c (`--momentum-unit`); wrong units gave KE≈0 |

## Still open (queued, task CCB-796-OPTICAL / KNOWN_ISSUES.md)
Photon **collection** at the readout is still 0 — sensors overlap the
scintillator and fibre ends are buried in the bar. Needs boolean-subtracted holes
+ protruding fibres + external sensors, and the geometry-report must reflect
Geant4's real `CheckOverlaps` (it currently reports a false PASS). Optical
calibration plots are gated on this.

## Reproduce
```bash
ssh lunarc; module load GCC/12.3.0 Geant4/11.2.2
git clone --depth 1 --branch main https://github.com/SzeChunYiu/ccb-testbeam /tmp/ccb   # clone to LOCAL disk, not fs10
cd /tmp/ccb/geant4/single_stave && bash slurm/build.sh build
# entry energies (venv with uproot):
python scripts/single_stave/extract_g4_entry_energies.py \
  --input .../geant4/data/output_krakow_1M.root --momentum-unit GeV --output entry_energies
```
