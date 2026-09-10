# Issue #1623 — deposited energy → light yield in a single stave

Single-stave Geant4 optical MC, 150 configuration points, **250 000 events**,
species p / d / µ⁻ / π⁺ / π⁻, with the impact point distributed over the active
area and a 10° incidence cone, plus a central perpendicular reference sample.

Producer: `geant4/single_stave`, branch `issue-1623-light-vs-energy`.
Campaign: `geant4/single_stave/slurm/points_1623.csv` + `points_1623_topup.csv`.
Analysis: `scripts/single_stave/light_vs_energy_1623.py`.

## Answer to the question that motivated the issue

> The existing MC gives roughly 11–12 MeV B2 deposits for protons and about
> 42–45 MeV for deuterons, whereas the measured ADC amplitudes differ by much
> less than a factor four.

**Yes — the simulated response reproduces that compression, and it is not
Birks quenching alone. It is Birks quenching acting on two different track
topologies.** In B2 the deuteron ranges out (Bragg peak inside the bar) while
the proton punches through, so the deuteron's deposit is laid down at a far
higher `dE/dx` and is quenched much harder.

Distributed sample, matched to the physical B2 case:

| | E_dep raw | E_vis | Birks | N_scint | N_pe |
|---|---|---|---|---|---|
| proton, **punch-through**, 11–12 MeV window (KE ≈ 160 MeV) | 11.34 MeV | 10.64 MeV | 0.938 | 106 396 | 127 |
| deuteron, **stopping**, 42–45 MeV window (KE ≈ 44 MeV) | 43.00 MeV | 25.26 MeV | 0.587 | 253 054 | 304 |
| **ratio d/p** | **3.79** | **2.38** | | **2.38** | **2.39** |

A deposit ratio of **3.79 turns into a light ratio of 2.39** — a compression
factor of 1.59. The central perpendicular reference gives the same answer
(3.86 → 2.39), so the compression is a quenching effect and not a light
collection effect.

### Why the fate split is not optional

A raw-deposit window is fed by two different populations. Ignoring that gives
the wrong answer, and in the wrong direction:

| comparison | E_dep ratio | N_pe ratio |
|---|---|---|
| stopping d vs punch-through p (**the real B2 case**) | 3.79 | **2.39** |
| both stopping | 3.58 | 4.47 |
| fate-pooled | 3.63 | 4.13 |

The pooled number is *larger* than the deposit ratio, i.e. it says the response
expands rather than compresses. That is an artefact of the energy-grid weights,
not detector physics. `report_1623.json` therefore reports all three.

## Quenching is a function of dE/dx, not of species

`sample_A/04_yield_and_birks_vs_dedx.png`: protons, deuterons, muons and pions
all collapse onto one `E_vis/E_dep` curve when plotted against the path-averaged
`dE/dx` of the primary. The Birks factor runs from ≈ 0.98 at minimum ionizing
(µ, π above ~100 MeV) down to ≈ 0.27 for a 6 MeV deuteron that stops in 0.28 mm.

| species / KE | path | dE/dx | E_dep | E_vis | Birks | N_pe |
|---|---|---|---|---|---|---|
| deuteron 6 MeV (stops) | 0.28 mm | 21.1 MeV/mm | 5.99 | 1.59 | 0.266 | 19 |
| proton 12 MeV (stops) | 1.62 mm | 7.4 MeV/mm | 12.00 | 5.80 | 0.484 | 68 |
| proton 46 MeV (stops) | 18.4 mm | 2.50 MeV/mm | 46.00 | 32.50 | 0.706 | 382 |
| proton 160 MeV (through) | 20.1 mm | 0.51 MeV/mm | 11.08 | 10.40 | 0.939 | 124 |
| µ⁻ 1 GeV (MIP) | 20.1 mm | 0.163 MeV/mm | 3.67 | 3.58 | 0.976 | 45 |

Note the two proton rows at nearly the same deposit (12.00 vs 11.08 MeV) giving
68 vs 124 photoelectrons — a factor 1.8 purely from track topology.

## Position dependence

