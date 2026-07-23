# SiPM/WLS audit and external research

## Review boundary

The source-level review was performed against `f147160f2c3be0df59f45c77cf209d2982547d04`. The handoff branch was later based on `2ad66f1016652a01a1adc44f3e9761024c9f621e` to include concurrent main changes. Re-read affected files before implementation.

## Current stave model findings

### P0

1. **Deterministic WLS delay.** `PhysicsList.cc` sets `SetWLSTimeProfile("delta")` while the Y-11 material sets `WLSTIMECONSTANT=8.5 ns`. Geant4 documents `delta` as a fixed delay and `exponential` as an exponentially sampled delay. The fixed model suppresses WLS timing variance and can bias first-photon timing, late-light fractions, resolution and pileup.
2. **Far-end mode is inert.** `far_end_boundary_absorb` is parsed and printed but not used by detector construction/stepping in the reviewed source.
3. **Overvoltage is inert.** `sipm_overvoltage_V` does not drive PDE, gain, DCR, crosstalk, afterpulse, recovery or run metadata.
4. **PDE is representative, not calibrated.** The committed table explicitly describes itself as manufacturer-representative and operating-point dependent. A scalar `pde_scale` is not a substitute for `PDE(lambda,Vov,T)`.
5. **No accepted response calibration.** The repository audit for issue 885 records 14/72 files, no timing/attenuation files, insufficient deuteron coverage and rejected proton global-line diagnostics.

### P1

6. The current finite-cell correction is only the non-recovery expectation `Ncell*(1-exp(-Npe/Ncell))`; it is not a sampled microcell process.
7. There is no recovery, dark count, crosstalk, afterpulse, gain spread, SPTR, waveform, front-end or ADC model.
8. The thin sensor disk uses the WLS core material and a manual boundary-transition detector rather than a dedicated sensor/window/surface/sensitive-detector contract.
9. A scalar coupling loss can double count losses when grease/window/interface optics are modelled explicitly.
10. Production can run with permissive fallback optical tables; campaign launchers should fail closed.
11. `BuildOpticalGap()` mutates the shared NIST `G4_AIR` MPT.
12. Arrival records lack local incidence, boundary status, reflection/WLS history and loss category.
13. Run metadata lacks effective WLS profile, temperature, overvoltage, device revision, correlated-noise/electronics parameters and implementation version.

### P2

14. `KNOWN_ISSUES.md` contains resolved/open historical contradictions.
15. Detector header/report comments contain stale overlap-token wording.
16. `kFastKernel` exists in the enum but CLI rejects fast mode.
17. Build evidence is currently tied to Geant4 11.2.2; forward compatibility must be tested rather than assumed.

## G4SiPM audit

Reviewed repository: `ntim/g4sipm`, head `40b0017f266c0708c39c595ebb4d09385acc2717`.

### Useful concepts

- sensor/model interface;
- cell mapping and recovery;
- prompt crosstalk;
- short/long afterpulse components;
- thermal noise;
- gain map;
- voltage trace;
- optional effective overvoltage/shunt response.

### Port hazards

- GPL-3.0 source versus no top-level CCB licence in the reviewed snapshot;
- last reviewed commit in 2017, targeting Geant4 10.3 compatibility;
- CMake 2.8-era global build configuration and broad Boost/Jansson/ROOT/SQLite coupling;
- global UI/RNG state with unclear modern MT determinism;
- raw ownership and verbose event logging;
- cell last-fire times initialised to the earliest queue time, making first-hit state suspect;
- cell-state map accessed before ID validation;
- logarithm/probability domains not centrally validated;
- edge cells lose invalid crosstalk neighbours unless that reduction is explicitly intended and validated.

**Decision:** clean-room reimplementation; use G4SiPM concepts, paper and frozen legacy comparisons as references.

## Recommended external projects

### Use now

- **Official Geant4 optical examples/docs:** OpNovice2 and WLS examples for maintained boundary/WLS regression patterns.
- **OPSim/OPSimTool:** useful architecture for reusable optical materials and surfaces; not a SiPM response model. Review licence before copying.
- **uproot/awkward/pandas:** streaming ROOT event/photon analysis and source tables.
- **SALib:** Morris screening followed by Sobol analysis for influential parameters.
- **SciPy/iminuit and emcee:** constrained likelihood/profile or Bayesian calibration after identifiability checks.
- **pyG4ometry:** independent geometry/GDML visualisation; not a replacement for Geant4 runtime overlap tests.

### Independent validation references

- **SiPM-APD-MPPC** (`JesusPenha/SiPM-APD-MPPC`, arXiv:2411.16710): waveform/noise/device cross-checks. No explicit repository licence was visible in the review; do not vendor without clarification.
- **GATE/OpenGATE:** useful digitizer-chain patterns; migrating the whole stave simulation is not justified.
- **SPICE/ngspice:** validate the analog transfer function offline, then use a fitted/tabulated impulse response in event simulation.

### Performance only after CPU acceptance

- **Opticks / EIC-Opticks / Simphony:** promising GPU optical transport, including recent WLS work. Require supported geometry, NVIDIA environment, batching benchmarks and frozen CPU/GPU wavelength/time/path/boundary/response gates.
- **Geant4 fast simulation/response kernels:** derive only after the accepted detailed model; index by relevant position, angle, energy-deposit topology and optical configuration.

## Required new analyses and plots

### Optical chain

- generated -> WLS -> fibre -> endpoint -> primary trigger -> avalanches -> unique cells -> charge waterfall;
- loss category by wavelength and boundary status;
- endpoint spectrum, arrival time, late-light fraction and path-time correlation;
- local sensor map and incidence angle;
- response versus x/y/angle and far-end mode;
- explicit `delta` versus `exponential` WLS timing comparison.

### Device

- PDE input/closure versus wavelength, Vov and temperature;
- primary triggers versus arrivals;
- cell occupancy map;
- unique cells and charge versus incident triggers;
- residual to analytic occupancy limit;
- recovery versus previous-cell delay;
- prompt-XT multiplicity;
- delayed-XT and afterpulse time-amplitude distributions;
- dark interarrival/threshold rates;
- charge spectrum and avalanche source fractions.

### Electronics/system

- measured versus simulated 1PE template;
- waveform overlays, baseline covariance/PSD, ADC occupancy/clipping;
- threshold efficiency/false rate, time walk and estimator residual;
- timing resolution versus PE and position;
- pileup separation;
- response/model residuals by energy/species/position;
- seed-level uncertainty and data/MC ratios;
- sensitivity indices and CPU/memory/GPU scaling.

Every plot requires its own source table, status label, exact input/config/code hashes, command and uncertainty definition.

## External source ledger

- Geant4 optical process documentation and official Geant4 repository;
- G4SiPM repository and NIM A paper (`10.1016/j.nima.2015.01.024`);
- Hamamatsu S13360-3050CS product page and MPPC technical guide;
- arXiv:2411.16710 (SiPM/APD/MPPC simulation framework);
- arXiv:2607.14290 (recent WLS-SiPM timing decomposition; preprint);
- arXiv:2512.06061 and arXiv:2502.13215 (Opticks/EIC GPU studies);
- arXiv:2606.05385 (Simphony GPU WLS; recent preprint);
- OPSim repository and CPC paper (`10.1016/j.cpc.2023.108873`);
- SALib, uproot, iminuit, emcee official documentation.

The full delivered ZIP contains a machine-readable CSV source ledger with URLs, review dates, source classes and intended use.
