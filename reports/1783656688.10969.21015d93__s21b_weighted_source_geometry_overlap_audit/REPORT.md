# S21b: Weighted Scattering-Source Closure and Geometry Overlap Audit

Ticket: `1783656688.10969.21015d93`

## Abstract

This study tests whether the Krakow `hibeam_g4` source produces the intended proton-deuteron angular distribution and whether the compact ROOT geometry is overlap-clean.  I read the Geant4 output ROOT ntuple directly, reconstruct the proton centre-of-mass angle from the recorded primary kinematics, compare the stored `PrimaryWeight` to the tabulated cross section evaluated in lab and centre-of-mass frames, and run `TGeoManager::CheckOverlaps` on the imported Krakow geometry.  The winner recorded in `result.json` is the validated interpretation of the source: `lab_angle_primary_weight_requires_weight_aware_analysis`.

## Inputs and Reproduction Gate

| Quantity | Value |
|---|---:|
| Claimed ticket id | `1783656688.10969.21015d93` |
| Raw Geant4 ROOT file | `/home/billy/ccb-geant4/output_30k.root` |
| ROOT ntuple entries | 30,000 |
| Exported events for closure | 30,000 |
| Exported primary particles | 60,000 |
| Exported protons used | 30,000 |
| Geometry volumes | 13 |
| Geometry top volume | `MOTHER` |
| ROOT overlap count at 1e-4 cm tolerance | 0 |

The reproduction gate is direct ROOT I/O: no prior S21 summary table is used for the event-level closure.  The prior S21 source review is used only to identify the expected files and failure modes.

## Applicability of the Benchmark Template

The queue item claimed in this run is S21b, a Geant4 generator-weight and ROOT geometry closure audit.  It does not define a supervised prediction target, labeled train/test split, waveform feature set, or per-run detector response sample.  Therefore ridge, boosted trees, MLP, 1D-CNN, and new neural architectures would not answer the claimed scientific question and are recorded as not applicable in `result.json`.  The appropriate comparison for this ticket is instead the physics closure benchmark between `PrimaryWeight = sigma(theta_lab)`, `PrimaryWeight = sigma(theta_cm)`, unweighted `theta_cm`, and `PrimaryWeight`-weighted angular distributions.

The available ROOT output used here is a single Geant4 simulation ntuple without a run-number branch.  Bootstrap intervals are therefore computed over exported event rows; a by-run bootstrap is not available from this ticket's raw ROOT schema.

## Methods

The source samples the proton centre-of-mass scattering angle as

$$\theta_{cm}=\pi U,\quad U\sim\mathcal{U}(0,1),$$

and then sets `PrimaryWeight` through a linearly interpolated cross-section table.  The physically intended polar density for a differential cross-section table is proportional to

$$p(\theta_{cm}) \propto \frac{d\sigma}{d\Omega}(\theta_{cm})\sin\theta_{cm}.$$

For each proton primary I compute

$$\theta_{lab}=\arccos(p_z/|p|),$$

and reconstruct the centre-of-mass angle from the recorded kinetic energy using the same two-body relativistic relation as the generator:

$$T_3 = (\gamma-1)m_p + \gamma T_{3,cm} + \gamma\beta p_{cm}\cos\theta_{cm}.$$

The closure scores compare the stored weight against two hypotheses: `sigma(theta_lab)` and `sigma(theta_cm)`.  Angular-distribution agreement is summarized by Jensen-Shannon distance and binned residuals between the ROOT sample and the intended `sigma*sin(theta)` distribution.  Uncertainty intervals are nonparametric bootstraps over exported event rows.

## Weight Frame Closure

| Hypothesis | RMS relative error | Median absolute relative error | R2 |
|---|---:|---:|---:|
| `PrimaryWeight = sigma(theta_lab)` | 4.014e-06 | 1.750e-06 | 1.000000 |
| `PrimaryWeight = sigma(theta_cm)` | 5.631e-01 | 5.886e-01 | 0.842869 |

The machine-readable row-level residuals are in `primary_weight_closure_sample.csv.gz`; binned summaries are in `weight_closure_bins.csv`.

## Angular Distribution

| Comparison | Jensen-Shannon distance | Interpretation |
|---|---:|---|
| Unweighted ROOT theta_cm vs intended `sigma*sin(theta)` | 0.3979 | uniform generator measure, not physical angular law |
| PrimaryWeight-weighted ROOT theta_cm vs intended `sigma*sin(theta)` | 0.1392 | improves cross-section shape but lacks the solid-angle Jacobian/source-sampling contract |
| PrimaryWeight-weighted ROOT theta_cm vs `sigma(theta)` only | 0.1610 | closest to how the current code applies weights |

Representative binned fractions:

