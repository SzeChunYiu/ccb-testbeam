# Single-stave plot completion matrix

| plot_id | plot | required_input | status | scientific_purpose |
|---|---|---|---|---|
| SS-01 | Deposited-energy distributions | events | generated in demo; rerun on real ROOT | Detect tails, stopping populations, species overlap |
| SS-02 | Raw/visible ratio vs dE/dx | events | generated in demo; critical on real ROOT | Exposes current Birks bookkeeping defect |
| SS-03 | PE vs Edep | events | generated in demo; real summary also included | Linearity, intercept, heteroscedasticity |
| SS-04 | Arrivals vs generated optical tracks | events | generated in demo | Collection model closure |
| SS-05 | Detected vs arrivals | events | generated in demo | PDE/coupling stage closure |
| SS-06 | Collection-efficiency distribution | events | generated in demo | Non-Gaussian optical losses |
| SS-07 | Effective PDE × coupling distribution | events | generated in demo | Check consistency with configured PDE/coupling |
| SS-08 | PE/MeV vs x position | events | generated in demo | Attenuation and longitudinal uniformity |
| SS-09 | Mean response by sensor | events | generated in demo | Four-channel symmetry/control comparison |
| SS-10 | Near/far asymmetry vs x | events | generated in demo | Position sensitivity and attenuation |
| SS-11 | Track length vs angle | events | generated in demo | Geometry/path-length closure |
| SS-12 | SiPM saturation transfer | events | generated in demo | Occupancy model and dynamic range |
| SS-13 | Mean PE vs KE | events | generated in demo and actual summary | Calibration-grid response |
| SS-14 | Resolution vs KE | events | generated in demo and actual summary | Energy/species dependence |
| SS-15 | Held-out unconstrained calibration bias | events | generated in demo | Reject nonphysical global intercept model |
| SS-16 | Held-out through-origin calibration bias | events | generated in demo | Compare physically constrained baseline |
| SS-17 | Zero-response fraction | events | generated in demo | Inefficiency and pathological events |
| SS-18 | Correlation matrix | events | generated in demo | Spot redundant or unexpected dependencies |
| SS-19 | Raw minus visible Edep | events | generated in demo; critical on real ROOT | Direct raw/visible equality check |
| SS-20 | Sensor arrival shares | events | generated in demo | Global optical symmetry |
| SS-21 | Arrival/detected wavelength spectra | photons | generated in demo; rerun on real photon tree | WLS spectrum and spectral acceptance |
| SS-22 | Detection fraction vs wavelength | photons | generated in demo | Reconstruct effective PDE curve |
| SS-23 | Arrival-time distributions by sensor | photons | generated in demo | Timing tails and sensor asymmetry |
| SS-24 | Time vs optical path length | photons | generated in demo | Group velocity/path closure |
| SS-25 | Detection fraction vs time | photons | generated in demo | Bias against late photons |
| SS-26 | Wavelength vs arrival time | photons | generated in demo | WLS/time correlations |
| SYS-01 | Mean PE vs Birks kB | scan ensemble | requires real systematic grid | Quenching systematic |
| SYS-02 | Mean PE vs reflectivity scale | scan ensemble | requires real systematic grid | Coating systematic |
| SYS-03 | Mean PE vs attenuation scale | scan ensemble | requires real systematic grid | Bulk attenuation systematic |
| SYS-04 | Mean PE vs PDE scale | scan ensemble | requires real systematic grid | Sensor systematic |
| SYS-05 | Mean PE vs coupling | scan ensemble | requires real systematic grid | Coupling systematic |
| SYS-06 | Absorb vs mirror far end | scan ensemble | requires real systematic grid | Boundary-condition systematic |
| SYS-07 | Response vs SiPM cell count | scan ensemble | requires real systematic grid | Saturation systematic |
| RNG-01 | Per-seed distributions and widths | multi-seed ROOT | summary plot included; full trees required | Mean stability alone is insufficient |
| MT-01 | 1T-vs-Nt event differences | paired ROOT | existing validator; retain event-key plots | Thread reproducibility |
| MT-02 | 1T-vs-Nt photon multiset differences | paired photon ROOT | existing validator | Order-independent photon reproducibility |
| REF-01 | dE/dx vs external stopping-power reference | events + PSTAR/SRIM | not generated; external reference required | Physics validation beyond self-consistency |

## Acceptance rule

A plot is not considered complete unless its source-data table, input hashes, run metadata, event count, units, and selection definition are stored beside it. Synthetic demonstration plots are templates only and must never be cited as detector-performance evidence.
