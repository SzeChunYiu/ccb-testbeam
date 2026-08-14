# CCB test-beam — manuscript outline (issue #797)

**Status:** skeleton. No claim may be written without a direct result-file path,
commit, config, input hash, uncertainty, and status label (see `docs/claim_ledger.csv`).
The figure generator must read result files dynamically — no hand-entered constants.

## Sections

1. **Introduction & detector** — extruded polystyrene stave (50 × 5.18 × 2.0 cm),
   two Y-11 fibres in 2 mm holes 2 cm apart, TiO2 coating, **one-fibre/one-end
   readout** on a Hamamatsu S13360-3050CS. Krakow 190 MeV proton/deuteron beam,
   HRD stacks A & B (8 B bars, 4 A bars).
2. **Data & MC samples** — run families; digitized-MC vs data-observable vs
   MC-truth distinction stated explicitly.
3. **Reconstruction & calibration** — v2 gain (not the obsolete 246 ADC/MeV),
   thresholds, saturation flags; never label ADC proxies as MeV.
4. **Timing (data & MC)** — after the `1/A` correction; sigma68 / RMS / core-σ /
   tail fraction / χ²; LORO spread; correction closure vs amplitude.
5. **ΔE–E PID** — correct Sample I/II definitions for data and MC; event key
   `(file_id, run, event)`; full-downstream vs data-matched four-layer MC.
6. **Stopping-depth & geometry systematics (#844)** — pinned deployed geometry,
   staged scan, χ²/ndf + likelihood GoF; the 11.12 g/cm² value is a scan start,
   not a calibrated answer.
7. **Single-stave optical calibration (#796)** — deposited-E vs photons/PE,
   held-out Edep reconstruction (PAPER-A09 / #1297), resolution/bias, collection
   efficiency, attenuation vs position, arrival-time vs position,
   proton/deuteron overlays, Birks scan, reflector/PDE/coupling/far-end/saturation
   systematics.
8. **What MC/ML learns and where it fails** — traditional baseline first, fair ML
   comparator, run-family splits (no leakage).
9. **Systematic uncertainty & external-data limitations** — see `limitations.md`.

## Figure list
Populated from `visualization/PLOT_MANIFEST.csv`; crosswalk in `plot_crosswalk.csv`.
Illustrative schematics are labelled `ILLUSTRATIVE` and kept separate from
quantitative figures.
