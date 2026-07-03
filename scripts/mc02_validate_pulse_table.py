#!/usr/bin/env python3
"""
mc02_validate_pulse_table.py
============================
Physical validation of the mc02 truth-labelled MC pulse table.

Checks (against the digitizer card and known data behaviour):
  1. occupancy ordering — B2 >> B4 > B6 > B8 rows (range-telescope geometry);
  2. per-stave amplitude spectra — medians/percentiles per stave (shape only;
     the absolute scale is NOT calibrated — gain is a placeholder);
  3. pulse tail decay — exponential fit to the per-stave MEAN baseline-
     subtracted waveform tail (10%-of-peak convention, matching the data
     template fit), compared with the card tau_decay values;
  4. MV7 pedestal MAE results (if mv7_pedestal_validation.json is present).

Writes REPORT.md into the report directory with tables and an honest caveat
list.

Usage:
  mc02_validate_pulse_table.py --report-dir <reports/mc02_pulse_table_STAMP>
      [--card configs/mc_validation/digitizer_card.yaml]
"""
from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR / "src"))

from ccb_mc_validation.digitizer.pipeline import DEFAULT_CARD_PATH, load_digitizer_card

STAVES = ("B2", "B4", "B6", "B8")

# Data reference values for side-by-side context (NOT a quantitative gate):
# net-amplitude medians from the MV0 v2 calibration.json data stats (C2:
# amplitude_adc is net/baseline-subtracted) and occupancy from the s00
# selected table (A>1000).
DATA_NET_MEDIAN = {"B2": 5752.0, "B4": 4132.0, "B6": 4178.0, "B8": 3851.0}
DATA_SELECTED_ROWS = {"B2": 579424, "B4": 36116, "B6": 17945, "B8": 7252}
DATA_TAU_DECAY = {"B2": 56.7, "B4": 51.7, "B6": 49.4, "B8": 50.1}


