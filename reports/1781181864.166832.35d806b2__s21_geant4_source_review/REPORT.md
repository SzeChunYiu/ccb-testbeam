# S21 Review: `hibeam_g4` Krakow CCB Geometry and Source Fidelity

Ticket: `1781181864.166832.35d806b2`  
Worker: `testbeam-laptop-1`  
Scope: source-level review of `/home/billy/ccb-geant4/hibeam_g4_github` and companion files copied under `/home/billy/ccb-geant4`.

## Executive Verdict

The current `hibeam_g4_github` source is a plausible first-order Geant4 implementation of the CCB telescope configuration for 190 MeV proton-on-CD2 elastic-scattering truth studies, but I do not judge it production-grade or fully faithful yet. The geometry file is loaded, the claimed CCB/Krakow configuration points to a compact ROOT geometry containing a CD2 target, two scintillator stack envelopes, scintillator bars, trigger bar, and ProtoTPC volumes, and the macro-level `/ElGen/CSFile` command that was reported missing in the earlier g4truth review is present in this source.

The major limitations are physics and reproducibility issues rather than a single fatal source breakage. The source samples centre-of-mass scattering angle uniformly and assigns the tabulated differential cross section only as a `G4PrimaryParticle` weight, so any downstream analysis that ignores `PrimaryWeight` is not distributed according to the measured cross section. The detector geometry has only 13 volumes and 37 placements, so it cannot be assumed to encode full real CCB mechanical material, fine stave segmentation, wrapping, support, or electronics-response fidelity. The physics list uses `G4EmStandardPhysics_option4` and `G4HadronPhysicsINCLXX`, which is reasonable for low/intermediate-energy hadrons, but it also constructs a PAI model without registering it with the EM configurator; the PAI call is therefore effectively inert in the inspected source. Reproducibility is incomplete because the run scripts do not pin a seed, output files do not record input hashes or macro/config provenance, and the source tree has untracked build directories.

## Inputs and Provenance

| Artifact | Path | SHA-256 / identifier |
|---|---|---|
| Source repository | `/home/billy/ccb-geant4/hibeam_g4_github` | commit `b73ea2a1bd2419e7c4a25a3bf23a419ad619234c`; untracked `build_conda/`, `build_fp/`, `hibeam_g4_build/` |
| Main config | `/home/billy/ccb-geant4/krakow.config` | `9bee1e7f1519d2796fb08333de01b3ee1344cbb515672fc537c2411dbd134d2f` |
| Geometry config | `/home/billy/ccb-geant4/krakow.geoconf` | `a2bfda12d722d07ea8993bfd765bf8f43e2921715cced9b1b739fd5ffd3871c7` |
| Run macro | `/home/billy/ccb-geant4/run_krakow.mac` | `f9bb3d5e6e44971a4f52a836ff95aad8b20acc8804f5d44ca5399cd938afd5a7` |
| ROOT geometry | `/home/billy/ccb-geant4/krakow_109_8-38deg_4-71deg.root` | `a71c5cd7ce4cd7085f7f0236d5852f81aba0b52ff56bc2e9593f677e1e410d4e` |
| Cross section table | `/home/billy/ccb-geant4/sigma_pd_cm_190.txt` | `0ca33e76a745dde08a12cc451d295c0d213a897c9993914cb3d2a1550d89edfc` |
| Stopping table | `/home/billy/ccb-geant4/dedx_p_in_CD2.txt` | `9c2dd0d42473a6ffb96ec317a26d97815699d6b9ced6d3c46e65093d0114cb7b` |

I did not rebuild the code, following the ticket instruction not to rebuild unless needed for a specific check. I did inspect the ROOT geometry with `ROOT 6.32.02` from `nnbar_env`.

## Configuration-to-Source Trace

The run path is coherent at the configuration level:

| Requirement | Evidence | Assessment |
|---|---|---|
| CCB/Krakow geometry selected | `krakow.config` sets `Geometry_Namefile krakow_109_8-38deg_4-71deg.root`; `WasaDetectorConstruction::Construct()` imports `Geometry_Namefile` through ROOT/VGM or GDML. | Pass for loading the intended file. |
| 190 MeV beam | `run_krakow.mac` sets `/ElGen/E 190. MeV`; `ScatteringGenerator` exposes `/ElGen/E`. | Pass. |
| 2.3 mm CD2 target | `run_krakow.mac` sets `/ElGen/TargetThickness 2.3 mm`; ROOT inventory shows `TARGET` material `CD2`. | Pass at file/config level. |
| Beam spot | macro sets `/ElGen/Beamspot 10 mm`; source samples radius as `fBeamspot*sqrt(U)`. | Pass. |
| Cross-section file command | macro sets `/ElGen/CSFile sigma_pd_cm_190.txt`; inspected source declares the `CSFile` property and loads it on first event. | Fixed relative to the reported command-not-found issue. |
| Telescope angles / layout | `krakow.geoconf` lists `krakow_distance 109`, `krakow_ang1 -38`, `krakow_ang2 71.5`, `krakow_nBars1 8`, `krakow_nBars2 4`; geometry file name encodes `8-38deg_4-71deg`. | Geometry provenance is consistent, but the source review cannot prove metrology-level fidelity without the builder and survey data. |

