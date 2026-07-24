# SiPM/Geant4 review v3

## Review provenance

- `ccb-testbeam`: `251353ffb0e200bd3c495b92c854f60593f44279`
- `ccb-sipm-core`: `b38e3dcbce696e487a6b455ada23e99518b8bb21`
- latest repository-recorded SiPM runtime check: `a0e498852a3275f8bdfe2b5aeb50fb4860c24dd9`
- independent Geant4 rerun in this review: **NOT RUN** (no Geant4 installation/artifacts in runtime)

## Functional status

The repository records a clean LUNARC GCC 12.3 / Geant4 11.2.2 build and passing `ccb_stave_sipm_arrivals` and `ccb_stave_sipm_adc` CTests. A comparison to current main shows 31 later commits without Geant4/SiPM source changes. This supports a repository-recorded operational smoke PASS on 11.2.2, not current-head independent reproduction or physical validation. Geant4 11.4.2 remains untested.

## Confirmed source defects

### P0

- no-arrival events bypass the core, forcing dark/noise-only ADC to zero;
- legacy PDE/static occupancy and microcell ADC semantics coexist;
- overvoltage/temperature do not alter device physics;
- parameter-level manufacturer provenance is incomplete/overclaimed;
- one unique seed per sensitivity value confounds seed and parameter;
- `DCR=0` grid point is not applied;
- `sipm_n_cells` does not configure the microcell core;
- core errors/candidate limits fail open;
- detailed core/submodule/model metadata are absent;
- stateful random stream and input ordering can perturb outputs;
- WLS/far-end tests verify configuration/logging, not physical distributions.

### P1

- far-end mode omitted from geometry hash;
- shared NIST `G4_AIR` MPT is mutated;
- sensor/termination surfaces remain idealized;
- no pre-window dark history;
- avalanche times are rounded to waveform samples;
- negative/bipolar measured pulse templates are unsupported;
- waveform allocation/convolution has no safe complexity bounds;
- fill-factor flag is inert;
- mixed-sensor incident count can be wrong.

## Analysis and claim audit

- claim ledger has a 43-column schema and multiple width-mismatched rows;
- Rmax `3.044–3.05 MHz` is quarantined: `0.38` is recorded as duty factor and no recovery-failure crossing was observed;
- gain central arithmetic near `92 ADC/MeV` is reproducible from recorded constants, but producer/artifact/CLI/schema and uncertainty are not;
- timing pulls depend on the blocked gain and lack complete interval/covariance evidence;
- PID and C12 remain truth-level MC only;
- stopping-depth is a failed model comparison;
- stopping-power closure and issue-885 calibration remain blocked.

## Public documentation defects

`WIKI.md`, the executive summary and project report still promote blocked values. `docs/academic_chapters/10_mc_validation.md` retains the superseded `245.6 ADC/MeV` chain, claims validation of conflicted Rmax and contains unsupported `ACCEPTED by nature-reviewer` wording. These documents must be quarantined and regenerated from a repaired fail-closed claim ledger.

## Figure review

The legacy generator uses dark-grid/cartoon styling and hard-coded blocked values. The canonical registry builder outputs generic 150-dpi PNGs from guessed columns. The v3 external package supplies fixed 89/183 mm, 5–7 pt, no-grid, accessible PDF/SVG/600-dpi PNG plots with source tables, exact n/error definitions, residuals and anomaly scans.

## Synthetic anomaly result

No hard violation was found. Expected structures were Poisson dark-count tails, pre-trigger dark first times, the ADC pedestal-code spike and a high-illumination multiplicity tail. One low charge/avalanche event was explained by repeated-cell recovery. These are software-test results, not detector evidence.

## Required ordering

1. repair response semantics and dark-only execution;
2. repair configuration, provenance, metadata and random streams;
3. repair claim ledger and public documents;
4. add statistical WLS/far-end/core tests;
5. rerun current head on Geant4 11.2.2 and 11.4.2;
6. only then launch sensitivity/calibration/publication campaigns.
