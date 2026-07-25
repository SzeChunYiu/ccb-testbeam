# MV6 — Truth-labelled MC toy morphology diagnostic

- status: **TRUTH_LEVEL_MC_ONLY / TOY_DIAGNOSTIC**
- generated: 2026-07-25 18:34:53
- MC file: `output_krakow_1M.root`
- tracks: 7,848 B-arm charged tracks from 20,000 scanned events
- seed: 42

## Question and boundary

The script applies a toy waveform generator and a morphology taxonomy to
truth-labelled simulation. It measures the composition of its own MC-defined
early-peak class. It does not identify the beam-data anomaly, whose observed
frequency and detector response are not matched to this toy sample.

## Overall morphology

The toy sample contains 38 early-peak tracks among 7,848 tracks (0.4842%). The
source result labels 25/38 as C12, 5/38 as electrons, 3/38 as alpha, 3/38 as
protons, and 2/38 as other heavy ions. These are small truth-MC composition counts,
not a data-class purity measurement.

## Per-species morphology (%)

| species | n | early_peak | low_area | saturated | normal |
|---|---:|---:|---:|---:|---:|
| proton | 2956 | 0.10 | 0.00 | 70.5 | 29.4 |
| deuteron | 2886 | 0.00 | 0.00 | 88.3 | 11.7 |
| alpha | 925 | 0.32 | 0.00 | 1.5 | 98.2 |
| C12 | 677 | 3.69 | 0.00 | 0.0 | 96.3 |
| heavy_ion | 291 | 0.69 | 0.00 | 4.5 | 94.8 |
| electron | 113 | 4.42 | 0.00 | 0.0 | 95.6 |

## PCA and GMM

The toy waveform PCA cumulative variance is 0.7487096194520252 at four
components and 0.8328085701449488 at eight components. These values describe this
new 7,848-track toy sample and do not supersede canonical `CL-023`/`CL-024`, which
refer to a different 87,555-track source run.

The four-component GMM is not a species classifier. Cluster 3 contains all 38
early-peak tracks but is dominated by 1,280 normal tracks; cluster 3 is only 46.4% C12-labelled overall. Thus the cluster cannot be described as a high-purity C12 selection.

## Verdict

The source supports only this statement: under the toy generator and morphology
used here, 25/38 truth-labelled MC early-peak tracks are C12. It does not identify
the beam-data anomaly, establish efficiency or false-positive rate, or authorize a
veto. Matched data/MC preprocessing, morphology closure, detector-response
systematics, uncertainty, and an independent data species tag or validated proxy
remain required under `AUD-ANOM-001`.

## Artifacts

- `mv6_representation_summary.json`
- `mv6_representation.png`
