# CCB test-beam — project-completion infrastructure report

**UTC stamp:** 20260720T075158Z
**Branch:** `ai/project-completion-20260720`
**Audited commit:** `d3b2beb217c7157693da45e3e8824489c7a8f036` (== current `origin/main`)
**Scope of this session:** everything that can be built and verified **without a
LUNARC connection**. Heavy Geant4 compilation, full-MC access, and data-fits are
staged and marked `BLOCKED_COMPUTE` / `BLOCKED_EXTERNAL` — never faked.

## Summary

| Area | Result |
|---|---|
| Single-stave G4 app (#796) — code | **DONE** — from-scratch, blueprint-faithful, every catalogued defect fixed; non-Geant4 core compiled + functionally verified; geometry-report validator green |
| Single-stave analyzers (#796) | **DONE (offline)** — 3 CLIs integrated + 9 pytest; stub `analyze_mc_stave_response.py` replaced |
| Provenance/reproducibility substrate | **DONE** — `tools/ccbprov` + JSON schemas + report scaffolding, 10 pytest |
| G4 compile + calibration run (#796) | **BLOCKED_COMPUTE** — needs LUNARC Geant4; `slurm/` staged |
| Entry-energy extraction (#796) | **BLOCKED_EXTERNAL** — needs full-MC ROOT on fs10 |
| MV3 geometry + stopping scan (#844) | **BLOCKED_COMPUTE** — needs deployed ROOT + ROOT/VGM |
| Timing rerun after 1/A | **BLOCKED_COMPUTE** — needs data + v2 calibration cards |
| ΔE–E `supervisor_deltaE_E.py` | **SUPERSEDED** — absent at audited commit (conflict record); fix queued `CCB-DELTAE-FIX` |
| Paper package (#797) | **IN_PROGRESS** — skeleton + claim ledger; content gated on blocked results |

**Tests:** 24 passed (`tools/ccbprov` 10, single-stave analyzers 9, geometry
report 5). See `closure_matrix.csv` / `.json` for the full acceptance grid.

## What was built (LUNARC-independent)

### 1. Single-stave Geant4 application — `geant4/single_stave/`
A complete replacement for the merged prototype `scripts/stave_sim.cc`. The
prototype's defects (from `audit/KNOWN_CODE_DEFECTS.md`) are each fixed —
see the crosswalk table in `geant4/single_stave/README.md`. Highlights:

- **Geometry**: 50 × 5.18 × 2.0 cm polystyrene bar; primary enters the **2.0 cm
  normal thickness** travelling `+z` (prototype sent it along the 50 cm axis).
  Two Y-11 fibres rotated `rotateY(90°)` to lie **along x**, contained in the
  bar with explicit hole/gap → outer/inner cladding → core, all overlap-checked.
- **Photon accounting**: `TrackingAction` counts generated photons by creator
  process (Scintillation / OpWLS / Cerenkov); `SteppingAction` counts boundary
  crossings into **named sensor volumes** and applies wavelength-dependent PDE
  *after* recording the raw arrival — replacing the prototype's fibre-Edep count
  (which is ~always zero). All four conceptual channels are instrumented
  (readout = fibre 1 +x end; the other three are simulation controls).
- **No overwrite**: one immutable config per invocation → one output file, with a
  per-photon ntuple in `optical` mode. Provenance sidecar `<output>.meta.json`
  records git commit, geometry hash, seed, config, and every optical-table
  sha256.
- **Physics/optics**: QGSP_BIC + `G4OpticalPhysics`; configurable Birks `kB`;
  TiO2 border optical surface; SiPM occupancy saturation
  `N_fired = N_cells(1-exp(-N/N_cells))`, `N_cells=3600` (S13360-3050CS).
- **Build**: headless CMake (`CCB_ENABLE_VIS=OFF` default) — fixes the Qt5/ICU
  failure; three ctests. CMake parses cleanly, stopping only at the Geant4
  dependency (verified locally).
- **Verified offline**: `AppConfig.cc` + `OpticalTables.cc` compiled standalone;
  the in-house SHA-256 matches system `shasum`; PDE interpolation/clamping and
  arg parsing/validation confirmed by a functional driver.

### 2. Single-stave analysis toolchain — `scripts/single_stave/`
`make_single_stave_fixture.py`, `analyze_single_stave.py`,
`extract_g4_entry_energies.py`, integrated from the (handoff-tested) starter
code and hardened. One real bug fixed: `extract_g4_entry_energies.py` used
`tree.iterate(..., report=True)` (unimplemented in uproot 5.7.4) → now uses the
maintained `event_offset` counter. The old `analyze_mc_stave_response.py` stub
(describe-only, hard-coded LUNARC paths) is now a forwarding CLI.

### 3. Provenance substrate — `tools/ccbprov/` + `schemas/`
`RunManifest` (schema-valid, auto git-commit, tz-aware UTC, env capture),
`ClosureRow`/`write_closure_matrix` (CSV+JSON, enum-validated), `validate_record`
(jsonschema with a graceful minimal fallback), `init_report_dir`. The manifest
in this very directory validates against `schemas/run_manifest.schema.json` with
zero errors.

## External blockers (exact missing inputs)
See `external_blockers.md` in this directory and `runbooks/EXTERNAL_BLOCKERS.md`.
Compute blockers need only a LUNARC session (Geant4 + the staged `slurm/`
scripts); data blockers need specific files on `fs10` or new acquisitions.

## Replication (once on LUNARC)
See `commands.log`. In short:
```bash
cd geant4/single_stave && module load Geant4 && bash slurm/build.sh build
python -m pytest tools/ccbprov single-stave tests   # already green offline
sbatch --array=0-8 slurm/submit_calibration.sh build slurm/points_example.csv out/
python scripts/analyze_mc_stave_response.py --input out/stave_proton_100MeV_x0_s2.root --output reports/stave_p100
```

## Honesty notes
- No optical/hardware parameter is asserted as a measured truth. Optical tables
  are labelled `MANUFACTURER_REPRESENTATIVE` / `NUISANCE_PRIOR`; PDE-overvoltage,
  coupling, far-end termination, and exact reflectivity are `UNKNOWN_EXTERNAL`,
  exposed as run-time systematic scans rather than single invented numbers.
- No task is marked `DONE` on code inspection alone: `DONE` here means code +
  offline tests pass; anything needing the cluster is `BLOCKED_*`.
- The `supervisor_deltaE_E.py` handoff instruction is a stale reference; the real
  defect is queued (`CCB-DELTAE-FIX`), not silently dropped.
