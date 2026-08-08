# Current atomic findings — recursive addendum 2 (2026-08-08)

This file continues `CURRENT_ATOMIC_FINDINGS_ADDENDUM_20260808.md` and covers AF-054 through AF-059. Base initially audited: `main@957c2fd6fa5b80233a283e88420631e93ee8cec7`.

## AF-054 — reflective coating is optical-only while its physical shell is air (#1005)

`docs/stave-geometry.md` describes a 0.25 mm TiO2 reflective shell. `DetectorConstruction.cc` creates the coating solid with **air** as its material, while a TiO2-like dielectric-metal surface supplies reflectivity. This is an optical approximation that removes the coating's charged-particle areal density from proton/deuteron transport. The actual paint/pigment/binder composition and dry thickness must be recovered from CCB construction evidence or scanned as a material nuisance; do not replace the air volume with pure bulk TiO2 by guesswork.

## AF-055 — hadronic transport model is hard-coded and has no applicable-model uncertainty (#1006)

`main.cc` hard-codes `QGSP_BIC` and a 0.1 mm production cut. The p/d programme spans roughly 2–190 MeV and uses stopping layer, secondary production and deposited energy as physics observables. Geant4 offers other applicable models in this domain, notably INCL++ for light-ion projectiles including deuterons, as well as data-driven low-energy charged-particle options where isotope/data coverage applies. The task is not to average arbitrary physics lists; it is to build an applicability matrix, make the configuration/provenance explicit, validate against external stopping/reaction data, and propagate a defensible model uncertainty.

## AF-056 — event `Edep/path` is not primary stopping power (#1007)

`SteppingAction.cc` accumulates `edep_scint_raw_MeV` and `track_len_scint_mm` for **every non-optical track** in the scintillator. `compare_stopping_power.py` forms an event/sample deposit/path ratio and compares proton rows with PSTAR. Once delta electrons, nuclear secondaries or other tracks contribute, this is a calorimetric all-particle transport ratio, not the stopping power of the primary proton at a defined kinetic energy. Persist separate primary path/entry/exit-energy quantities, classify nuclear interactions, and reserve PSTAR/local stopping-power validation for a physically comparable primary estimator.

## AF-057 — kB scan covers parameter uncertainty inside one quenching model, not model-form uncertainty (#1008)

The current single-stave grid varies Birks `kB` but leaves the Birks functional form fixed. Primary plastic-scintillator literature compares multiple quenching models and provides proton/deuteron response measurements. The final p/d PID/light-response uncertainty therefore needs a model-form dimension as well as parameter uncertainty, with parameters/source material/density conventions kept explicit. Literature models are priors/cross-checks; the CCB hardware still needs held-out validation.

Primary anchors already entered into the literature map:

- Pöschl et al., *Measurement of ionization quenching in plastic scintillators*, NIM A 988 (2021) 164865, DOI `10.1016/j.nima.2020.164865`.
- O'Rielly, Kolb & Pywell, *The response of plastic scintillator to protons and deuterons*, NIM A 368 (1996) 745–749, DOI `10.1016/0168-9002(95)00671-0`.

## AF-058 — production Geant4 discards the SiPM waveform and keeps only a peak (#1009)

`EventAction` obtains the complete `ccb-sipm-core` ADC waveform but stores only the maximum ADC above baseline. The representative core runs on a fine internal time grid, whereas the real DAQ contract is still under 8×16/8×18 forensic resolution. A historical S17c study uses an independent parametric 18-sample bridge; it is not equivalent to the current Geant4+core response by construction. Persist the production waveform, distinguish high-resolution internal response from the actual DAQ observation grid, model clock phase/aperture/quantisation/polarity/channel ordering, and run the identical reconstruction on data and DAQ-sampled MC.

## AF-059 — default front-end transfer function is explicitly unmeasured (#1010)

The pinned `ccb-sipm-core` labels its generic CR-RC(-RC) electronics impulse as `ASSUMPTION_GENERIC_CRRC_NOT_MEASURED` and exposes a measured-impulse hook. Timing, tail, pile-up and saturation studies are directly sensitive to the real CCB front-end transfer function and noise covariance. Recover the board/channel identity and measured/injected-pulser or isolated-single-PE response; if inferred from data, label the result `DATA_FIT`, freeze it on calibration data, and validate on held-out runs before using it to authorise detector timing/pile-up claims.

## Updated dependency insight

These six findings tighten the data→transport→response chain:

`hardware/material ledger (#987,#991,#992,#1000,#1005)`
→ `physics model (#1006)`
→ `primary/all-particle transport truth (#1007)`
→ `quenching model ensemble (#1008)`
→ `optical/SiPM/electronics effective response (#979–#981,#974–#977,#1010)`
→ `exact DAQ waveform observation schema (#952,#993,#1009)`
→ `identical real/MC reconstruction (#963–#968,#956)`.

A later agreement in ADC amplitude cannot retroactively validate an upstream material, hadronic or quenching assumption if compensating detector-response parameters are free. Calibration and validation splits must therefore be defined by parameter layer, and nuisance parameters should be constrained by the observables they physically control rather than jointly tuned to the final PID plot.