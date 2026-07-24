# SiPM / WLS simulation upgrade handoff

**Prepared:** 2026-07-24  
**Current source review:** `251353ffb0e200bd3c495b92c854f60593f44279`  
**SiPM core review:** `SzeChunYiu/ccb-sipm-core@b38e3dcbce696e487a6b455ada23e99518b8bb21`  
**Status:** v3 source, analysis, claim and figure re-audit; no new Geant4 execution or detector-validation claim.

## Current functional statement

Repository history records a clean LUNARC GCC 12.3 / Geant4 11.2.2 build with passing SiPM-arrival and ADC smoke CTests at commit `a0e498852a3275f8bdfe2b5aeb50fb4860c24dd9`. Current `main` is 31 commits later, but the compared changes do not modify Geant4 or SiPM source.

This session did not rerun Geant4 or open the LUNARC ROOT artifacts. Geant4 11.4.2 is not tested. The accurate state is therefore repository-recorded operational PASS on 11.2.2, current-head independent reproduction NOT RUN, and scientific model acceptance PARTIAL/BLOCKED.

## Important fixes already present

- WLS time profile is configurable; default is `exponential`.
- far-end modes `instrumented|mirror|absorb|open` are implemented.
- photon arrivals are passed to the independent `ccb-sipm-core`.
- four ADC peak branches are written.

## New P0 findings

1. Empty-arrival events skip the core, so dark/noise-only ADC and false triggers are forced to zero.
2. Legacy Bernoulli PDE/static occupancy and microcell-core ADC models run in parallel in one event schema.
3. Overvoltage/temperature still do not drive PDE, gain, DCR, crosstalk, afterpulsing or recovery.
4. Exact PDE/recovery/DCR/CT/AP defaults have over-broad manufacturer provenance.
5. Sensitivity values are confounded with one unique seed each; no common replicated seed set exists.
6. The nominal zero-DCR grid point is not applied because the wrapper only accepts values `>0`.
7. `--sipm-n-cells` changes the legacy occupancy model but not the 60x60 microcell core.
8. Core errors/candidate caps are fail-open and detailed core validity is not persisted.
9. Core/submodule/model metadata are absent from the stave run sidecar.
10. Random draws are one stateful stream and arrival ordering can perturb results.

## Claim and documentation state

The canonical claim ledger remains structurally flawed. Public wiki/executive/MC-validation documents still label quarantined Rmax, blocked gain and dependent timing claims as validated. The old MC chapter retains a superseded `245.6 ADC/MeV` chain and unsupported acceptance wording. These surfaces must be quarantined and regenerated fail-closed from a repaired claim ledger.

## Figure and analysis upgrade

The external v3 ZIP contains:

- fixed 89 mm / 183 mm quantitative figure layouts;
- PDF, SVG and 600-dpi PNG output;
- editable/embedded fonts and accessible colors;
- one exact source CSV per figure;
- exact n/error-definition metadata;
- robust spike/outlier, clipping, occupancy and waveform diagnostics;
- a common-replicated-seed sensitivity replacement that rejects seed/value confounding.

The 800-event synthetic demonstration generated 22 figure specifications and 66 files. File dimensions, fonts, SVG text, hashes and source tables passed validation. The anomaly pass found zero hard failures, four expected structures and one recovery-genealogy review event. All remain `SYNTHETIC_SOFTWARE_TEST`.

## Read order

1. `REVIEW_V3.md`
2. `TASKS_V3.json`
3. `PUBLIC_CLAIM_AUDIT_V3.md`
4. `NATURE_PLOT_STANDARD.md`
5. existing v2 plan and research files for historical context

## Scientific boundary

An executable smoke test is not detector validation. Do not launch a sensitivity, calibration, timing or publication campaign until empty-arrival behavior, response-model exclusivity, configuration/provenance, deterministic streams, claim-ledger structure and current-head Geant4 reruns are resolved.
