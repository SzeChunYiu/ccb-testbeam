# Single-stave analysis toolchain

Analysis tools for the CCB test-beam single-stave Geant4 simulation. Three
standalone CLIs plus a deterministic fixture, so the offline diagnostic chain
(fixture -> analyze) can be exercised and unit-tested without any real MC, while
the full-MC extraction path (`extract_g4_entry_energies`) targets the LUNARC
ROOT trees.

All three tools:

- expose an `argparse` CLI with `--help`;
- validate their inputs and fail with a clear message + **nonzero exit code**;
- use explicit, fixed random seeds wherever sampling occurs;
- write provenance (input SHA-256, environment, git commit) into their outputs;
- contain **no analyst-specific hard-coded absolute paths** (all paths are args).

---

## 1. `make_single_stave_fixture.py` — synthetic event table (fully offline)

Generates a deterministic synthetic single-stave event CSV/Parquet for testing
`analyze_single_stave.py`. Same `--seed` reproduces byte-identical output.

```bash
python scripts/single_stave/make_single_stave_fixture.py \
  --output /tmp/fixture.csv --n 2000
```

| flag | default | meaning |
|------|---------|---------|
| `--output` | *(required)* | output path; `.parquet` -> Parquet, else CSV |
| `--n` | 5000 | number of events |
| `--seed` | 20260720 | RNG seed (explicit, deterministic) |

Emits the full event schema consumed by the analyzer: `run_id`, `event_id`,
`particle_pdg`, `kinetic_energy_MeV`, `entry_x/y/z_cm`, `incidence_angle_deg`,
`track_length_scint_cm`, `edep_scint_MeV`, `n_scint_generated`,
`n_end_selected`, `n_detected_pe`, photon-timing columns, `birks_kB_mm_per_MeV`,
and geometry/optical config hashes. By construction it respects the physical
photon-count inequality `n_scint_generated >= n_end_selected >= n_detected_pe`.

## 2. `analyze_single_stave.py` — validate + diagnose (fully offline)

Validates the event schema, checks physics inequalities, fits a held-out linear
PE->energy calibration, and writes source tables, figures, `result.json`, and a
provenance `manifest.json`.

```bash
python scripts/single_stave/analyze_single_stave.py \
  --input /tmp/fixture.csv \
  --output /tmp/fixture_report \
  --bins 8
```

| flag | default | meaning |
|------|---------|---------|
| `--input` | *(required)* | CSV / Parquet / ROOT flat ntuple |
| `--output` | *(required)* | output directory |
| `--tree` | auto | ROOT tree name (required if ambiguous) |
| `--seed` | 20260720 | RNG seed for bootstrap |
| `--bins` | 12 | quantile-profile bin count |
| `--max-display-points` | 100000 | scatter down-sampling cap |

**Required input columns:** `event_id`, `particle_pdg`, `kinetic_energy_MeV`,
`edep_scint_MeV`, `n_scint_generated`, `n_end_selected`, `n_detected_pe`.
Legacy aliases (`event`, `ke_MeV`, `photons_seen`, `pe`, string `particle`
labels) are mapped explicitly; missing required columns -> nonzero exit.

**Physics validation.** The analyzer enforces the photon-count inequality
`n_scint_generated >= n_end_selected >= n_detected_pe` (and non-negativity, and
`(run_id,event_id)` uniqueness). On violation it:

- records the offending check in `result.json` -> `validation.problems`;
- sets `result.json` -> `status = "FAIL_VALIDATION"` and
  `validation.passed = false`;
- **exits with code 2** (0 only when validation passes).

**Artifacts written to `--output`:**

- `single_stave_events_normalized.parquet` (or `.csv.gz` fallback) — normalized event table
- `single_stave_summary.csv` — per-(species, KE) summary
- `result.json` — validation, calibration, species counts, plot records, status
- `manifest.json` — command, env, git commit, input/output SHA-256
- `figures/G4S-01..09_*.png` + `.pdf` — diagnostics
- `tables/G4S-*_source.csv` — per-figure source data

## 3. `extract_g4_entry_energies.py` — stave-entry spectra (**requires real full-MC ROOT**)

Extracts empirical B-stack entry kinematics (per species / arm / layer / sample
mimic) from the full CCB Geant4 truth tree, and writes per-species quantile-grid
summaries. Schema-adaptive: it resolves each logical field from a candidate
branch list, prints the selected contract, and refuses to guess when ambiguous.

```bash
python scripts/single_stave/extract_g4_entry_energies.py \
  --input /projects/hep/fs10/.../full_mc.root \
  --tree hibeam \
  --output /tmp/entry_energies.parquet
```

| flag | default | meaning |
|------|---------|---------|
| `--input` | *(required)* | full-MC ROOT file |
| `--tree` | `hibeam` | truth tree name |
| `--output` | *(required)* | output Parquet (`.csv.gz` fallback) |
| `--b-arm-id` | 1 | B-arm id in `Sci_bar_LayerID1` (1=B, 2=A) |
| `--a-arm-id` | 2 | A-arm id |
| `--coincidence-ns` | 15.0 | A/B coincidence window for Sample-I mimic |
| `--step-size` | `200 MB` | uproot iterate chunk size |
| `--max-events` | 0 | 0 = all events |

**Branch contract** (logical -> candidate branch names, first match wins;
`>1` match = hard error): `track` (`Sci_bar_TrackID`), `arm`
(`Sci_bar_LayerID1`), `layer` (`Sci_bar_LayerID`), `pdg` (`Sci_bar_PDG`),
`time` (`Sci_bar_Time`) are **required**; kinetic energy comes from an explicit
`Sci_bar_EKin`-type branch **or** all three momentum components
(`Sci_bar_Px/Py/Pz`), otherwise it exits. An entry record is the earliest
`Sci_bar` hit per `(event, arm, track, layer)`; only B-arm charged hits are kept.

**Outputs:** the entry-record table (Parquet/CSV), `*_summary.csv` (per
`particle_pdg` x `layer_id` x Sample-I-mimic: `n_entries`, `ke_p05/p16/median/p84/p95_MeV`,
mean, std), and `*_metadata.json` (contract, definition, env, hashes).

### Offline vs LUNARC coverage

| path | environment | test coverage |
|------|-------------|---------------|
| fixture + analyze | fully offline | full CLI + artifact + validation tests |
| extract core logic | offline | synthetic ROOT fixture (uproot `recreate`) + pure-function unit tests |
| extract vs production truth | **LUNARC full-MC** | must be run against the real `hibeam` tree and the printed branch contract reviewed before use |

The extractor's real-MC run cannot be reproduced offline (needs the multi-GB
production ROOT trees on LUNARC fs10); the test suite exercises its full code
path against a small synthetic ROOT file whose branches match the production
contract, plus direct unit tests of its pure helpers.

## Reproduce (offline, exactly what the tests run)

```bash
python scripts/single_stave/make_single_stave_fixture.py --output /tmp/fixture.csv --n 2000
python scripts/single_stave/analyze_single_stave.py --input /tmp/fixture.csv --output /tmp/fixture_report --bins 8
python -m pytest tests/test_single_stave_analysis.py -q
```
