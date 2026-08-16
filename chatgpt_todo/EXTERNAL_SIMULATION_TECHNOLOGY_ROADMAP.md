# External Simulation Technology Roadmap

**Repository:** `SzeChunYiu/ccb-testbeam`  
**Prepared:** 2026-07-23  
**Status:** research and implementation roadmap; not a claim that any external engine is already validated for CCB  
**Parent plan:** `chatgpt_todo/SCIENTIFIC_GRADE_AUDIT_VISUALIZATION_CLAIM_PLAN.md`

## 1. Decision

The strongest near-term upgrade is a measured and validated **optical photon -> SiPM avalanche -> analogue waveform -> ADC code** chain. GPU acceleration should follow a frozen CPU reference model rather than precede it. The recommended order is:

1. close geometry, optical-table, SiPM-parameter and electronics contracts;
2. implement a formal hit/avalanche/analogue/ADC digitisation chain;
3. validate it against dedicated bench and existing waveform data;
4. profile the reference simulation;
5. pilot Opticks/Simphony for optical photons;
6. use DD4hep/conditions and a versioned event model for the full detector;
7. integrate Garfield++ only in gaseous detector regions;
8. benchmark Celeritas/AdePT only where profiling shows a supported EM workload;
9. introduce response kernels or ML surrogates last, with explicit support-domain gates.

External packages must close named gaps and pass paired validation against CPU Geant4 and real measurements. More dependencies are not automatically more scientific.

## 2. Layered architecture

```text
beam/reaction truth
  -> geometry + materials + time-dependent conditions
  -> Geant4 hadronic/EM transport and optical production
  -> optical-photon propagation (CPU reference or validated GPU path)
  -> SiPM avalanche and microcell response
  -> analogue front end and ADC digitisation
  -> trigger/readout and versioned event data
```

Each boundary must preserve before/after truth, event/source/channel keys, units, weights, configuration, seeds and hashes.

## 3. Technology assessment

| Technology | Role | Relevance | Risk | Recommendation |
|---|---|---|---|---|
| **Opticks / Opticks-derived Simphony** | GPU optical-photon ray tracing with a hybrid Geant4 workflow | Highest performance value for the optical-heavy stave and optical components of the full detector | NVIDIA CUDA/OptiX dependency; geometry conversion, WLS and boundary-process parity must be validated | Pilot against frozen CPU Geant4; never replace the reference path before equivalence tests pass |
| **G4SiPM** | Detailed SiPM model including temperature/bias, PDE, gain variance, dark noise, dead/recovery time, crosstalk and afterpulsing | High scientific value for converting arriving photons into avalanches | Documentation targets an old Geant4/compiler stack; maintenance and Geant4 11 compatibility are uncertain | Create an isolated maintained fork or adapter; port and test effects individually rather than trusting legacy binaries |
| **Geant4 `G4DigiManager` / `G4VDigitizerModule`** | Formal hit-to-digit separation | Essential | Low; native Geant4 architecture | Adopt directly or reproduce the same separation in a framework-independent digitizer |
| **ngspice** | Transient and noise simulation of bias network, cable, amplifier and shaping | High for realistic ADC waveform formation | Per-event circuit solving is too expensive | Use offline to derive/validate impulse and noise models; production uses a validated reduced model |
| **DD4hep/DDG4/DDCond** | Unified geometry, materials, readout, alignment, calibration and conditions | Very high for full detector; useful source for extracted stave geometry | Migration cost | Adopt for the full detector and make the stave consume the same source of truth |
| **EDM4hep/podio** | Typed truth/hit/digit relations and schema evolution | High for full-detector reproducibility | Migration cost | Evaluate as canonical event-data layer if DD4hep is adopted |
| **HepMC3** | Generator ancestry, weights and extensible event metadata | High | Low-medium | Use at the generator-to-Geant4 boundary instead of bespoke truth branches |
| **Garfield++/Magboltz/Heed** | Gas ionisation, drift, avalanche and induced signal | High only for ProtoTPC/gas regions | Specialized handoff and unit complexity | Integrate regionally; Geant4 remains responsible for surrounding materials and transport |
| **Allpix Squared + TCAD** | Semiconductor charge transport and frontend digitisation | Good for conventional silicon sensors; not an out-of-box SiPM avalanche model | Custom SiPM microcell work would be large | Use for other silicon sensors; treat TCAD-informed SiPM work as a separate advanced study |
| **Celeritas** | GPU particle transport integrated with Geant4 | Potentially valuable for large supported EM workloads in the full detector | Physics coverage/callback cost must be checked | Benchmark after optical acceleration and geometry closure |
| **AdePT/G4HepEm** | GPU electron/positron/gamma transport in selected regions | Limited for the proton/deuteron stave; useful only for EM-heavy regions | Active R&D and limited particle scope | Optional full-detector benchmark, not the primary stave accelerator |
| **VecGeom** | GPU-compatible geometry/navigation | Indirect performance benefit | Additional geometry path | Use through DD4hep/Celeritas/AdePT where justified |
| **CAD-to-GDML tools** | Import surveyed mechanical structures and passive material | High when real CAD exists | Mesh/material/overlap/navigation risks | Use only with immutable CAD plus mesh-convergence, mass and material validation |

