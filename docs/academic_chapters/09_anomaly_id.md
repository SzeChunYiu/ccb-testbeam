# Chapter 9: Early-Peak Morphology in Truth-Labelled Monte Carlo

> **Evidence boundary.** This chapter describes one tracked truth-labelled Monte
> Carlo study. It does not identify the related beam-data anomaly as carbon-12,
> and it does not establish a production veto, detection efficiency,
> false-positive rate, or detector-performance result.

## Abstract

The tracked MV6 producer scanned 220,000 simulated events and retained 87,555
charged B-arm tracks. Its deterministic morphology taxonomy classified 283
tracks as `early_peak` and none as `low_area`, giving a total early-peak rate of
283 / 87,555 = 0.003232254011764034. An independent Wilson 95% interval is
[0.002877452112691542, 0.003630645177388446].

The early-peak class is compositionally mixed. Carbon-12 truth labels account
for 156 / 283 = 0.5512367491166078 of the selected class, with Wilson 95%
interval [0.4929885941153212, 0.6081125511627331]. Among all 7,302 carbon-12
tracks, 156 / 7,302 = 0.021364009860312245 are early-peak, with Wilson 95%
interval [0.018290520583369645, 0.024940838952822255]. These three binomial
quantities answer different questions and must not be interchanged.

The tracked representation is also narrower than earlier prose claimed. The
producer fits PCA to peak-normalised 18-sample waveforms, records cumulative
explained variance of 0.745517570480533 at four components and
0.821883926913117 at eight components, and fits one Gaussian mixture with
K = 4 on the first four PCs. No BIC scan was run, no K = 7 model is present in
the tracked producer, and the source artifacts do not establish named physical
meanings for individual PCs.

## 1. Tracked input and event selection

The canonical source for this chapter is
[`scripts/mv6_representation_study.py`](../../scripts/mv6_representation_study.py),
with numerical output in
[`mv6_representation_summary.json`](../../reports/mv6_representation_1782678362/mv6_representation_summary.json)
and a human-readable report in
[`REPORT.md`](../../reports/mv6_representation_1782678362/REPORT.md).

The tracked run records:

| Quantity | Value | Evidence type |
|---|---:|---|
| Events scanned | 220,000 | fixed-output count |
| Charged B-arm tracks retained | 87,555 | fixed-output count |
| Random seed | 42 | producer configuration |
| Carbon-12 tracks | 7,302 | truth-labelled MC count |
| Early-peak tracks | 283 | morphology count |
| Low-area tracks | 0 | morphology count |

The producer selects B-arm hits using `Sci_bar_LayerID1 == 1`, groups hits by
`Sci_bar_TrackID` within each event, retains charged tracks, and requires summed
energy deposition above 0.02 MeV before waveform construction. These are
software selections on truth-labelled simulation, not a demonstrated beam-data
selection efficiency.

## 2. Waveform construction and morphology taxonomy

Each retained track is converted to an 18-sample synthetic waveform. The
explicit producer constants are:

| Parameter | Value |
|---|---:|
| ADC gain used by this producer | 246 ADC/MeV (producer constant; superseded as a physics gain — canonical calibrated MV0 digitizer gain is 92 ± 28 ADC/MeV, see WIKI correction table) |
| Gaussian sample noise | 50 ADC |
| Pedestal | 350 ADC |
| Rise constant | 2.5 ns |
| Decay constant | 42 ns |
| Samples | 18 |
| Sampling interval | 10 ns |
| ADC ceiling | 7,000 ADC |
| Saturation flag threshold | 6,500 ADC |
| Earliest-hit trigger offset | 20 ns |

These constants define this historical simulation producer. They are not an
accepted detector calibration merely because they appear in the waveform
model.

The implemented taxonomy is evaluated in this order:

1. `saturated` if any sample is above 6,500 ADC;
2. `early_peak` if the maximum pedestal-subtracted sample has index below 2;
3. `low_area` if the peak is positive and the clipped positive area is below
   0.3 times the peak amplitude;
4. otherwise `normal`.

Because `early_peak` is checked before `low_area`, the labels are mutually
exclusive under this implementation. The tracked summary contains no
`low_area` tracks. Consequently, the recorded 0.003232254011764034 total
anomaly fraction is numerically the early-peak fraction for this run.

## 3. PCA and GMM implementation actually used

The producer subtracts the 350-ADC pedestal and divides every waveform by its
own positive peak amplitude. PCA is then fit with up to ten components. The
recorded explained-variance ratios begin:

| PC | Explained-variance ratio |
|---:|---:|
| 1 | 0.6397275304111596 |
| 2 | 0.05803144748933653 |
| 3 | 0.027701235443287935 |
| 4 | 0.02005735713674897 |

The cumulative values are:

| Representation | Cumulative explained variance |
|---|---:|
| First four PCs | 0.745517570480533 |
| First eight PCs | 0.821883926913117 |

The Gaussian mixture is instantiated explicitly with four components,
`random_state=42`, and `n_init=3`, then fit to `Z[:, :4]`. Therefore the
source-backed description is:

> **K = 4 on the first four PCs. No BIC scan was run in the tracked producer.**

Earlier descriptions of an eight-dimensional K = 7 BIC-selected model,
99.7% cumulative variance at eight PCs, a 127-iteration convergence result,
or a component isolated primarily along a named PC are not supported by the
tracked producer or summary and must not be used as current evidence.

The four recorded clusters are:

| Cluster | Tracks | Fraction | Dominant truth label | Dominant-label purity | Early-peak tracks |
|---:|---:|---:|---|---:|---:|
| 0 | 22,345 | 0.2552110102221461 | deuteron | 0.8538375475497875 | 0 |
| 1 | 28,191 | 0.3219804694192222 | proton | 0.3946649639956014 | 1 |
| 2 | 14,587 | 0.16660384900919423 | carbon-12 | 0.4450538150407897 | 282 |
| 3 | 22,432 | 0.2562046713494375 | proton | 0.729894793152639 | 0 |

