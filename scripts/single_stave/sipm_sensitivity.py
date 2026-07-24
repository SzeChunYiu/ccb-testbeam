#!/usr/bin/env python3
"""SiPM sensitivity campaign analyzer (SIPM-P2-001).

For each knob swept by the campaign, reads every per-point .root under
<OUTDIR>/<knob>/, computes the mean (+ standard error) of the ADC and PE
channels, and emits:
  * <OUTDIR>/<knob>/<knob>_sensitivity.png   adc & PE vs knob
  * <OUTDIR>/<knob>/SUMMARY.md                per-knob table + findings
  * <OUTDIR>/SUMMARY.md                       global summary across all knobs

The knob value is recovered from the output filename (<knob>=<value>.root) so
no separate manifest join is required. Categorical knobs (e.g. far_end) are
plotted as a bar chart.

Channels (single-stave events ntuple):
  adc_readout / adc_f1far / adc_f2near / adc_f2far  (peak ADC above baseline)
  pe_sat_readout / pe_sat_f2near / ...               (occupancy-saturated PE)
  detected_readout / detected_f2near / ...           (raw detected PE)
  edep_scint_MeV                                     (visible energy, control)

The ADC clips at (2^adc_bits - 1) - baseline = 3895 for the default 12-bit /
baseline-200 electronics; a clipped point is flagged so saturation is visible
rather than mistaken for a flat response.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

ADC_CLIP_DEFAULT = 3895.0  # 2**12 - 1 - baseline(200); points at this are saturated

# Channels we extract. "readout" is the primary near sensor.
ADC_CH = ["adc_readout", "adc_f2near", "adc_f2far"]
PE_CH = ["pe_sat_readout", "detected_readout"]
CTRL_CH = ["edep_scint_MeV"]


def _stderr(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 2:
        return float("nan")
    return float(np.std(x, ddof=1) / math.sqrt(n))


def _mean(x: np.ndarray) -> float:
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan")
    return float(np.mean(x))


def read_point(root_path: Path) -> Dict[str, float]:
    """Return per-point means for the channels of interest + n_events."""
    import uproot

    cols = ADC_CH + PE_CH + CTRL_CH + ["adc_f1far", "pe_sat_f2near", "detected_f2near"]
    df = uproot.open(str(root_path))["events"].arrays(cols, library="pd")
    out: Dict[str, float] = {}
    for c in cols:
        if c in df.columns:
            out[f"mean_{c}"] = _mean(df[c].to_numpy())
            out[f"sem_{c}"] = _stderr(df[c].to_numpy())
    out["n_events"] = int(len(df))
    # Fraction of events where the readout ADC is at the clip ceiling.
    if "adc_readout" in df.columns:
        out["frac_clipped_readout"] = float(
            np.mean(df["adc_readout"].to_numpy() >= ADC_CLIP_DEFAULT - 0.5)
        )
    else:
        out["frac_clipped_readout"] = float("nan")
    return out


def _parse_label(label: str) -> Tuple[str, str]:
    """'knob=value' -> (knob, value_str)."""
    if "=" not in label:
        return label, label
    knob, val = label.split("=", 1)
    return knob, val


def _is_numeric_column(vals: List[str]) -> bool:
    try:
        for v in vals:
            float(v)
        return True
    except ValueError:
        return False


def collect_knob(knob_dir: Path) -> Tuple[List[str], List[Dict[str, float]], List[str]]:
    """Return (values_in_order, per_point_stats, labels)."""
    files = sorted(knob_dir.glob("*.root"))
    if not files:
        return [], [], []
    values: List[str] = []
    stats: List[Dict[str, float]] = []
    labels: List[str] = []
    for fp in files:
        knob, val = _parse_label(fp.stem)
        try:
            st = read_point(fp)
        except Exception as e:  # pragma: no cover - corrupt run
            print(f"warn: failed to read {fp}: {e}", file=sys.stderr)
            continue
        values.append(val)
        stats.append(st)
        labels.append(fp.stem)
    return values, stats, labels


def _safe_float(v: str) -> float:
    try:
        return float(v)
    except ValueError:
        return float("nan")


def plot_knob(
    knob: str,
    unit: str,
    values: List[str],
    stats: List[Dict[str, float]],
    out_png: Path,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    numeric = _is_numeric_column(values)
    x = [_safe_float(v) for v in values] if numeric else range(len(values))
    xlabels = values if not numeric else None

    fig, (ax_adc, ax_pe) = plt.subplots(2, 1, figsize=(7, 7), sharex=numeric)
    # ADC panel.
    for ch, marker in zip(ADC_CH, ["o", "s", "^"]):
        ys = [s.get(f"mean_{ch}", float("nan")) for s in stats]
        es = [s.get(f"sem_{ch}", 0.0) for s in stats]
        ax_adc.errorbar(x, ys, yerr=es, marker=marker, capsize=3, label=ch)
    ax_adc.axhline(ADC_CLIP_DEFAULT, color="red", ls="--", lw=1,
                   label=f"ADC clip ({ADC_CLIP_DEFAULT:.0f})")
    ax_adc.set_ylabel("peak ADC above baseline")
    ax_adc.set_title(f"SiPM sensitivity: {knob}  [{unit}]")
    ax_adc.legend(fontsize=8)
    ax_adc.grid(alpha=0.3)
    # PE panel.
    for ch, marker in zip(PE_CH, ["o", "s"]):
        ys = [s.get(f"mean_{ch}", float("nan")) for s in stats]
        es = [s.get(f"sem_{ch}", 0.0) for s in stats]
        ax_pe.errorbar(x, ys, yerr=es, marker=marker, capsize=3, label=ch)
    ax_pe.set_ylabel("photo-electrons / event")
    if numeric:
        ax_pe.set_xlabel(f"{knob}  [{unit}]")
    else:
        ax_pe.set_xticks(list(range(len(values))))
        ax_pe.set_xticklabels(values, rotation=30, ha="right")
        ax_pe.set_xlabel(knob)
    ax_pe.legend(fontsize=8)
    ax_pe.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def summarize_knob(
    knob: str,
    unit: str,
    rationale: str,
    values: List[str],
    stats: List[Dict[str, float]],
) -> str:
    lines = [
        f"# {knob}",
        f"",
        f"- **unit**: {unit}",
        f"- **rationale**: {rationale}",
        f"- **points**: {len(values)}",
        "",
        "| value | n_events | adc_readout | pe_sat_readout | detected_readout | edep_scint_MeV | frac_clipped |",
        "|-------|----------|-------------|----------------|------------------|----------------|--------------|",
    ]
    for v, s in zip(values, stats):
        lines.append(
            f"| {v} | {int(s.get('n_events', 0))} | "
            f"{s.get('mean_adc_readout', float('nan')):.1f} | "
            f"{s.get('mean_pe_sat_readout', float('nan')):.2f} | "
            f"{s.get('mean_detected_readout', float('nan')):.2f} | "
            f"{s.get('mean_edep_scint_MeV', float('nan')):.3f} | "
            f"{s.get('frac_clipped_readout', float('nan')):.2f} |"
        )
    # Sensitivity slope (ADC and PE vs knob) for numeric knobs.
    if _is_numeric_column(values) and len(values) >= 2:
        xs = np.array([_safe_float(v) for v in values], dtype=float)
        for obs, label in [("mean_adc_readout", "adc_readout"),
                           ("mean_pe_sat_readout", "pe_sat_readout"),
                           ("mean_detected_readout", "detected_readout")]:
            ys = np.array([s.get(obs, float("nan")) for s in stats], dtype=float)
            m = np.isfinite(xs) & np.isfinite(ys)
            if m.sum() >= 2 and np.ptp(xs[m]) > 0:
                slope, intercept = np.polyfit(xs[m], ys[m], 1)
                # Relative sensitivity: fractional change per fractional knob change
                # at the midpoint, i.e. d(ln y)/d(ln x) (elasticity).
                x0, y0 = float(np.median(xs[m])), float(np.median(ys[m]))
                elast = (slope * x0 / y0) if abs(y0) > 1e-9 else float("nan")
                lines.append(
                    f"  - `{label}` d(obs)/d({knob}) = {slope:.4g} per {unit}; "
                    f"elasticity d(ln y)/d(ln x) at midpoint = {elast:.3f}"
                )
    # Saturation flag.
    frac_clip = [s.get("frac_clipped_readout", 0.0) for s in stats]
    if any(f > 0.5 for f in frac_clip):
        lines.append("")
        lines.append(
            f"> **ADC saturation**: >=1 point has >50% of events at the clip "
            f"ceiling; the ADC response is uninformative there. See the PE "
            f"panel for the underlying optical sensitivity."
        )
    lines.append("")
    return "\n".join(lines)


def load_grid_meta(grids_dir: Path, knob: str) -> Tuple[str, str]:
    """Read unit + rationale from the points_<knob>.csv header comments."""
    csv = grids_dir / f"points_{knob}.csv"
    unit, rationale = "?", ""
    if csv.exists():
        for ln in csv.read_text().splitlines():
            if ln.startswith("# channel"):
                m = re.search(r"unit:\s*(.+)$", ln)
                if m:
                    unit = m.group(1).strip()
            elif ln.startswith("# rationale:"):
                rationale = ln.split("rationale:", 1)[1].strip()
    return unit, rationale


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("outdir", help="campaign output root (contains <knob>/ dirs)")
    ap.add_argument(
        "--grids-dir",
        default=None,
        help="points_<knob>.csv dir for unit/rationale (default: infer from repo)",
    )
    ap.add_argument(
        "--knob", action="append", default=None,
        help="specific knob(s) to analyze (default: every <knob>/ subdir)",
    )
    args = ap.parse_args()

    outdir = Path(args.outdir)
    if not outdir.is_dir():
        print(f"error: {outdir} is not a directory", file=sys.stderr)
        return 2

    # Locate grids dir for metadata (unit/rationale).
    grids_dir = Path(args.grids_dir) if args.grids_dir else None
    if grids_dir is None:
        here = Path(__file__).resolve()
        # scripts/single_stave/ -> ../../geant4/single_stave/slurm/grids
        cand = here.parents[2] / "geant4" / "single_stave" / "slurm" / "grids"
        if cand.is_dir():
            grids_dir = cand

    knobs = args.knob if args.knob else sorted(
        d.name for d in outdir.iterdir() if d.is_dir()
    )
    if not knobs:
        print(f"no knob sweep dirs found under {outdir}", file=sys.stderr)
        return 1

    global_sections: List[str] = [
        "# SiPM Sensitivity Campaign — SUMMARY",
        "",
        f"Output root: `{outdir}`",
        "",
        "One-knob-at-a-time sweeps. ADC = peak above baseline (12-bit electronics, "
        f"clip ceiling = {ADC_CLIP_DEFAULT:.0f}). PE = occupancy-saturated / raw detected "
        "photo-electrons. Elasticity = d(ln obs)/d(ln knob) at the midpoint.",
        "",
    ]
    n_total_points = 0
    n_clipped_points = 0
    per_knob_rows = ["| knob | unit | npoints | adc_readout range | clipped pts | elasticity(adc) |",
                     "|------|------|---------|--------------------|-------------|------------------|"]

    for knob in knobs:
        kdir = outdir / knob
        if not kdir.is_dir():
            print(f"warn: no dir for knob {knob}", file=sys.stderr)
            continue
        unit, rationale = ("?", "")
        if grids_dir:
            unit, rationale = load_grid_meta(grids_dir, knob)
        values, stats, labels = collect_knob(kdir)
        if not stats:
            print(f"warn: no readable .root for knob {knob}", file=sys.stderr)
            continue
        n_total_points += len(stats)
        n_clipped_points += sum(
            1 for s in stats if s.get("frac_clipped_readout", 0.0) > 0.5
        )
        # Per-knob plot + summary.
        out_png = kdir / f"{knob}_sensitivity.png"
        try:
            plot_knob(knob, unit, values, stats, out_png)
            print(f"  wrote {out_png}")
        except Exception as e:  # pragma: no cover
            print(f"warn: plot failed for {knob}: {e}", file=sys.stderr)
        per_knob_md = kdir / "SUMMARY.md"
        per_knob_md.write_text(summarize_knob(knob, unit, rationale, values, stats))
        # Global table row.
        adcs = [s.get("mean_adc_readout", float("nan")) for s in stats]
        clipped = sum(1 for s in stats if s.get("frac_clipped_readout", 0.0) > 0.5)
        elast_str = "n/a"
        if _is_numeric_column(values) and len(values) >= 2:
            xs = np.array([_safe_float(v) for v in values], dtype=float)
            ys = np.array(adcs, dtype=float)
            m = np.isfinite(xs) & np.isfinite(ys)
            if m.sum() >= 2 and np.ptp(xs[m]) > 0:
                slope, _ = np.polyfit(xs[m], ys[m], 1)
                x0 = float(np.median(xs[m]))
                y0 = float(np.median(ys[m]))
                if abs(y0) > 1e-9:
                    elast_str = f"{slope * x0 / y0:.3f}"
        per_knob_rows.append(
            f"| {knob} | {unit} | {len(stats)} | "
            f"{min(v for v in adcs if math.isfinite(v)):.0f}..{max(v for v in adcs if math.isfinite(v)):.0f} | "
            f"{clipped} | {elast_str} |"
        )
        global_sections.append(f"## {knob}")
        global_sections.append(f"![{knob}]({knob}/{knob}_sensitivity.png)")
        global_sections.append("")
        global_sections.append(f"see `{knob}/SUMMARY.md` for the table.")

    global_sections += ["", "## Cross-knob sensitivity", ""]
    global_sections += per_knob_rows
    global_sections += [
        "",
        f"**Totals**: {n_total_points} points across {len(knobs)} knobs; "
        f"{n_clipped_points} point(s) ADC-clipped.",
        "",
    ]
    (outdir / "SUMMARY.md").write_text("\n".join(global_sections) + "\n")
    print(f"\nwrote {outdir / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
