# External blockers — exact missing inputs

Two kinds. **Compute** blockers need only a LUNARC session (the code is done and
staged). **External-data** blockers need specific files on `fs10` or new
acquisitions and cannot be closed from a laptop.

## BLOCKED_COMPUTE (unblock = LUNARC session)

| Task | Exact requirement | Staged artifact |
|---|---|---|
| CCB-796-RUN | Geant4 (+ optical physics) build env; run `bash slurm/build.sh build` then the array | `geant4/single_stave/slurm/{build,submit_calibration}.sh`, `points_example.csv` |
| CCB-844-GEOM | ROOT + ROOT/VGM to hash & enumerate volumes of `krakow_109_8-38deg_4-71deg.root` | `geant4/configs/krakow.geoconf` (referenced) |
| CCB-844-SCAN | Compute for staged stopping-depth scan (overlap→pilot→final) | scan plan in `AI_SESSION_MASTER_PROMPT.md` Phase 2 |
| CCB-TIMING | Rerun `mv4_timing_study.py` with v2 gain + data anchors from result files | `1/A` fix already in tree |

## BLOCKED_EXTERNAL (unblock = specific data/hardware)

| Task | Exact missing item |
|---|---|
| CCB-796-ENTRY | Full-MC truth ROOT tree on `fs10` to extract empirical stave-entry energy spectra per species/stave/angle |
| CCB-796 PDE/coupling | Hamamatsu S13360-3050CS **operating overvoltage**, optical coupling efficiency, far-end termination (mirror vs open) for the actual run — currently `UNKNOWN_EXTERNAL`, scanned via `--pde-scale`/`--coupling`/`--far-end` |
| CCB-796 reflectivity | Measured TiO2 surface reflectivity vs wavelength (currently literature prior, scanned via `--reflectivity-scale`) |
| CCB-DELTAE-FIX | Real `(file_id, run, event)` keys in data to replace `eventno`-only joins |

## Handoff acquisition contracts (unchanged, still open)
`runbooks/EXTERNAL_BLOCKERS.md`: forced/random pedestal waveforms; two-ended
readout with synchronized clock; absolute-TOF reference (TPC/independent
trigger); beam current/position/energy scans. **Do not simulate these and claim
closure** — each needs a real acquisition with the schema listed there.