Cluster 2 contains 282 of the 283 early-peak tracks, but it is not a pure
carbon-12 cluster: 6,492 of 14,587 cluster-2 tracks have carbon-12 truth labels.
The separate early-peak composition calculation gives 156 carbon-12 tracks
among 283 early-peak tracks. Cluster membership, cluster dominant-species
purity, and selected-class composition are different quantities.

## 4. Source-backed statistical statements

For a binomial count k out of n, this chapter reports the Wilson score interval
at 95% confidence:

```text
centre = (p + z^2/(2n)) / (1 + z^2/n)
half   = z * sqrt(p(1-p)/n + z^2/(4n^2)) / (1 + z^2/n)
```

with `p = k/n` and `z = 1.959963984540054`.

| Quantity | Numerator | Denominator | Estimate | Wilson 95% interval |
|---|---:|---:|---:|---:|
| Early-peak rate among retained MC tracks | 283 | 87,555 | 0.003232254011764034 | [0.002877452112691542, 0.003630645177388446] |
| Carbon-12 share of early-peak class | 156 | 283 | 0.5512367491166078 | [0.4929885941153212, 0.6081125511627331] |
| Early-peak rate within carbon-12 | 156 | 7,302 | 0.021364009860312245 | [0.018290520583369645, 0.024940838952822255] |

The historical producer function named `binom_ci` returns the normal-approximate
half-width `1.96*sqrt(p(1-p)/n)`. It does not return a Wilson interval and it
does not return lower and upper bounds. The confidence intervals above were
independently reconstructed from the exact source counts.

These intervals quantify finite-count uncertainty conditional on the fixed
simulation and implemented selection. They do not include generator,
geometry, detector-response, waveform-model, taxonomy, or domain-transfer
uncertainty.

## 5. What the tracked study does and does not show

### Established for this fixed simulation output

- The producer retained 87,555 charged B-arm truth-labelled MC tracks from
  220,000 scanned events.
- The implemented taxonomy selected 283 early-peak tracks and zero low-area
  tracks.
- Carbon-12 is the largest truth-labelled species in the selected early-peak
  class, accounting for 156 of 283 tracks.
- A four-component GMM on the first four PCs places 282 of 283 early-peak tracks
  in cluster 2.
- The first four and first eight PCs explain 74.5517570480533% and
  82.1883926913117% of variance, respectively.

### Not established

- The related beam-data morphology is not identified as carbon-12.
- The simulated 0.32% rate is not a prediction for the approximately 4% data
  morphology rate without matched selection and detector-response closure.
- No event-level carbon-12 proxy has been validated in beam data.
- No anomaly-detection efficiency, false-positive rate, purity in data, veto
  impact, retained-event fraction, or deuteron-yield systematic has been
  measured.
- No BIC scan, K = 7 model selection, manual-review campaign, inter-reviewer
  agreement study, alternative anomaly-detector benchmark, SRIM table,
  Birks-law closure, elastic-scattering rate calculation, or end-to-end optical
  response validation is present in the tracked MV6 artifacts.
- Individual principal components have not been assigned validated physical
  meanings by a version-controlled eigenvector analysis.

The correct scientific conclusion is therefore limited: carbon-12 is a
candidate simulated contributor to the early-peak morphology, not a validated
identity for the beam-data anomaly.

## 6. Required matched data/MC closure

The open task `AUD-ANOM-001` requires an analysis in which data and simulation
use the same waveform preprocessing, sample indexing, pedestal convention,
selection, morphology taxonomy, and clustering transformation. At minimum it
must retain:

1. immutable data and simulation input hashes;
2. run, event, and track counts through a complete cut flow;
3. the fitted PCA transform and GMM parameters or a preregistered refit policy;
4. bootstrap or run-group uncertainty for data rates;
5. simulation seed and model-variation uncertainty;
6. data sidebands or independent controls for false-positive estimation;
7. a species-identification strategy independent of the same morphology used
   to define the anomaly;
8. efficiency, purity, false-positive rate, and veto-impact plots with confidence
   intervals;
9. sensitivity to thresholds, component count, waveform normalisation, and
   detector-response assumptions.

Simulation alone cannot establish empirical beam-data performance.

## 7. Evidence map and reproducibility

| Item | Repository path | Role |
|---|---|---|
| Producer | `scripts/mv6_representation_study.py` | selection, waveform model, taxonomy, PCA, GMM |
| Summary | `reports/mv6_representation_1782678362/mv6_representation_summary.json` | exact counts and representation outputs |
| Historical report | `reports/mv6_representation_1782678362/REPORT.md` | generated human-readable result; its data-transfer verdict is not accepted |
| Canonical claim | `docs/claim_ledger.csv`, `CL-022` | early-peak rate and evidence boundary |
| Public summary synchronizer | `scripts/sync_c12_public_claims.py` | prevents unsupported public-claim drift |

Validation policy: `CHAPTER9_MUST_MATCH_TRACKED_MV6_PRODUCER_AND_SUMMARY`.

The tracked summary records seed 42 but does not record package versions,
producer SHA-256, worktree cleanliness, environment lock, or immutable input
ROOT hash. These provenance gaps limit exact rerun claims even though the
current repository binds the producer path and historical source commit.

## Chapter verdict

**Status: PARTIAL.** The fixed simulation counts, Wilson intervals, PCA
cumulative variance, and K = 4 / four-PC implementation are source-backed. The
beam-data identity, transfer performance, physical production model, and veto
impact remain unvalidated.
