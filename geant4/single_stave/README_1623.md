# Issue #1623 — single-stave light-vs-energy study

Deposited energy → scintillation photons → photoelectrons, per particle species,
over a distributed hit phase space, with Birks quenching and light collection
separated.

```
E_dep  ->  N_scint  ->  N_arrival(readout)  ->  N_pe  ->  ADC
```

## What was added to the producer

`geant4/single_stave` previously fired one species (proton or deuteron) at one
fixed point with a fixed incidence. Four additions, all opt-in:

| flag | meaning |
|---|---|
| `--particle mu-\|mu+\|pi+\|pi-` | in addition to `proton\|deuteron`; resolved through `G4ParticleTable::FindParticle` |
| `--hit-x-range MIN:MAX` / `--hit-y-range MIN:MAX` | impact point sampled uniformly over the active stave area, per event |
| `--theta-spread DEG` | incidence sampled isotropically inside a cone of that half-angle about `(theta, phi)` |
| `--no-photon-ntuple` | drop the per-photon table (output-volume control for high-statistics points) |
| `--optical-max-time-ns` / `--optical-max-steps` | optical transport cost guards, both off by default, every kill counted |

New `events` columns, appended so existing column indices are unchanged:

| column | meaning |
|---|---|
| `gen_x_cm`, `gen_y_cm` | primary vertex on the launch plane (sampled or fixed) |
| `dir_ux`, `dir_uy`, `dir_uz` | primary vertex momentum direction |
| `primary_exit_{x,y,z}_cm` | post-point of the primary's last scintillator step |
| `primary_ke_end_MeV` | primary kinetic energy after that step |
| `primary_stopped` | 1 if that residual is ≤ 10 keV — the primary terminated in the bar |
| `n_optical_killed_time`, `n_optical_killed_steps` | optical photons truncated by the cost guards |

### Reproducibility of the sampled phase space

The per-event draw uses a counter-based SplitMix64 stream keyed on
`(seed, eventID)`, **not** the Geant4/CLHEP engine. The impact point and
direction of event *N* are therefore a pure function of the run seed and the
event index, identical for any `--threads` value and any worker scheduling. The
recorded 1T/48T same-seed branch equality for the physics stream is untouched:
with none of the sampling flags set, the generator draws no random number at all
and the launch is bit-identical to the historic fixed-point path
(`slurm/verify_1623.sbatch` section 2 checks exactly this against a pristine
build of the parent commit).

### Beam-envelope preflight

ADR-0003 (#999) validates that the primary intersects the stave. That check is
computed from one configuration point, so once the beam is distributed it would
go vacuous. `main.cc` now additionally validates the **envelope**: every corner
of the sampled `(x, y)` rectangle at the extreme incidence angle, over four
azimuths. Any corner that misses aborts the run (`CCB_BEAM_ENVELOPE_PREFLIGHT`,
exit 4) unless `--allow-miss` is given.

### Optical transport cost guards (#1623 / #1083)

A few optical photons per 10⁷ get trapped bouncing on a thin-layer boundary —
the 10 µm end-face air gap and the cladding shells, both still
`UNKNOWN_EXTERNAL` under #1083 — and burn tens of millions of post-step `DoIt`
calls, so a single event costs minutes and a campaign task dies at its wall
limit having written nothing.

Measured on 300 events of 20 and 60 MeV protons with the per-photon ntuple on
(`slurm/guard_1623.sbatch` section A):

* the **latest** photon arrival at the readout is 222 ns, and no arrival exceeds
  250 ns, so a 1000 ns tracking-time cut removes exactly zero recorded arrivals
  (the SiPM response window is `[-20, 250] ns` and discards later arrivals in
  any case);
* the 200 000-step cut truncates **5 × 10⁻⁸** of generated optical photons
  (1 of 20.3 M at 20 MeV, 2 of 42.2 M at 60 MeV) and removes the pathological
  events entirely.

Both guards are OFF by default, every kill is counted per event, and the
per-run totals go into the sidecar — a guarded run states what it truncated
instead of silently changing the optical result.

## Campaign

`slurm/points_1623.csv` (built by `scripts/single_stave/make_points_1623.py`),
132 points, one immutable configuration per array task:

* **Sample A — distributed.** Impact point uniform over `x ∈ [-22, 22] cm`,
  `y ∈ [-2.2, 2.2] cm` of the 50 × 5.18 × 2.0 cm bar; incidence isotropic inside
  a 10° cone. Two seeds × 2000 events per (species, energy).
* **Sample B — central reference.** `x = y = 0`, normal incidence, one seed ×
  1000 events — the controlled comparison the issue asks for.

Energy grids are set by the geometry rather than by round numbers: 2.0 cm of
polystyrene ranges out protons below ≈ 50 MeV and deuterons below ≈ 66 MeV, so
both the stopping and the punch-through regime are populated for p and d.
Muons and charged pions at CCB energies are near-minimum-ionizing and anchor the
low-quenching end; they cannot reach the 60–100 MeV deposit span, which in a
single 2 cm stave is reachable only by a stopping deuteron.

```bash
mkdir -p logs
N=$(grep -cvE '^\s*(#|$)' slurm/points_1623.csv)
sbatch --array=0-$((N-1))%40 --cpus-per-task=16 --time=08:00:00 \
       slurm/submit_1623.sh build slurm/points_1623.csv <outdir>
```

## Analysis

```bash
python scripts/single_stave/light_vs_energy_1623.py \
    --inputs '<outdir>/*.root' --out <reportdir>
```

Deliverables: `events_1623.parquet` and `events_1623.csv.gz` (event level),
`summary_by_point.csv`, `report_1623.json`, and the figures under
`sample_A/` and `sample_B/`.

The loader is fail-closed: every ROOT file must carry its `.meta.json` sidecar
and its row count must equal the sidecar's `n_events`, otherwise the analysis
aborts (exit 3) rather than quietly analysing a campaign with dead tasks in it.

### Reading the proton/deuteron comparison

A raw-deposit window is fed by two physically different populations — a
low-energy primary that ranges out in the bar, and a high-energy one that punches
through — with very different `dE/dx` and therefore very different quenching.
Pooling them makes the ratio a function of the energy-grid weights rather than of
the detector, so `report_1623.json` reports the ratio **split by primary fate**.
In the CCB the B2 deuteron stops and the B2 proton punches through:
`ratios_matched_b2_stoppingD_over_punchthroughP` is that pair.

## Status boundary

The optical parameters remain `UNKNOWN_EXTERNAL` (PDE overvoltage, optical
coupling, far-end termination, TiO₂ reflectivity — README and #1083). Nothing
here is an absolute PE/MeV calibration; the defensible output is the **shape**
of the response and the **ratio** between species at matched deposits, with the
systematics knobs (`--pde-scale`, `--collection-efficiency`, `--far-end`,
`--reflectivity-scale`) available to bracket them.
