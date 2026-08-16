# Cycle-3 submission audit — optical campaign addendum

**Date:** 2026-08-12  
**Parent audit:** `PAPER_SUBMISSION_AUDIT_CYCLE3_20260812.md`  
**Publication umbrella:** #1301  
**Regeneration issue:** #1303

## Decision

The July five-point single-stave grid used by manuscript Sections 8–9 is a **historical/superseded model diagnostic**, not a defensible nominal current optical model. Figure 9 and A09/Figure 11 must be regenerated from a current provenance-bound model before submission.

## O-P0-001 — exact calibration revision contains a shared-material double-cladding bug

The grid metadata binds Geant4/superproject commit `0005ed0cb2c06617abd36b3bb1e615497e15832a` (2026-07-21).

At that revision:

```cpp
BuildFibreInnerClad(): FindOrBuildMaterial("G4_PLEXIGLASS"); SetMaterialPropertiesTable(n=1.49)
BuildFibreOuterClad(): FindOrBuildMaterial("G4_PLEXIGLASS"); SetMaterialPropertiesTable(n=1.42)
```

Both builders can receive the same NIST material singleton. The outer-clad MPT assignment therefore overwrites the intended inner-clad optical table; the simulated double-clad fibre does not have two independently defined cladding indices as claimed by the geometry model.

Current source explicitly repairs this with distinct material instances `CCB_FibreInnerClad` and `CCB_FibreOuterClad`. The July PE yield/transport must be regenerated; this is not an uncertainty that can be repaired by relabelling.

## O-P0-002 — historical grid predates multiple later optical-response corrections/contracts

The exact campaign also predates the fixes/contracts associated with:

- #1082: one `attenuation_scale` changed both scintillator self-absorption and Y-11 bulk attenuation;
- #1086: the TiO2 UNIFIED surface token combination did not encode the claimed rough-surface model;
- #1088: WLS fluorescence multiplicity/yield was implicit and not source-bound;
- #1083: fibre-end/SiPM interface is a 10-um air-gap + placeholder sensor material plus a scalar post-crossing efficiency, not source-bound installed coupling;
- #1084: Geant4-side `detected_*`/analytic `pe_sat_*` and SiPM-core ADC are independent stochastic response branches;
- #1035: direct charged-particle Y-11 light was omitted and not yet bounded over CCB phase space;
- #1092: campaign samples a central transverse line rather than the full/data-weighted stave phase space;
- #1005: the nominal 0.25-mm coating is optically represented but physically massless air for charged-particle transport;
- #1302: historical `edep_scint_MeV` is Birks-visible energy, not raw deposited energy.

Some may remain declared hypotheses in a model-study paper, but their combined impact must be propagated from the current implementation; the July files cannot stand in for that exercise.

## O-P0-003 — current “detected PE” is a legacy diagnostic branch, not the upstream state of ADC

A09 and the historical grid use `detected_readout` / `n_detected_pe`. Under #1084 this is a Geant4-side Bernoulli PDE draw. The same sensor-arrival photons are independently redrawn inside `ccb-sipm-core` for the ADC path. Therefore `detected_readout` is not the event-level primary-avalanche state that generated `adc_readout`.

Publication choices:

- use it only as a precisely named **legacy optical detection diagnostic**, or
- regenerate a canonical response product exposing primary candidates/fired cells/avalanches from one SiPM state graph.

Do not call it a calibrated detector PE scale or use it as causal ADC truth.

## O-P0-004 — the 0.25-mm TiO2 “coating” is not a physical TiO2 shell in the historical transport geometry

`coatLV` is constructed with air; TiO2 exists only as an optical border surface. The 0.25-mm shell therefore contributes no charged-particle mass/energy loss. This distinction is important when the paper composes the single-stave response with range/stopping studies.

Until #1005/#1296 material closure, call it an **optical reflector boundary model with a nominal geometric shell**, not a validated physical coating material.

## O-P1-005 — historical PE/MeV denominator is Birks-visible energy

`analyze_calibration_grid.py` explicitly reads `edep_scint_MeV` and its result definition says `Birks-quenched`. Yet the historical report/issue/manuscript repeatedly call the values PE per deposited MeV. Under #1302 these must be PE per `E_vis` unless regenerated against `edep_scint_raw_MeV`.

## O-P1-006 — table “±” is event spread, not uncertainty on the mean

The July analysis reports `pe_mean ± pe_std`. E.g. `282.4 ± 25.2` is mean ± event standard deviation, not a statistical confidence interval or standard error. Manuscript/table captions must say so. Likewise “resolution=pe_std/pe_mean” is the response coefficient of variation at a fixed incident-KE point; it is not an energy-resolution measurement.

## O-P1-007 — the historical grid uses only 200 events per point and provides no uncertainty on spread/yield

For a publication model curve, report uncertainty on mean, quantiles/spread and PE-per-energy ratio (bootstrap/appropriate MC statistical interval), separately from model-systematic variation. Five point estimates with event RMS do not quantify calibration uncertainty.

## O-P1-008 — transverse and longitudinal applicability is not established

The geometry is one-ended and has fibres at y=±1 cm. The historical calibration phase space is not shown to match the real beam's `(x,y,theta,phi)` distribution. A central-point result cannot be called stave-average response. Regeneration must carry impact position/angle in the manifest and either integrate over a data-bound phase space or state the restricted support.

## O-P1-009 — “physics is right” / “realistic light yield” / “validated end-to-end” in historical report are prohibited current-facing claims

`reports/reaudit_20260720/lunarc_results/calibration/REPORT.md` describes the ~10 PE/MeV result as “realistic” and the chain as “validated end-to-end”. Later source/physics audits falsify that status. #1299 must quarantine these phrases as historical, not publication evidence.

## O-P1-010 — current nominal model must not be tuned only to reproduce the old mean

Because WLS yield, attenuation, reflector angular response, end coupling, PDE and SiPM response can compensate in the mean, regeneration needs stage counters and multi-observable comparisons (yield variance, position, timing, sensor covariance) rather than tuning total PE back to ~10 PE/MeV.

## Required paper action

Until #1303 closes:

- Figure 9 = RED/GATED, not nominal-current-model prediction;
- Figure 11 = RED/GATED in addition to #1297/#1302;
- abstract/conclusion must remove the ~10 PE/MeV and ~9% held-out performance numbers or explicitly call them historical superseded-model diagnostics;
- optical section may describe the simulation architecture and unresolved mechanisms, but not a nominal current performance scale.

After regeneration, update result files -> canonical ledger -> figure registry/source tables -> manuscript -> evidence matrix/WIKI -> reviewer cycle.