## 4. G4SiPM does not generate the measured ADC by itself

The scientifically correct chain is:

```text
optical photon at sensor
  -> wavelength/position/angle-dependent detection
  -> primary avalanche
  -> crosstalk, afterpulse and dark avalanches
  -> microcell recovery and finite-cell saturation
  -> summed SiPM current
  -> cable/bias/front-end transfer function
  -> noise, baseline memory and clock jitter
  -> ADC aperture, quantisation, nonlinearity and clipping
  -> trigger/readout logic
```

G4SiPM can strengthen the avalanche/microcell layer. A separate electronics and ADC digitizer is still required.

Required SiPM parameters include device/batch identity, active area, cell count/fill factor, breakdown voltage, bias/overvoltage, temperature coefficients, wavelength-dependent PDE, gain distribution, dark count, prompt/delayed crosstalk, afterpulse delays, cell recovery, partial-recovery charge, illumination nonuniformity and sensor-window optics. Product-page typical values are priors, not substitutes for measurements of the installed hardware.

## 5. Electronics and ADC model

Provide two fidelity modes:

- **circuit-reference mode:** ngspice transient/noise simulations for single-PE and representative multi-PE current patterns;
- **production mode:** validated impulse-response convolution plus explicit nonlinearities, baseline memory, noise and digitisation.

Model or measure:

- SiPM capacitance and bias/quench network;
- cable impedance, delay, reflections and termination;
- transimpedance/preamp gain and bandwidth;
- shaping and AC coupling;
- saturation, slew rate and recovery;
- thermal, shot, amplifier, common-mode and quantisation noise;
- baseline drift, droop and previous-event memory;
- sample clock phase/jitter;
- ADC gain/offset, DNL/INL, effective bits, aperture and clipping;
- trigger threshold, hysteresis, dead time and readout window.

Persist ideal optical/avalanche/analogue intermediates and final ADC codes so every distortion is visible.

## 6. Single-stave Opticks/Simphony pilot

Keep two paths from identical geometry and pre-optical truth:

1. CPU Geant4 optical reference;
2. Geant4 charged-particle transport and optical generation followed by GPU optical propagation.

Paired validation must compare generated/transported/detected counts; wavelength, arrival time, path length and incidence angle; boundary-loss categories; WLS count, spectrum and delay; position/angle response; inter-sensor covariance; late-photon tails; initialization/transfer overhead; memory and batching performance.

Use equivalence tests and confidence intervals, not visual overlay alone. Tolerances must come from detector precision requirements and Monte Carlo uncertainty. Unsupported optical features remain blocking.

Before offload, strengthen the optical model with measured wavelength-dependent scintillator emission/absorption, Y-11 absorption/emission/attenuation, refractive indices, surface reflectivity, PDE, glue/grease/air gaps, fibre-hole roughness and actual far-end treatment. GPU acceleration cannot repair an undefined reference model.

## 7. Full-detector architecture

### Geometry and conditions

Use DD4hep/DDCond to hold physical geometry, passive material, channel mapping, alignment/survey uncertainty and per-run temperature, bias, gain, threshold and disabled-channel states. The single-stave geometry should eventually be extracted from the same description.

### Generator and event model

Use HepMC3 or an equivalent standard for beam/reaction ancestry, event/particle weights, vertices, times, generator configuration and cross-section provenance. Use EDM4hep/podio or an equivalent typed schema for truth, hits, avalanches, digits and relations.

### ProtoTPC/gas response