## Geometry-Fidelity Assessment

The inspected ROOT file contains one `geometry` key, a `TGeoManager` named `geometry`, top volume `MOTHER`, 13 volume UIDs, and 37 placements. The relevant volume inventory was:

| Volume | Material | Shape |
|---|---|---|
| `TARGET` | `CD2` | `TGeoTube` |
| `Sci_stack1` | `Vacuum` | `TGeoBBox` |
| `Sci_stack2` | `Vacuum` | `TGeoBBox` |
| `Sci_bar` | `PSci` | `TGeoBBox` |
| `Trig_bar` | `PSci` | `TGeoBBox` |
| `ProtoTPCHull` | `Al` | `TGeoTube` |
| `ProtoTPCGas` | `Ar80CO2` | `TGeoTube` |
| `ProtoTPCActive` | `Ar80CO2` | `TGeoBBox` |
| `ProtoTPC` | `Ar80CO2` | `TGeoBBox` |

This is a deliberately compact detector model. It is adequate for checking broad acceptance, particle stopping, and truth-level hit/energy-deposit relations in the CD2 target and scintillator stack. It is not, by itself, a faithful full CCB telescope model at the level required for detailed efficiency, material-budget, multiple-scattering, or optical/electronics response claims. Missing or unverified items include detailed stave wrapping, support plates, photosensor/electronics material, cabling, dead layers, measured target mounting, survey uncertainty, and overlap checking. `CheckOverlaps` defaults to 0 unless supplied, and the reviewed `krakow.config` does not set it.

## Scattering Generator Review

The generator models a two-body elastic final state:

\\[
p + d \\rightarrow p + d,
\\]

with projectile energy after target energy loss

\\[
E_{\\mathrm{beam}}(z) = E_0 - \\int_0^z \\left(\\frac{dE}{dx}\\right)(E)\\,dx,
\\]

implemented numerically as 100 fixed substeps through the upstream target thickness. It computes relativistic two-body centre-of-mass kinematics and boosts both outgoing particles into the lab. That structure is physically sensible for elastic scattering from a stationary deuteron target.

The central caveat is the sampling measure. The code draws `theta3cm = pi*G4UniformRand()` and then evaluates `EvalWeight(theta3)` from the differential cross-section table. Thus, the event distribution is not sampled from

\\[
P(\\theta_{\\mathrm{cm}}) \\propto \\frac{d\\sigma}{d\\Omega}(\\theta_{\\mathrm{cm}})\\sin\\theta_{\\mathrm{cm}},
\\]

unless downstream analyses consistently use `PrimaryWeight`. The output tree does include `PrimaryWeight`, so weighted analyses are possible; unweighted analyses are biased. A robust generator would either sample directly from the tabulated cumulative distribution in solid angle or make every analysis gate explicitly weight-aware.

There are also smaller implementation risks:

- The generated azimuth is constrained by a fixed `det_size=5 cm`, `det_distance=1 m` acceptance approximation inside the generator, not by the imported actual geometry.
- `EvalWeight(theta3)` uses the lab proton angle, while the table name and generator context suggest a centre-of-mass differential cross section. If the table is centre-of-mass, this is a frame mismatch.
- The extrapolation branches allow weights outside the tabulated angular range rather than clipping or rejecting.
- `LoadFiles()` runs when `event->GetEventID()==0`; in multithreaded runs, event-id assumptions and mutable table vectors need stricter validation, even though the action-level mutex serializes generation.

## Physics List Review

The physics list registers:

- `G4EmStandardPhysics_option4`
- `G4EmExtraPhysics`
- `G4DecayPhysics`
- `G4HadronElasticPhysics`
- `G4HadronPhysicsINCLXX("INCL", true, true, true)`
- `G4StoppingPhysics`
- `G4IonPhysics`

This is a reasonable starting point for 190 MeV protons/deuterons and secondary hadrons in light materials. INCLXX is generally more appropriate than a pure high-energy FTFP-only configuration at these energies, and option4 EM is a strong choice for precision ionization and multiple scattering. However, this review does not validate the physics list against reference p/d stopping ranges, angular distributions, or target yield data. The earlier output files should therefore be treated as a simulation hypothesis, not a calibrated detector model.

