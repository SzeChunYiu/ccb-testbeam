# Independent public SiPM project — architecture and v3 boundary

Date: 2026-07-24

## Decision

Build the SiPM response engine as an independent public clean-room project. It may implement the same published physical mechanisms as G4SiPM, but must not copy incompatible source, comments, internal class organization, tests, data files or documentation expression. Physics equations, distributions and measurement methods should be cited and independently implemented.

## State-of-the-art position

The project must be compared with both historical G4SiPM and active MIT-licensed SimSiPM. Its intended measurable differentiators are:

1. Geant4 11.2.2 and 11.4.2 adapters;
2. actual local photon position, direction, wavelength, time, path, creator and boundary truth;
3. process-keyed deterministic streams and thread/order invariance;
4. selectable named recovery, crosstalk, afterpulse, global-bias and external-crosstalk models;
5. parameter-level device provenance, uncertainty and applicability;
6. formal verification, physical validation, UQ and claim-evidence records;
7. exact source table and immutable manifest per plot;
8. reference CPU distributions before acceleration.

## Current CCB integration boundary

Current source has configurable WLS timing, four far-end modes, photon-arrival collection and independent-core ADC output. The v3 review additionally finds:

- empty-arrival dark/noise events bypass the core;
- legacy PDE/static occupancy and microcell ADC coexist;
- overvoltage and temperature do not drive device response;
- parameter provenance and run metadata are incomplete;
- sensitivity values are confounded with one seed each;
- zero DCR and cell-count points do not affect the intended core;
- current-head Geant4 11.2.2 reproduction and 11.4.2 validation remain to be run.

Read `REVIEW_V3.md`, `TASKS_V3.json`, `PUBLIC_CLAIM_AUDIT_V3.md` and `NATURE_PLOT_STANDARD.md` before implementation.

## Scientific boundary

The external project scaffold and polished figures are software-test artifacts. No device, beam, detector-accuracy, calibration, timing or performance-superiority claim is accepted merely because the reference core builds.