For accepted gas regions, Geant4 handles external transport while Garfield++/Heed or a validated Geant4 PAI handoff produces ionisation; Magboltz supplies gas transport; Garfield++ models drift, avalanche and induced current. Gas composition, pressure, temperature, fields, attachment, Penning transfer and electronics are versioned conditions. Validate W value, Fano factor, drift, gain, signal shape, energy accounting and handoff thresholds.

### Hadronic model ensemble at about 190 MeV

Do not rely on one physics list. Compare the current Binary Cascade configuration with applicable alternatives such as `QGSP_BIC_AllHP` and `QGSP_INCLXX`/`FTFP_INCLXX`. INCL++ explicitly supports proton and light-ion projectiles including deuterons and deuterium targets in the relevant energy domain. Also vary electromagnetic constructors, cuts and de-excitation where justified. Compare to external reaction/cross-section data and held-out detector observables; model spread is not automatically a valid systematic unless all variants are applicable.

### GPU transport

- Opticks/Simphony: first priority when optical transport dominates.
- Celeritas: benchmark for supported full-detector electromagnetic workloads.
- AdePT: benchmark only in electron/positron/gamma-heavy regions.
- CPU Geant4: reference for proton/deuteron hadronic and unsupported transport.

Record which engine handled every region/track class and test energy conservation across all handoffs.

## 8. Bench measurements required

1. single-PE charge and waveform versus temperature/overvoltage;
2. dark count, crosstalk and afterpulse distributions;
3. double-pulse microcell recovery;
4. PDE or relative spectral response;
5. electronics impulse/frequency response from injected signals;
6. ADC pedestal, PSD, transfer curve, DNL/INL, saturation and recovery;
7. fibre attenuation and propagation-time scans along the stave;
8. source/beam scans versus position, angle, species and energy;
9. alternate wrapping, coupling and far-end configurations.

Reserve held-out conditions for final closure rather than using every measurement for tuning.

## 9. Required diagnostic plots

- CPU Geant4 versus GPU optical count ratios and wavelength/time/path distributions;
- optical loss and boundary-process categories;
- GPU photons/s, batching, memory and end-to-end overhead;
- PDE, gain, saturation, recovery, crosstalk, afterpulse and dark-count plots;
- single/multi-PE charge and waveform distributions;
- ngspice versus reduced impulse/frequency/noise response;
- analogue-to-ADC step plot, transfer curve, DNL/INL, clipping and recovery;
- DD4hep/TGeo/Geant4 geometry, mass, material and channel-map differences;
- Geant4/Garfield ionisation, drift, gain, induced signal and handoff accounting;
- hadronic model yields, stopping, secondary spectra and trigger acceptance;
- hybrid engine track/energy/time accounting;
- T0/T1/T2 fidelity-tier closure and support-domain maps.

Every plot needs exact input/output hashes, code/config versions, axes/units, selection, uncertainty meaning and acceptance criteria.

## 10. Fidelity tiers

| Tier | Purpose | Detail | Claim boundary |
|---|---|---|---|
| **T0 reference** | Calibration/validation | CPU Geant4 optical truth plus detailed sensor/electronics | Scientific reference only after data/physics closure |
| **T1 accelerated** | Large production | Validated GPU optical and/or supported EM offload with the same sensor/electronics | Production only after T0 equivalence |
| **T2 fast/surrogate** | Design scans and ML generation | Response kernels or fast models trained on T0/T1 | Diagnostic/design use; final claims require T0/T1 closure |

The simulation tier is mandatory metadata. T2 outputs may not be silently mixed with reference results.

## 11. Work packages