def load_amplitudes(table_path: Path) -> dict[str, np.ndarray]:
    amps: dict[str, list[float]] = {s: [] for s in STAVES}
    with gzip.open(table_path, "rt", encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        i_stave = header.index("stave")
        i_amp = header.index("amplitude_adc")
        for line in handle:
            parts = line.rstrip("\n").split(",")
            amps[parts[i_stave]].append(float(parts[i_amp]))
    return {s: np.asarray(v) for s, v in amps.items()}


def fit_tail_tau(mean_wave: np.ndarray, spacing_ns: float) -> tuple[float, int, int]:
    """Log-linear exponential fit to the tail of the mean waveform.

    Tail window: from the first sample after the peak whose value has fallen
    below 90% of peak, down to 10% of peak (mirroring the data template-fit
    10% convention). Returns (tau_ns, i_start, i_stop).
    """
    peak = int(np.argmax(mean_wave))
    peak_val = float(mean_wave[peak])
    if peak_val <= 0:
        return float("nan"), -1, -1
    i_start = peak + 1
    while i_start < len(mean_wave) and mean_wave[i_start] > 0.9 * peak_val:
        i_start += 1
    i_stop = i_start
    while i_stop < len(mean_wave) and mean_wave[i_stop] > 0.10 * peak_val:
        i_stop += 1
    if i_stop - i_start < 3:
        i_stop = min(len(mean_wave), i_start + 3)
    seg = mean_wave[i_start:i_stop]
    if len(seg) < 2 or np.any(seg <= 0):
        return float("nan"), i_start, i_stop
    t = np.arange(i_start, i_stop, dtype=np.float64) * spacing_ns
    slope, _ = np.polyfit(t, np.log(seg), 1)
    if slope >= 0:
        return float("nan"), i_start, i_stop
    return float(-1.0 / slope), i_start, i_stop


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--report-dir", required=True)
    ap.add_argument("--card", default=str(DEFAULT_CARD_PATH))
    args = ap.parse_args()

    report_dir = Path(args.report_dir)
    manifest = json.loads((report_dir / "manifest.json").read_text(encoding="utf-8"))
    card = load_digitizer_card(args.card)
    tau_card = {s: float(card["digitizer"]["staves"][s]["tau_decay_ns"]) for s in STAVES}

    amps = load_amplitudes(report_dir / "mc02_pulse_table.csv.gz")
    rows_by_stave = {s: int(len(amps[s])) for s in STAVES}
    occupancy_ok = (
        rows_by_stave["B2"] > 2 * rows_by_stave["B4"]  # B2 >> B4
        and rows_by_stave["B4"] > rows_by_stave["B6"] > rows_by_stave["B8"]
    )

    wf = np.load(report_dir / "mc02_waveform_means.npz")
    spacing = float(wf["sample_spacing_ns"])
    tau_fit = {}
    for s in STAVES:
        n = int(wf[f"{s}_n"])
        mean_wave = wf[f"{s}_sum"] / max(n, 1)
        tau, i0, i1 = fit_tail_tau(mean_wave, spacing)
        tau_fit[s] = {"tau_ns": tau, "fit_samples": [i0, i1], "n_waveforms": n}

    mv7_path = report_dir / "mv7_pedestal_validation.json"
    mv7 = json.loads(mv7_path.read_text(encoding="utf-8")) if mv7_path.exists() else None

    # ---------- assemble REPORT.md ----------
    q = lambda a, p: float(np.percentile(a, p)) if len(a) else float("nan")
    lines = []
    lines.append(f"# mc02 MC pulse table — physical validation\n")
    lines.append(f"Generated {time.strftime('%Y-%m-%dT%H:%M:%S+00:00', time.gmtime())} from `{report_dir.name}`.")
    lines.append(f"Card: `{manifest['card']['path']}` (sha256 `{manifest['card']['sha256'][:12]}…`, "
                 f"gain status **{manifest['card']['gain_status']}**). Mapping: `{manifest['mapping']}`.\n")
    lines.append(f"- events scanned: **{manifest['n_events_scanned']:,}** "
                 f"(tree entries {manifest['n_entries_in_tree']:,})")
    lines.append(f"- table rows (no selection): **{manifest['n_rows']:,}**; "
                 f"A>1000 companion: **{manifest.get('n_rows_a1000') or 0:,}**")
    lines.append(f"- Sample I events: {manifest['events_sample_I']:,}; "
                 f"Sample II events: {manifest['events_sample_II']:,}\n")

    lines.append("## 1. Occupancy ordering (expect B2 >> B4 > B6 > B8)\n")
    lines.append("| stave | MC rows (all deposits) | MC fraction | data selected rows (A>1000) | data fraction |")
    lines.append("|---|---|---|---|---|")
    tot_mc = sum(rows_by_stave.values())
    tot_da = sum(DATA_SELECTED_ROWS.values())
    for s in STAVES:
        lines.append(f"| {s} | {rows_by_stave[s]:,} | {rows_by_stave[s]/max(tot_mc,1):.3f} "
                     f"| {DATA_SELECTED_ROWS[s]:,} | {DATA_SELECTED_ROWS[s]/tot_da:.3f} |")
    lines.append(f"\nOrdering check (B2>2×B4 and B4>B6>B8): **{'PASS' if occupancy_ok else 'FAIL'}**.")
    lines.append("MC rows here are *unselected* (any deposit) while the data column is the A>1000 "
                 "selected table — fractions are context, not a quantitative comparison. The MC "
                 "occupancy weights are known to be geometry-poisoned (review P1/MV3: MC stopping "
                 "fractions B2 47% vs data 90%+).\n")

    lines.append("## 2. Per-stave amplitude spectra (shape only — gain is a placeholder)\n")
    lines.append("| stave | n | median [ADC] | p10 | p90 | data net median [ADC] |")
    lines.append("|---|---|---|---|---|---|")
    for s in STAVES:
        a = amps[s]
        lines.append(f"| {s} | {len(a):,} | {q(a,50):.0f} | {q(a,10):.0f} | {q(a,90):.0f} "
                     f"| {DATA_NET_MEDIAN[s]:.0f} |")
    lines.append("\nAbsolute-scale agreement is NOT claimed: gain 297 ADC/MeV is the C2-resolution "
                 "placeholder on a geometry-poisoned MC anchor. Only the ordering/shape is "
                 "informative at Phase 1.\n")

    lines.append("## 3. Pulse tail decay vs card (data-tuned tau_decay)\n")
    lines.append("| stave | fitted tau [ns] (mean-waveform tail) | card tau [ns] (data) | ratio | n waveforms |")
    lines.append("|---|---|---|---|---|")
    for s in STAVES:
        tf = tau_fit[s]["tau_ns"]
        ratio = tf / tau_card[s] if np.isfinite(tf) else float("nan")
        lines.append(f"| {s} | {tf:.1f} | {tau_card[s]:.1f} | {ratio:.3f} | {tau_fit[s]['n_waveforms']:,} |")
    lines.append("\nFit: log-linear on the mean baseline-subtracted waveform tail between 90% and 10% "
                 "of peak (10 ns sampling). Multi-hit pile-in within an event and the 2.5 ns rise "
                 "bias the fitted tau slightly high relative to the pure kernel.\n")

    if mv7:
        lines.append("## 4. MV7 pedestal validation (zero-signal sample)\n")
        lines.append(f"- records: {mv7['n_records']:,} (train {mv7['n_train']:,} / test {mv7['n_test']:,})")
        lines.append(f"- adaptive estimator (median samples 0-3): "
                     f"**MAE {mv7['adaptive_estimator']['mae_adc']:.3f} ADC** "
                     f"(rmse {mv7['adaptive_estimator']['rmse_adc']:.3f}, bias {mv7['adaptive_estimator']['bias_adc']:+.3f})")
        lines.append(f"- learned estimator (ridge on 18 samples): "
                     f"**MAE {mv7['learned_estimator']['mae_adc']:.3f} ADC** "
                     f"(rmse {mv7['learned_estimator']['rmse_adc']:.3f}, bias {mv7['learned_estimator']['bias_adc']:+.3f})")
        lines.append(f"- limitation: {mv7['limitation']}\n")
    else:
        lines.append("## 4. MV7 pedestal validation\n\nNOT RUN (no mv7_pedestal_validation.json).\n")

    lines.append("## Caveats (honest list)\n")
    lines.append("1. **Gain placeholder**: gain 297 ADC/MeV = data B2 net median 5752 / "
                 "(MC B2 edep median 26.44 MeV × peak_frac 0.733). The MC-side anchor is "
                 "geometry-poisoned and peak_frac is phase-locked (review P1/P2). No ADC/MeV "
                 "claim is made; re-anchor in Phase 2.")
    lines.append("2. **Geometry-poisoned spectrum weights**: missing upstream material dilutes "
                 "B2 with through-goers (MV3 chi2/ndf=68,269); per-stave occupancies and "
                 "amplitude spectra inherit this defect. Shape ordering only.")
    lines.append("3. **Mapping under review**: the paired {0,1}->B2 … {6,7}->B8 LayerID mapping "
                 "is an unvalidated guess; the odd-layer alternative (odd bars unread) is a live "
                 "hypothesis (review P4). Rebuild with `--mapping odd` to test.")
    lines.append("4. **MV7 is MC-level only**: white-Gaussian noise + uniform pedestal jitter; "
                 "no correlated noise/drift/signal contamination. Real data still has no true "
                 "pedestal sample.")
    lines.append("5. **No Birks quenching** (card `apply_birks: false`): heavy-ion light yield "
                 "is overstated; species composition of the high-amplitude tail is unreliable.")

    report_path = report_dir / "REPORT.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    summary = {
        "rows_by_stave": rows_by_stave,
        "occupancy_ordering_pass": bool(occupancy_ok),
        "amplitude_median_adc": {s: q(amps[s], 50) for s in STAVES},
        "tail_tau_fit_ns": {s: tau_fit[s]["tau_ns"] for s in STAVES},
        "tail_tau_card_ns": tau_card,
        "mv7": {
            "adaptive_mae_adc": mv7["adaptive_estimator"]["mae_adc"] if mv7 else None,
            "learned_mae_adc": mv7["learned_estimator"]["mae_adc"] if mv7 else None,
        },
    }
    (report_dir / "validation_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"[mc02-validate] wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