At fixed deposit, geometry alone moves the light yield substantially
(`sample_A/06_position_long.png`, `06_position_trans.png`):

* **longitudinal**, E_dep ∈ [40, 46) MeV: 540 pe at 0–5 cm from the SiPM end
  falling to 291 pe at 45–50 cm — a factor **1.86** across the stave;
* **transverse**, same window: 440 pe within 0.6 cm of the readout fibre
  falling to 314 pe at 3.0–3.6 cm — a factor **1.40**;
* the resulting 16–84 % spread at fixed deposit is **±36 %** at 10–13 MeV and
  **±25 %** at 40–46 MeV.

Any ΔE-E analysis that maps ADC to deposit with a single scale factor inherits
that spread as an irreducible width unless the hit position is used.

## Caveat: the simulated ADC chain is saturated over this whole range

`adc_readout` hard-clips at 3895 counts (12-bit, with a baseline offset). 79 % of
proton events and 82 % of deuteron events in the distributed sample sit at the
ceiling; the ADC ratio between the two B2 populations is therefore 1.00 by
construction and carries no information. Everything above uses `detected_readout`
(N_pe). Pinning the digitizer gain and dynamic range to the real DAQ is filed
separately; until then the simulated ADC must not be compared with measured
amplitudes.

## Figures

`sample_A/` is the distributed sample, `sample_B/` the central perpendicular
reference. All profiles show the median with a 16–84 % band.

| file | content |
|---|---|
| `01_nscint_vs_edep.png` | N_scint vs E_dep (raw and Birks-visible), per species |
| `02_npe_vs_edep.png` | photons at the readout and detected PE vs E_dep |
| `03_lightyield_per_MeV_vs_edep.png` | N_pe / E_dep vs E_dep — the non-linearity |
| `04_yield_and_birks_vs_dedx.png` | yield and Birks factor vs dE/dx |
| `05_birks_ratio_vs_edep.png` | E_vis / E_dep vs deposit |
| `06_position_long.png`, `06_position_trans.png` | yield vs distance to SiPM / to the WLS fibre, in fixed deposit bands |
| `07_proton_vs_deuteron.png` | B2 windows and the stopping/punch-through split |
| `08_adc_vs_edep.png` | ADC-equivalent (saturated — see caveat) |

## Event-level data

Committed here: the figures, `summary_by_point.csv` (one row per
species/sample/energy with medians and 16–84 % quantiles) and
`report_1623.json`.

The full event-level tables are too large for git and live on LUNARC, with
`SHA256SUMS.data` recording their digests:

```
/projects/hep/fs10/shared/nnbar/billy/ccb1623_report/events_1623.parquet   (61 MB)
/projects/hep/fs10/shared/nnbar/billy/ccb1623_report/events_1623.csv.gz    (63 MB)
/projects/hep/fs10/shared/nnbar/billy/ccb1623_campaign/*.root              (150 files, 87 MB)
```

Per event the table carries species, incident KE, entry position and direction,
scintillator path length, raw and Birks-visible deposit, generated
scintillation / WLS / Cerenkov counts, photons arriving at each of the four
sensors, detected PE, saturation-corrected PE, ADC, the primary's exit point and
residual kinetic energy, the `primary_stopped` flag, and the optical-guard kill
counters.

## Simulation-status boundary

The optical parameters are representative priors, not hardware measurements —
PDE overvoltage, optical coupling, far-end termination and TiO₂ reflectivity are
all `UNKNOWN_EXTERNAL` (#1083). Absolute PE/MeV from this campaign is **not** a
calibration. What is defensible is the *shape* of the response and the *ratio*
between species at matched deposits; `--pde-scale`, `--collection-efficiency`,
`--far-end` and `--reflectivity-scale` exist to bracket the rest.

Optical transport cost guards were active (1000 ns, 200 000 steps). They
truncated 6.0×10⁵ of 4.4×10¹⁰ optical photons (1.4×10⁻⁵) in 2675 of 250 000
events. No photon arrives at the readout later than 222 ns, and the SiPM
response window ends at 250 ns, so none of the truncated photons could have
contributed to a recorded observable.
