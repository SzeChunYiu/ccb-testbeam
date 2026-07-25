# Strict A-002 ΔE-E rerun

Use `deltaE_E_data_bridge_strict.py` only after the exact A-002 pulse-table bytes and the amplitude convention/polarity evidence have been accepted under `AUD-AMP-009`, `AUD-AMP-010`, and `BLK-AMP-001`.

## Prerequisites

- clean tracked checkout at the exact commit passed to `--expected-repo-commit`;
- immutable pulse table with a measured SHA-256 passed to `--expected-input-sha256`;
- explicit source-file identity;
- explicit amplitude column and `absolute` or `net` convention;
- for absolute ADC codes, independently supported `positive` or `negative` pulse polarity;
- a dedicated output directory that does not contain the input or either producer script.

## Command template

```bash
python scripts/single_stave/deltaE_E_data_bridge_strict.py \
  --input /immutable/path/pulse_taxonomy_table.csv.gz \
  --output-dir /immutable/output/a002_deltae_bundle \
  --expected-input-sha256 <64-hex-input-digest> \
  --expected-repo-commit <40-hex-main-commit> \
  --source-file-id 1781014251.574.7a497937 \
  --amplitude-column amplitude_adc \
  --amplitude-convention absolute \
  --amplitude-polarity negative \
  --threshold-adc 200
```

Use `--overwrite` only after reviewing the existing bundle. Replacement is staged in a sibling directory; the previous bundle is restored if the in-process publication sequence fails. `result.json` is published as the bundle commit marker.

## Required outputs

The dedicated bundle contains:

- `result.json`: exact input/code/runtime/command provenance, bridge result, cardinality checks, and CSV/SVG hashes;
- `deltaE_E_events_data.csv`: one row per `(source_file_id, run, evt)` plus repeated provenance columns;
- `DE-01_deltaE_E_data.svg`: ΔE–E display with visible provenance footer and complete metadata.

The runner requires the input SHA-256 both before and after the bridge call, a clean tracked checkout, the exact expected commit, unique physical-event keys, finite numeric ADC outputs, and equality of event-row and stopping-distribution totals.

## Scientific boundary

A successful runner status validates the software/provenance bundle only. It does not establish that the selected amplitude convention or polarity is correct, that the threshold is physically accepted, that the stopping distribution is unbiased, or that the ΔE–E plot supports particle identification. Those conclusions require the exact A-002 evidence map, real rerun, uncertainty/systematic evaluation, and independent closure.