| ID | Priority | Deliverable | Gate |
|---|---:|---|---|
| `SIM-EXT-001` | P0 | Current simulation wall-time/memory profiler by physics stage | Reproducible bottleneck report |
| `SIM-EXT-002` | P0 | Versioned optical/SiPM/electronics parameter registry with units, uncertainty and source class | Missing required inputs abort production |
| `SIM-EXT-003` | P0 | Formal hit -> avalanche -> analogue -> ADC interfaces | Intermediate truth retained and held-out waveform closure achieved |
| `SIM-EXT-004` | P0 | G4SiPM compatibility spike or maintained Geant4 11.4.x fork | Clean build and individual stochastic-effect tests |
| `SIM-EXT-005` | P0 | ngspice reference circuit and reduced production model | Impulse/frequency/noise and component-variation closure |
| `SIM-EXT-006` | P0 | Opticks/Simphony single-stave pilot | Optical equivalence and net end-to-end speed benefit |
| `SIM-EXT-007` | P0 | 190 MeV hadronic physics-model ensemble | Applicability, model/data diagnostics and uncertainty interpretation |
| `SIM-EXT-008` | P0 | DD4hep geometry/readout/conditions prototype | Geometry/material/channel equivalence |
| `SIM-EXT-009` | P1 | EDM4hep/podio or equivalent event schema | Round-trip, relation and schema-evolution tests |
| `SIM-EXT-010` | P1 | Geant4/Garfield++ gas-region prototype | W/Fano/drift/gain/signal and handoff closure |
| `SIM-EXT-011` | P1 | Celeritas EM benchmark | Supported physics and end-to-end reference agreement |
| `SIM-EXT-012` | P2 | AdePT regional benchmark | e-/e+/gamma-only scope explicit |
| `SIM-EXT-013` | P2 | CAD/GDML passive-material study | Mesh convergence, mass/material/overlap validation |
| `SIM-EXT-014` | P2 | Allpix/TCAD feasibility study | Separate silicon/advanced-SiPM scope; no false equivalence to SiPM avalanche physics |
| `SIM-EXT-015` | P2 | Validated fast/surrogate tier | Independent coverage and automatic rejection outside support |

## 12. Deployment and provenance

Pin Geant4/datasets, compiler, CUDA/OptiX, GPU architecture, Opticks/Simphony commit, G4SiPM fork, DD4hep/ROOT/VecGeom, Celeritas/AdePT, Garfield++/Magboltz/Heed, ngspice and every circuit/table/config hash in Spack and/or Apptainer definitions. GPU outputs must record device model, driver/runtime, precision mode, batching and relevant environment variables.

## 13. Primary references

- Geant4 CaTS/G4Opticks example: https://geant4.web.cern.ch/docs/advanced_examples_doc/example_cats.html
- Geant4 Opticks integration task: https://geant4.web.cern.ch/collaboration/working_groups/task_force_rd/g4rd13
- Recent Opticks-derived GPU optical studies: https://arxiv.org/abs/2512.06061 and https://arxiv.org/abs/2606.05385
- G4SiPM documentation/model: https://g4sipm.readthedocs.io/en/latest/ and https://g4sipm.readthedocs.io/en/latest/g4sipm_model.html
- Hamamatsu S13360-3050CS: https://www.hamamatsu.com/jp/en/product/optical-sensors/mppc/mppc_mppc-array/S13360-3050CS.html
- Geant4 digitisation: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/Detector/digitization.html
- ngspice: https://ngspice.sourceforge.io/docs.html
- DD4hep/DDG4: https://dd4hep.web.cern.ch/page/about/ and https://dd4hep.web.cern.ch/usermanuals/DDG4Manual/DDG4Manual.html
- EDM4hep/podio: https://key4hep.github.io/key4hep-doc/main/how-tos/key4hep-tutorials/edm4hep_analysis/edm4hep_api_intro.html
- HepMC3: https://arxiv.org/abs/1912.08005
- Garfield++ Geant4 interface: https://garfieldpp.docs.cern.ch/tutorials/g4/
- Allpix Squared: https://allpix-squared.docs.cern.ch/docs/01_introduction/
- Celeritas Geant4 integration: https://celeritas-project.github.io/celeritas/user/example/geant4.html
- AdePT: https://adept-project.readthedocs.io/en/latest/
- Geant4 INCL++: https://geant4.web.cern.ch/documentation/dev/prm_html/PhysicsReferenceManual/hadronic/INCL/Incl.html
- Geant4 QGSP_BIC: https://geant4.web.cern.ch/documentation/dev/plg_html/PhysicsListGuide/reference_PL/QGSP_BIC.html
- Geant4 optical surfaces: https://geant4.web.cern.ch/documentation/pipelines/master/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/physicsProcess.html
- GUIMesh CAD-to-GDML: https://arxiv.org/abs/1807.04319

## 14. Final recommendation

Proceed first with `SIM-EXT-001` through `SIM-EXT-006`. This creates a scientifically defined CPU reference, a realistic SiPM/electronics/ADC response, and a controlled optical-GPU pilot. For the full detector, follow with DD4hep/conditions, the event-data model, Garfield++ where applicable and the hadronic model ensemble. Celeritas and AdePT are promising performance options but do not replace the proton/deuteron hadronic, optical, sensor or electronics validation programme.
