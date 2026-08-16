# Cluster D — CCB MC-validation programme + single-stave campaign aggregation

**Branch:** `studies/clusterD-mc-validation`  
**Original base:** `origin/main` @ `44deedd1` (2026-07-25)  
**Site:** LUNARC `cosmos3` plus `cx*`, account `hep2023-1-3`  
**Python:** `/projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/python` with
`PYTHONNOUSERSITE=1`  
**MC truth:** Krakow 1M ROOT file, referenced by absolute LUNARC path  
**Single-stave campaigns:** `i885_v1`, `sys_birks_smoke2`, and `sipm-p2-001`

> **Post-merge scientific governance correction (2026-07-25):** Script exit
> status, toy/analytic self-closure, and truth-labelled MC composition are not
> empirical detector validation. The canonical cross-domain claim status is
> controlled by `docs/claim_ledger.csv`. The rows below retain the measured
> Cluster D outputs while removing production, Rmax, absolute-energy, and
> beam-data species-identification overclaims.

## MV0–MV6 status

| ID | Title | Tier | Evidence state | Evidence and limitation |
|---|---|---:|---|---|
| MV0 | ADC-gain scan | 2 | **GATED (MARGINAL DATA/MC PROXY)** | The rerun selects 110.0 ADC/MeV with KS=0.10773131550396098 on 377,362 data pulses and 48,300 MC events, but its own report calls the result MARGINAL, records chi2/ndf=2928.1720074390482, and shows per-stave KS values 0.197–0.603. Inputs are absolute-path references without a content-addressed run manifest. This does not supersede canonical `CL-013` or authorize a production gain; resolve `BLK-MV0-001`. |
| MV1 | Truth p/d PID ceiling | 1 | **TRUTH_LEVEL_MC_ONLY** | HGB AUC 0.985 and purity 0.962 at nominal 90% efficiency are simulation-only diagnostics. They do not establish beam-data PID performance or transfer. |
| MV2 | Range/energy tables | 1 | **TRUTH_LEVEL_MC_ONLY / TABLE GENERATED** | Per-stop-layer MC means were generated for protons and deuterons. This does not close the data-side absolute-energy calibration, detector response, or uncertainty problem. |
| MV3 | Stopping-depth/stave profile | 1 | **TENSION / NOT ACCEPTED CLOSURE** | The mapping score is descriptive. The large B8 shape discrepancy remains scientifically unresolved; exact canonical legacy values are gated by `BLK-MV3-LEGACY-001`. |
| MV4 | Timing and timewalk | 2 | **BLOCKED (TOY_DIAGNOSTIC)** | The run uses a placeholder digitizer and hard-coded fallback data anchors. It is not a beam-data timing validation. |
| MV5 | Pile-up and two-pulse recovery | 2 | **BLOCKED (RMAX DEFINITION UNRESOLVED), TOY DIAGNOSTIC** | The study reuses rounded `tau_eff=124.8 ns` and computes `(1/tau_eff)×0.38 = 3.0448717948717947 MHz`. The machine-readable result has `rmax_from_failure_ceiling_mhz = null`; therefore 3.0449 MHz is a superseded duty-factor product, not an accepted capacity. Canonical Rmax remains withheld under `S-STAT-003`. |
| MV6 | Waveform representation and anomaly morphology | 2 | **TRUTH_LEVEL_MC_ONLY, TOY DIAGNOSTIC** | The toy sample contains 38 early-peak tracks, of which 25/38 are C12-labelled. The associated GMM cluster is only 46.4% C12-labelled overall. This does not identify the beam-data anomaly, establish classifier efficiency/purity on data, or supersede canonical `CL-022`–`CL-024`; matched data/MC closure remains required under `AUD-ANOM-001`. |

**Tier-2 boundary:** MV4/MV5/MV6 use a placeholder or toy digitizer rather than
an accepted end-to-end waveform pipeline. Their output is diagnostic only.

## Campaign aggregation

Plotters live under `scripts/single_stave/campaign_plots/`. Reproduction order is
captured in `reports/studies/clusterD/run_campaign_aggregation.sh`.

### i885_v1 calibration campaign

The campaign contains 72 proton/deuteron runs over the configured energy grid and
two seeds. Generated plots show light production, detected PE, response shape,
and timing. These are simulation diagnostics, not detector calibration constants.

