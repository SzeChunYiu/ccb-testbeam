# Canonical dE-E (Delta-E vs E) analysis

`deltaE_E.py` is the correct replacement for the absent / unsafe
`supervisor_deltaE_E.py` (audit finding **A-002**, audit item **#8**). It builds
the dE/dx particle-identification plane (thin **Delta-E** layer vs thick
downstream **E**) for the CCB test-beam B-stack, on both the **data** (ADC) and
**Monte-Carlo** (MeV) sides, with the join and threshold bugs of the old code
fixed.

---

## Data contract (enforced, not assumed)

| Rule | Where enforced |
|------|----------------|
| Event key is **composite** `(source_file_id, run_id, event_id)`; never `event_id` alone | `KEY_COLS`, `validate_event_keys`, `composite_merge` (pandas `validate="one_to_one"`) |
| Duplicate event numbers in different runs **never** join | `composite_merge` + `join_report.cross_run_collision` |
| Missing downstream bars map to 0 **only after** event-key validation | `prepare_*_side`: `validate_event_keys` → then `fill_missing_layers` |
| Stopping layer = **deepest layer passing the threshold** (not "max layer with any deposit") | `stopping_layers`, `assign_stop_category` |
| All-zero / all-subthreshold events get an **explicit** category | `NO_REACH_CATEGORY = "no_layer_passes"` |
| `--stop-thresholds` / `--data-thresholds` actually **define** the stored stopping distributions | `stopping_distribution` per threshold in `result.json` |
| Raising the stopping threshold changes cumulative reach **monotonically** | monotone by construction; asserted by `check_monotonic_reach` |
| Sample I / II inclusive **and** exclusive counts reported; subset relationship tested | `sample_counts` |
| Saturation flags propagated into outputs | `derive_data_columns` → `saturated_any`, per-layer `saturation_B*` |
| Units kept distinct — ADC is never relabeled MeV | `UNIT_LABELS`, `*_adc` vs `*_mev` column suffixes |

### Derived quantities (units strictly separated)

```
deltaE_data_adc  = amp_B2                         [ADC]
E_data_adc       = amp_B4 + amp_B6 + amp_B8        [ADC]
deltaE_mc_mev    = edep_B2                         [MeV]
E_mc_4layer_mev  = edep_B4 + edep_B6 + edep_B8     [MeV]
E_mc_full_mev    = sum(edep_B4 .. deepest B layer) [MeV]   (both 4-layer and full-downstream)
```

Stopping layer per event = deepest B layer whose signal `>= threshold`
(data → `--data-thresholds` in ADC; MC → `--stop-thresholds` in MeV). If no
layer passes, the category is `no_layer_passes`.

---

## CLI

```bash
python scripts/single_stave/deltaE_E.py \
  --data-table  DATA.parquet \
  --mc-table    MC.parquet \
  --out         out/ \
  --stop-thresholds 0.05,0.15,0.30 \
  --data-thresholds 20,40,80 \
  --sample all \
  --seed 20260720 \
  --bins 16
```

| flag | default | meaning |
|------|---------|---------|
| `--data-table` | *(required)* | wide DATA event table (`.parquet`/`.csv`): `amp_B2/4/6/8`, `saturation_B*`, `threshold_pass_B*`, `sample`, `trigger_definition`, composite key |
| `--mc-table` | *(required)* | wide MC event table: `edep_B2/4/6/8` (+ deeper `edep_B*` for full mode), composite key |
| `--out` | *(required)* | output directory |
| `--stop-thresholds` | `0.05,0.15,0.30` | MC edep thresholds [MeV] defining MC stopping distributions |
| `--data-thresholds` | `20,40,80` | data amp thresholds [ADC] defining data stopping distributions |
| `--sample` | `all` | which sample (`I`/`II`/`all`) to store & plot; counts for **both** are always reported |
| `--seed` | `20260720` | deterministic seed for any subsampling |
| `--bins` | `16` | conditional-profile bin count |

`--help` works; input validation fails with a clear message and a **nonzero
exit code**. The lowest of each threshold list is the "primary" threshold stored
per-event in the `stop_layer` column; all thresholds appear in `result.json`.

Defaults are documented, not arbitrary: MC 0.05 MeV ~ a conservative
plastic-scintillator hit floor; data 20 ADC ~ pedestal + a few sigma of noise.
Every numeric knob is CLI-overridable.

---

## Outputs (into `--out`)

| file | contents |
|------|----------|
| `deltaE_E_events_data.parquet` | data event table: composite key, `deltaE_data_adc`, `E_data_adc`, `amp_B*`, `saturation_B*`, `saturated_any`, `stop_layer`, `stop_threshold_adc` |
| `deltaE_E_events_mc.parquet` | MC event table: composite key, `deltaE_mc_mev`, `E_mc_4layer_mev`, `E_mc_full_mev`, `edep_B*`, `stop_layer`, `stop_threshold_mev` |
| `result.json` | Sample I/II inclusive+exclusive counts & subset flag; stopping fractions per threshold + monotonic-reach flag (data & MC); join cardinality report; saturation counts; `unit_labels`; `status` |
| `manifest.json` | provenance: input SHA-256, env, git commit, args, output hashes |
| `figures/deltaE_E_data_adc.{png,pdf}` | data ADC panel: log-count hexbin + median & 16/84% conditional curves + marginal projections + saturation-onset lines |
| `figures/deltaE_E_mc_mev.{png,pdf}` | MC MeV panel (truth energy; no saturation lines) |
| `tables/*_profile.csv` | per-plot source data (bin `x_median`, `y_median`, `y_p16`, `y_p84`, support count `n`) |

Plots are density maps (hexbin / log-count + contoured conditional band), **not**
raw scatter. Matplotlib runs on the `Agg` backend (no display).

---

## Offline vs real data

- **Offline (this repo / CI):** `make_deltaE_fixture.py` emits a deterministic
  synthetic DATA + MC pair sharing composite keys, with a known
  cross-run duplicate-event-number case (`event_id 5` in `runA` and `runB`) and a
  known all-zero-downstream event (`runA`/`event_id 0`). This drives the unit
  tests (`tests/test_deltaE_E.py`) with no real MC.

  ```bash
  python scripts/single_stave/make_deltaE_fixture.py --out-dir /tmp/fx --n-per-run 800
  python scripts/single_stave/deltaE_E.py \
    --data-table /tmp/fx/deltaE_data.parquet --mc-table /tmp/fx/deltaE_mc.parquet --out /tmp/de_out
  ```

- **Real run:** the real wide event tables (data amplitudes + MC edep) live on
  **LUNARC fs10** under the canonical CCB test-beam tree. Point `--data-table`
  / `--mc-table` at those Parquet files. No analyst-specific absolute paths are
  baked into the code — every path is an argument.

## Tests

```bash
cd /Users/billy/ccb-pr && python -m pytest tests/test_deltaE_E.py -q
```

Covers all six required guarantees plus unit-label integrity, `E_mc_full`
deep-layer inclusion, a full CLI run, nonzero-exit-on-bad-input, and `--help`.
