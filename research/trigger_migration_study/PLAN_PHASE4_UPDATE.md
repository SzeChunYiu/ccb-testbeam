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

