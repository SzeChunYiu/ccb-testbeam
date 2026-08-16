# Trigger Hardware-Response Migration Study (Issue #1045, P0)

## Executive Summary

**Objective**: Replace the HRD first-stack-layer charged-hit proxy with a validated hardware-trigger response model by adding T1/T2 trigger scintillator volumes to the MC geometry and computing migration matrices.

**Current Status**: Phase 1 COMPLETE as HISTORICAL DIAGNOSTIC (non-authorising MC — see PHASE1B_NONAUTHORISING_MC_NOTICE.md), Phase 1B REQUIRED (mc-1045-1b), Phase 2 DESIGN COMPLETE (PR #1542), Phase 3 HARNESS COMPLETE (PR pending)

**Evidence State**: MC_TRIGGER_PROXY / UNKNOWN_EXTERNAL per docs/contracts/TRIGGER_HARDWARE_RESPONSE.json

## Phase Status Summary

| Phase | Name | Status | Commit |
|-------|------|--------|--------|
| 1 | Baseline HRD Proxy Characterization | **COMPLETE — historical diagnostic only** (non-authorising MC) | f6f22dfd |
| 1B | Baseline on Authorising Corrected-Source MC | **REQUIRED** (CL-021 chain, owned by mc-1045-1b) | — |
| 2 | Truth-Trigger Volume Addition | **DESIGN COMPLETE** (PR #1542, awaiting mc-1045-1b pinned source) | e0a9d52c |
| 3 | Threshold/Coincidence SCAN | **HARNESS COMPLETE** (ready to execute once data lands) | — |
| 4 | Migration Matrix Analysis | **HARNESS COMPLETE** (ready to execute once data lands) | — |
| 5 | MC Regeneration (conditional) | PENDING | — |
| 6 | Contract Bump | PENDING | — |

## Phase 3: Threshold/Coincidence SCAN 🔧 HARNESS COMPLETE

**Status**: Scan harness complete and tested. Ready to execute the day Phase 1B (1M events) + Phase 2 (trigger branches) data land.

**Entry Point**: `scripts/trigger_threshold_scan.py`

**Hardware Constants** (from trigger_baseline_characterization.py):
- A_ARM = 2 (first A-arm bar layer ID)
- B_ARM = 1 (first B-arm bar layer ID)
- COINC_NS = 15.0 (historical coincidence window)

**Scan Bands** (config-driven via env vars, documented defaults):
- **Threshold**: 0.5, 1.0, 2.0, 5.0 MeV (4 values)
  - Override: `TRIGGER_THRESHOLD_SCAN_THRESHOLDS` env var
- **Coincidence Window**: 5, 10, 15, 20, 30 ns (5 values)
  - Override: `TRIGGER_THRESHOLD_SCAN_COINCIDENCE_WINDOWS` env var
- **Total configs**: 4 × 5 = 20 combinations

**Execution** (once Phase 1B + Phase 2 data land):
```bash
# Full hardware-response scan (requires Phase 2 trigger branches)
python scripts/trigger_threshold_scan.py \
    --input /path/to/phase2_output.root \
    --output research/trigger_migration_study/phase3/scan_results.json

# Proxy-mode scan (for Phase 1B baseline comparison)
python scripts/trigger_threshold_scan.py \
    --input /path/to/phase1b_output.root \
    --output research/trigger_migration_study/phase3/baseline_proxy_scan.json \
    --mode proxy
```

**Schema Tolerance**:
- Auto-detects mode from branch presence:
  - T1_EDep/T1_Time/T2_EDep/T2_Time → hardware-response mode
  - Sci_bar_LayerID/Sci_bar_LayerID1 → proxy mode
- Force mode with `--mode hardware|proxy`

**Output**: JSON with per-configuration efficiency and species breakdown

**Tests**: `tests/test_trigger_threshold_scan.py`
- Synthetic-branch unit tests (pure hits, off-time, sub-threshold, edge-of-window, mixed)
- Validates scan logic without requiring MC files

**Blocker**: Awaiting Phase 1B (mc-1045-1b) and Phase 2 (trigger branches) data.

## Phase 1: Baseline HRD Proxy Characterization ⚠️ COMPLETE (historical diagnostic)

**Provenance caveat (2026-08-16)**: the input `output_krakow_1M.root` is a product of the
superseded uniform-source generator and is NONAUTHORISING per `geant4/REPRODUCTION_STATUS.md`.
The numbers below are diagnostics of that MC, retained as the pipeline shakedown and the
Phase-1B comparison point — they must not be quoted as validated efficiencies. The earlier
truncated-data diagnosis was wrong: Phase 1 reads only MC truth branches and never consumed
the ccb_data staged waveforms. See `PHASE1B_NONAUTHORISING_MC_NOTICE.md`.

**Results**:
- Sample I is 99.3% deuteron with ε_HRD = 45.6%
- Protons suppressed to 0.4% efficiency
- Established baseline for migration matrix comparison

**Deliverables**:
- `scripts/trigger_baseline_characterization.py`
- `research/trigger_migration_study/PHASE1_COMPLETE_FINDINGS.md`
- `research/trigger_migration_study/PHASE1_SUMMARY.md`

## Phase 2: Truth-Trigger Volume Addition 🔄 DESIGN COMPLETE

**Status**: Design complete (PR #1542). Implementation awaiting mc-1045-1b pinned source.

**Geometry Specifications** (from DESIGN.md):
- T1: A-arm trigger at 71.5°, 10×10×1 cm (PSci material)
- T2: B-arm trigger at -38°, 15×15×1 cm (PSci material)

**Deliverables** (design):
- `research/trigger_migration_study/phase2_design/DESIGN.md`
- PR #1542

**Deliverables** (implementation, pending mc-1045-1b):
- `scripts/trigger_phase2/patch_gdml_trigger_volumes.py`
- `scripts/trigger_phase2/TriggerSensitiveDetector.hh/.cc`
- Validation runs (Phases 2A/2B/2C)

**Blocking**: Requires mc-1045-1b pinned source (CL-021 chain).

## Phase 4: Migration Matrix Analysis 🔄 HARNESS COMPLETE

**Status**: Analysis harness complete. Ready to execute once Phase 3 scan results land (proxy + hardware modes).

**Entry Point**: `scripts/trigger_migration_matrix.py`

**Function**: Consumes one or more threshold-scan JSON outputs and computes:
- Per-species migration matrix (quadrants: both/neither/proxy-only/hardware-only)
- Efficiency vs threshold curves
- Efficiency vs coincidence window curves
- Headline migration metrics (fraction of proxy-selected events that FAIL hardware trigger)

**Execution** (once Phase 3 scan results land):
```bash
# Compare proxy baseline vs hardware response
python scripts/trigger_migration_matrix.py \
    --proxy-json research/trigger_migration_study/phase3/baseline_proxy_scan.json \
    --hardware-json research/trigger_migration_study/phase3/scan_results.json \
    --output research/trigger_migration_study/phase4/migration_matrix.json
```

**Reference Configuration** (for quadrant analysis):
- Threshold: 1.0 MeV (proxy threshold-equivalent)
- Coincidence: 15 ns (historical baseline)
- Override with `--reference-threshold` / `--reference-coinc`

**Output Structure** (`migration_matrix.json`):
- `proxy_config` / `hardware_config`: Scan input metadata
- `species_migration`: Per-species quadrant counts and loss fractions
- `aggregate_migration`: Total quadrants and efficiencies
- `efficiency_vs_threshold`: Curve data (threshold → species → efficiency)
- `efficiency_vs_coincidence`: Curve data (window → species → efficiency)
- `headline_metrics`: Migration loss %, proxy/hardware efficiencies, dominant loss species

**Figure Generation**: `scripts/plot_trigger_migration.py`
- `efficiency_vs_threshold.png`: Per-species efficiency curves vs threshold
- `efficiency_vs_coincidence.png`: Per-species efficiency curves vs coincidence window
- `migration_matrix_table.png`: Migration matrix table visualization

**Tests**: `tests/test_trigger_migration_matrix.py`
- Synthetic scan-output JSON tests (perfect migration, complete loss, partial migration, species breakdown)

**Governance Line**:
- HISTORICAL_DIAGNOSTIC input (e.g., Phase 1 dry-run on `output_krakow_1M.root`) cannot authorise paper figures.
- Do NOT add figure-registry rows or `figures.yaml` entries yet.
- Figure-registry integration waits for authorising Phase 1B + Phase 2 data.

**Decision Matrix** (from migration_matrix.json output):
- |M - 1| ≤ 10%: proxy is adequate → no MC regeneration needed
- 10% < |M - 1| ≤ 20%: acceptable but document → consider targeted updates
- |M - 1| > 20%: migration required → Phase 5 MC regeneration

**Blocker**: Awaiting Phase 3 scan results (requires Phase 1B + Phase 2 data).

## Phase 5: MC Regeneration (conditional) ⏳ PENDING

**Trigger**: Phase 4 decision matrix indicates migration is required (M deviates >20%)

## Phase 6: Contract Bump ⏳ PENDING

**Deliverable**: Update docs/contracts/TRIGGER_HARDWARE_RESPONSE.json with validated trigger response.

## References

- Issue: #1045 (P0)
- Phase 1 findings: `research/trigger_migration_study/PHASE1_COMPLETE_FINDINGS.md`
- Phase 2 design: `research/trigger_migration_study/phase2_design/DESIGN.md`
