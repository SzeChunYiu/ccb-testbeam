# MV4 timing study — corrected contract

`scripts/mv4_timing_study.py`

## Status: `TOY_DIAGNOSTIC` (was `MV4` / PRODUCTION)

This script is a **toy-digitizer diagnostic**, not a production measurement. It
stays `TOY_DIAGNOSTIC` until it is re-run **on LUNARC** against:

1. the **current v2 data-driven calibration** (`mv0 calibration.json`), loaded
   with `--calibration`, and
2. the **real measured data anchors** (result files + CIs), loaded with
   `--data-anchors`,

both under `--strict`. Until then every reported number is a placeholder driven
by hard-coded fallbacks and must not be quoted as a result.

## What MUST be loaded vs what is a labelled fallback

| Quantity | Production source | Labelled fallback (diagnostic only) |
|---|---|---|
| Digitizer **gain** (ADC/MeV) | `--calibration <mv0 calibration.json>` → `calibration.gain_adc_per_mev` (+ `gain_adc_per_mev_unc`, else derived from the gain scan) | `246.0` — prints a WARNING to stderr; `--strict` → **exit 3** |
| Data **anchors** (S02 raw, S03 corrected sigma68) + their uncertainty/CIs | `--data-anchors <json>` | `1.85` / `1.50` ns, `±0.10` ns — prints a WARNING; `--strict` → **exit 4** |

- **Non-strict + no file** → the run proceeds using the fallback, prints a
  stderr WARNING, and `result.json` records `calibration_source: "fallback"` /
  `data_anchors_source: "fallback"`.
- **`--strict` + missing/absent required file** → hard error, **nonzero exit**;
  the fallback is never silently used.
- Calibration is loaded **before** any compute so `--strict` fails fast.
- Gain uncertainty is propagated: when the calibration carries an uncertainty,
  `result.json.gain_propagation` re-digitizes at `gain·(1±rel_unc)` and reports
  the resulting raw-sigma68 band. `calibration.gain_rel_unc` is always recorded.

### `--data-anchors` JSON format

```json
{
  "S02_raw":       {"sigma68_ns": 1.85, "unc_ns": 0.08, "ci68": [1.77, 1.93]},
  "S03_corrected": {"sigma68_ns": 1.50, "unc_ns": 0.07, "ci68": [1.43, 1.57]}
}
```

Flat keys (`raw` / `corrected`, `sigma68`, `unc`, `value`) are also accepted.

## Metrics reported (pure functions, per residual array)

Global (raw and timewalk-corrected) and per-slice:

- **`sigma68`** — robust 68% half-width `(p84−p16)/2`.
- **`rms`** — full RMS spread (standard deviation about the mean, non-robust).
- **`gaussian_core_sigma`** — sigma of a Gaussian fit to the sigma-clipped core.
- **`tail_fraction`** — fraction beyond `--tail-nsigma` robust widths of the median.
- **`chi2_ndf`** — `(chi2, ndf, chi2/ndf)` of a Poisson Gaussian core fit.

Bootstrap standard error of sigma68 is i.i.d. by default, or **run/block-level**
(`--bootstrap-blocks`) so within-run correlation is respected.

## Slicing

`--slice-by` accepts any comma list of
`species, stave, sample, run, amplitude, topology` (or `all`).

- `species` — proton / deuteron / other (from PDG)
- `stave` — B2/B4/B6/B8 (LayerID→stave for ROOT; synthetic assigns staves)
- `sample` — Sample I / II (synthetic; `all` for ROOT unless a branch provides it)
- `run` — per-run label (synthetic runs; ROOT uses the file name)
- `amplitude` — quantile amplitude bins `amp_q1..q4`
- `topology` — `single` vs `multi` hit track

Per-slice metrics go to `mv4_slice_metrics.csv` and `result.json.slices`.
Groups below `MIN_SLICE_N` (20) are skipped.

## LORO / run-spread

`result.json.loro_raw` / `loro_corrected` give leave-one-run-out sigma68
(mean/std/min/max) and the per-run sigma68 spread, when ≥2 runs are present.

## Running

Offline (no ROOT / uproot; built-in toy truth generator):

```
python scripts/mv4_timing_study.py --synthetic 4000 --out /tmp/mv4 \
    --slice-by all --tail-nsigma 3.0 --seed 20260720
```

Production-grade (LUNARC, real inputs, fail-closed):

```
python scripts/mv4_timing_study.py --mc <root> --out <dir> \
    --calibration <mv0 calibration.json> --data-anchors <anchors.json> \
    --strict --slice-by species,stave,sample,run,amplitude,topology
```

Deterministic: a fixed `--seed` reproduces the synthetic truth and all
bootstraps, so the same seed yields the same key metrics. Matplotlib uses the
Agg backend; there are no hard-coded analyst absolute paths.

## Outputs

`result.json` (primary), `mv4_summary.json` (legacy alias),
`mv4_slice_metrics.csv`, `REPORT.md`, and the PNG figures
(`mv4_waveform_examples`, `mv4_residuals`, `mv4_sigma_vs_amp`,
`mv4_data_vs_mc`, `mv4_pull`).
