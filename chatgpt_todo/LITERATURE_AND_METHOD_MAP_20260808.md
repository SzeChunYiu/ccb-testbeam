# Literature and method map — 2026-08-08

Purpose: connect atomic project assumptions to primary/authoritative references and, crucially, to experiments that still have to be performed on the CCB hardware/data. Literature values are priors or comparison points, not substitutions for detector-specific calibration.

## Plastic-scintillator quenching and p/d response

- Pöschl et al., *Measurement of ionization quenching in plastic scintillators*, NIM A 988 (2021) 164865, DOI: https://doi.org/10.1016/j.nima.2020.164865. Measures quenching-vs-energy-deposition density and fits multiple models. Use to justify model comparison rather than assuming one universal Birks constant.
- Awe et al., *Measurement of proton quenching in a plastic scintillator detector*, JINST 16 (2021) P02035, DOI: https://doi.org/10.1088/1748-0221/16/02/P02035. Proton-specific response evidence.
- O'Rielly, Kolb & Pywell, *The response of plastic scintillator to protons and deuterons*, NIM A 368 (1996) 745–749, DOI: https://doi.org/10.1016/0168-9002(95)00671-0. Directly relevant p/d light-response comparison over energies extending to the CCB range.
- Madey et al., *Determination of the light response of BC-404 plastic scintillator for protons and deuterons with energies between 1 and 11 MeV*, NIM A 268 (1988) 200–203, DOI: https://doi.org/10.1016/0168-9002(88)90606-7. Reinforces non-linearity at low p/d energy.

**CCB consequence:** fit/compare physically plausible quenching laws on independent MC energies and propagate model uncertainty. Do not promote a single literature kB to detector truth without material-specific closure.

## WLS fibre transport and timing

- Kuraray technical data for Y-11(200): emission peak ~476 nm, absorption peak ~430 nm and representative attenuation length >3.5 m for the stated measurement conditions: https://methacrylate.kuraray.com/en/products/psf/tech/ . Vendor data explicitly say values are representative, not guaranteed.
- Adamyan et al., *Measurement of light attenuation angular dependence in a double-clad wavelength shifting fibre Y11(200)MS*, NIM A 534 (2004) 434–440, DOI: https://doi.org/10.1016/j.nima.2004.06.167. Shows attenuation is not a single geometry-independent scalar.
- Kodama et al., *Performance of new Kuraray wavelength-shifting fibers with short decay time*, arXiv:2311.07297. Measures Y-11 decay time ~7.10 ns in the same apparatus used to compare new fibres. Treat as device-family timing evidence, not CCB timing calibration.

**CCB consequence:** the optical MC needs measured/validated wavelength-dependent absorption/emission, WLS time constant, bulk/surface losses, end reflectivity/coupling and SiPM PDE. A single effective propagation speed is inadequate for final timing uncertainty.

## SiPM recovery, crosstalk and afterpulsing

- Rosado & Hidalgo, *Characterization and modeling of crosstalk and afterpulsing in Hamamatsu silicon photomultipliers*, arXiv:1509.02286. Separates prompt/delayed crosstalk and afterpulsing components using amplitude-delay distributions and MC.
- Gallego et al., *Modeling crosstalk in silicon photomultipliers*, arXiv:1302.1455. Includes finite-neighbour models, recovery/dead-time effects and dedicated waveform measurements.
- Hamamatsu MPPC characterization guide: https://hub.hamamatsu.com/us/en/technical-notes/mppc-sipms/a-technical-guide-to-silicon-photomutlipliers-MPPC-Section-4.html . Gives digitizer-based procedures for DCR, prompt crosstalk, recovery, afterpulse and delayed-crosstalk measurements; vendor example recovery times are device-specific.

**CCB consequence:** B2 late/overlap waveforms cannot be uniquely labelled pile-up from morphology alone. Bench or dark-run measurements should constrain the exact installed SiPM/electronics recovery and correlated-noise time scales, then inject those into the digitiser MC.

## Digital timing

- Fallu-Labruyere et al., *Time resolution studies using digital constant fraction discrimination*, NIM A 579 (2007) 247–251, DOI: https://doi.org/10.1016/j.nima.2007.04.048.
- Cleland & Stern, *Signal processing considerations for liquid ionization calorimeters in a high rate environment*, NIM A 338 (1994) 467–497, DOI: https://doi.org/10.1016/0168-9002(94)91332-3.

**CCB consequence:** timing performance depends on sampled pulse shape, phase, noise covariance and calibration. The 10 ns sample interval does not by itself forbid sub-bin timing, but sub-bin claims require phase-aware waveform closure and validated interpolation/template assumptions.

## ΔE–E and range telescopes

- Tassan-Got, *A new functional for charge and mass identification in ΔE–E telescopes*, NIM B 194 (2002) 503–512, DOI: https://doi.org/10.1016/S0168-583X(02)00957-6. Defines the telescope concept as energy loss in one/several components versus residual energy in the detector where the particle stops, and explicitly treats non-linear scintillator light response.
- Schneider et al., *A detector system for proton radiography on the gantry of the Paul-Scherrer-Institute*, NIM A 432 (1999) 483–495, DOI: https://doi.org/10.1016/S0168-9002(99)00284-3. Demonstrates residual-range measurement with a plastic-scintillator range telescope.

**CCB consequence:** the data analogue should be defined as a labelled amplitude proxy for ΔE and downstream residual response. Missing every second stave creates an explicit censoring/segmentation nuisance; parity and energy scans belong in the acceptance test, not only in interpretation.

## Geant4 optical/scintillation implementation

Authoritative Geant4 documentation:
- Physics Reference Manual: https://geant4.web.cern.ch/documentation/pipelines/master/prm_html/PhysicsReferenceManual/index.html
- Scintillation: https://geant4.web.cern.ch/documentation/dev/prm_html/PhysicsReferenceManual/electromagnetic/xray_production/scint.html
- Application Developers optical/scintillation guide: https://geant4.web.cern.ch/documentation/dev/bfad_html/ForApplicationDevelopers/TrackingAndPhysics/physicsProcess.html

The documentation states that scintillation yield can be non-linear with local energy deposition, that Birks saturation changes the visible-energy deposit used for scintillation yield, and that optical transport requires absorption, wavelength shifting and boundary interactions.

**CCB consequence:** every data/MC light-yield claim needs a complete chain from deposited energy through quenching, optical transport, sensor detection, correlated noise/recovery and electronics digitisation, with each property versioned and source-bound.

## Research gaps this map creates

1. Measure or identify the exact scintillator formulation, WLS fibre grade/diameter/cladding, SiPM model, overvoltage, temperature and front-end shaping used in the beam test.
2. Build a detector-property ledger with source type (`BENCH`, `DATASHEET`, `PRIMARY_PAPER`, `FIT`, `ASSUMED`) and uncertainty/range for every optical/electronic parameter.
3. Run parameter/nuisance ensembles, not one nominal optical MC.
4. Compare simulation to held-out real runs at waveform level before comparing only derived amplitudes/times.
5. Treat literature disagreement/model dependence as a systematic dimension rather than selecting the value that best matches data.