The source prints `PAI model` and constructs `G4PAIModel`, but the `SetExtraEmModel(...)` calls are commented out. Therefore the PAI model is not actually attached to a region/process in the inspected code. If TPC gas energy-loss microphysics matters, this is not currently active.

## Tabulated Input Review

The two tabulated inputs are wired into the generator, but their scientific provenance is not self-describing:

| Table | Use in source | Concern |
|---|---|---|
| `dedx_p_in_CD2.txt` | Loaded as energy-loss table; energy is scaled by `938.28/931.5`, loss by `1000`. | No header/provenance was available in the reviewed file; units and conversion factors should be documented and checked against PSTAR/SRIM/Geant4 stopping powers. |
| `sigma_pd_cm_190.txt` | Loaded as angle/cross-section table and used as particle weight. | The file name implies CM cross section at 190 MeV, but the source applies weights to `theta3` after lab transform; this possible frame mismatch must be resolved. |

## Reproducibility Review

The run scripts are useful but not fully reproducible:

| Feature | Status |
|---|---|
| Environment setup | `run_full.sh` and `run_sim.sh` activate `nnbar_env`, source Geant4 11.2.2, and set VGM library paths. |
| Working directory | Scripts run from `hibeam_g4_github/build_conda`, not from a clean source/build recipe. |
| Seed pinning | No `--seed` is supplied in the reviewed scripts, although the binary supports `-s/--seed`. |
| Input provenance | Output ROOT ntuple records kinematics/hits/weights, but not input file hashes, macro text, config text, source commit, or random seed. |
| Build provenance | Source repo has untracked build directories; binary provenance is not cleanly recoverable from Git alone. |

Minimum fixes before relying on production outputs: require `--seed`, record source commit and dirty status, record SHA-256 of macro/config/geometry/tables into the ROOT file or a sidecar JSON, set `CheckOverlaps 1` at least once in validation mode, and archive the exact run command.

## Correctness Issues

| Severity | Issue | Consequence | Recommended fix |
|---|---|---|---|
| High | Cross-section table is used as event weight after uniform angular sampling, not as the generator sampling distribution. | Unweighted output is physically biased; downstream analyses can silently ignore the intended cross section. | Sample from the tabulated `dσ/dΩ` CDF including `sinθ`, or require/validate weight use in all analyses. |
| High | Possible CM-vs-lab angle mismatch in `EvalWeight(theta3)`. | Differential cross-section weights may be assigned to the wrong frame. | Confirm table frame; if CM, evaluate weights at `theta3cm`, not lab `theta3`. |
| Medium | PAI model constructed but not registered. | TPC ionization microphysics is not using the intended PAI model. | Either remove the inert call or attach PAI to the intended region/process with `SetExtraEmModel`. |
| Medium | Geometry is compact and overlap checking is not enabled in reviewed config. | Acceptance/material conclusions can be overconfident. | Run and document overlap checks; compare geometry positions/material budget with survey/build source. |
| Medium | Run scripts do not pin seed or capture provenance. | Results are not exactly reproducible from output files alone. | Add seed and sidecar manifest generation. |
| Low | `exit(0)` on missing input tables. | Batch failure can look successful. | Throw a fatal Geant4 exception or return nonzero. |

## Physics-Validity Judgement

For qualitative truth studies such as "do p/d deposits appear in the expected stack" or "is the ROOT output schema adequate for downstream truth analysis", this source is acceptable with explicit weight handling. For quantitative claims about CCB telescope response, rates, efficiencies, angular acceptance, energy loss, or particle identification, it is not yet fully validated. The largest unresolved risks are the angular weighting/frame issue, compact geometry fidelity, unvalidated tabulated stopping/cross-section provenance, and incomplete run provenance.

## Caveats

This was a source and input review, not a rebuild or high-stat rerun. I inspected the geometry file with ROOT in the documented conda environment, but I did not independently compare against survey drawings or the geometry builder source that produced the ROOT file. I also did not validate the output ROOT files statistically against experimental distributions. Those are separate validation tickets.

## Proposed Next Ticket

`S21b: Weighted scattering-source closure and geometry overlap audit`  
Question: Does the Krakow source produce the intended p-d angular distribution and a clean, non-overlapping geometry when weights, frames, and ROOT geometry are checked end-to-end?  
Expected information gain: high. It directly tests the two largest blockers from this review: CM/lab cross-section correctness and geometry overlap/fidelity risk.