| theta_cm_bin_low | theta_cm_bin_high | unweighted_fraction | primary_weighted_fraction | intended_sigma_sintheta_fraction | sigma_only_fraction |
| --- | --- | --- | --- | --- | --- |
| 0.00000 | 10.00000 | 0.04583 | 0.20314 | 0.09457 | 0.34480 |
| 10.00000 | 20.00000 | 0.06470 | 0.24431 | 0.20801 | 0.25537 |
| 20.00000 | 30.00000 | 0.05567 | 0.16860 | 0.22071 | 0.16595 |
| 30.00000 | 40.00000 | 0.05580 | 0.12863 | 0.15197 | 0.08419 |
| 40.00000 | 50.00000 | 0.05470 | 0.08661 | 0.09570 | 0.04300 |
| 50.00000 | 60.00000 | 0.05570 | 0.05482 | 0.06271 | 0.02432 |
| 60.00000 | 70.00000 | 0.05723 | 0.03546 | 0.04063 | 0.01424 |
| 70.00000 | 80.00000 | 0.05503 | 0.02245 | 0.02621 | 0.00862 |
| 80.00000 | 90.00000 | 0.05573 | 0.01415 | 0.01754 | 0.00559 |
| 90.00000 | 100.00000 | 0.05640 | 0.00964 | 0.01344 | 0.00429 |
| 100.00000 | 110.00000 | 0.05420 | 0.00609 | 0.01036 | 0.00341 |
| 110.00000 | 120.00000 | 0.05307 | 0.00388 | 0.00935 | 0.00328 |
| 120.00000 | 130.00000 | 0.05393 | 0.00291 | 0.00914 | 0.00354 |
| 130.00000 | 140.00000 | 0.05660 | 0.00240 | 0.00925 | 0.00416 |
| 140.00000 | 150.00000 | 0.05580 | 0.00221 | 0.00918 | 0.00508 |
| 150.00000 | 160.00000 | 0.05710 | 0.00277 | 0.00974 | 0.00732 |
| 160.00000 | 170.00000 | 0.05563 | 0.00417 | 0.00792 | 0.00972 |
| 170.00000 | 180.00000 | 0.05687 | 0.00775 | 0.00359 | 0.01310 |

Bootstrap CIs over event rows:

| metric | mean | ci95_low | ci95_high | unit |
| --- | --- | --- | --- | --- |
| abs_relative_error_lab_weight_closure | 2.62695e-06 | 2.59283e-06 | 2.66347e-06 | mixed |
| abs_relative_error_cm_weight_closure | 0.508617 | 0.505808 | 0.511366 | mixed |
| theta_cm_reco_deg | 90.3621 | 89.7677 | 90.9593 | mixed |
| primary_weight | 3.25279 | 3.20423 | 3.3031 | mixed |

## Geometry Overlap and Fidelity

`TGeoManager::CheckOverlaps(1e-4)` reports **0** overlaps for `/home/billy/ccb-geant4/krakow_109_8-38deg_4-71deg.root`.  Volume inventory:

| name | material | shape | capacity_cm3 |
| --- | --- | --- | --- |
| MOTHER |  Vacuum | TGeoTube | 2.35619e+08 |
| PIPE | Al | TGeoTube | 745.83 |
| Window | Mylar | TGeoTube | 1.5708 |
| TARGET | CD2 | TGeoTube | 6.20316 |
| Sci_stack1 |  Vacuum | TGeoBBox | 4000 |
| Sci_stack2 |  Vacuum | TGeoBBox | 2000 |
| Sci_bar | PSci | TGeoBBox | 500 |
| ProtoTPCHull | Al | TGeoTube | 13571.7 |
| ProtoTPCGas | Ar80CO2 | TGeoTube | 12903.7 |
| ProtoTPCActive | Ar80CO2 | TGeoBBox | 2300 |
| ProtoTPC | Ar80CO2 | TGeoBBox | 230 |
| Trig_stack |  Vacuum | TGeoBBox | 320 |
| Trig_bar | PSci | TGeoBBox | 160 |

A zero-overlap result at this tolerance is necessary but not sufficient for production detector fidelity.  The model remains compact: it has the CD2 target, stack envelopes, scintillator bars, trigger bars, and ProtoTPC volumes, but it does not encode detailed wrapping, survey uncertainty, cabling, photosensor material, or electronics response.

## Systematics and Caveats

- The frame closure is very strong for lab-angle evaluation because the source code calls `EvalWeight(theta3)` after transforming from centre-of-mass to lab.
- The output ROOT ntuple does not record the original sampled centre-of-mass angle, seed, macro hash, or input table hashes.  This study reconstructs theta_cm from kinematics and records hashes in `manifest.json`.
- The event-level closure uses a capped export from the available ROOT output to keep the artifact lightweight.  The total ROOT entry count is still recorded as the reproduction number.
- Geometry overlap checking via ROOT validates the imported TGeo geometry, not the post-VGM Geant4 physical-volume tree after any conversion-specific tolerance behavior.
- If downstream analyses ignore `PrimaryWeight`, the generated sample remains uniformly distributed in theta_cm rather than distributed as the physical differential cross section.

## Verdict

The S21b audit closes the geometry-overlap question for the compact ROOT geometry at the tested tolerance: overlap count is 0.  It also confirms the S21 weighting concern: the stored `PrimaryWeight` is a lab-angle cross-section weight applied after uniform centre-of-mass angle sampling.  The correct winner is therefore `lab_angle_primary_weight_requires_weight_aware_analysis`; unweighted ROOT output should not be used as a physical p-d angular distribution.

No follow-up ticket is appended from this run; S21b directly resolves the S21 follow-up and any further work should be implementation rather than more queue expansion.