### Birks smoke grid

Three 100 MeV proton runs at `kB={0.100,0.126,0.160} mm/MeV` demonstrate the
configured monotonic quenching response. This small grid is not a systematic
uncertainty evaluation or material-model validation.

### SiPM one-knob sensitivity campaign

Twelve one-knob sweeps provide local response sensitivities. Reported elasticities
are conditional on the chosen nominal configuration, sweep ranges, and toy/readout
model; they are not global causal rankings or measured detector uncertainties.

## VIS-MC internal diagnostic plots; not proof that the simulation is empirically correct

| Figure | What it checks | Acceptance boundary |
|---|---|---|
| VIS-MC-001 | Configured generator spectra, positions, angles, and weights | Configuration/internal consistency only. |
| VIS-MC-002 | Local raw deposited-energy/track-length proxy versus canonical PSTAR total stopping power | The historical `VIS-MC-002_transport_vs_pstar.png` used an embedded coarse table and is **SUPERSEDED**. Regenerate `VIS-MC-002_transport_vs_pstar_canonical.png` plus its JSON sidecar with `vis_mc_002_transport.py`; the canonical CSV/parser and SHA-256 are recorded. The comparison remains diagnostic because local deposit is not projectile total energy loss and the uncertainty model is incomplete. |
| VIS-MC-003 | Optical-generation and detected-photon distributions | Simulation-internal bookkeeping; no beam-data optical closure. |
| VIS-MC-004 | Two-seed distribution comparison | Two seeds and a fixed four-thread campaign are not the dedicated thread-invariance or multiseed acceptance study. |
| VIS-MC-005 | Gain×truth plus injected Gaussian-noise closure | MC-internal and unbiased by construction; no single-stave beam-data input. |

## Verification recorded by the originating run

- Python offline geometry tests: 7/7 passed.
- Geant4 CTest: eight passed and one intentionally skipped on `cx04`.
- Standalone scripts returned zero and emitted JSON/PNG/Markdown artifacts.

These software execution results do not upgrade the scientific evidence states
above. The uncommitted build log and raw ROOT files were not independently
reproduced in this documentation-remediation run.

## Preserved external inputs and residue

- Raw campaign ROOT files and the Krakow 1M ROOT file remain outside Git.
- The selected data CSV and `truth_tracks.npz` are referenced by absolute path and
  are not content-addressed in the Cluster D report bundle.
- Reproducibility therefore requires immutable input hashes, exact producer and
  configuration identity, output hashes, and environment capture in addition to
  the commands below.

## Reproduce the originating scripts

```bash
ssh lunarc
cd /projects/hep/fs10/shared/nnbar/billy/ccb-wt-clD
export MPLCONFIGDIR=/projects/hep/fs10/shared/nnbar/billy/.mplcache
export PYTHONNOUSERSITE=1
PY=/projects/hep/fs10/shared/nnbar/billy/ccb-py/bin/python
MC=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/geant4/data/output_krakow_1M.root
DATA=/projects/hep/fs10/shared/nnbar/billy/ccb-testbeam/reports/1780917628.449525.085b2dc0__s01b_s00_selected_table_manifest/s00_selected_b_pulses.csv.gz
OUT=reports/studies/clusterD/mv_runs

$PY scripts/mv1_mv2_truth_pid_energy.py --mc "$MC" --out "$OUT/mv1_mv2" --max-events 200000
$PY scripts/mv3_stopping_v3.py --mc "$MC" --data "$DATA" --out "$OUT/mv3" --max-events 200000 --gain 92 --peak-frac 0.75 --net-threshold 100
$PY scripts/mv0_calibrate_from_data.py --mc "$MC" --data-csv "$DATA" --truth-npz "$OUT/mv1_mv2/truth_tracks.npz" --out "$OUT/mv0" --max-events 200000
$PY scripts/mv4_timing_study.py --out "$OUT/mv4" --mc "$MC" --calibration "$OUT/mv0/calibration.json" --synthetic 5000 --max-tracks 5000 --max-events 50000
$PY scripts/mv5_pileup_study.py --truth "$OUT/mv1_mv2/truth_tracks.npz" --out "$OUT/mv5" --n-spill 5000 --n-overlap 4
$PY scripts/mv6_representation_study.py --mc "$MC" --out "$OUT/mv6" --max-events 50000 --max-tracks 5000
```
